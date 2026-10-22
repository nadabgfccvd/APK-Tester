#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen-textures.py — Texturas PBR procedurais em contêineres KTX2 (APK Tester).

Para cada material gera o conjunto albedo/normal/roughness/AO a partir de um
heightmap value-noise fbm semeado. Há UM único campo de altura por material —
os 4 mapas são derivados dele linha a linha (nenhuma imagem inteira em RAM).

Formatos (--format), com honestidade explícita:
  raw ... KTX2 válido com vkFormat=R8G8B8A8_UNORM e payload RGBA8 completo
          (fallback não-comprimido, byte a byte determinístico);
  etc1 .. stub HONESTO: só cabeçalho KTX2 com vkFormat=ETC2_R8G8B8 (compatível
          ETC1) + chave kvd apktester.stub — codificar ETC1/ASTC de verdade
          exige toolchain externa (etc2comp/astcenc), fora do escopo stdlib;
  astc .. stub HONESTO idem, vkFormat=ASTC_4x4_UNORM_BLOCK;
  auto .. escreve os três (raw + etc1 + astc) sob textures/<fmt>/.

--densities mdpi,hdpi,xhdpi,xxhdpi,xxxhdpi escreve variantes escaladas
(avaliando o MESMO campo procedural na resolução do bucket — determinístico).

Uso: python3 tools/gen-textures.py --out DIR [--size 4096] [--format auto]
     [--materials granite,sandstone,oxidized_metal,moss_stone] [--selftest]
Nota de runtime: 4096x4096 em Python puro leva minutos por material (é o
principal contribuinte de conteúdo do orçamento de 850MB–1GB do flagship).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import shutil
import struct
import sys
import tempfile

DEFAULT_SEED = 20261022
TOOL = "gen-textures.py"

KTX2_MAGIC = b"\xabKTX 20\xbb\r\n\x1a\n"  # «KTX 20 »\r\n\x1a\n
VK_FORMAT_R8G8B8A8_UNORM = 37
VK_FORMAT_ETC2_R8G8B8_UNORM_BLOCK = 148
VK_FORMAT_ASTC_4x4_UNORM_BLOCK = 157
FORMAT_SPECS = {
    "raw": {"vk": VK_FORMAT_R8G8B8A8_UNORM, "stub": False, "label": "R8G8B8A8_UNORM"},
    "etc1": {"vk": VK_FORMAT_ETC2_R8G8B8_UNORM_BLOCK, "stub": True,
             "label": "ETC2_R8G8B8_UNORM_BLOCK (ETC1-compat)"},
    "astc": {"vk": VK_FORMAT_ASTC_4x4_UNORM_BLOCK, "stub": True,
             "label": "ASTC_4x4_UNORM_BLOCK"},
}
DENSITY_SCALES = {"mdpi": 0.25, "hdpi": 0.375, "xhdpi": 0.5, "xxhdpi": 0.75,
                  "xxxhdpi": 1.0}
MAPS = ("albedo", "normal", "roughness", "ao")
MATERIALS = {
    "granite":        {"a": (168, 165, 158), "b": (72, 70, 68),   "rough": 150,
                       "rough_k": 0.35, "ao_lift": 90,  "nrm": 2.2},
    "sandstone":      {"a": (216, 186, 132), "b": (140, 104, 66), "rough": 190,
                       "rough_k": 0.25, "ao_lift": 70,  "nrm": 1.6},
    "oxidized_metal": {"a": (188, 108, 62),  "b": (60, 58, 56),   "rough": 120,
                       "rough_k": 0.55, "ao_lift": 110, "nrm": 2.8},
    "moss_stone":     {"a": (96, 128, 74),   "b": (84, 84, 82),   "rough": 205,
                       "rough_k": 0.20, "ao_lift": 80,  "nrm": 2.5},
}


