#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen-meshes.py — Gerador determinístico de malhas 3D do APK Tester.

Gera, sob <out>/mesh/, os ativos 3D procedurais do flagship "Behemoth":

  * teapot.obj / teapot.ply ..... bule de revolução (~8k triângulos). O perfil
    2D (raio, altura) vem de uma spline Catmull-Rom sobre pontos de controle
    com jitter determinístico; a superfície é a revolução do perfil em torno
    do eixo Y, com tampa inferior em leque.
  * terrain_1024.obj ............ grade 1024x1024 de heightmap (value-noise
    fbm semeado), ~2M triângulos, escrita linha a linha (memória controlada).
  * terrain_1024.glb ............ o mesmo terreno em contêiner GLB binário
    (glTF 2.0: chunk JSON + chunk BIN, POSITION + índices uint32).
  * crowd_50k.gltf .............. 50.000 humanoides low-poly instanciados via
    nós glTF (uma malha base compartilhada + translation/rotation/scale
    semeados por instância) — instancing de verdade, sem duplicar geometria.
  * index.json / manifest.json .. sha256 + metadados por artefato.

Somente stdlib; nenhum timestamp nos artefatos (determinismo byte a byte).
Uso: python3 tools/gen-meshes.py --out DIR [--seed N] [--selftest]
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import random
import shutil
import struct
import sys
import tempfile
from array import array

DEFAULT_SEED = 20261022
TOOL = "gen-meshes.py"
CROWD_COLUMNS = 224  # grade X do público (224 x 224 >= 50000 assentos)


