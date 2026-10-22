#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen-arsc-stress.py — resources.arsc sintético determinístico (APK Tester).

Escreve um resources.arsc BINÁRIO compatível com aapt2 (formato ResTable do
AOSP) para a fixture huge-arsc do parser-torture: 10.000 entradas de tipo
"string" x 40 configs de locale (dense, sem config default) + 12 entradas de
tipo "integer" x 7 configs de densidade. Cada valor de string é ÚNICO no pool
global (400.000 strings semeadas) — o parser do RustyDroid tem que aguentar
tamanho e multi-locale sem OOM/timeout.

Layout binário emitido (little-endian, chunk chain do ResTable):
  RES_TABLE_TYPE (0x0002, headerSize 12, packageCount 1)
  ├─ RES_STRING_POOL_TYPE (0x0001, UTF-8) — pool global de valores
  └─ RES_TABLE_PACKAGE_TYPE (0x0200, headerSize 288, id 0x7f, nome "torture")
     ├─ pool typeStrings ["string","integer"]
     ├─ pool keyStrings (10012 chaves ordenadas: ikey_* + key_*)
     ├─ RES_TABLE_TYPE_SPEC_TYPE (0x0202, id 1) + 40 chunks RES_TABLE_TYPE_TYPE
     │  (0x0201), um por locale; cada entrada = ResTable_entry(8) + Res_value(8),
     │  dataType 0x03 (STRING) apontando para o pool global
     └─ RES_TABLE_TYPE_SPEC_TYPE (0x0202, id 2) + 7 chunks 0x0201 (densidades
        120..640), dataType 0x10 (INT_DEC)

ResTable_config de 28 bytes (layout real do AOSP: language/country são
char[2] ASCII, density u16 no offset 14). O tipo string NÃO tem config
default (40 configs de locale) e o tipo integer NÃO tem default (7 configs
de densidade) — decisão documentada em huge-arsc-audit.md.

O binário NÃO é commitado no repo: gerado no pack; o sha256 canônico fica
ancorado em arsc-report.json (e em contracts/parser-torture/, renderizado
pelo tools/gen-torture-contracts.py com o MESMO builder).

Uso:
  python3 tools/gen-arsc-stress.py --out DIR [--seed N] [--entries N]
  python3 tools/gen-arsc-stress.py --verify FILE     (re-parse + contagens)
  python3 tools/gen-arsc-stress.py --selftest