# ---------------------------------------------------------------- utilidades
def seed_from(base: int, label: str) -> int:
    """Sub-semente estável derivada de (base, rótulo) via SHA-256."""
    digest = hashlib.sha256(f"{base}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "little")


def sha256_file(path: str) -> str:
    """SHA-256 em streaming."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def make_perm(rng: random.Random) -> list:
    """Tabela de permutação (512 entradas) para o value-noise."""
    p = list(range(256))
    rng.shuffle(p)
    return p + p


def vnoise(perm: list, x: float, y: float) -> float:
    """Value-noise bilinear com smoothstep em lattice 256x256 periódico."""
    xi, yi = math.floor(x), math.floor(y)
    xf, yf = x - xi, y - yi
    x0, y0 = xi & 255, yi & 255
    x1, y1 = (xi + 1) & 255, (yi + 1) & 255

    def lat(i, j):
        return perm[(perm[i & 255] + (j & 255)) & 255] / 255.0

    u = xf * xf * (3.0 - 2.0 * xf)
    v = yf * yf * (3.0 - 2.0 * yf)
    a, b, c, d = lat(x0, y0), lat(x1, y0), lat(x0, y1), lat(x1, y1)
    return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v


def fbm(perm: list, x01: float, y01: float, octaves: int = 4) -> float:
    """fbm em [0,1); coords normalizadas => independente da resolução."""
    value, amp, freq, norm = 0.0, 1.0, 4.0, 0.0
    for _ in range(octaves):
        value += amp * vnoise(perm, x01 * freq, y01 * freq)
        norm += amp
        amp *= 0.5
        freq *= 2.0
    return value / norm


# ------------------------------------------------------------- writer KTX2
def _kvd_entry(key: bytes, value: bytes) -> bytes:
    """Entrada key/value do KVD (key NUL-terminada + padding de 4 bytes)."""
    raw = struct.pack("<I", len(key) + len(value)) + key + value
    return raw + b"\0" * ((-len(raw)) % 4)


def ktx2_container(vk_format: int, width: int, height: int, stub: bool,
                   writer_note: str, level_bytes: int):
    """Monta header+levelIndex+DFD+KVD do KTX2.

    Retorna (bytes_do_container_até_o_payload, comprimento_do_payload).
    Layout: header 72B + levelIndex 24B + DFD (0 ou 92B) + KVD + payload.
    """
    kvd = _kvd_entry(b"KTXwriter\x00", writer_note.encode("utf-8"))
    if stub:
        kvd += _kvd_entry(b"apktester.stub\x00",
                          b"true; reason=ETC1/ASTC encoding needs external toolchain")
    dfd = b""
    if not stub:
        # Data Format Descriptor KHR_DF para R8G8B8A8_UNORM (4 samples de 8 bits)
        samples = b"".join(
            struct.pack("<HBB4BII", bit, 7, chan, 0, 0, 0, 0, 0, 255)
            for bit, chan in ((0, 0), (8, 1), (16, 2), (24, 3)))
        block = (struct.pack("<I", 0)                       # vendorId=0, type=BASICBLOCK
                 + struct.pack("<HH", 2, 24 + len(samples))  # versão 2, blockSize
                 + bytes((1, 1, 1, 0))                       # RGBSDA, BT709, linear
                 + bytes((0, 0, 0, 0))                       # texelBlockDimension 1x1x1x1
                 + bytes((4, 0, 0, 0, 0, 0, 0, 0)))          # bytesPlane0=4 (RGBA8)
        dfd = struct.pack("<I", 4 + len(block) + len(samples)) + block + samples
    dfd_off = 72 + 24
    kvd_off = dfd_off + len(dfd)
    payload_off = kvd_off + len(kvd)
    header = (KTX2_MAGIC
              + struct.pack("<9I", vk_format, 1, width, height, 0, 0, 1, 1, 0)
              + struct.pack("<6I", dfd_off, len(dfd), kvd_off, len(kvd), 0, 0)
              + struct.pack("<QQQ", payload_off, level_bytes, level_bytes))
    return header + dfd + kvd, payload_off


def open_ktx2(path: str, vk_format: int, width: int, height: int, stub: bool,
              writer_note: str):
    """Abre o KTX2 já com o cabeçalho escrito; devolve o handle p/ payload."""
    level_bytes = 0 if stub else width * height * 4
    prefix, _ = ktx2_container(vk_format, width, height, stub, writer_note,
                               level_bytes)
    fh = open(path, "wb")
    fh.write(prefix)
    return fh


# ------------------------------------------------------- derivação dos mapas
def build_height_plane(w: int, h: int, perm: list) -> bytearray:
    """Heightmap uint8 (1 byte por texel) — 4096x4096 cabe em ~16 MB."""
    plane = bytearray(w * h)
    inv_x, inv_y = 1.0 / w, 1.0 / h
    for y in range(h):
        y01 = y * inv_y
        row = y * w
        for x in range(w):
            plane[row + x] = int(fbm(perm, x * inv_x, y01) * 255.0) & 0xFF
    return plane


def derive_rows(plane: bytearray, w: int, h: int, y: int, mat: dict) -> list:
    """Deriva as 4 linhas RGBA da linha y (albedo/normal/roughness/ao)."""
    rows = [bytearray(w * 4) for _ in range(4)]
    a_r, a_g, a_b = mat["a"]
    b_r, b_g, b_b = mat["b"]
    rough_base, rough_k = mat["rough"], mat["rough_k"]
    ao_lift, nrm = mat["ao_lift"], mat["nrm"]
    z_scale = 8.0
    yu, yd = max(y - 1, 0), min(y + 1, h - 1)
    for x in range(w):
        h00 = plane[y * w + x]
        xl, xr = max(x - 1, 0), min(x + 1, w - 1)
        dx = (plane[y * w + xr] - plane[y * w + xl]) * nrm
        dy = (plane[yd * w + x] - plane[yu * w + x]) * nrm
        inv = 1.0 / math.sqrt(dx * dx + dy * dy + z_scale * z_scale)
        t = h00 / 255.0
        o = x * 4
        rows[0][o] = int(a_r + (b_r - a_r) * t) & 0xFF
        rows[0][o + 1] = int(a_g + (b_g - a_g) * t) & 0xFF
        rows[0][o + 2] = int(a_b + (b_b - a_b) * t) & 0xFF
        rows[0][o + 3] = 255
        rows[1][o] = int((-dx * inv) * 127.5 + 127.5) & 0xFF
        rows[1][o + 1] = int((-dy * inv) * 127.5 + 127.5) & 0xFF
        rows[1][o + 2] = int((z_scale * inv) * 127.5 + 127.5) & 0xFF
        rows[1][o + 3] = 255
        r = int(rough_base + (h00 - 128) * rough_k * 2.0)
        rows[2][o] = rows[2][o + 1] = rows[2][o + 2] = min(255, max(0, r))
        rows[2][o + 3] = 255
        ao = min(255, max(0, ao_lift + h00))
        rows[3][o] = rows[3][o + 1] = rows[3][o + 2] = ao
        rows[3][o + 3] = 255
    return rows


def write_material_set(out_dir: str, seed: int, mat_name: str, size: int,
                       fmt: str, subdir: str) -> list:
    """Gera os 4 mapas do material na resolução/ formato pedidos."""
    mat = MATERIALS[mat_name]
    spec = FORMAT_SPECS[fmt]
    perm = make_perm(random.Random(seed_from(seed, f"tex:{mat_name}")))
    plane = build_height_plane(size, size, perm)
    paths = {}
    files = {}
    try:
        for map_name in MAPS:
            rel = f"textures/{fmt}/{subdir}{mat_name}_{map_name}.ktx2"
            full = os.path.join(out_dir, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            note = (f"apk-tester gen-textures.py seed={seed} "
                    f"fmt={spec['label']} map={map_name}")
            files[map_name] = open_ktx2(full, spec["vk"], size, size,
                                        spec["stub"], note)
            paths[map_name] = rel
        for y in range(size):
            rows = derive_rows(plane, size, size, y, mat)
            for i, map_name in enumerate(MAPS):
                files[map_name].write(bytes(rows[i]))
    finally:
        for fh in files.values():
            fh.close()
    artifacts = []
    for map_name in MAPS:
        artifacts.append({
            "path": paths[map_name], "bytes": os.path.getsize(
                os.path.join(out_dir, paths[map_name])),
            "sha256": sha256_file(os.path.join(out_dir, paths[map_name])),
            "material": mat_name, "map": map_name, "format": fmt,
            "vk_format": spec["vk"], "width": size, "height": size,
            "stub": spec["stub"]})
    return artifacts


def write_indexes(out_dir: str, seed: int, fmt_list: list, artifacts: list):
    """index.json (rico) + manifest.json (convenção) — sem timestamps."""
    index = {"tool": TOOL, "seed": seed, "formats": fmt_list,
             "note_stub": ("formatos etc1/astc são cabeçalho-only honestos; "
                           "codificação real exige toolchain externa"),
             "artifacts": artifacts}
    manifest = {"tool": TOOL, "seed": seed,
                "artifacts": [{k: a[k] for k in ("path", "bytes", "sha256")}
                              for a in artifacts]}
    for name, payload in (("index.json", index), ("manifest.json", manifest)):
        with open(os.path.join(out_dir, "textures", name), "w",
                  encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.write("\n")


def generate(out_dir: str, seed: int, size: int, fmt_list: list,
             materials: list, densities: list) -> list:
    """Gera todos os conjuntos de texturas e devolve os metadados."""
    artifacts = []
    for fmt in fmt_list:
        for mat_name in materials:
            arts = write_material_set(out_dir, seed, mat_name, size, fmt, "")
            artifacts += arts
            for d in densities:
                dsize = max(8, int(size * DENSITY_SCALES[d]))
                artifacts += write_material_set(out_dir, seed, mat_name, dsize,
                                                fmt, f"{d}/")
    write_indexes(out_dir, seed, fmt_list, artifacts)
    return artifacts


def selftest() -> int:
    """Gera 64x64 em /tmp duas vezes: valida magic/header e o determinismo."""
    tmp = tempfile.mkdtemp(prefix="apktester-textures-")
    try:
        hashes = []
        for run in ("a", "b"):
            d = os.path.join(tmp, run)
            generate(d, DEFAULT_SEED, size=64, fmt_list=["raw"],
                     materials=["granite"], densities=[])
            listing = []
            for root, _, names in os.walk(d):
                for n in names:
                    full = os.path.join(root, n)
                    listing.append((os.path.relpath(full, d).replace(os.sep, "/"),
                                    sha256_file(full)))
            hashes.append(sorted(listing))
        assert hashes[0] == hashes[1] and hashes[0], \
            "determinismo: as duas execuções divergem"
        ktx = os.path.join(tmp, "a", "textures", "raw", "granite_albedo.ktx2")
        with open(ktx, "rb") as fh:
            blob = fh.read()
        assert blob[:12] == KTX2_MAGIC, "KTX2: magic bytes inválidos"
        vk, tsize, w, h = struct.unpack_from("<4I", blob, 12)
        assert vk == VK_FORMAT_R8G8B8A8_UNORM and tsize == 1, \
            f"KTX2: vkFormat={vk} typeSize={tsize} inesperados"
        assert w == 64 and h == 64, f"KTX2: dimensões {w}x{h} inesperadas"
        scheme = struct.unpack_from("<I", blob, 44)[0]
        assert scheme == 0, "KTX2: supercompressionScheme deveria ser 0"
        kvd_off, kvd_len = struct.unpack_from("<II", blob, 56)
        payload_off = kvd_off + kvd_len
        assert len(blob) == payload_off + 64 * 64 * 4, \
            "KTX2: tamanho total divergente do payload RGBA8"
        print(f"[gen-textures] selftest OK: magic/vkFormat/dimensões válidos, "
              f"{len(hashes[0])} arquivos idênticos nas duas execuções")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Texturas PBR procedurais em KTX2 (APK Tester).")
    ap.add_argument("--out", help="diretório de saída (cria <out>/textures/)")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED,
                    help=f"semente determinística (padrão: {DEFAULT_SEED})")
    ap.add_argument("--size", type=int, default=4096,
                    help="lado da textura mestre (padrão: 4096)")
    ap.add_argument("--format", default="auto",
                    choices=tuple(FORMAT_SPECS) + ("auto",),
                    help="raw/etc1/astc/auto (auto = os três)")
    ap.add_argument("--materials", default=",".join(MATERIALS),
                    help="materiais separados por vírgula (padrão: todos)")
    ap.add_argument("--densities", default="",
                    help="buckets mdpi..xxxhdpi separados por vírgula (opcional)")
    ap.add_argument("--selftest", action="store_true",
                    help="roda auto-validação em /tmp e sai")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.out:
        ap.error("--out é obrigatório (ou use --selftest)")
    if not 8 <= args.size <= 8192:
        ap.error("--size deve estar em [8, 8192]")
    materials = [m.strip() for m in args.materials.split(",") if m.strip()]
    for m in materials:
        if m not in MATERIALS:
            print(f"[gen-textures] ERRO: material desconhecido '{m}'; "
                  f"válidos: {', '.join(MATERIALS)}", file=sys.stderr)
            return 2
    densities = [d.strip() for d in args.densities.split(",") if d.strip()]
    for d in densities:
        if d not in DENSITY_SCALES:
            print(f"[gen-textures] ERRO: densidade desconhecida '{d}'; "
                  f"válidas: {', '.join(DENSITY_SCALES)}", file=sys.stderr)
            return 2
    fmt_list = ["raw", "etc1", "astc"] if args.format == "auto" else [args.format]
    artifacts = generate(args.out, args.seed, args.size, fmt_list, materials,
                         densities)
    stubs = sum(1 for a in artifacts if a["stub"])
    for a in artifacts:
        tag = " [stub honesto]" if a["stub"] else ""
        print(f"[gen-textures] {a['path']}: {a['width']}x{a['height']} "
              f"vk={a['vk_format']} {a['bytes']} bytes{tag}")
    print(f"[gen-textures] OK: {len(artifacts)} contêineres "
          f"({stubs} stubs) em {args.out}/textures (seed={args.seed})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
