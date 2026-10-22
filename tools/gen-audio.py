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

Cabeçalho: PCM clássico do módulo wave (não WAVE_FORMAT_EXTENSIBLE); os
parsers-alvo do fixture toleram — anotado no index.json.

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
    """Grava o WAV repetindo o chunk de 1 s em lotes (RAM limitada a ~34 MB)."""
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


# ----------------------------------------------------------------- geração
def generate(out_dir: str, seed: int, channels: int, loops: int,
             loop_seconds: int, budget_mb: float | None = None) -> list:
    """Gera os loops em <out>/audio/ e escreve index.json + manifest.json."""
    names = channel_layout(channels)
    bands = channel_bands(names)
    bytes_per_loop = WAV_HEADER_BYTES + loop_seconds * SAMPLE_RATE * channels * 2
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
             "note": ("PCM classico do modulo wave (sem WAVE_FORMAT_EXTENSIBLE); "
                      "chunk de 1 s sintetizado (fases/frequencias semeadas) e "
                      "repetido ate loop_seconds — loops sao periodicos"),
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
    """1 s / 2 canais em /tmp: lê de volta via wave; e determinismo 2 execuções."""
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
              f"({1 * SAMPLE_RATE} frames, 16-bit/48000 Hz); "
              f"{len(hashes[0])} arquivos idênticos nas duas execuções")
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