"""
from __future__ import annotations

import argparse
import array
import hashlib
import json
import os
import random
import shutil
import struct
import sys
import tempfile

DEFAULT_SEED = 20261022
TOOL = "gen-arsc-stress.py"
PACKAGE_NAME = "torture"
DEFAULT_ENTRIES = 10000
INTEGER_ENTRIES = 12
STRING_WORDS = 8
DENSITY_BUCKETS = (120, 160, 213, 240, 320, 480, 640)

# 40 locales (configs do tipo string, ordenados p/ determinismo; SEM default).
# Desvio documentado: a lista do plano tinha 39 entradas; "ca" completa o
# conjunto para fechar as 40 configs prometidas (10k x 40 = 400k valores).
LOCALES = (
    "ar", "bg", "bn", "ca", "cs", "da", "de", "el", "en", "en-US",
    "es", "es-US", "fa", "fi", "fr", "fr-CA", "he", "hi", "hr", "hu",
    "id", "it", "ja", "ko", "ms", "nb", "nl", "no", "pl", "pt-BR",
    "pt-PT", "ro", "ru", "sk", "sv", "th", "tr", "uk", "vi", "zh-CN",
)

# Palavras ASCII do conteúdo semiado das strings (sem acento: pool simples).
WORDS = (
    "apk", "droid", "parser", "binary", "chunk", "seeded", "stable",
    "fixture", "stress", "locale", "dense", "pool", "entry", "offset",
    "header", "table", "package", "config", "density", "string",
    "integer", "value", "index", "armor", "torture", "limit", "bound",
    "guard", "probe", "audit", "answer", "key", "test", "pack", "zip",
    "dex", "rust", "engine", "runtime", "floor",
)

# Constantes do formato ResTable (AOSP frameworks/base/libs/androidfw).
RES_TABLE_TYPE = 0x0002
RES_STRING_POOL_TYPE = 0x0001
RES_TABLE_PACKAGE_TYPE = 0x0200
RES_TABLE_TYPE_TYPE = 0x0201
RES_TABLE_TYPE_SPEC_TYPE = 0x0202
UTF8_FLAG = 0x100
SORTED_FLAG = 0x1
DATA_TYPE_STRING = 0x03
DATA_TYPE_INT_DEC = 0x10


# ------------------------------------------------------------------ helpers
def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def u32_array(values) -> bytes:
    """u32 little-endian em lote (array p/ não pagar struct por item)."""
    arr = array.array("I", values)
    if arr.itemsize != 4:
        raise SystemExit(f"[{TOOL}] plataforma com array.itemsize != 4")
    if sys.byteorder == "big":
        arr.byteswap()
    return arr.tobytes()


def encode_varlen(value: int) -> bytes:
    """Codificação de comprimento do pool UTF-8 do aapt2: 1 byte se <128,
    senão (value>>8)|0x80 + (value&0xFF)."""
    if value < 0x80:
        return bytes((value,))
    return bytes((0x80 | (value >> 8), value & 0xFF))


def utf8_string_pool(strings, sorted_pool: bool = False) -> bytes:
    """Chunk RES_STRING_POOL_TYPE completo (header 28 + offsets + dados)."""
    offsets = []
    data = bytearray()
    for s in strings:
        offsets.append(len(data))
        raw = s.encode("utf-8")
        data += encode_varlen(len(s))
        data += encode_varlen(len(raw))
        data += raw
        data += b"\x00"
    while len(data) % 4:
        data += b"\x00"
    strings_start = 28 + 4 * len(strings)
    flags = UTF8_FLAG | (SORTED_FLAG if sorted_pool else 0)
    header = struct.pack(
        "<HHIIIIII", RES_STRING_POOL_TYPE, 28,
        strings_start + len(data), len(strings), 0, flags, strings_start, 0)
    return header + u32_array(offsets) + bytes(data)


def config_bytes(locale: str = "", density: int = 0) -> bytes:
    """ResTable_config de 28 bytes (layout AOSP real: char[2] ASCII).

    size u32, mcc u16, mnc u16, language[2], country[2], orientation u8,
    touchscreen u8, density u16, keyboard u8, navigation u8, inputFlags u8,
    inputPad0 u8, screenWidth u16, screenHeight u16, sdkVersion u16,
    minorVersion u16.
    """
    lang, country = b"\x00\x00", b"\x00\x00"
    if locale:
        parts = locale.split("-")
        lang = parts[0].encode("ascii")[:2].ljust(2, b"\x00")
        if len(parts) > 1:
            country = parts[1].encode("ascii")[:2].ljust(2, b"\x00")
    return struct.pack("<IHH2s2sBBHBBBBHHHH", 28, 0, 0, lang, country,
                       0, 0, density, 0, 0, 0, 0, 0, 0, 0, 0)


def type_spec_chunk(type_id: int, entry_count: int) -> bytes:
    """RES_TABLE_TYPE_SPEC_TYPE: máscara de configs (tudo zero aqui)."""
    size = 16 + 4 * entry_count
    header = struct.pack("<HHIBBHI", RES_TABLE_TYPE_SPEC_TYPE, 16, size,
                         type_id, 0, 0, entry_count)
    return header + b"\x00" * (4 * entry_count)


def type_chunk(type_id: int, config: bytes, offsets, entries: bytes) -> bytes:
    """RES_TABLE_TYPE_TYPE dense: header 20 + config 28 + offsets + entradas."""
    entry_count = len(offsets)
    offsets_bytes = u32_array(offsets)
    entries_start = 20 + len(config) + len(offsets_bytes)
    size = entries_start + len(entries)
    header = struct.pack("<HHIBBHII", RES_TABLE_TYPE_TYPE, 20, size,
                         type_id, 0, 0, entry_count, entries_start)
    return header + config + offsets_bytes + entries


# ------------------------------------------------------------------ content
def value_strings(entries: int, seed: int) -> list:
    """Conteúdo único por (chave, locale): 8 palavras semeadas por string.

    Ordem do pool: locale externo, chave interna — o índice do pool da
    entrada (locale li, chave k) é li*entries + k (determinístico).
    """
    rng = random.Random(seed)
    out = []
    append = out.append
    choice = rng.choice
    for loc in LOCALES:
        for k in range(entries):
            words = " ".join(choice(WORDS) for _ in range(STRING_WORDS))
            append(f"key_{k:04d} locale {loc} valor {words}")
    return out


def integer_values(seed: int) -> list:
    """84 valores INT_DEC semeados: 12 entradas x 7 densidades, em ordem."""
    rng = random.Random(seed)
    return [rng.randint(-2 ** 31, 2 ** 31 - 1)
            for _ in range(INTEGER_ENTRIES * len(DENSITY_BUCKETS))]


def key_names(entries: int) -> list:
    """10012 chaves ordenadas (ikey_* primeiro, depois key_*)."""
    keys = [f"ikey_{i:04d}" for i in range(INTEGER_ENTRIES)]
    keys += [f"key_{k:04d}" for k in range(entries)]
    keys.sort()
    return keys


# ------------------------------------------------------------------ builder
def build_arsc(entries: int, seed: int) -> bytes:
    """Monta o resources.arsc completo em memória (bytes determinísticos)."""
    values = value_strings(entries, seed)
    global_pool = utf8_string_pool(values)
    del values
    type_pool = utf8_string_pool(["string", "integer"])
    keys = key_names(entries)
    key_pool = utf8_string_pool(keys, sorted_pool=True)
    del keys

    # Tipo 1 ("string"): spec + 40 chunks de locale, dense, sem default.
    string_chunks = bytearray()
    string_chunks += type_spec_chunk(1, entries)
    fmt = struct.Struct("<HHIHBBI").pack
    for li, loc in enumerate(LOCALES):
        entries_bytes = b"".join(
            fmt(8, 0, INTEGER_ENTRIES + k, 8, 0, DATA_TYPE_STRING,
                li * entries + k)
            for k in range(entries))
        offsets = range(0, 16 * entries, 16)
        string_chunks += type_chunk(1, config_bytes(locale=loc),
                                    offsets, entries_bytes)

    # Tipo 2 ("integer"): spec + 7 chunks de densidade, sem default.
    ivals = integer_values(seed)
    integer_chunks = bytearray()
    integer_chunks += type_spec_chunk(2, INTEGER_ENTRIES)
    for di, bucket in enumerate(DENSITY_BUCKETS):
        entries_bytes = b"".join(
            fmt(8, 0, k, 8, 0, DATA_TYPE_INT_DEC,
                ivals[k * len(DENSITY_BUCKETS) + di] & 0xFFFFFFFF)
            for k in range(INTEGER_ENTRIES))
        offsets = range(0, 16 * INTEGER_ENTRIES, 16)
        integer_chunks += type_chunk(2, config_bytes(density=bucket),
                                     offsets, entries_bytes)

    # Pacote: header 288 (id u32 0x7f + nome UTF-16LE 256B + offsets das
    # pools + lastPublicType/lastPublicKey + typeIdOffset) + chunks internos.
    name = PACKAGE_NAME.encode("utf-16-le")
    name += b"\x00" * (256 - len(name))
    body = bytes(type_pool) + bytes(key_pool) + \
        bytes(string_chunks) + bytes(integer_chunks)
    pkg_size = 288 + len(body)
    pkg = struct.pack("<HHI", RES_TABLE_PACKAGE_TYPE, 288, pkg_size)
    pkg += struct.pack("<I", 0x7F)
    pkg += name
    pkg += struct.pack("<IIIII", 288, 1, 288 + len(type_pool),
                       len(["string", "integer"]) - 1, 0)
    package = pkg + body

    filesize = 12 + len(global_pool) + len(package)
    table = struct.pack("<HHII", RES_TABLE_TYPE, 12, filesize, 1)
    return table + global_pool + package


def build_report(entries: int, seed: int, arsc: bytes) -> dict:
    """arsc-report.json — âncora de contagens + sha256 do binário canônico."""
    return {
        "schema_version": 1,
        "generated_by": f"tools/{TOOL}",
        "seed": seed,
        "package": PACKAGE_NAME,
        "entries": entries,
        "locales_count": len(LOCALES),
        "locales": list(LOCALES),
        "density_buckets": list(DENSITY_BUCKETS),
        "integer_entries": INTEGER_ENTRIES,
        "string_entries_total": entries * len(LOCALES),
        "integer_entries_total": INTEGER_ENTRIES * len(DENSITY_BUCKETS),
        "file_bytes": len(arsc),
        "sha256": sha256_bytes(arsc),
    }


def report_json(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def build_audit_md(report: dict) -> str:
    """huge-arsc-audit.md — auditoria PT-BR (mesma função usada pelos
    contratos commitados: zero drift com tools/gen-torture-contracts.py)."""
    lines = []
    add = lines.append
    add("# Huge ARSc — auditoria da fixture huge-arsc")
    add("")
    add(f"Gerado por `tools/{TOOL}` (seed {report['seed']}, stdlib-only,\n"
        "determinístico). Este documento acompanha o pacote parser-torture e\n"
        "é a answer key do resources.arsc sintético.")
    add("")
    add("## O que a fixture prova")
    add("")
    add(f"- ARSc grande e multi-locale ({report['entries']} entradas de tipo "
        f"string x {report['locales_count']} configs de locale = "
        f"{report['string_entries_total']} valores de string ÚNICOS no pool "
        "global) parseado sem OOM/timeout.")
    add(f"- Tipo integer com {report['integer_entries']} entradas x "
        f"{len(report['density_buckets'])} configs de densidade "
        f"({', '.join(str(d) for d in report['density_buckets'])} dpi) = "
        f"{report['integer_entries_total']} valores INT_DEC.")
    add("- Chunk chain ResTable íntegro: table -> pool global -> package "
        "(0x7f \"torture\") -> 2 pools internas -> 2 TypeSpec + chunks de "
        "config dense.")
    add("")
    add("## Contagens canônicas")
    add("")
    add("| campo | valor |")
    add("|---|---|")
    for field in ("package", "entries", "locales_count",
                  "string_entries_total", "integer_entries",
                  "integer_entries_total", "file_bytes"):
        add(f"| {field} | {report[field]} |")
    add(f"| sha256 | {report['sha256']} |")
    add("")
    add("## Decisão de configs (documentada)")
    add("")
    add(f"- Tipo `string`: {report['locales_count']} configs de locale, "
        "**SEM config default** — recurso sem default é válido e é exatamente "
        "o que se quer torturar aqui (o `aapt2 dump resources` mostra "
        f"{report['locales_count']} configs por chave).")
    add(f"- Tipo `integer`: {len(report['density_buckets'])} configs de "
        "densidade, **sem default**.")
    add("- A lista canônica de locales do plano tinha 39 entradas; `ca` "
        "completa o conjunto para fechar as "
        f"{report['locales_count']} configs prometidas "
        f"(10.000 x {report['locales_count']} = "
        f"{report['string_entries_total']} valores) — desvio documentado.")
    add("")
    add("## Como validar")
    add("")
    add("1. Re-parse local (gold standard): "
        "`python3 tools/gen-arsc-stress.py --verify <resources.arsc>` — sai 0 "
        "se a cadeia de chunks fecha e as contagens batem.")
    add("2. Segunda opinião no CI: `aapt2 dump resources <apk>` deve listar "
        f"{report['locales_count']} configs por chave de string e "
        f"{len(report['density_buckets'])} por chave integer.")
    add("3. O sha256 acima deve bater com `arsc-report.json` "
        "(contracts/parser-torture/) — âncora do binário.")
    add("")
    add("## Binário não commitado")
    add("")
    add("O resources.arsc é gerado no pack (o fixture-pack remove o arsc do "
        "aapt2 e anexa este no lugar). O binário NÃO vai para o git — o "
        "sha256 canônico em `arsc-report.json` é a âncora de integridade.")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ verify
def _read_varlen(data: bytes, pos: int) -> tuple:
    b0 = data[pos]
    if b0 & 0x80:
        return ((b0 & 0x7F) << 8) | data[pos + 1], pos + 2
    return b0, pos + 1


def _parse_string_pool(data: bytes, off: int, what: str) -> tuple:
    if off + 28 > len(data):
        raise ValueError(f"{what}: pool truncada em {off}")
    ctype, hsize, size, count, style_count, flags, strings_start, _ss = \
        struct.unpack_from("<HHIIIIII", data, off)
    if ctype != RES_STRING_POOL_TYPE:
        raise ValueError(f"{what}: tipo {ctype:#06x} != pool")
    if hsize != 28 or style_count != 0:
        raise ValueError(f"{what}: headerSize {hsize} / styles {style_count}")
    if off + size > len(data):
        raise ValueError(f"{what}: size {size} estoura o arquivo")
    if not flags & UTF8_FLAG:
        raise ValueError(f"{what}: esperado pool UTF-8 (flags {flags:#x})")
    offsets = array.array("I")
    offsets.frombytes(data[off + hsize:off + hsize + 4 * count])
    if sys.byteorder == "big":
        offsets.byteswap()
    strings = []
    base = off + strings_start
    for o in offsets:
        p = base + o
        u16len, p = _read_varlen(data, p)
        u8len, p = _read_varlen(data, p)
        raw = data[p:p + u8len]
        if len(raw) != u8len:
            raise ValueError(f"{what}: string truncada")
        s = raw.decode("utf-8")
        if len(s) != u16len:
            raise ValueError(f"{what}: u16len {u16len} != {len(s)} chars")
        strings.append(s)
    return strings, size


def _config_locale(config: bytes) -> str:
    lang = config[8:10].decode("ascii", "replace").rstrip("\x00")
    country = config[10:12].decode("ascii", "replace").rstrip("\x00")
    if not lang:
        return "default"
    return f"{lang}-{country}" if country else lang


def _config_density(config: bytes) -> int:
    return struct.unpack_from("<H", config, 14)[0]


def verify_arsc(data: bytes) -> dict:
    """Re-parse estrito do resources.arsc: valida a cadeia de chunks, os
    campos de tamanho e conta entradas por config. Levanta ValueError em
    qualquer inconsistência (o --verify converte em exit 1)."""
    if len(data) < 12:
        raise ValueError("arquivo menor que o header da tabela")
    ctype, hsize, size, package_count = struct.unpack_from("<HHII", data, 0)
    if ctype != RES_TABLE_TYPE or hsize != 12:
        raise ValueError(f"header da tabela inválido (type {ctype:#06x}, "
                         f"headerSize {hsize})")
    if size != len(data):
        raise ValueError(f"tabela declara size {size}, arquivo tem "
                         f"{len(data)}")
    if package_count != 1:
        raise ValueError(f"packageCount {package_count} != 1")

    global_strings, pool_size = _parse_string_pool(data, 12, "pool global")
    pos = 12 + pool_size
    if pos >= len(data):
        raise ValueError("pool global consome o arquivo inteiro")

    ptype, phsize, psize = struct.unpack_from("<HHI", data, pos)
    if ptype != RES_TABLE_PACKAGE_TYPE or phsize != 288:
        raise ValueError(f"pacote inválido (type {ptype:#06x}, "
                         f"headerSize {phsize})")
    if pos + psize != len(data):
        raise ValueError(f"pacote declara size {psize}; restam "
                         f"{len(data) - pos}")
    pkg_id = struct.unpack_from("<I", data, pos + 8)[0]
    raw_name = data[pos + 12:pos + 268]
    pkg_name = raw_name.decode("utf-16-le").rstrip("\x00")
    type_strings_off, last_public_type, key_strings_off, last_public_key, \
        _type_id_offset = struct.unpack_from("<IIIII", data, pos + 268)
    if pkg_id != 0x7F:
        raise ValueError(f"id do pacote {pkg_id:#x} != 0x7f")

    type_names, tsize = _parse_string_pool(data, pos + type_strings_off,
                                           "typeStrings")
    key_names_p, ksize = _parse_string_pool(data, pos + key_strings_off,
                                            "keyStrings")

    types = {}
    inner = pos + 288
    expect_type_pool = True
    while inner < pos + psize:
        itype, ihsize, isize = struct.unpack_from("<HHI", data, inner)
        if inner + isize > pos + psize:
            raise ValueError(f"chunk {itype:#06x} estoura o pacote")
        if itype == RES_STRING_POOL_TYPE:
            # typeStrings/keyStrings já parseadas via offsets do header;
            # aqui só conferimos que ficam exatamente onde o header aponta.
            if inner not in (pos + type_strings_off, pos + key_strings_off):
                raise ValueError("pool interna em posição inesperada")
        elif itype == RES_TABLE_TYPE_SPEC_TYPE:
            _tid, _res0, _res1, entry_count = struct.unpack_from("<BBHI",
                                                                 data,
                                                                 inner + 8)
            if isize != 16 + 4 * entry_count:
                raise ValueError(f"TypeSpec declara size {isize}, esperado "
                                 f"{16 + 4 * entry_count}")
            mask = data[inner + 16:inner + isize]
            if any(mask):
                raise ValueError("TypeSpec com máscara não zero")
        elif itype == RES_TABLE_TYPE_TYPE:
            tid, flags, _reserved, entry_count, entries_start = \
                struct.unpack_from("<BBHII", data, inner + 8)
            if flags != 0:
                raise ValueError(f"Type flags {flags:#x} != 0 (dense)")
            config = data[inner + 20:inner + 48]
            if len(config) != 28 or struct.unpack_from("<I", config, 0)[0] != 28:
                raise ValueError("ResTable_config != 28 bytes")
            offsets = array.array("I")
            offsets.frombytes(data[inner + 48:inner + 48 + 4 * entry_count])
            if sys.byteorder == "big":
                offsets.byteswap()
            if entries_start != 20 + 28 + 4 * entry_count:
                raise ValueError(f"entriesStart {entries_start} != layout "
                                 "dense esperado")
            locale = _config_locale(config)
            density = _config_density(config)
            acc = types.setdefault(tid, {"configs": [], "entries_total": 0})
            acc["configs"].append({"locale": locale, "density": density,
                                   "entries": entry_count})
            for i in range(entry_count):
                e = inner + entries_start + offsets[i]
                esize, eflags, key_idx = struct.unpack_from("<HHI", data, e)
                if esize != 8 or eflags != 0:
                    raise ValueError(f"entrada {i}: size {esize} flags "
                                     f"{eflags}")
                if key_idx >= len(key_names_p):
                    raise ValueError(f"keyIdx {key_idx} fora do pool")
                vsize, res0, dtype, dvalue = struct.unpack_from("<HBBI",
                                                                data, e + 8)
                if vsize != 8 or res0 != 0:
                    raise ValueError(f"Res_value inválido na entrada {i}")
                if dtype == DATA_TYPE_STRING and dvalue >= len(global_strings):
                    raise ValueError(f"índice de string {dvalue} fora do pool")
                acc["entries_total"] += 1
        else:
            raise ValueError(f"chunk interno inesperado {itype:#06x}")
        inner += isize
    if inner != pos + psize:
        raise ValueError("cadeia de chunks do pacote não fecha exata")

    locales = sorted({c["locale"] for c in types.get(1, {}).get("configs", [])
                      if c["locale"] != "default"})
    densities = sorted({c["density"] for c in types.get(2, {}).get("configs",
                                                                    [])
                        if c["density"]})
    return {
        "tool": TOOL,
        "mode": "verify",
        "structure_ok": True,
        "file_bytes": len(data),
        "sha256": sha256_bytes(data),
        "package": pkg_name,
        "package_id": pkg_id,
        "global_strings": len(global_strings),
        "keys_total": len(key_names_p),
        "last_public_type": last_public_type,
        "last_public_key": last_public_key,
        "type_strings": type_names,
        "types": [
            {"id": tid,
             "name": (type_names[tid - 1] if 0 < tid <= len(type_names)
                      else f"type{tid}"),
             "configs": len(types[tid]["configs"]),
             "entries_total": types[tid]["entries_total"]}
            for tid in sorted(types)
        ],
        "locales": locales,
        "locales_count": len(locales),
        "density_buckets": densities,
    }


# ------------------------------------------------------------------ output
def generate(out_dir: str, entries: int, seed: int) -> dict:
    """Gera resources.arsc + arsc-report.json + huge-arsc-audit.md +
    manifest.json (convenção de ledger do repo) em out_dir."""
    arsc = build_arsc(entries, seed)
    report = build_report(entries, seed, arsc)
    outputs = {
        "resources.arsc": arsc,
        "arsc-report.json": report_json(report).encode("utf-8"),
        "huge-arsc-audit.md": build_audit_md(report).encode("utf-8"),
    }
    artifacts = []
    for rel in sorted(outputs):
        full = os.path.join(out_dir, rel)
        os.makedirs(out_dir, exist_ok=True)
        with open(full, "wb") as fh:
            fh.write(outputs[rel])
        artifacts.append({"path": rel, "bytes": len(outputs[rel]),
                          "sha256": sha256_bytes(outputs[rel])})
    ledger = {"tool": f"tools/{TOOL}", "seed": seed, "entries": entries,
              "note": "gerado; NAO editar a mao — regenere com a ferramenta",
              "artifacts": artifacts}
    with open(os.path.join(out_dir, "manifest.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(ledger, ensure_ascii=False, indent=2,
                            sort_keys=True) + "\n")
    return report


def selftest() -> int:
    """Duas gerações byte-idênticas + verify estrutural + corrupção detectada."""
    tmp = tempfile.mkdtemp(prefix="apktester-arsc-")
    try:
        out_a, out_b = os.path.join(tmp, "a"), os.path.join(tmp, "b")
        report_a = generate(out_a, DEFAULT_ENTRIES, DEFAULT_SEED)
        report_b = generate(out_b, DEFAULT_ENTRIES, DEFAULT_SEED)
        for rel in ("resources.arsc", "arsc-report.json", "huge-arsc-audit.md",
                    "manifest.json"):
            with open(os.path.join(out_a, rel), "rb") as fh:
                a = fh.read()
            with open(os.path.join(out_b, rel), "rb") as fh:
                b = fh.read()
            assert a == b, f"determinismo quebrado em {rel}"
        with open(os.path.join(out_a, "resources.arsc"), "rb") as fh:
            arsc = fh.read()
        counts = verify_arsc(arsc)
        assert counts["file_bytes"] == report_a["file_bytes"], "file_bytes diverge"
        assert counts["sha256"] == report_a["sha256"], "sha256 diverge"
        by_name = {t["name"]: t for t in counts["types"]}
        assert by_name["string"]["configs"] == report_a["locales_count"], \
            "configs de string divergem"
        assert by_name["string"]["entries_total"] == \
            report_a["string_entries_total"], "entradas de string divergem"
        assert by_name["integer"]["configs"] == \
            len(report_a["density_buckets"]), "configs de densidade divergem"
        assert by_name["integer"]["entries_total"] == \
            report_a["integer_entries_total"], "entradas integer divergem"
        assert counts["keys_total"] == report_a["entries"] + \
            INTEGER_ENTRIES, "chaves divergem"
        assert counts["locales_count"] == report_a["locales_count"], \
            "locales divergem"
        # Corrupção: aumentar o size do pacote tem que derrubar o verify.
        corrupt = bytearray(arsc)
        pool_size = struct.unpack_from("<I", arsc, 16)[0]  # size da pool global
        pkg_off = 12 + pool_size
        old = struct.unpack_from("<I", corrupt, pkg_off + 4)[0]
        struct.pack_into("<I", corrupt, pkg_off + 4, old + 16)
        try:
            verify_arsc(bytes(corrupt))
            raise AssertionError("verify aceitou arquivo corrompido")
        except ValueError:
            pass
        print(f"[{TOOL}] selftest OK: 2 gerações byte-idênticas "
              f"({report_a['file_bytes']} bytes), verify estrutural OK "
              f"({report_a['string_entries_total']} strings + "
              f"{report_a['integer_entries_total']} integers), corrupção "
              "detectada")
        return 0
    except AssertionError as exc:
        print(f"[{TOOL}] selftest FALHOU: {exc}", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="resources.arsc sintético determinístico (APK Tester).")
    ap.add_argument("--out", help="diretório de saída (resources.arsc + "
                                  "arsc-report.json + huge-arsc-audit.md)")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED,
                    help=f"semente determinística (padrão: {DEFAULT_SEED})")
    ap.add_argument("--entries", type=int, default=DEFAULT_ENTRIES,
                    help=f"entradas do tipo string (padrão: {DEFAULT_ENTRIES})")
    ap.add_argument("--verify", metavar="FILE",
                    help="re-parseia um resources.arsc e imprime contagens")
    ap.add_argument("--selftest", action="store_true",
                    help="auto-validação em tmp (determinismo + verify) e sai")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.verify:
        try:
            with open(args.verify, "rb") as fh:
                counts = verify_arsc(fh.read())
        except (OSError, ValueError) as exc:
            print(f"[{TOOL}] verify FALHOU: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(counts, ensure_ascii=False, indent=2,
                         sort_keys=True))
        return 0
    if not args.out:
        ap.error("--out é obrigatório (ou use --selftest/--verify)")
    if not 1 <= args.entries <= 100000:
        ap.error("--entries fora da faixa [1, 100000]")
    report = generate(args.out, args.entries, args.seed)
    print(f"[{TOOL}] resources.arsc: {report['entries']} entradas x "
          f"{report['locales_count']} locales = "
          f"{report['string_entries_total']} strings únicas + "
          f"{report['integer_entries_total']} integers em "
          f"{report['file_bytes']} bytes (sha256 {report['sha256'][:12]}…)")
    print(f"[{TOOL}] OK: resources.arsc + arsc-report.json + "
          f"huge-arsc-audit.md + manifest.json em {args.out} "
          f"(seed={args.seed})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
