#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen-textures.py — Texturas PBR procedurais em contêineres KTX2 (APK Tester).

Para cada material gera o conjunto albedo/normal/roughness/AO a partir de um
heightmap value-noise fbm semeado. Há UM único campo de altura por material —
os 4 mapas são derivados dele linha a linha (nenhuma imagem inteira em RAM).

Formatos (--format), com honestidade explícita:
  raw ... KTX2 válido com vkFormat=R8G8B8A8_UNORM e payload RGBA8 completo
          (fallback não-comprimido, byte a byte determinístico);
  etc1 .. stub HONESTO: container KTX2 spec-completo com vkFormat=ETC2_R8G8B8
          (compatível ETC1), DFD de formato comprimido (modelo ETC2, bloco
          4x4/8B) e payload de blocos de RUÍDO com o byte-count exato do
          formato — NÃO é imagem codificada (codificar ETC1/ASTC de verdade
          exige toolchain externa etc2comp/astcenc, fora do escopo stdlib);
          a chave kvd apktester.stub declara isso no próprio arquivo;
  astc .. stub HONESTO idem, vkFormat=ASTC_4x4_UNORM_BLOCK (DFD modelo ASTC,
          bloco 4x4/16B, payload de ruído do tamanho exato);
  auto .. escreve os três (raw + etc1 + astc) sob textures/<fmt>/.

Container (KTX 2.0 spec, ktxspec.adoc): identificador 12 B + 9 u32 + 4 u32
+ 2 u64 (sgdByteOffset/sgdByteLength) = header de 80 B (NÃO 72 — os campos
sgd são u64); level index logo após (1 entrada x 3 u64); DFD obrigatório em
dfdByteOffset >= 80+24; DFD básico KHR_DF (khr_df.h 1.4.1): word0
vendorId/descriptorType, word1 versionNumber/descriptorBlockSize, word2
colorModel/colorPrimaries/transferFunction/flags, word3 texelBlockDimension
(dimensão-1), words4-5 bytesPlane0..7, samples de 16 B (bitOffset/bitLength-
1/channelType/qualifiers + samplePosition + lower/upper). Canais RGBSDA:
R=0, G=1, B=2, A=15. Modelos comprimidos: ETC2=161, ASTC=162.

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
KTX2_HEADER_LEN = 80   # 12 magic + 13 u32 + 2 u64 (sgd) — spec KTX 2.0
KTX2_LEVELINDEX_LEN = 24  # 1 entrada x 3 u64 (offset, length, uncompressed)
VK_FORMAT_R8G8B8A8_UNORM = 37
VK_FORMAT_ETC2_R8G8B8_UNORM_BLOCK = 148
VK_FORMAT_ASTC_4x4_UNORM_BLOCK = 157
# Constantes KHR_DF (khr_df.h v1.4.1, KhronosGroup/KTX-Software)
KHR_DF_VENDOR_KHRONOS = 0
KHR_DF_DESCRIPTORTYPE_BASIC = 0
KHR_DF_VERSION_1_3 = 2          # versionNumber do bloco básico
KHR_DF_MODEL_RGBSDA = 1
KHR_DF_MODEL_ETC2 = 161
KHR_DF_MODEL_ASTC = 162
KHR_DF_PRIMARIES_BT709 = 1
KHR_DF_TRANSFER_LINEAR = 1
KHR_DF_FLAG_ALPHA_STRAIGHT = 0
KHR_DF_CHANNEL_RED = 0
KHR_DF_CHANNEL_GREEN = 1
KHR_DF_CHANNEL_BLUE = 2
KHR_DF_CHANNEL_ALPHA = 15
KHR_DF_CHANNEL_ETC2_COLOR = 2
KHR_DF_CHANNEL_ASTC_DATA = 0


