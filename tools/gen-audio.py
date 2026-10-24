#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen-audio.py — Loops ambiente WAV determinísticos (5.1) — APK Tester.

Gera WAV PCM 16-bit 48000 Hz via módulo wave, com síntese em camadas por
canal: seno fundamental + harmônico com FM (modulador semeado) + ruído
branco suavizado 1-polo. Fases e frequências saem de random.Random(seed)
derivado por loop — bytes idênticos em qualquer máquina/execução.

Layouts (--channels):
  6 (padrão) .. 5.1: FL,FR,FC,LFE,BL,BR intercalados por frame; o LFE é
               restrito a 25–90 Hz pelo papel do canal;
  2 .......... estéreo FL,FR (o selftest usa este caminho);
  1 .......... mono FC; demais quantidades recebem nomes genéricos CHxx.

Modos:
  padrão ............ --loops N (8) loops de --loop-seconds s (60) cada;
  --size-budget-mb X  gera loops longos até o total de WAV >= X MiB
                      (1048576 bytes) — alimenta a engenharia de tamanho do
                      flagship (A6, gate 850–1000 MB). O número de loops é
                      fechado para cima; o excedente do último é reportado.

Custo: por canal sintetiza-se 1 s (frequências inteiras em Hz fecham o ciclo
com emenda perfeita) e o chunk é repetido até --loop-seconds — loops
ambientes são periódicos por natureza; o arquivo final é PCM completo.

Cabeçalho: 5.1 (6 canais) usa WAVE_FORMAT_EXTENSIBLE (0xFFFE) com channel
mask FL|FR|FC|LFE|BL|BR (0x3F, posições de alto-falante da Microsoft) e
SubFormat GUID KSDATAFORMAT_SUBTYPE_PCM — header manual de 68 B (RIFF 12 +
fmt 8+40 + data 8), correção da auditoria A9/roadmap 3.2: o fmt clássico de
44 B não descreve layout 5.1. Estéreo/mono seguem no PCM clássico do módulo
wave (44 B, sem máscara — layouts triviais); anotado no index.json.

Uso: python3 tools/gen-audio.py --out DIR [--channels 6] [--loops 8]
     [--loop-seconds 60] [--size-budget-mb X] [--seed 20261022] [--selftest]
