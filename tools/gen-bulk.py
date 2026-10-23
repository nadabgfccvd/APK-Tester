#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen-bulk.py — cargas de volume (bulk) determinísticas para o gate de
tamanho do flagship "Behemoth" (APK Tester, fase A6).

Preenche OUT/bulk/{textures,meshes,audio,data}/ com arquivos sintéticos que
fecham a cota de volume do APK: o preset "full" entrega ~768 MiB de carga
adicional (29 arquivos) para o flagship cruzar o gate [850, 1000] MB medido
pelo tools/size-budget.sh (.ktx2 cai em textures, .ply em meshes, .wav em
audio, .bulk em other). O preset "quick" (15 MiB) existe para debug local e
para o selftest. O A6 integra a árvore gerada em assets/bulk/ do APK.

HONESTIDADE (lei do repo): todo payload é ruído determinístico — o keystream
hashlib.shake_256(f"{seed}:{categoria}:{ordinal}") gravado em fatias de
1 MiB. Os containers têm cabeçalhos estruturalmente válidos (KTX2 com
vkFormat real, PLY binary_little_endian parseável, WAV PCM16 canônico de 44 B
e APKT-BULK1 com metadados JSON), porém NÃO há conteúdo real capturado — é
ruído declarado, e o bulk/manifest.json de cada árvore afirma isso em
português claro. APLY leva a nota no próprio comentário do header; KTX2 e
WAV não têm campo de comentário no formato — o manifest responde por eles.

FOLGA DE CABEÇALHO (header slack): os nominais por arquivo (NOMINAL_PRESETS)
são alvos; o tamanho FINAL exato de cada arquivo é o que o manifest registra,
e é ele a fonte da verdade (o plano pede: constantes = tamanho final, payload
derivado). Desvios por arquivo, todos documentados e <= BULK_SLACK (128 B):
  - KTX2: o cabeçalho REAL do formato tem 72 B (12 magic + 15 u32); o plano
    citava 80. As dimensões de pixel fecham MiB exato de pixels (4096x4096
    RGB565 = 32 MiB; 1024x512 = 1 MiB), logo o final fica +72 B acima do
    nominal — "header + pixels exatos" é a regra declarada do formato.
  - PLY: o cabeçalho depende da contagem de vértices; fecha o MAIOR N cujo
    cabeçalho+payload cabe no nominal (folga < 12 B por arquivo).
  - WAV: 44 B canônicos + 2*samples; nominal par => final == nominal.
  - .bulk: DESVIO declarado — o plano pedia cabeçalho de 64 B, mas o JSON de
    metadados exigido (magic/seed/kind/ordinal/bytes/synthetic) não cabe nos
    53 B úteis; o cabeçalho foi fixado em 128 B (magic + JSON + padding '\n'),
    exato e determinístico. Final == nominal.

CLI:
  python3 tools/gen-bulk.py --out DIR [--preset full|quick] [--seed S]
      Gera DIR/bulk/{textures,meshes,audio,data}/ + DIR/bulk/manifest.json.
  python3 tools/gen-bulk.py --verify DIR
      Revalida a árvore contra o próprio bulk/manifest.json (presença,
      tamanhos, sha256, contagens por categoria e magics). exit 0 ok /
      1 divergência / 2 fatal (manifest ausente/ilegível).
  python3 tools/gen-bulk.py --selftest
      Provas in-process (determinismo 2x, magics, headers, manifest,
      round-trip do verify, keystream) e sai. exit 0/1.

--preset full é o default de PRODUÇÃO: o gate A6 depende dele e o gradle
passa -PbulkPreset explicitamente; use --preset quick para debug local
(15 MiB). Nota de integração: o tools/verify-deterministic.sh invoca este
gerador sem flags extras — com o default full são ~2x768 MB por rodada
(correto, porém pesado); acrescentar "--preset quick" ao mapa turbo_args é o
follow-up barato de A6. Sem rede, sem timestamps, sem aleatoriedade além da
seed; somente python3 stdlib.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import struct
import sys
import tempfile

TOOL = "gen-bulk.py"
GENERATOR_ID = "tools/gen-bulk.py"
DEFAULT_SEED = "20261022"
CHUNK = 1 << 20  # 1 MiB: o payload é gravado em fatias do digest já pronto