# ---------------------------------------------------------------- utilidades
def seed_from(base: int, label: str) -> int:
    """Sub-semente estável derivada de (base, rótulo) via SHA-256."""
    digest = hashlib.sha256(f"{base}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "little")


def sha256_file(path: str) -> str:
    """SHA-256 em streaming (artefatos podem ter centenas de MB)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------- value-noise 2D
def make_perm(rng: random.Random) -> list:
    """Tabela de permutação (512 entradas) para o value-noise estilo Perlin."""
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
    """fbm em [0,1); coords normalizadas => campo independente da resolução."""
    value, amp, freq, norm = 0.0, 1.0, 4.0, 0.0
    for _ in range(octaves):
        value += amp * vnoise(perm, x01 * freq, y01 * freq)
        norm += amp
        amp *= 0.5
        freq *= 2.0
    return value / norm


# ------------------------------------------------------------------- teapot
TEAPOT_CTRL = [  # silhueta (raio, altura) do bule de revolução
    (0.90, 0.00), (1.30, 0.30), (1.16, 0.55), (0.98, 0.78),
    (0.86, 0.94), (0.52, 1.02), (0.40, 1.06), (0.30, 1.14), (0.00, 1.20),
]


def catmull_rom(points, samples_per_seg):
    """Amostra spline Catmull-Rom (extremidades com clamp de vizinhança)."""
    out = []
    n = len(points)
    for i in range(n - 1):
        p0 = points[max(i - 1, 0)]
        p1 = points[i]
        p2 = points[i + 1]
        p3 = points[min(i + 2, n - 1)]
        for s in range(samples_per_seg):
            t = s / samples_per_seg
            t2, t3 = t * t, t * t * t
            out.append(tuple(
                0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t +
                       (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2 +
                       (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3)
                for k in (0, 1)))
    out.append(points[-1])
    return out


def teapot_profile(seed: int, samples_per_seg: int):
    """Perfil final com jitter determinístico e pontas exatas do bule."""
    rng = random.Random(seed_from(seed, "teapot-profile"))
    pts = []
    for i, (r, h) in enumerate(TEAPOT_CTRL):
        if 0 < i < len(TEAPOT_CTRL) - 1:
            r += rng.uniform(-0.035, 0.035)
            h += rng.uniform(-0.02, 0.02)
        pts.append((r, h))
    pts[0] = (0.90, 0.0)
    pts[-1] = (0.0, pts[-1][1])
    return catmull_rom(pts, samples_per_seg)


def write_teapot_obj(path: str, profile, radial: int):
    """OBJ com v/vn e faces trianguladas; retorna (verts, tris)."""
    n = len(profile)

    def vid(i, j):
        return i * radial + (j % radial) + 1

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("# APK Tester — teapot determinístico (gen-meshes.py)\n")
        f.write(f"# profile={n} radial={radial}\n")
        for i, (r, h) in enumerate(profile):
            for j in range(radial):
                th = 2.0 * math.pi * j / radial
                f.write(f"v {r * math.cos(th):.5f} {h:.5f} {r * math.sin(th):.5f}\n")
        center = n * radial + 1
        f.write("v 0.00000 0.00000 0.00000\n")
        for i in range(n):  # normais analíticas da superfície de revolução
            pr, ph = profile[max(i - 1, 0)]
            nr, nh = profile[min(i + 1, n - 1)]
            dr, dh = nr - pr, nh - ph
            if dr == 0.0 and dh == 0.0:
                dh = 1.0
            for j in range(radial):
                th = 2.0 * math.pi * j / radial
                nx, ny, nz = dh * math.cos(th), -dr, dh * math.sin(th)
                ln = math.sqrt(nx * nx + ny * ny + nz * nz)
                if ln < 1e-12:
                    nx, ny, nz = 0.0, 1.0, 0.0
                else:
                    nx, ny, nz = nx / ln, ny / ln, nz / ln
                f.write(f"vn {nx:.5f} {ny:.5f} {nz:.5f}\n")
        vn_center = n * radial + 1
        f.write("vn 0.00000 -1.00000 0.00000\n")
        for i in range(n - 1):
            for j in range(radial):
                a, b = vid(i, j), vid(i + 1, j)
                c, d = vid(i + 1, j + 1), vid(i, j + 1)
                f.write(f"f {a}//{a} {b}//{b} {c}//{c}\n")
                f.write(f"f {a}//{a} {c}//{c} {d}//{d}\n")
        for j in range(radial):  # tampa inferior em leque
            f.write(f"f {center}//{vn_center} {vid(0, j)}//{vn_center} {vid(0, j + 1)}//{vn_center}\n")
    return center, 2 * (n - 1) * radial + radial


def write_teapot_ply(path: str, profile, radial: int):
    """PLY ASCII do mesmo bule (0-based); retorna (verts, tris)."""
    n = len(profile)
    verts = []
    for (r, h) in profile:
        for j in range(radial):
            th = 2.0 * math.pi * j / radial
            verts.append((r * math.cos(th), h, r * math.sin(th)))
    verts.append((0.0, 0.0, 0.0))

    def vid(i, j):
        return i * radial + (j % radial)

    tris = []
    for i in range(n - 1):
        for j in range(radial):
            a, b = vid(i, j), vid(i + 1, j)
            c, d = vid(i + 1, j + 1), vid(i, j + 1)
            tris.append((a, b, c))
            tris.append((a, c, d))
    center = n * radial
    for j in range(radial):
        tris.append((center, vid(0, j), vid(0, j + 1)))
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("ply\nformat ascii 1.0\ncomment APK Tester gen-meshes.py teapot\n")
        f.write(f"element vertex {len(verts)}\n")
        f.write("property float x\nproperty float y\nproperty float z\n")
        f.write(f"element face {len(tris)}\nproperty list uchar int vertex_indices\nend_header\n")
        for (x, y, z) in verts:
            f.write(f"{x:.5f} {y:.5f} {z:.5f}\n")
        for (a, b, c) in tris:
            f.write(f"3 {a} {b} {c}\n")
    return len(verts), len(tris)


# ------------------------------------------------------------------ terreno
def build_height_grid(res: int, perm: list) -> array:
    """Heightmap res x res (array 'f') via fbm determinístico."""
    grid = array("f", bytes(4 * res * res))
    inv = 1.0 / res
    for y in range(res):
        y01 = y * inv
        row = y * res
        for x in range(res):
            grid[row + x] = fbm(perm, x * inv, y01)
    return grid


def write_terrain_obj(path: str, res: int, grid: array):
    """OBJ do terreno escrito linha a linha; retorna (verts, tris)."""
    inv = 1.0 / (res - 1) if res > 1 else 1.0
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# APK Tester — terreno {res}x{res} (value-noise determinístico)\n")
        for y in range(res):
            base = y * res
            z = y * inv
            for x in range(res):
                f.write(f"v {x * inv:.5f} {grid[base + x] * 0.35:.5f} {z:.5f}\n")
        for y in range(res - 1):
            r0, r1 = y * res, (y + 1) * res
            for x in range(res - 1):
                a, b = r0 + x + 1, r0 + x + 2
                c, d = r1 + x + 1, r1 + x + 2
                f.write(f"f {a} {c} {d}\n")
                f.write(f"f {a} {d} {b}\n")
    return res * res, 2 * (res - 1) * (res - 1)


def write_terrain_glb(path: str, res: int, grid: array):
    """GLB binário (glTF 2.0): chunk JSON + chunk BIN; retorna (verts, tris)."""
    inv = 1.0 / (res - 1) if res > 1 else 1.0
    pos = array("f")
    lo = [float("inf")] * 3
    hi = [-float("inf")] * 3
    for y in range(res):
        z = y * inv
        base = y * res
        for x in range(res):
            p = (x * inv, grid[base + x] * 0.35, z)
            pos += array("f", p)
            for k in range(3):
                if p[k] < lo[k]:
                    lo[k] = p[k]
                if p[k] > hi[k]:
                    hi[k] = p[k]
    idx = array("I")
    for y in range(res - 1):
        r0, r1 = y * res, (y + 1) * res
        for x in range(res - 1):
            a, b = r0 + x, r0 + x + 1
            c, d = r1 + x, r1 + x + 1
            idx.append(a)
            idx.append(c)
            idx.append(d)
            idx.append(a)
            idx.append(d)
            idx.append(b)
    if sys.byteorder != "little":
        pos.byteswap()
        idx.byteswap()
    pos_len = pos.itemsize * len(pos)
    bin_data = pos.tobytes() + idx.tobytes()
    gltf = {
        "asset": {"version": "2.0", "generator": "apk-tester gen-meshes.py"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": f"terrain_{res}"}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1, "mode": 4}]}],
        "buffers": [{"byteLength": len(bin_data)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": pos_len, "target": 34962},
            {"buffer": 0, "byteOffset": pos_len, "byteLength": len(bin_data) - pos_len,
             "target": 34963},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": res * res, "type": "VEC3",
             "min": [round(v, 5) for v in lo], "max": [round(v, 5) for v in hi]},
            {"bufferView": 1, "componentType": 5125, "count": len(idx), "type": "SCALAR"},
        ],
    }
    js = json.dumps(gltf, sort_keys=True, separators=(",", ":")).encode("utf-8")
    js += b" " * ((-len(js)) % 4)
    bin_data += b"\0" * ((-len(bin_data)) % 4)
    total = 12 + 8 + len(js) + 8 + len(bin_data)
    with open(path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, total))
        f.write(struct.pack("<I4s", len(js), b"JSON"))
        f.write(js)
        f.write(struct.pack("<I4s", len(bin_data), b"BIN\0"))
        f.write(bin_data)
    return res * res, len(idx) // 3


# --------------------------------------------------------------- crowd 50k
def _box(positions: list, indices: list, cx, cy, cz, hx, hy, hz):
    """Adiciona um caixo eixo-alinhado (8 vértices, 12 triângulos)."""
    base = len(positions) // 3
    for sy in (-1, 1):
        for sz in (-1, 1):
            for sx in (-1, 1):
                positions += [cx + sx * hx, cy + sy * hy, cz + sz * hz]
    faces = [
        (0, 1, 5), (0, 5, 4), (2, 7, 3), (2, 6, 7),  # ±X
        (0, 2, 3), (0, 3, 1), (4, 5, 7), (4, 7, 6),  # ±Y
        (0, 4, 6), (0, 6, 2), (1, 3, 7), (1, 7, 5),  # ±Z
    ]
    for (a, b, c) in faces:
        indices += [base + a, base + b, base + c]


def humanoid_base():
    """Malha base do humanoide low-poly: 6 caixos => 48 verts / 72 tris."""
    positions, indices = [], []
    _box(positions, indices, 0.00, 1.62, 0.00, 0.13, 0.15, 0.13)   # cabeça
    _box(positions, indices, 0.00, 1.20, 0.00, 0.22, 0.28, 0.13)   # torso
    _box(positions, indices, -0.34, 1.16, 0.00, 0.07, 0.26, 0.07)  # braço E
    _box(positions, indices, 0.34, 1.16, 0.00, 0.07, 0.26, 0.07)   # braço D
    _box(positions, indices, -0.12, 0.44, 0.00, 0.09, 0.42, 0.09)  # perna E
    _box(positions, indices, 0.12, 0.44, 0.00, 0.09, 0.42, 0.09)   # perna D
    return positions, indices


def write_crowd_gltf(path: str, count: int, seed: int):
    """glTF JSON com 1 malha base (buffer base64) + count nós instanciados."""
    rng = random.Random(seed_from(seed, "crowd"))
    positions, indices = humanoid_base()
    pos_bytes = array("f", positions).tobytes()
    blob = pos_bytes + array("I", indices).tobytes()
    lo = [min(positions[k::3]) for k in range(3)]
    hi = [max(positions[k::3]) for k in range(3)]
    uri = base64.b64encode(blob).decode("ascii")
    nodes = []
    for i in range(count):
        col, row = i % CROWD_COLUMNS, i // CROWD_COLUMNS
        yaw = rng.uniform(0.0, 2.0 * math.pi)
        s = rng.uniform(0.85, 1.15)
        nodes.append({
            "name": f"crowd_{i:05d}",
            "mesh": 0,
            "translation": [round(col * 1.15 + rng.uniform(-0.25, 0.25), 4), 0.0,
                            round(row * 1.15 + rng.uniform(-0.25, 0.25), 4)],
            "rotation": [0.0, round(math.sin(yaw / 2.0), 6), 0.0,
                         round(math.cos(yaw / 2.0), 6)],
            "scale": [round(s, 4), round(s, 4), round(s, 4)],
        })
    gltf = {
        "asset": {"version": "2.0", "generator": "apk-tester gen-meshes.py"},
        "scene": 0,
        "scenes": [{"nodes": list(range(count))}],
        "nodes": nodes,
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1, "mode": 4}]}],
        "buffers": [{"byteLength": len(blob),
                     "uri": f"data:application/octet-stream;base64,{uri}"}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(pos_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": len(pos_bytes), "byteLength": len(blob) - len(pos_bytes),
             "target": 34963},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": len(positions) // 3,
             "type": "VEC3", "min": lo, "max": hi},
            {"bufferView": 1, "componentType": 5125, "count": len(indices), "type": "SCALAR"},
        ],
    }
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(gltf, f, sort_keys=True, separators=(",", ":"))
    return count, len(indices) // 3


# ------------------------------------------------------------------- saída
def write_indexes(mesh_dir: str, seed: int, artifacts: list):
    """index.json (rico) + manifest.json (convenção do repo) — sem timestamps."""
    index = {"tool": TOOL, "seed": seed, "artifacts": artifacts}
    manifest = {"tool": TOOL, "seed": seed,
                "artifacts": [{k: a[k] for k in ("path", "bytes", "sha256")}
                              for a in artifacts]}
    for name, payload in (("index.json", index), ("manifest.json", manifest)):
        with open(os.path.join(mesh_dir, name), "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.write("\n")


def generate(out_dir: str, seed: int, terrain_res: int, crowd: int,
             profile_samples: int, radial: int) -> list:
    """Gera todos os artefatos em <out>/mesh/ e devolve a lista de metadados."""
    mesh_dir = os.path.join(out_dir, "mesh")
    os.makedirs(mesh_dir, exist_ok=True)
    artifacts = []

    def record(path, kind, verts=None, tris=None):
        entry = {"path": os.path.relpath(path, out_dir).replace(os.sep, "/"),
                 "bytes": os.path.getsize(path), "sha256": sha256_file(path),
                 "kind": kind}
        if verts is not None:
            entry["vertices"] = verts
        if tris is not None:
            entry["triangles"] = tris
        artifacts.append(entry)

    profile = teapot_profile(seed, profile_samples)
    v, t = write_teapot_obj(os.path.join(mesh_dir, "teapot.obj"), profile, radial)
    record(os.path.join(mesh_dir, "teapot.obj"), "obj", v, t)
    v, t = write_teapot_ply(os.path.join(mesh_dir, "teapot.ply"), profile, radial)
    record(os.path.join(mesh_dir, "teapot.ply"), "ply", v, t)

    perm = make_perm(random.Random(seed_from(seed, "terrain-noise")))
    grid = build_height_grid(terrain_res, perm)
    v, t = write_terrain_obj(os.path.join(mesh_dir, f"terrain_{terrain_res}.obj"),
                             terrain_res, grid)
    record(os.path.join(mesh_dir, f"terrain_{terrain_res}.obj"), "obj", v, t)
    v, t = write_terrain_glb(os.path.join(mesh_dir, f"terrain_{terrain_res}.glb"),
                             terrain_res, grid)
    record(os.path.join(mesh_dir, f"terrain_{terrain_res}.glb"), "glb", v, t)

    v, t = write_crowd_gltf(os.path.join(mesh_dir, f"crowd_{crowd}.gltf"), crowd, seed)
    record(os.path.join(mesh_dir, f"crowd_{crowd}.gltf"), "gltf", v, t)

    write_indexes(mesh_dir, seed, artifacts)
    return artifacts


def selftest() -> int:
    """Gera em /tmp com parâmetros reduzidos e valida contagens lendo de volta."""
    tmp = tempfile.mkdtemp(prefix="apktester-meshes-")
    try:
        artifacts = generate(tmp, DEFAULT_SEED, terrain_res=24, crowd=96,
                             profile_samples=7, radial=32)
        by = {os.path.basename(a["path"]): a for a in artifacts}
        v = f = 0
        with open(os.path.join(tmp, "mesh", "teapot.obj"), encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("v "):
                    v += 1
                elif line.startswith("f "):
                    f += 1
        assert v == by["teapot.obj"]["vertices"], \
            f"teapot.obj: {v} verts lidos != {by['teapot.obj']['vertices']} esperados"
        assert f == by["teapot.obj"]["triangles"], \
            f"teapot.obj: {f} faces lidas != {by['teapot.obj']['triangles']} esperadas"
        v = f = 0
        with open(os.path.join(tmp, "mesh", "terrain_24.obj"), encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("v "):
                    v += 1
                elif line.startswith("f "):
                    f += 1
        assert v == 24 * 24 and f == 2 * 23 * 23, f"terreno: v={v} f={f} inesperados"
        with open(os.path.join(tmp, "mesh", "terrain_24.glb"), "rb") as fh:
            blob = fh.read()
        assert blob[:4] == b"glTF" and struct.unpack_from("<I", blob, 4)[0] == 2, \
            "GLB: magic/versão inválidos"
        total_len = struct.unpack_from("<I", blob, 8)[0]
        assert total_len == len(blob), "GLB: comprimento total divergente"
        js_len = struct.unpack_from("<I", blob, 12)[0]
        gltf = json.loads(blob[20:20 + js_len].decode("utf-8"))
        assert gltf["accessors"][0]["count"] == 24 * 24, "GLB: contagem POSITION"
        with open(os.path.join(tmp, "mesh", "crowd_96.gltf"), encoding="utf-8") as fh:
            crowd = json.load(fh)
        assert len(crowd["nodes"]) == 96 and crowd["scenes"][0]["nodes"][-1] == 95, \
            "crowd: nós instanciados divergem"
        print(f"[gen-meshes] selftest OK: {len(artifacts)} artefatos validados "
              f"(teapot/terreno GLB/crowd re-lidos e conferidos)")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Gerador determinístico de malhas 3D (OBJ/PLY/glTF) do APK Tester.")
    ap.add_argument("--out", help="diretório de saída (cria <out>/mesh/)")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED,
                    help=f"semente determinística (padrão: {DEFAULT_SEED})")
    ap.add_argument("--terrain-res", type=int, default=1024,
                    help="lado da grade do terreno (padrão: 1024)")
    ap.add_argument("--crowd", type=int, default=50000,
                    help="número de humanoides instanciados (padrão: 50000)")
    ap.add_argument("--profile-samples", type=int, default=7,
                    help="amostras por segmento do perfil do bule (padrão: 7)")
    ap.add_argument("--radial", type=int, default=64,
                    help="segmentos radiais da revolução (padrão: 64)")
    ap.add_argument("--selftest", action="store_true",
                    help="roda auto-validação em /tmp e sai")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.out:
        ap.error("--out é obrigatório (ou use --selftest)")
    if not 8 <= args.terrain_res <= 4096:
        ap.error("--terrain-res deve estar em [8, 4096]")
    if not 1 <= args.crowd <= 100000:
        ap.error("--crowd deve estar em [1, 100000]")
    if not 3 <= args.profile_samples <= 64 or not 8 <= args.radial <= 512:
        ap.error("--profile-samples deve estar em [3,64] e --radial em [8,512]")
    artifacts = generate(args.out, args.seed, args.terrain_res, args.crowd,
                         args.profile_samples, args.radial)
    for a in artifacts:
        extra = f", {a.get('vertices', '?')} verts, {a.get('triangles', '?')} tris" \
            if "vertices" in a else ""
        print(f"[gen-meshes] {a['path']}: {a['bytes']} bytes{extra}")
    print(f"[gen-meshes] OK: {len(artifacts)} artefatos em {args.out}/mesh "
          f"(seed={args.seed})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