"""
from __future__ import annotations

import argparse
import array
import hashlib
import json
import math
import os
import random
import shutil
import struct
import sys
import tempfile
import wave

DEFAULT_SEED = 20261022
TOOL = "gen-audio.py"
SAMPLE_RATE = 48000
MIB = 1024 * 1024
WAV_HEADER_BYTES = 44  # RIFF+fmt+data que o módulo wave grava para PCM 16-bit
WAVE_FORMAT_EXTENSIBLE = 0xFFFE
KSDATAFORMAT_SUBTYPE_PCM = bytes.fromhex("0100000000001000800000aa00389b71")
CHANNEL_MASK_5_1 = 0x0000003F  # FL|FR|FC|LFE|BL|BR (SPEAKER_* Microsoft)
EXTENSIBLE_HEADER_BYTES = 68   # RIFF 12 + fmt 8+40 (cbSize 22 + mask +
                               # SubFormat GUID) + data 8
TWO_PI = 2.0 * math.pi
LAYOUT_5_1 = ("FL", "FR", "FC", "LFE", "BL", "BR")
LAYOUT_2_0 = ("FL", "FR")
LAYOUT_1_0 = ("FC",)
ROLE_BANDS = {
    "FL": (90, 620), "FR": (95, 640), "FC": (120, 800), "LFE": (25, 90),
    "BL": (70, 460), "BR": (75, 480),
}
BAND_DEFAULT = (60, 600)


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


def channel_layout(channels: int) -> list:
    """Nomes dos canais conforme a quantidade (5.1 / estéreo / mono / genérico)."""
    if channels == 6:
        return list(LAYOUT_5_1)
    if channels == 2:
        return list(LAYOUT_2_0)
    if channels == 1:
        return list(LAYOUT_1_0)
    return [f"CH{i:02d}" for i in range(1, channels + 1)]


def channel_bands(names: list) -> list:
    """Faixa de frequência (Hz) por papel do canal; genéricos usam a padrão."""
    return [ROLE_BANDS.get(n, BAND_DEFAULT) for n in names]


# ------------------------------------------------------------------ síntese
def synth_channel(rng: random.Random, band: tuple, n: int) -> array.array:
    """Um segundo (n amostras) int16 de seno + harmônico FM + ruído, por canal.

    Frequências inteiras em Hz e fases iniciais semeadas: o chunk fecha o
    ciclo exatamente em 1 s (emenda perfeita ao repetir) e é reproduzível.
    """
    f1 = rng.randint(band[0], band[1])
    f2 = f1 * rng.choice((2, 3))
    fmod = rng.randint(1, 13)
    p1, p2, pm = (rng.uniform(0.0, TWO_PI) for _ in range(3))
    depth = rng.uniform(0.2, 2.2)
    amp2 = rng.uniform(0.15, 0.45)
    namp = rng.uniform(0.012, 0.06)
    k = TWO_PI / SAMPLE_RATE
    prev = 0.0
    noise = []
    push = noise.append
    for _ in range(n):
        prev = 0.75 * prev + 0.25 * rng.uniform(-1.0, 1.0)
        push(prev)
    out = array.array("h", bytes(2 * n))
    for i in range(n):
        v = math.sin(k * f1 * i + p1)
        v += amp2 * math.sin(k * f2 * i + p2 + depth * math.sin(k * fmod * i + pm))
        v = 0.5 * v + namp * noise[i]
        if v > 1.0:
            v = 1.0
        elif v < -1.0:
            v = -1.0
        out[i] = int(v * 32000.0)
    return out


def interleave(chunks: list) -> bytes:
    """Intercala os canais por frame (listas por canal -> PCM little-endian)."""
    n = len(chunks[0])
    stride = 2 * len(chunks)
    packer = struct.Struct("<" + "h" * len(chunks)).pack_into
    buf = bytearray(n * stride)
    off = 0
    for frame in zip(*chunks):
        packer(buf, off, *frame)
        off += stride
    return bytes(buf)


def write_wav(path: str, chunk: bytes, loop_seconds: int, channels: int) -> None:
    """Grava o WAV repetindo o chunk de 1 s em lotes (RAM limitada a ~34 MB).

    6 canais (5.1) saem com header WAVE_FORMAT_EXTENSIBLE manual (máscara de
canais + SubFormat GUID); demais seguem no PCM clássico do módulo wave.
    """
    if channels == 6:
        _write_wav_extensible(path, chunk, loop_seconds)
        return
    wf = wave.open(path, "wb")
    try:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        batches, rest = divmod(loop_seconds, 64)
        if batches:
            wf.writeframes(chunk * batches)
        if rest:
            wf.writeframes(chunk * rest)
    finally:
        wf.close()


def _write_wav_extensible(path: str, chunk: bytes, loop_seconds: int) -> None:
    """WAVE_FORMAT_EXTENSIBLE 5.1 (A9/roadmap 3.2): fmt estendido com 22 B
    extras (wValidBitsPerSample, dwChannelMask FL|FR|FC|LFE|BL|BR, SubFormat
    GUID KSDATAFORMAT_SUBTYPE_PCM) — o layout 5.1 DECLARADO no próprio
    arquivo, não só na documentação. Tamanhos fechados upfront (sem
    seek/patch): determinístico e idempotente."""
    n_data = loop_seconds * len(chunk)
    block_align = 6 * 2
    byte_rate = SAMPLE_RATE * block_align
    fmt = (struct.pack("<HHIIHHHHI", WAVE_FORMAT_EXTENSIBLE, 6, SAMPLE_RATE,
                       byte_rate, block_align, 16, 22, 16, CHANNEL_MASK_5_1)
           + KSDATAFORMAT_SUBTYPE_PCM)
    header = (b"RIFF" + struct.pack("<I", 4 + 8 + len(fmt) + 8 + n_data)
              + b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt
              + b"data" + struct.pack("<I", n_data))
    with open(path, "wb") as fh:
        fh.write(header)
        batches, rest = divmod(loop_seconds, 64)
        if batches:
            fh.write(chunk * batches)
        if rest:
            fh.write(chunk * rest)


# ----------------------------------------------------------------- geração
def generate(out_dir: str, seed: int, channels: int, loops: int,
             loop_seconds: int, budget_mb: float | None = None) -> list:
    """Gera os loops em <out>/audio/ e escreve index.json + manifest.json."""
    names = channel_layout(channels)
    bands = channel_bands(names)
    header_bytes = (EXTENSIBLE_HEADER_BYTES if channels == 6
                    else WAV_HEADER_BYTES)
    bytes_per_loop = header_bytes + loop_seconds * SAMPLE_RATE * channels * 2
    if budget_mb is not None:
        target = int(round(budget_mb * MIB))
        loops = max(1, -(-target // bytes_per_loop))  # teto: >= orçamento
    os.makedirs(os.path.join(out_dir, "audio"), exist_ok=True)
    artifacts = []
    for i in range(loops):
        rng = random.Random(seed_from(seed, f"audio:loop:{i}"))
        chunk = interleave([synth_channel(rng, b, SAMPLE_RATE) for b in bands])
        rel = f"audio/loop_{i + 1:05d}.wav"
        full = os.path.join(out_dir, rel.replace("/", os.sep))
        write_wav(full, chunk, loop_seconds, channels)
        artifacts.append({"path": rel, "bytes": os.path.getsize(full),
                          "sha256": sha256_file(full), "channels": channels,
                          "channel_roles": list(names),
                          "seconds": loop_seconds,
                          "frames": loop_seconds * SAMPLE_RATE})
    write_indexes(out_dir, seed, names, artifacts, loop_seconds, budget_mb)
    return artifacts


def write_indexes(out_dir: str, seed: int, names: list, artifacts: list,
                  loop_seconds: int, budget_mb: float | None) -> None:
    """audio/index.json (rico) + audio/manifest.json (convenção) — sem timestamps."""
    total = sum(a["bytes"] for a in artifacts)
    index = {"tool": TOOL, "seed": seed, "sample_rate": SAMPLE_RATE,
             "bit_depth": 16, "channels": len(names), "channel_layout": names,
             "loop_seconds": loop_seconds, "size_budget_mb": budget_mb,
             "total_bytes": total,
             "note": ("5.1 (6 canais) em WAVE_FORMAT_EXTENSIBLE com channel "
                      "mask FL|FR|FC|LFE|BL|BR (0x3F) e SubFormat GUID PCM "
                      "(header de 68 B); estéreo/mono em PCM clássico do módulo "
                      "wave (44 B); chunk de 1 s sintetizado (fases/frequências "
                      "semeadas) e repetido até loop_seconds — loops são "
                      "periódicos"),
             "artifacts": artifacts}
    manifest = {"tool": TOOL, "seed": seed,
                "artifacts": [{k: a[k] for k in ("path", "bytes", "sha256")}
                              for a in artifacts]}
    for fname, payload in (("index.json", index), ("manifest.json", manifest)):
        with open(os.path.join(out_dir, "audio", fname), "w",
                  encoding="utf-8", newline="\n") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")


# ----------------------------------------------------------------- selftest
def selftest() -> int:
    """1 s / 2 canais + 1 s / 6 canais (EXTENSIBLE) em /tmp: lê de volta via
    wave e valida o fmt estendido campo a campo; e determinismo 2 execuções."""
    tmp = tempfile.mkdtemp(prefix="apktester-audio-")
    try:
        probe_dir = os.path.join(tmp, "probe")
        generate(probe_dir, DEFAULT_SEED, channels=2, loops=1, loop_seconds=1)
        with wave.open(os.path.join(probe_dir, "audio", "loop_00001.wav"),
                       "rb") as wf:
            assert wf.getnchannels() == 2, \
                f"canais={wf.getnchannels()} != 2"
            assert wf.getsampwidth() == 2, "sampwidth != 16-bit"
            assert wf.getframerate() == SAMPLE_RATE, "framerate != 48000"
            assert wf.getnframes() == 1 * SAMPLE_RATE, \
                f"frames={wf.getnframes()} != {1 * SAMPLE_RATE}"

        # 5.1: WAVE_FORMAT_EXTENSIBLE — lido de volta via wave E validado
        # campo a campo no fmt estendido (A9/roadmap 3.2)
        probe51 = os.path.join(tmp, "probe51")
        generate(probe51, DEFAULT_SEED, channels=6, loops=1, loop_seconds=1)
        wav51 = os.path.join(probe51, "audio", "loop_00001.wav")
        with wave.open(wav51, "rb") as wf:
            assert wf.getnchannels() == 6, f"canais={wf.getnchannels()} != 6"
            assert wf.getsampwidth() == 2, "sampwidth != 16-bit"
            assert wf.getframerate() == SAMPLE_RATE, "framerate != 48000"
            assert wf.getnframes() == SAMPLE_RATE, "frames != 48000"
        with open(wav51, "rb") as fh:
            blob = fh.read(EXTENSIBLE_HEADER_BYTES)
        assert blob[:4] == b"RIFF" and blob[8:12] == b"WAVE", "RIFF/WAVE"
        assert blob[12:16] == b"fmt ", "sem chunk fmt"
        fmt_len = struct.unpack_from("<I", blob, 16)[0]
        assert fmt_len == 40, f"fmt de {fmt_len} B != 40 (EXTENSIBLE)"
        (tag, nch, rate, byte_rate, block_align, bits, cb_size, valid_bits,
         mask) = struct.unpack_from("<HHIIHHHHI", blob, 20)
        assert tag == WAVE_FORMAT_EXTENSIBLE, f"wFormatTag={tag:#x} != 0xFFFE"
        assert nch == 6 and rate == SAMPLE_RATE, "canais/rate divergem"
        assert byte_rate == SAMPLE_RATE * 12 and block_align == 12, \
            "byte_rate/block_align divergem (6ch x 16-bit)"
        assert bits == 16 and cb_size == 22 and valid_bits == 16, \
            "bits/cbSize/validBits divergem"
        assert mask == CHANNEL_MASK_5_1, f"channelMask={mask:#x} != 0x3F"
        sub_format = blob[20 + 24:20 + 24 + 16]
        assert sub_format == KSDATAFORMAT_SUBTYPE_PCM, \
            "SubFormat GUID != KSDATAFORMAT_SUBTYPE_PCM"
        assert blob[60:64] == b"data", "sem chunk data no offset 60"
        data_size = struct.unpack_from("<I", blob, 64)[0]
        assert data_size == SAMPLE_RATE * 12, "data size != 1 s de 5.1"
        file_size = os.path.getsize(wav51)
        assert file_size == EXTENSIBLE_HEADER_BYTES + data_size, \
            f"tamanho {file_size} != header+data"
        riff_size = struct.unpack_from("<I", blob, 4)[0]
        assert riff_size == file_size - 8, "riff size != filesize-8"

        hashes = []
        for run in ("a", "b"):
            run_dir = os.path.join(tmp, run)
            generate(run_dir, DEFAULT_SEED, channels=2, loops=2, loop_seconds=1)
            listing = []
            for root, _, names in os.walk(run_dir):
                for name in names:
                    full = os.path.join(root, name)
                    listing.append((os.path.relpath(full, run_dir)
                                    .replace(os.sep, "/"), sha256_file(full)))
            hashes.append(sorted(listing))
        assert hashes[0] == hashes[1] and hashes[0], \
            "determinismo: as duas execuções divergem"
        print(f"[gen-audio] selftest OK: 1 s/2 ch lidos via wave "
              f"({1 * SAMPLE_RATE} frames, 16-bit/48000 Hz); 5.1 "
              f"EXTENSIBLE validado campo a campo (tag 0xFFFE, máscara "
              f"0x3F, GUID PCM, blockAlign 12); {len(hashes[0])} arquivos "
              f"idênticos nas duas execuções")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------- main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Loops ambiente WAV 5.1 determinísticos (APK Tester).")
    ap.add_argument("--out", help="diretório de saída (cria <out>/audio/)")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED,
                    help=f"semente determinística (padrão: {DEFAULT_SEED})")
    ap.add_argument("--channels", type=int, default=6,
                    help="1=mono, 2=estéreo, 6=5.1 FL/FR/FC/LFE/BL/BR (padrão)")
    ap.add_argument("--loops", type=int, default=8,
                    help="quantidade de loops no modo padrão (padrão: 8)")
    ap.add_argument("--loop-seconds", type=int, default=60,
                    help="duração de cada loop em segundos (padrão: 60)")
    ap.add_argument("--size-budget-mb", type=float, default=None,
                    help="modo orçamento: loops até >= X MiB totais (ignora --loops)")
    ap.add_argument("--selftest", action="store_true",
                    help="roda auto-validação em /tmp e sai")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.out:
        ap.error("--out é obrigatório (ou use --selftest)")
    if not 1 <= args.channels <= 8:
        ap.error("--channels deve estar em [1, 8]")
    if not 1 <= args.loops <= 100000:
        ap.error("--loops deve estar em [1, 100000]")
    if not 1 <= args.loop_seconds <= 3600:
        ap.error("--loop-seconds deve estar em [1, 3600]")
    if args.size_budget_mb is not None and not 0.0 < args.size_budget_mb <= 4096.0:
        ap.error("--size-budget-mb deve estar em (0, 4096]")
    artifacts = generate(args.out, args.seed, args.channels, args.loops,
                         args.loop_seconds, args.size_budget_mb)
    total = sum(a["bytes"] for a in artifacts)
    if len(artifacts) <= 24:
        for a in artifacts:
            print(f"[gen-audio] {a['path']}: {a['channels']}ch {a['seconds']}s "
                  f"{a['bytes']} bytes sha256={a['sha256'][:12]}")
    if args.size_budget_mb is not None:
        print(f"[gen-audio] orçamento: alvo {args.size_budget_mb} MiB -> "
              f"{total / MIB:.1f} MiB em {len(artifacts)} loops "
              f"(excedente {total / MIB - args.size_budget_mb:.1f} MiB)")
    names = channel_layout(args.channels)
    print(f"[gen-audio] OK: {len(artifacts)} loops {args.channels}ch "
          f"({'+'.join(names)}) {SAMPLE_RATE} Hz 16-bit, {total} bytes em "
          f"{args.out}/audio (seed={args.seed})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