# ------------------------------------------------------------------ formatos
KTX2_MAGIC = b"\xabKTX 20\xbb\r\n\x1a\n"
VK_FORMAT_R5G6B5_UNORM_PACK16 = 65
KTX2_HEADER_LEN = 72  # 12 magic + 15 u32 — cabeçalho real do KTX2
PLY_NOTE = ("APK-Tester: malha sintetica deterministica; "
            "coordenadas = ruido do keystream, declarado no manifest")
WAV_HEADER_LEN = 44  # RIFF+fmt+data canônico
WAV_RATE = 8000      # PCM16 mono => byte_rate 16000, block_align 2
BULK_MAGIC = b"APKT-BULK1\n"
BULK_HEADER_LEN = 128  # magic 11 + linha JSON + padding '\n' (desvio do plano)
BULK_SLACK = 128       # folga máxima documentada por arquivo vs nominal

# ------------------------------------------------------------------ categorias
CATEGORY_ORDER = ("textures", "meshes", "audio", "data")
CATEGORY_EXT = {"textures": ".ktx2", "meshes": ".ply", "audio": ".wav",
                "data": ".bulk"}
CATEGORY_STEM = {"textures": "bulk_tex", "meshes": "bulk_mesh",
                 "audio": "bulk_stem", "data": "bulk_data"}
CATEGORY_MAGIC = {"textures": KTX2_MAGIC, "meshes": b"ply\n",
                  "audio": b"RIFF", "data": BULK_MAGIC}

# Alvos NOMINAIS por arquivo (tamanho FINAL desejado; a folga de cabeçalho
# está documentada no docstring e no manifest — manifest manda).
NOMINAL_PRESETS = {
    "full": {"textures": (6, 33554432), "meshes": (4, 25165824),
             "audio": (8, 16777216), "data": (11, 33554432)},
    "quick": {"textures": (3, 1048576), "meshes": (2, 1048576),
              "audio": (2, 1048576), "data": (4, 2097152)},
}

# Dimensões RGB565 que fecham MiB exato de pixels (2*w*h): 4096x4096 = 32 MiB,
# 1024x512 = 1 MiB. O tamanho final do KTX2 é header (72 B) + pixels exatos.
TEXTURE_DIMS = {"full": (4096, 4096), "quick": (1024, 512)}

MANIFEST_NOTE = (
    "Conteúdo 100% sintético e determinístico: cada payload é o keystream "
    "shake_256(seed:categoria:ordinal) gravado em fatias de 1 MiB; os "
    "containers têm cabeçalhos estruturalmente válidos (KTX2, PLY "
    "binary_little_endian, WAV PCM16, APKT-BULK1) mas não há conteúdo real "
    "capturado. Os tamanhos finais exatos registrados aqui prevalecem sobre "
    "os nominais (folga de cabeçalho <= 128 B por arquivo: KTX2 = 72 B de "
    "cabeçalho real + pixels exatos; PLY fecha o maior número de vértices "
    "cujo cabeçalho+payload cabe no nominal, folga < 12 B; WAV e .bulk "
    "fecham exatos). Sem timestamps, sem rede, sem aleatoriedade além da "
    "seed."
)


# ------------------------------------------------------------------ headers
def build_ktx2_header(width: int, height: int) -> bytes:
    """Cabeçalho KTX2 real (12 magic + 15 u32) para textura RGB565 2D.

    vkFormat 65 (R5G6B5_UNORM_PACK16), typeSize 2, 1 level/face/layer,
    sem depth e sem dfd/kvd/sgd (offsets/lengths zerados). O payload que
    segue o header é o keystream — largura*altura*2 bytes exatos.
    """
    fields = (
        VK_FORMAT_R5G6B5_UNORM_PACK16,  # vkFormat
        2,                              # typeSize (R5G6B5 = 2 bytes)
        width, height,                  # pixelWidth, pixelHeight
        0,                              # pixelDepth
        1,                              # layerCount
        1,                              # faceCount
        1,                              # levelCount
        0,                              # supercompressionScheme
        0, 0, 0, 0, 0, 0,               # dfd/kvd/sgd byteOffset+byteLength
    )
    return KTX2_MAGIC + struct.pack("<15I", *fields)