# spec por formato: vk, tipo de stub, DFD (modelo, bloco WxH, bytes/bloco,
# samples (bitOffset, bits, canal)) e alinhamento do level (regra do
# mipPadding: lcm(bytes do bloco de teixel, 4) — 4 p/ RGBA8, 8 p/ ETC2,
# 16 p/ ASTC 4x4, exigido pelo ktx2check) — os stubs pagam payload do
# tamanho EXATO do formato (blocos de ruído, não-imagem), declarado no kvd
# apktester.stub.
FORMAT_SPECS = {
    "raw": {"vk": VK_FORMAT_R8G8B8A8_UNORM, "stub": False,
            "label": "R8G8B8A8_UNORM", "type_size": 1,
            "model": KHR_DF_MODEL_RGBSDA, "block_wh": (1, 1),
            "block_bytes": 4, "align": 4,
            "samples": ((0, 8, KHR_DF_CHANNEL_RED),
                        (8, 8, KHR_DF_CHANNEL_GREEN),
                        (16, 8, KHR_DF_CHANNEL_BLUE),
                        (24, 8, KHR_DF_CHANNEL_ALPHA))},
    "etc1": {"vk": VK_FORMAT_ETC2_R8G8B8_UNORM_BLOCK, "stub": True,
             "label": "ETC2_R8G8B8_UNORM_BLOCK (ETC1-compat)",
             "type_size": 1, "model": KHR_DF_MODEL_ETC2,
             "block_wh": (4, 4), "block_bytes": 8, "align": 8,
             "samples": ((0, 64, KHR_DF_CHANNEL_ETC2_COLOR),)},
    "astc": {"vk": VK_FORMAT_ASTC_4x4_UNORM_BLOCK, "stub": True,
             "label": "ASTC_4x4_UNORM_BLOCK", "type_size": 1,
             "model": KHR_DF_MODEL_ASTC, "block_wh": (4, 4),
             "block_bytes": 16, "align": 16,
             "samples": ((0, 128, KHR_DF_CHANNEL_ASTC_DATA),)},
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


def _align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def _dfd_block(spec: dict) -> bytes:
    """Data Format Descriptor KHR_DF completo (dfdTotalSize + bloco básico
    + samples de 16 B), conforme khr_df.h 1.4.1 e o layout de bits do spec
    (word1: versionNumber bits 0-15 | descriptorBlockSize bits 16-31;
    word2: colorModel/primaries/transfer/flags um byte cada;
    word3: texelBlockDimension0..3 = dimensão-1; words4-5: bytesPlane0..7;
    sample: bitOffset bits 0-15, bitLength bits 16-23 = bits-1,
    channelType bits 24-27, qualifiers 28-31, samplePosition (4 B),
    sampleLower/sampleUpper u32).
    """
    samples = b"".join(
        struct.pack("<HBB4BII", bit_off, bits - 1, chan, 0, 0, 0, 0,
                    0, min((1 << bits) - 1, 0xFFFFFFFF))
        for bit_off, bits, chan in spec["samples"])
    bw, bh = spec["block_wh"]
    block = (struct.pack("<I", (KHR_DF_VENDOR_KHRONOS
                                 | (KHR_DF_DESCRIPTORTYPE_BASIC << 17)))
             + struct.pack("<HH", KHR_DF_VERSION_1_3, 24 + len(samples))
             + bytes((spec["model"],
                      KHR_DF_PRIMARIES_BT709, KHR_DF_TRANSFER_LINEAR,
                      KHR_DF_FLAG_ALPHA_STRAIGHT))
             + bytes((bw - 1, bh - 1, 0, 0))
             + bytes((spec["block_bytes"], 0, 0, 0, 0, 0, 0, 0)))
    return struct.pack("<I", 4 + len(block) + len(samples)) + block + samples


def ktx2_container(spec: dict, width: int, height: int, writer_note: str,
                   stub: bool):
    """Monta header+levelIndex+DFD+KVD(+mipPadding) do KTX2 (spec 2.0).

    Retorna (bytes_do_container_até_o_payload, comprimento_do_payload,
    payload_off). Layout: header 80 B (12 magic + 9 u32 + 4 u32 + 2 u64 sgd)
    + levelIndex 24 B + DFD (24+16*n samples bytes) + KVD + mipPadding de
    zeros até o alinhamento do formato (lcm(tamanho do bloco, 4): 4 p/
    RGBA8, 8 p/ ETC2, 16 p/ ASTC — exigência do ktx2check) + payload.
    Level 0 único; supercompressão 0 => uncompressed == byteLength.
    vkFormat/typeSize do spec do formato. O valor KTXwriter termina em NUL
    (terminação encorajada pelo ktx2check).
    """
    kvd = _kvd_entry(b"KTXwriter\x00", writer_note.encode("utf-8") + b"\x00")
    if stub:
        kvd += _kvd_entry(
            b"apktester.stub\x00",
            b"true; payload=exact-size noise blocks (real ETC1/ASTC encoding "
            b"needs external toolchain)\x00")
    dfd = _dfd_block(spec)
    dfd_off = KTX2_HEADER_LEN + KTX2_LEVELINDEX_LEN
    kvd_off = dfd_off + len(dfd)
    payload_off = _align_up(kvd_off + len(kvd), spec["align"])
    padding = b"\0" * (payload_off - (kvd_off + len(kvd)))
    level_bytes = level_payload_bytes(spec, width, height)
    header = (KTX2_MAGIC
              + struct.pack("<9I", spec["vk"], spec["type_size"],
                            width, height, 0, 0, 1, 1, 0)
              + struct.pack("<4I", dfd_off, len(dfd), kvd_off, len(kvd))
              + struct.pack("<2Q", 0, 0)
              + struct.pack("<QQQ", payload_off, level_bytes, level_bytes))
    return header + dfd + kvd + padding, level_bytes, payload_off


def level_payload_bytes(spec: dict, width: int, height: int) -> int:
    """Bytes do level 0: blocos ceil(w/bw)*ceil(h/bh)*block_bytes
    (para raw, block 1x1/4 B => w*h*4 — o cálculo é o mesmo)."""
    bw, bh = spec["block_wh"]
    blocks_x = (width + bw - 1) // bw
    blocks_y = (height + bh - 1) // bh
    return blocks_x * blocks_y * spec["block_bytes"]


def open_ktx2(path: str, spec: dict, width: int, height: int,
              writer_note: str):
    """Abre o KTX2 já com o cabeçalho escrito; devolve o handle p/ payload
    (comprimento esperado = level_payload_bytes)."""
    prefix, _level, _off = ktx2_container(spec, width, height, writer_note,
                                          spec["stub"])
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


def _stub_noise(seed: int, fmt: str, mat_name: str, map_name: str,
                total: int) -> bytes:
    """Keystream determinístico para o payload de blocos do stub: cadeia de
    SHA-256 (state inicial derivado de seed:formato:material:mapa). Sem
    random, sem relógio — reexecutar devolve os mesmos bytes."""
    state = hashlib.sha256(
        f"{seed}:{fmt}:{mat_name}:{map_name}".encode("utf-8")).digest()
    out = bytearray()
    while len(out) < total:
        state = hashlib.sha256(state).digest()
        out += state
    return bytes(out[:total])


def write_material_set(out_dir: str, seed: int, mat_name: str, size: int,
                       fmt: str, subdir: str) -> list:
    """Gera os 4 mapas do material na resolução/formato pedidos.

    raw: payload RGBA8 derivado do heightmap (linha a linha). Stubs
    (etc1/astc): payload de blocos de ruído com o byte-count EXATO do
    formato comprimido (não é imagem codificada — kvd apktester.stub).
    """
    mat = MATERIALS[mat_name]
    spec = FORMAT_SPECS[fmt]
    artifacts = []
    if spec["stub"]:
        payload = level_payload_bytes(spec, size, size)
        for map_name in MAPS:
            rel = f"textures/{fmt}/{subdir}{mat_name}_{map_name}.ktx2"
            full = os.path.join(out_dir, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            note = (f"apk-tester gen-textures.py seed={seed} "
                    f"fmt={spec['label']} map={map_name}")
            with open(full, "wb") as fh:
                prefix, _lvl, _off = ktx2_container(
                    spec, size, size, note, True)
                fh.write(prefix)
                fh.write(_stub_noise(seed, fmt, mat_name, map_name, payload))
            artifacts.append({
                "path": rel, "bytes": os.path.getsize(full),
                "sha256": sha256_file(full),
                "material": mat_name, "map": map_name, "format": fmt,
                "vk_format": spec["vk"], "width": size, "height": size,
                "stub": True})
        return artifacts
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
            files[map_name] = open_ktx2(full, spec, size, size, note)
            paths[map_name] = rel
        for y in range(size):
            rows = derive_rows(plane, size, size, y, mat)
            for i, map_name in enumerate(MAPS):
                files[map_name].write(bytes(rows[i]))
    finally:
        for fh in files.values():
            fh.close()
    for map_name in MAPS:
        artifacts.append({
            "path": paths[map_name], "bytes": os.path.getsize(
                os.path.join(out_dir, paths[map_name])),
            "sha256": sha256_file(os.path.join(out_dir, paths[map_name])),
            "material": mat_name, "map": map_name, "format": fmt,
            "vk_format": spec["vk"], "width": size, "height": size,
            "stub": False})
    return artifacts


def write_indexes(out_dir: str, seed: int, fmt_list: list, artifacts: list):
    """index.json (rico) + manifest.json (convenção) — sem timestamps."""
    index = {"tool": TOOL, "seed": seed, "formats": fmt_list,
             "note_stub": ("formatos etc1/astc são stubs honestos: container "
                           "KTX2 spec-completo (DFD do formato comprimido) + "
                           "payload de blocos de ruído no byte-count exato — "
                           "não são imagens codificadas; a chave kvd "
                           "apktester.stub declara no próprio arquivo"),
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
    """Gera 64x64 (raw+etc1+astc) em /tmp duas vezes: valida o container
    KTX2 campo a campo contra a spec 2.0 (header 80 B com sgd u64 zerados,
    level index coerente, DFD parseável, KVD alinhado, payload do tamanho
    exato do formato) e o determinismo byte a byte."""
    tmp = tempfile.mkdtemp(prefix="apktester-textures-")
    try:
        hashes = []
        for run in ("a", "b"):
            d = os.path.join(tmp, run)
            generate(d, DEFAULT_SEED, size=64,
                     fmt_list=["raw", "etc1", "astc"],
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
        n_tex = len(hashes[0]) - 2  # fora index.json + manifest.json

        for fmt, spec in FORMAT_SPECS.items():
            ktx = os.path.join(tmp, "a", "textures", fmt,
                               "granite_albedo.ktx2")
            with open(ktx, "rb") as fh:
                blob = fh.read()
            assert blob[:12] == KTX2_MAGIC, f"{fmt}: magic bytes inválidos"
            (vk, tsize, w, h, depth, layers, faces, levels,
             scheme) = struct.unpack_from("<9I", blob, 12)
            assert vk == spec["vk"] and tsize == spec["type_size"], \
                f"{fmt}: vkFormat={vk} typeSize={tsize} inesperados"
            assert (w, h) == (64, 64) and depth == 0, \
                f"{fmt}: dimensões {w}x{h}x{depth} inesperadas"
            assert layers == 0 and faces == 1 and levels == 1, \
                f"{fmt}: layer/face/level count inesperados"
            assert scheme == 0, f"{fmt}: supercompressionScheme != 0"
            dfd_off, dfd_len, kvd_off, kvd_len = \
                struct.unpack_from("<4I", blob, 48)
            sgd_off, sgd_len = struct.unpack_from("<2Q", blob, 64)
            assert sgd_off == 0 and sgd_len == 0, f"{fmt}: sgd deveria ser 0"
            assert dfd_off == KTX2_HEADER_LEN + KTX2_LEVELINDEX_LEN, \
                f"{fmt}: dfdByteOffset={dfd_off} != " \
                f"{KTX2_HEADER_LEN + KTX2_LEVELINDEX_LEN}"
            assert kvd_off == dfd_off + dfd_len, \
                f"{fmt}: KVD não colado no fim do DFD"
            assert kvd_len % 4 == 0 and kvd_len > 0, \
                f"{fmt}: KVD vazio/desalinhado"
            lvl_off, lvl_len, lvl_uncomp = struct.unpack_from("<QQQ", blob, 80)
            expected_payload = level_payload_bytes(spec, 64, 64)
            assert lvl_len == expected_payload and lvl_uncomp == lvl_len, \
                f"{fmt}: level byteLength={lvl_len} != esperado " \
                f"{expected_payload} (ou uncompressed diverge)"
            assert lvl_off == _align_up(kvd_off + kvd_len, spec["align"]), \
                f"{fmt}: payload não alinhado a {spec['align']} B após o KVD"
            assert lvl_off % spec["align"] == 0, \
                f"{fmt}: payload não {spec['align']}-alinhado"
            assert len(blob) == lvl_off + lvl_len, \
                f"{fmt}: tamanho total != levelOffset + byteLength"
            # DFD: dfdTotalSize + bloco básico (vendor/type, versão/tamanho,
            # modelo/primárias/transferência/flags, dimensões do bloco,
            # bytesPlane) + samples
            dfd_total = struct.unpack_from("<I", blob, dfd_off)[0]
            assert dfd_total == dfd_len, \
                f"{fmt}: dfdTotalSize={dfd_total} != dfdByteLength={dfd_len}"
            vendor_type = struct.unpack_from("<I", blob, dfd_off + 4)[0]
            assert vendor_type == 0, \
                f"{fmt}: vendorId/descriptorType != Khronos/basic (0)"
            ver_size = struct.unpack_from("<I", blob, dfd_off + 8)[0]
            version, block_size = ver_size & 0xFFFF, ver_size >> 16
            assert version == 2, f"{fmt}: versionNumber={version} != 2"
            n_samples = (block_size - 24) // 16
            assert block_size == 24 + 16 * n_samples \
                and n_samples == len(spec["samples"]), \
                f"{fmt}: descriptorBlockSize={block_size} incoerente"
            model, primaries, transfer, flags = \
                struct.unpack_from("<4B", blob, dfd_off + 12)
            assert (model, primaries, transfer, flags) == \
                (spec["model"], 1, 1, 0), f"{fmt}: word2 do DFD diverge"
            bw, bh = struct.unpack_from("<2B", blob, dfd_off + 16)
            assert (bw + 1, bh + 1) == spec["block_wh"], \
                f"{fmt}: texelBlockDimension diverge"
            bytes_plane = struct.unpack_from("<B", blob, dfd_off + 20)[0]
            assert bytes_plane == spec["block_bytes"], \
                f"{fmt}: bytesPlane0={bytes_plane} != {spec['block_bytes']}"
            for i, (bit_off, bits, chan) in enumerate(spec["samples"]):
                s_off = dfd_off + 4 + 24 + 16 * i
                s_bit, s_len, s_chan = struct.unpack_from("<HBB", blob, s_off)
                assert (s_bit, s_len + 1, s_chan) == (bit_off, bits, chan), \
                    f"{fmt}: sample {i} diverge do spec"
            kvd_blob = blob[kvd_off:kvd_off + kvd_len]
            first_len = struct.unpack_from("<I", blob, kvd_off)[0]
            assert 4 <= first_len <= kvd_len, f"{fmt}: KVD incoerente"
            assert b"KTXwriter" in kvd_blob, f"{fmt}: KVD sem KTXwriter"
            if spec["stub"]:
                assert b"apktester.stub" in kvd_blob, \
                    f"{fmt}: stub sem a chave kvd de honestidade"
        print(f"[gen-textures] selftest OK: containers KTX2 spec-completos "
              f"(header 80 B + levelIndex + DFD + KVD) validados campo a "
              f"campo nos 3 formatos; {n_tex} texturas byte-idênticas nas "
              f"duas execuções")
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