def ply_header(vertex_count: int) -> bytes:
    """Cabeçalho ASCII de PLY binary_little_endian com N vértices.

    Payload = 3 floats (x,y,z) por vértice = 12*N bytes de keystream;
    coordenadas são ruído — a declaração honesta vai no comment do header.
    """
    lines = (
        "ply",
        "format binary_little_endian 1.0",
        "comment " + PLY_NOTE,
        f"element vertex {vertex_count}",
        "property float x",
        "property float y",
        "property float z",
        "end_header",
    )
    return ("\n".join(lines) + "\n").encode("ascii")


def wav_header(final_size: int) -> bytes:
    """RIFF/WAVE canônico de 44 B, PCM16 mono 8000 Hz (ruído = stem honesto)."""
    return struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", final_size - 8, b"WAVE",
        b"fmt ", 16,
        1,                      # audio format = PCM
        1,                      # channels = mono
        WAV_RATE,               # sample rate
        WAV_RATE * 2,           # byte rate = 8000 * 1 canal * 2 bytes
        2,                      # block align
        16,                     # bits por sample
        b"data", final_size - WAV_HEADER_LEN,
    )


def bulk_header(seed: str, ordinal: int, payload_len: int) -> bytes:
    """Cabeçalho APKT-BULK1 de 128 B: magic + linha JSON + padding '\n'.

    JSON determinístico (ordem fixa de chaves, ensure_ascii, separadores
    compactos); "bytes" é o tamanho do payload keystream após o header.
    """
    meta = {"magic": "APKT-BULK1", "seed": seed, "kind": "data",
            "ordinal": ordinal, "bytes": payload_len, "synthetic": True}
    line = json.dumps(meta, ensure_ascii=True, separators=(",", ":"))
    body = BULK_MAGIC + line.encode("ascii")
    pad = BULK_HEADER_LEN - len(body)
    if pad < 1:
        raise ValueError(f"metadados .bulk não cabem no cabeçalho de "
                         f"{BULK_HEADER_LEN} B (corpo precisa de "
                         f"{len(body) + 1} B)")
    return body + b"\n" * pad


# ------------------------------------------------------------------ plano
def resolve_plan(preset: str) -> dict:
    """Fecha o plano exato do preset: por categoria, contagem, tamanho final
    por arquivo (header+payload) e totais. Função pura e determinística."""
    if preset not in NOMINAL_PRESETS:
        raise ValueError(f"preset desconhecido: {preset!r}")
    nominal = NOMINAL_PRESETS[preset]
    plan = {"preset": preset, "categories": {}, "files": []}
    for cat in CATEGORY_ORDER:
        count, per_file = nominal[cat]
        if cat == "textures":
            width, height = TEXTURE_DIMS[preset]
            header_len = KTX2_HEADER_LEN
            payload_len = width * height * 2   # 2 bytes por pixel RGB565
            final = header_len + payload_len
            extra = {"dims": (width, height)}
        elif cat == "meshes":
            # fixed = comprimento do header sem os dígitos de N (truque:
            # medir com N=1 e subtrair o dígito). Fecha o maior N que cabe.
            fixed = len(ply_header(1)) - 1
            vertices = max((per_file - fixed - 10) // 12, 1)
            while fixed + len(str(vertices)) + 12 * vertices > per_file:
                vertices -= 1
            header_len = fixed + len(str(vertices))
            payload_len = 12 * vertices
            final = header_len + payload_len
            extra = {"vertices": vertices}
        elif cat == "audio":
            if per_file <= WAV_HEADER_LEN or per_file % 2:
                raise ValueError(f"nominal de áudio inválido: {per_file}")
            header_len = WAV_HEADER_LEN
            payload_len = per_file - WAV_HEADER_LEN  # par => fecha exato
            final = per_file
            extra = {}
        else:  # data
            payload_len = per_file - BULK_HEADER_LEN
            if payload_len <= 0:
                raise ValueError(f"nominal de data inválido: {per_file}")
            header_len = BULK_HEADER_LEN
            final = per_file
            extra = {}
        plan["categories"][cat] = {
            "count": count, "file_bytes": final, "header_len": header_len,
            "payload_len": payload_len,
            "nominal_file_bytes": per_file, **extra,
        }
        for ordinal in range(count):
            name = f"{CATEGORY_STEM[cat]}_{ordinal:02d}{CATEGORY_EXT[cat]}"
            plan["files"].append({
                "path": f"{cat}/{name}", "category": cat,
                "ordinal": ordinal, "bytes": final,
                "header_len": header_len, "payload_len": payload_len,
            })
    plan["nominal_total"] = sum(
        c["count"] * c["nominal_file_bytes"]
        for c in plan["categories"].values())
    plan["total_bytes"] = sum(f["bytes"] for f in plan["files"])
    return plan


def build_header(entry: dict, seed: str, plan: dict) -> bytes:
    """Despacha o cabeçalho do formato para uma entrada do plano."""
    cat = entry["category"]
    info = plan["categories"][cat]
    if cat == "textures":
        width, height = info["dims"]
        return build_ktx2_header(width, height)
    if cat == "meshes":
        return ply_header(info["vertices"])
    if cat == "audio":
        return wav_header(entry["bytes"])
    return bulk_header(seed, entry["ordinal"], entry["payload_len"])


def keystream(seed: str, category: str, ordinal: int, length: int) -> bytes:
    """Fonte única de bytes: shake_256(seed:categoria:ordinal) — ruído
    determinístico, sem random, sem rede, sem relógio."""
    return hashlib.shake_256(
        f"{seed}:{category}:{ordinal}".encode("utf-8")).digest(length)


# ------------------------------------------------------------------ geração
def sha256_file(path: str) -> str:
    """SHA-256 em streaming (1 MiB por leitura)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def write_asset(bulk_root: str, entry: dict, seed: str, plan: dict) -> dict:
    """Grava um arquivo bulk (header + keystream em fatias de 1 MiB),
    calculando o sha256 durante a escrita. Devolve a entrada do manifest."""
    header = build_header(entry, seed, plan)
    if len(header) != entry["header_len"]:
        raise RuntimeError(f"header de {entry['path']}: {len(header)} B != "
                           f"planejado {entry['header_len']} B")
    stream = keystream(seed, entry["category"], entry["ordinal"],
                       entry["payload_len"])
    sha = hashlib.sha256()
    with open(os.path.join(bulk_root, entry["path"]), "wb") as fh:
        fh.write(header)
        sha.update(header)
        view = memoryview(stream)
        for off in range(0, entry["payload_len"], CHUNK):
            piece = view[off:off + CHUNK]
            fh.write(piece)
            sha.update(piece)
    return {
        "path": entry["path"],
        "category": entry["category"],
        "bytes": entry["header_len"] + entry["payload_len"],
        "sha256": sha.hexdigest(),
        "synthetic": True,
    }


def generate(out_dir: str, preset: str, seed: str) -> dict:
    """Gera a árvore bulk/ completa + manifest.json; devolve o manifest.

    Determinístico: ordem fixa de categorias e ordinais, sem timestamps,
    manifest com chaves em ordem declarada. Reexecutar sobre a mesma pasta
    reescreve os mesmos bytes (idempotente).
    """
    plan = resolve_plan(preset)
    bulk_root = os.path.join(out_dir, "bulk")
    for cat in CATEGORY_ORDER:
        os.makedirs(os.path.join(bulk_root, cat), exist_ok=True)
    entries = [write_asset(bulk_root, entry, seed, plan)
               for entry in plan["files"]]
    manifest = {
        "schema_version": 1,
        "generator": GENERATOR_ID,
        "seed": seed,
        "preset": plan["preset"],
        "synthetic": True,
        "note": MANIFEST_NOTE,
        "categories": {
            cat: {
                "count": plan["categories"][cat]["count"],
                "bytes": sum(e["bytes"] for e in entries
                             if e["category"] == cat),
                "ext": CATEGORY_EXT[cat],
            }
            for cat in CATEGORY_ORDER
        },
        "total_bytes": sum(e["bytes"] for e in entries),
        "files": entries,
    }
    with open(os.path.join(bulk_root, "manifest.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


# ------------------------------------------------------------------ verify
def verify_tree(root_dir: str):
    """Revalida ROOT/bulk contra o próprio bulk/manifest.json.

    Confere presença (sem extras/ausentes), tamanho, sha256, magics por
    categoria e contagens/totais do manifest. Devolve (ok, problemas, info).
    """
    problems = []
    bulk_root = os.path.join(root_dir, "bulk")
    manifest_path = os.path.join(bulk_root, "manifest.json")
    if not os.path.isfile(manifest_path):
        return False, [f"manifest ausente: {manifest_path}"], {}
    try:
        with open(manifest_path, "rb") as fh:
            manifest = json.loads(fh.read().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return False, [f"manifest ilegível/inválido: {exc}"], {}
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        return False, ["manifest sem lista 'files'"], {}

    actual = {}
    for dirpath, _dirnames, filenames in os.walk(bulk_root):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, bulk_root).replace(os.sep, "/")
            if rel != "manifest.json":
                actual[rel] = full
    listed = {e.get("path"): e for e in files
              if isinstance(e, dict) and isinstance(e.get("path"), str)}
    for rel in sorted(set(actual) - set(listed)):
        problems.append(f"arquivo extra fora do manifest: {rel}")
    for rel in sorted(set(listed) - set(actual)):
        problems.append(f"arquivo listado ausente na árvore: {rel}")
    if any(not isinstance(e, dict) or not isinstance(e.get("path"), str)
           for e in files):
        problems.append("manifest com entrada de arquivo malformada")

    counts = {cat: [0, 0] for cat in CATEGORY_ORDER}
    total = 0
    for e in files:
        rel = e.get("path") if isinstance(e, dict) else None
        if rel not in actual:
            continue
        full = actual[rel]
        size = os.path.getsize(full)
        if size != e.get("bytes"):
            problems.append(f"{rel}: tamanho {size} != manifest "
                            f"{e.get('bytes')}")
        if sha256_file(full) != e.get("sha256"):
            problems.append(f"{rel}: sha256 diverge do manifest")
        with open(full, "rb") as fh:
            head = fh.read(16)
        magic = CATEGORY_MAGIC.get(e.get("category"))
        if magic is None:
            problems.append(f"{rel}: categoria desconhecida "
                            f"{e.get('category')!r}")
        elif not head.startswith(magic):
            problems.append(f"{rel}: magic de {e['category']} ausente")
        if e.get("category") == "audio" and head[8:12] != b"WAVE":
            problems.append(f"{rel}: 'WAVE' ausente no offset 8")
        bucket = counts.get(e.get("category"))
        if bucket is not None:
            bucket[0] += size
            bucket[1] += 1
        total += size
    for cat, (cat_bytes, cat_count) in counts.items():
        declared = manifest.get("categories", {}).get(cat, {})
        if declared.get("count") != cat_count:
            problems.append(f"categoria {cat}: contagem {cat_count} != "
                            f"manifest {declared.get('count')}")
        if declared.get("bytes") != cat_bytes:
            problems.append(f"categoria {cat}: bytes {cat_bytes} != "
                            f"manifest {declared.get('bytes')}")
    if manifest.get("total_bytes") != total:
        problems.append(f"total_bytes {total} != manifest "
                        f"{manifest.get('total_bytes')}")
    return not problems, problems, {"files": len(actual), "bytes": total}


# ------------------------------------------------------------------ selftest
def _tree_hashes(root: str) -> dict:
    """Mapa caminho-relativo -> sha256 de todos os arquivos da árvore."""
    out = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            out[rel] = sha256_file(full)
    return out


def selftest() -> int:
    """Provas in-process com o preset quick (leve). exit 0 ok / 1 falha."""
    seed = DEFAULT_SEED
    proofs = 0

    def ok(desc: str) -> None:
        nonlocal proofs
        proofs += 1
        print(f"[{TOOL}] PASS {proofs:02d}: {desc}")

    try:
        with tempfile.TemporaryDirectory(prefix="apktester-bulk-") as tmp:
            dir_a = os.path.join(tmp, "a")
            dir_b = os.path.join(tmp, "b")
            man_a = generate(dir_a, "quick", seed)
            man_b = generate(dir_b, "quick", seed)

            # (a) determinismo: duas gerações byte-idênticas
            with open(os.path.join(dir_a, "bulk", "manifest.json"), "rb") as fh:
                man_bytes_a = fh.read()
            with open(os.path.join(dir_b, "bulk", "manifest.json"), "rb") as fh:
                man_bytes_b = fh.read()
            assert man_bytes_a == man_bytes_b, "manifest difere entre execuções"
            tree_a = _tree_hashes(dir_a)
            tree_b = _tree_hashes(dir_b)
            assert tree_a == tree_b, "árvores divergem entre execuções"
            ok(f"determinismo 2x quick: {len(tree_a)} arquivos byte-idênticos")

            bulk_a = os.path.join(dir_a, "bulk")

            # nomes/ordem/contagens contratados do preset
            nominal = NOMINAL_PRESETS["quick"]
            expected_paths = [
                f"{cat}/{CATEGORY_STEM[cat]}_{i:02d}{CATEGORY_EXT[cat]}"
                for cat in CATEGORY_ORDER for i in range(nominal[cat][0])
            ]
            assert [e["path"] for e in man_a["files"]] == expected_paths, \
                "nomes/ordem de arquivos inesperados"
            for cat in CATEGORY_ORDER:
                assert man_a["categories"][cat]["count"] == nominal[cat][0]
            ok("nomes, ordem e contagens batem com o preset quick")

            # (b) magics por categoria
            for e in man_a["files"]:
                with open(os.path.join(bulk_a, e["path"]), "rb") as fh:
                    head = fh.read(16)
                assert head.startswith(CATEGORY_MAGIC[e["category"]]), \
                    f"magic ausente em {e['path']}"
                if e["category"] == "audio":
                    assert head[8:12] == b"WAVE"
            ok("magics conferidos (KTX2 / ply / RIFF+WAVE / APKT-BULK1)")

            # (c) header WAV são (riff/data coerentes com o tamanho)
            for e in man_a["files"]:
                if e["category"] != "audio":
                    continue
                full = os.path.join(bulk_a, e["path"])
                size = os.path.getsize(full)
                with open(full, "rb") as fh:
                    hdr = fh.read(WAV_HEADER_LEN)
                (_riff, riff_size, _wave, _fmt, _fsize, pcm, channels,
                 rate, byte_rate, block_align, bits,
                 _data, data_size) = struct.unpack("<4sI4s4sIHHIIHH4sI", hdr)
                assert riff_size == size - 8, "riff size != filesize-8"
                assert data_size == size - WAV_HEADER_LEN, \
                    "data size != filesize-44"
                assert (pcm, channels, rate, byte_rate, block_align, bits) == \
                    (1, 1, WAV_RATE, WAV_RATE * 2, 2, 16), "fmt WAV inesperado"
            ok("headers WAV saneis (PCM16 mono 8000 Hz, tamanhos fecham)")

            # (d) header PLY parseável (element vertex N bate com payload/12)
            for e in man_a["files"]:
                if e["category"] != "meshes":
                    continue
                full = os.path.join(bulk_a, e["path"])
                with open(full, "rb") as fh:
                    raw = fh.read()
                end = raw.index(b"end_header\n") + len(b"end_header\n")
                text = raw[:end].decode("ascii")
                assert text.startswith("ply\nformat binary_little_endian 1.0\n")
                n_line = next(l for l in text.splitlines()
                              if l.startswith("element vertex "))
                n = int(n_line.rsplit(" ", 1)[1])
                assert len(raw) - end == 12 * n, "payload PLY != 12*N"
                assert (b"comment " + PLY_NOTE.encode("ascii")) in raw
            ok("headers PLY parseáveis (N vértices = payload/12, comment ok)")

            # (e) manifest confere com a árvore (round-trip do verify)
            okv, problems, info = verify_tree(dir_a)
            assert okv, f"verify reprovou na árvore fresca: {problems}"
            ok(f"manifest confere com a árvore ({info['files']} arquivos, "
               f"{info['bytes']} bytes)")

            # (e2) folga de cabeçalho documentada por arquivo vs nominal
            nominal_total = sum(c[0] * c[1] for c in nominal.values())
            for e in man_a["files"]:
                target = nominal[e["category"]][1]
                assert abs(e["bytes"] - target) <= BULK_SLACK, \
                    f"folga de cabeçalho estourada em {e['path']}"
            ok(f"folga de cabeçalho <= {BULK_SLACK} B/arquivo vs nominal "
               f"(total real {man_a['total_bytes']} vs nominal "
               f"{nominal_total})")

            # (f) corrupção de 1 byte tem que derrubar o verify
            corrupt_dir = os.path.join(tmp, "corrupt")
            shutil.copytree(dir_a, corrupt_dir)
            victim = os.path.join(corrupt_dir, "bulk", "data",
                                  "bulk_data_00.bulk")
            with open(victim, "rb") as fh:
                raw = bytearray(fh.read())
            raw[len(raw) // 2] ^= 0xFF
            with open(victim, "wb") as fh:
                fh.write(raw)
            okv, problems, _info = verify_tree(corrupt_dir)
            assert not okv, "verify aceitou árvore corrompida"
            ok("round-trip do verify: árvore fresca passa, 1 byte corrompido "
               "derruba")

            # (g) keystream: prefixo recompute independente
            with open(os.path.join(bulk_a, "data", "bulk_data_00.bulk"),
                      "rb") as fh:
                fh.seek(BULK_HEADER_LEN)
                prefix = fh.read(32)
            expect = hashlib.shake_256(f"{seed}:data:0".encode("utf-8")) \
                .digest(32)
            assert prefix == expect, "payload .bulk != keystream esperado"
            ok("keystream confere: prefixo == shake_256(seed:data:0) "
               "recomputado")

        print(f"[{TOOL}] SELFTEST OK ({proofs} provas)")
        return 0
    except AssertionError as exc:
        print(f"[{TOOL}] selftest FALHOU: {exc}", file=sys.stderr)
        return 1


# ------------------------------------------------------------------ CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Cargas bulk sintéticas determinísticas para o gate de "
                    "tamanho do flagship Behemoth (APK Tester, fase A6).")
    ap.add_argument("--out", metavar="DIR",
                    help="raiz de saída; grava DIR/bulk/{textures,meshes,"
                         "audio,data}/ + DIR/bulk/manifest.json")
    ap.add_argument("--preset", choices=("full", "quick"), default="full",
                    help="full = ~768 MiB para o gate A6 (default de "
                         "produção; o gradle passa -PbulkPreset "
                         "explicitamente); quick = 15 MiB para debug local")
    ap.add_argument("--seed", default=DEFAULT_SEED,
                    help=f"semente do keystream (default: {DEFAULT_SEED})")
    ap.add_argument("--verify", metavar="DIR",
                    help="revalida a árvore contra o próprio "
                         "bulk/manifest.json e sai")
    ap.add_argument("--selftest", action="store_true",
                    help="auto-validação in-process (preset quick) e sai")
    args = ap.parse_args(argv)

    if args.selftest and args.verify:
        ap.error("--selftest e --verify são mutuamente exclusivos")
    if args.verify and args.out:
        ap.error("--verify e --out são mutuamente exclusivos")
    if args.selftest:
        return selftest()
    if args.verify:
        if not os.path.isdir(args.verify):
            print(f"[{TOOL}] erro: diretório inexistente: {args.verify}",
                  file=sys.stderr)
            return 2
        ok, problems, info = verify_tree(args.verify)
        if not ok:
            for p in problems[:20]:
                print(f"[{TOOL}] DIVERGENCIA: {p}", file=sys.stderr)
            if len(problems) > 20:
                print(f"[{TOOL}] ... +{len(problems) - 20} divergências",
                      file=sys.stderr)
            print(f"[{TOOL}] verify FALHOU em {args.verify} "
                  f"({len(problems)} divergências)", file=sys.stderr)
            return 1
        print(f"[{TOOL}] PASS: árvore confere com o manifest "
              f"({info['files']} arquivos, {info['bytes']} bytes)")
        return 0
    if not args.out:
        ap.error("--out é obrigatório (ou use --selftest/--verify)")

    manifest = generate(args.out, args.preset, args.seed)
    nominal = NOMINAL_PRESETS[args.preset]
    print(f"[{TOOL}] preset={args.preset} seed={args.seed}")
    for cat in CATEGORY_ORDER:
        c = manifest["categories"][cat]
        print(f"[{TOOL}]   {cat:<8} {c['count']:>2} arquivos "
              f"{c['bytes']:>12} bytes (nominal "
              f"{nominal[cat][0] * nominal[cat][1]})")
    print(f"[{TOOL}] total: {manifest['total_bytes']} bytes "
          f"({manifest['total_bytes'] / 1048576:.2f} MiB; nominal "
          f"{sum(c[0] * c[1] for c in nominal.values())} — folga de "
          f"cabeçalho documentada)")
    print(f"[{TOOL}] manifest: "
          f"{os.path.join(args.out, 'bulk', 'manifest.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
