#!/usr/bin/env python3
"""Gerador da shader-library GLSL ES 3.1 do APK Tester ("Behemoth").

Fase: A0/A5 — geradores core. Produz 239 programas a partir de templates
paramétricos com variação determinística por --seed (contagens de loop,
constantes float, local sizes):
  - 215 programas gráficos (par .vert + .frag): PBR cook-torrance, raymarching
    por sphere tracing, fluido (jacobi), SSAO, biblioteca de ruído (value +
    simplex), stress de 512 uniforms (u_stress[512] lido em loop) e long-loop
    fragment. O vertex padrão é o fullscreen triangle (gl_VertexID).
  - 24 compute shaders GLSL ES 3.1 (arquivo único .comp, sem .vert) em 3
    templates rotativos determinísticos: jacobi de pressão (buffers
    readonly/writeonly), reduce por workgroup com memória compartilhada
    (shared + memoryBarrierShared() + barrier()) e integração de partículas
    (gravidade + drag, uniforms dt/seed).

Cada programa (gráfico OU compute) ganha também um blob binário .spv
"estilo SPIR-V": asset opaco SINTÉTICO com header válido de 20 bytes
(magic 0x07230203, versão 1.0, generator 0, bound = 1000 + ordinal, schema 0)
e payload derivado de keystream SHA-256 determinístico por programa —
NÃO é um módulo SPIR-V real; a fonte GLSL é o contrato compilável
(validação real acontece no CI via glslangValidator).

Cada programa vira uma entrada em shader-library/index.json com
{id, files, sha256, uniforms, stage: graphics|compute, spirv: {file, bytes,
magic, synthetic}}. Apenas stdlib python3; nenhum binário externo.

Uso:
    python3 tools/gen-shaders.py --out /tmp/out [--seed 20261022]
    python3 tools/gen-shaders.py --selftest
"""

import argparse
import hashlib
import json
import random
import re
import struct
import sys
import tempfile
from pathlib import Path

DEFAULT_SEED = 20261022
GLSL_VERSION = "#version 310 es"
UNIFORM_RE = re.compile(r"^\s*uniform\s+\w+\s+(\w+)\s*(\[\d+\])?\s*;", re.M)

# (categoria, quantidade) — 8 categorias, soma = 239 programas (215 graphics
# + 24 compute; compute usa .comp único, as demais usam par .vert/.frag).
PLAN = [
    ("pbr", 40),
    ("raymarch", 40),
    ("fluid", 30),
    ("ssao", 24),
    ("noise", 30),
    ("stress", 25),
    ("longloop", 26),
    ("compute", 24),
]

# Blobs .spv "estilo SPIR-V": header válido, conteúdo sintético opaco.
SPIRV_MAGIC = 0x07230203
SPIRV_VERSION = 0x00010300  # SPIR-V 1.0
SPIRV_MAGIC_TEXT = "0x07230203"
SPIRV_HEADER_WORDS = 5  # magic, version, generator, bound, schema = 20 bytes
SPIRV_NOTE = (
    "Os blobs .spv são assets opacos SINTÉTICOS gerados por esta tool: magic "
    "SPIR-V válido (0x07230203, versão 1.0) e conteúdo sintético "
    "determinístico (keystream sha256 por programa) — não são módulos SPIR-V "
    "reais. A fonte GLSL é o contrato compilável; validação real acontece no "
    "CI via glslangValidator."
)

VERT_TEMPLATE = """#version 310 es
// apk-tester shader-library | @ID@ | fullscreen triangle vertex | seed @SEED@
precision highp float;
out vec2 v_uv;
void main() {
    vec2 pos = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));
    v_uv = pos;
    gl_Position = vec4(pos * 2.0 - 1.0, 0.0, 1.0);
}
"""

PBR_FRAG = """#version 310 es
// apk-tester shader-library | @ID@ | PBR cook-torrance (GGX) | seed @SEED@
precision highp float;
in vec2 v_uv;
out vec4 fragColor;
uniform vec3 u_camPos;
uniform vec3 u_albedo;
uniform vec3 u_lightDirs[4];
uniform float u_metallic;
uniform float u_roughness;
uniform float u_lightIntensity;
const int LIGHT_COUNT = @LIGHT_COUNT@;
const float ROUGHNESS_BIAS = @ROUGH_BIAS@;
const float METALLIC_BIAS = @METAL_BIAS@;
const float PI = 3.14159265359;

float dGgx(float noh, float a) {
    float a2 = a * a;
    float d = noh * noh * (a2 - 1.0) + 1.0;
    return a2 / (PI * d * d + 1e-5);
}

float smith(float nov, float nol, float a) {
    float k = (a + 1.0) * (a + 1.0) / 8.0;
    return (nov / (nov * (1.0 - k) + k)) * (nol / (nol * (1.0 - k) + k));
}

vec3 schlick(float woh, vec3 f0) { return f0 + (1.0 - f0) * pow(1.0 - woh, 5.0); }

void main() {
    vec3 n = normalize(vec3(v_uv - 0.5, 0.65));
    vec3 v = normalize(u_camPos);
    float a = max(u_roughness + ROUGHNESS_BIAS, 0.02);
    vec3 f0 = mix(vec3(0.04), u_albedo, clamp(u_metallic + METALLIC_BIAS, 0.0, 1.0));
    vec3 color = vec3(0.0);
    for (int l = 0; l < LIGHT_COUNT; l++) {
        vec3 L = normalize(u_lightDirs[l]);
        vec3 h = normalize(v + L);
        float nol = max(dot(n, L), 0.0);
        float noh = max(dot(n, h), 0.0);
        float woh = max(dot(v, h), 0.0);
        float nov = max(dot(n, v), 0.001);
        vec3 fterm = schlick(woh, f0);
        vec3 spec = (dGgx(noh, a) * smith(nov, nol, a) * fterm)
            / max(4.0 * nov * nol, 0.001);
        vec3 diffuse = (1.0 - fterm) * (1.0 - f0) * u_albedo / PI;
        color += (diffuse + spec) * u_lightIntensity * nol;
    }
    fragColor = vec4(color / float(LIGHT_COUNT), 1.0);
}
"""

RAYMARCH_FRAG = """#version 310 es
// apk-tester shader-library | @ID@ | sphere tracing | seed @SEED@
precision highp float;
in vec2 v_uv;
out vec4 fragColor;
uniform vec3 u_camPos;
uniform float u_time;
#define MAX_STEPS @MAX_STEPS@
#define MAX_DIST @MAX_DIST@
#define SURF_EPS @SURF_EPS@
#define SEED_X @SEED_X@

float sdSphere(vec3 p, float r) { return length(p) - r; }

float sdBox(vec3 p, vec3 b) {
    vec3 q = abs(p) - b;
    return length(max(q, vec3(0.0))) + min(max(q.x, max(q.y, q.z)), 0.0);
}

float sdScene(vec3 p) {
    float d = sdSphere(p, 1.0);
    d = min(d, sdBox(p - vec3(SEED_X, sin(u_time) * 0.5, 0.0), vec3(0.35)));
    return min(d, sdSphere(p - vec3(-SEED_X, 0.5, 0.0), 0.5));
}

void main() {
    vec3 rd = normalize(vec3(v_uv * 2.0 - 1.0, -1.5));
    vec3 ro = u_camPos;
    float t = 0.0;
    for (int i = 0; i < MAX_STEPS; i++) {
        vec3 p = ro + rd * t;
        float d = sdScene(p);
        if (d < SURF_EPS || t > MAX_DIST) { break; }
        t += d * 0.9;
    }
    fragColor = vec4(vec3(clamp(1.0 - t / MAX_DIST, 0.0, 1.0)), 1.0);
}
"""

FLUID_FRAG = """#version 310 es
// apk-tester shader-library | @ID@ | jacobi pressure solve | seed @SEED@
precision highp float;
in vec2 v_uv;
out vec4 fragColor;
uniform sampler2D u_pressure;
uniform sampler2D u_divergence;
uniform vec2 u_texel;
#define JACOBI_ITERS @JACOBI_ITERS@
#define RELAX @RELAX@

float samplePressure(vec2 uv) {
    return texture(u_pressure, clamp(uv, vec2(0.0), vec2(1.0))).x;
}

void main() {
    float center = samplePressure(v_uv);
    float divergence = texture(u_divergence, v_uv).x;
    float acc = 0.0;
    for (int i = 0; i < JACOBI_ITERS; i++) {
        vec2 step = u_texel * float(i + 1);
        float left = samplePressure(v_uv + vec2(-step.x, 0.0));
        float right = samplePressure(v_uv + vec2(step.x, 0.0));
        float down = samplePressure(v_uv + vec2(0.0, -step.y));
        float up = samplePressure(v_uv + vec2(0.0, step.y));
        acc += (left + right + down + up - divergence) * 0.25;
    }
    float pressure = mix(center, acc / float(JACOBI_ITERS), RELAX);
    fragColor = vec4(pressure, 0.0, 0.0, 1.0);
}
"""

SSAO_FRAG = """#version 310 es
// apk-tester shader-library | @ID@ | SSAO kernel | seed @SEED@
precision highp float;
in vec2 v_uv;
out vec4 fragColor;
uniform sampler2D u_depth;
uniform sampler2D u_noise;
uniform vec2 u_texel;
uniform float u_radius;
#define KERNEL_SIZE @KERNEL_SIZE@
#define BIAS @BIAS@

void main() {
    float center = texture(u_depth, v_uv).x;
    float angle = texture(u_noise, v_uv * u_texel * 64.0).x * 6.2831853;
    vec2 dir = vec2(cos(angle), sin(angle));
    float occlusion = 0.0;
    for (int i = 1; i <= KERNEL_SIZE; i++) {
        vec2 offset = dir * (u_radius * float(i) / float(KERNEL_SIZE)) * u_texel;
        float d1 = texture(u_depth, v_uv + offset).x;
        float d2 = texture(u_depth, v_uv - offset).x;
        occlusion += (d1 < center - BIAS) ? 1.0 : 0.0;
        occlusion += (d2 < center - BIAS) ? 1.0 : 0.0;
    }
    float ao = clamp(1.0 - occlusion / float(KERNEL_SIZE), 0.0, 1.0);
    fragColor = vec4(vec3(ao), 1.0);
}
"""

NOISE_FRAG = """#version 310 es
// apk-tester shader-library | @ID@ | value + simplex noise lib | seed @SEED@
precision highp float;
in vec2 v_uv;
out vec4 fragColor;
uniform float u_freq;
uniform float u_amp;
#define OCTAVES @OCTAVES@

float hash21(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

float valueNoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    float a = hash21(i);
    float b = hash21(i + vec2(1.0, 0.0));
    float c = hash21(i + vec2(0.0, 1.0));
    float d = hash21(i + vec2(1.0, 1.0));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

vec2 hash22(vec2 p) {
    vec2 q = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
    return fract(sin(q) * 43758.5453);
}

float simplexNoise(vec2 p) {
    const float k1 = 0.366025404;
    const float k2 = 0.211324865;
    vec2 i = floor(p + (p.x + p.y) * k1);
    vec2 a = p - i + (i.x + i.y) * k2;
    float m = step(a.y, a.x);
    vec2 o = vec2(m, 1.0 - m);
    vec2 b = a - o + k2;
    vec2 c = a - 1.0 + 2.0 * k2;
    vec3 w = max(0.5 - vec3(dot(a, a), dot(b, b), dot(c, c)), 0.0);
    vec3 g = vec3(dot(hash22(i), a), dot(hash22(i + o), b),
                  dot(hash22(i + 1.0), c));
    vec3 t = w * w * w * (w * (w * 6.0 - 15.0) + 10.0);
    return dot(t * 4.0, g) * 2.0 - 1.0;
}

float fbm(vec2 p) {
    float sum = 0.0;
    float amp = 0.5;
    for (int i = 0; i < OCTAVES; i++) {
        sum += valueNoise(p) * amp;
        p = p * 2.02 + vec2(17.3, 9.1);
        amp *= 0.5;
    }
    return sum;
}

void main() {
    vec2 p = v_uv * u_freq;
    float n = fbm(p) * u_amp + simplexNoise(p * 1.7) * 0.25;
    fragColor = vec4(vec3(n), 1.0);
}
"""

STRESS_FRAG = """#version 310 es
// apk-tester shader-library | @ID@ | 512-uniform stress | seed @SEED@
precision highp float;
in vec2 v_uv;
out vec4 fragColor;
uniform float u_stress[512];
uniform float u_gain;
uniform float u_offset;
#define STRESS_LEN 512

void main() {
    float acc = 0.0;
    for (int i = 0; i < STRESS_LEN; i++) {
        acc += u_stress[i] * (u_gain + fract(float(i) * 0.0001));
    }
    float value = clamp(abs(acc) * 0.001 + u_offset, 0.0, 1.0);
    fragColor = vec4(vec3(value), 1.0);
}
"""

LONGLOOP_FRAG = """#version 310 es
// apk-tester shader-library | @ID@ | long-loop accumulation | seed @SEED@
precision highp float;
in vec2 v_uv;
out vec4 fragColor;
uniform float u_freq;
uniform float u_phase;
#define LOOP_END @LOOP_END@
#define HASH_SCALE 43758.5453

float hash1(float n) { return fract(sin(n) * HASH_SCALE); }

void main() {
    float acc = 0.0;
    float stepSize = u_freq / float(LOOP_END);
    for (int i = 0; i < LOOP_END; i++) {
        acc += hash1(float(i) * stepSize + u_phase) / float(LOOP_END);
    }
    fragColor = vec4(vec3(clamp(acc, 0.0, 1.0)), 1.0);
}
"""

COMPUTE_JACOBI = """#version 310 es
// apk-tester shader-library | @ID@ | compute jacobi pressure | seed @SEED@
precision highp float;
layout(local_size_x = @LSX@, local_size_y = @LSY@) in;

uniform float u_relax;
uniform float u_bias;
#define JACOBI_ITERS @JACOBI_ITERS@
#define GRID @GRID@

layout(std430, binding = 0) readonly buffer PressureIn { float p_in[]; };
layout(std430, binding = 1) writeonly buffer PressureOut { float p_out[]; };

float sampleP(ivec2 c) {
    ivec2 cc = clamp(c, ivec2(0), ivec2(GRID - 1, GRID - 1));
    return p_in[cc.y * GRID + cc.x];
}

void main() {
    ivec2 gid = ivec2(gl_GlobalInvocationID.xy);
    if (gid.x >= GRID || gid.y >= GRID) { return; }
    float acc = 0.0;
    for (int i = 0; i < JACOBI_ITERS; i++) {
        int s = i + 1;
        acc += sampleP(gid + ivec2(s, 0));
        acc += sampleP(gid - ivec2(s, 0));
        acc += sampleP(gid + ivec2(0, s));
        acc += sampleP(gid - ivec2(0, s));
    }
    float neighbors = acc / float(JACOBI_ITERS);
    float center = sampleP(gid);
    float pressure = mix(center, (neighbors - u_bias) * 0.25, u_relax);
    p_out[gid.y * GRID + gid.x] = pressure;
}
"""

COMPUTE_REDUCE = """#version 310 es
// apk-tester shader-library | @ID@ | compute workgroup reduce (shared) | seed @SEED@
precision highp float;
layout(local_size_x = @LSX@) in;

uniform float u_gain;
uniform float u_offset;
#define LSX @LSX@

shared float s_data[@LSX@];

layout(std430, binding = 0) readonly buffer DataIn { float data_in[]; };
layout(std430, binding = 1) writeonly buffer DataOut { float data_out[]; };

void main() {
    uint lid = gl_LocalInvocationID.x;
    s_data[lid] = data_in[gl_GlobalInvocationID.x] * u_gain + u_offset;
    barrier();
    memoryBarrierShared();
    for (uint stride = uint(LSX) / 2u; stride > 0u; stride >>= 1u) {
        if (lid < stride) {
            s_data[lid] += s_data[lid + stride];
        }
        barrier();
        memoryBarrierShared();
    }
    if (lid == 0u) {
        data_out[gl_WorkGroupID.x] = s_data[0];
    }
}
"""

COMPUTE_PARTICLES = """#version 310 es
// apk-tester shader-library | @ID@ | compute particle integration | seed @SEED@
precision highp float;
layout(local_size_x = @LSX@) in;

uniform float u_dt;
uniform float u_seed;
#define PARTICLES @PARTICLES@
const float GRAVITY = @GRAVITY@;
const float DRAG = @DRAG@;
const float GAIN = @GAIN@;

layout(std430, binding = 0) readonly buffer PosIn { vec4 pos_in[]; };
layout(std430, binding = 1) writeonly buffer PosOut { vec4 pos_out[]; };

void main() {
    uint gid = gl_GlobalInvocationID.x;
    if (gid >= uint(PARTICLES)) { return; }
    vec4 state = pos_in[gid];
    vec3 p = state.xyz;
    float mass = max(state.w, 0.1);
    vec3 swirl = vec3(sin(p.y * GAIN + u_seed),
                      cos(p.x * GAIN - u_seed),
                      sin((p.x + p.z) * GAIN));
    vec3 vel = swirl + vec3(0.0, -GRAVITY * mass, 0.0);
    vel *= exp(-DRAG * u_dt);
    pos_out[gid] = vec4(p + vel * u_dt, state.w);
}
"""

TEMPLATES = {"pbr": PBR_FRAG, "raymarch": RAYMARCH_FRAG, "fluid": FLUID_FRAG,
             "ssao": SSAO_FRAG, "noise": NOISE_FRAG, "stress": STRESS_FRAG,
             "longloop": LONGLOOP_FRAG}

COMPUTE_TEMPLATES = {"jacobi": COMPUTE_JACOBI, "reduce": COMPUTE_REDUCE,
                     "particles": COMPUTE_PARTICLES}


def compute_template_key(n: int) -> str:
    """Rotação determinística dos 3 templates compute (n é o índice 1-based)."""
    if n % 3 == 1:
        return "jacobi"
    if n % 3 == 2:
        return "reduce"
    return "particles"

# Parâmetros sorteados por categoria (variação determinística por --seed).
PARAMS = {
    "pbr": lambda rng: {
        "LIGHT_COUNT": rng.randint(1, 4),
        "ROUGH_BIAS": f"{rng.uniform(0.0, 0.25):.3f}",
        "METAL_BIAS": f"{rng.uniform(0.0, 0.25):.3f}",
    },
    "raymarch": lambda rng: {
        "MAX_STEPS": rng.randrange(48, 129, 8),
        "MAX_DIST": f"{float(rng.randrange(20, 61)):.1f}",
        "SURF_EPS": f"{rng.uniform(0.001, 0.01):.4f}",
        "SEED_X": f"{rng.uniform(0.5, 3.0):.2f}",
    },
    "fluid": lambda rng: {
        "JACOBI_ITERS": rng.randint(8, 24),
        "RELAX": f"{rng.uniform(0.5, 1.0):.3f}",
    },
    "ssao": lambda rng: {
        "KERNEL_SIZE": rng.randrange(8, 25, 2),
        "BIAS": f"{rng.uniform(0.01, 0.05):.4f}",
    },
    "noise": lambda rng: {"OCTAVES": rng.randint(3, 6)},
    "stress": lambda rng: {
        "GAIN": f"{rng.uniform(0.001, 0.01):.5f}",
        "OFFSET": f"{rng.uniform(0.0, 0.5):.4f}",
    },
    "longloop": lambda rng: {
        "LOOP_END": rng.randrange(1000, 2001, 25),
        "FREQ": f"{rng.uniform(1.0, 16.0):.3f}",
        "PHASE": f"{rng.uniform(0.0, 6.283):.4f}",
    },
    # Tokens dos 3 templates compute (render ignora os não usados por template).
    "compute": lambda rng: {
        "LSX": rng.choice((8, 16, 32)),
        "LSY": rng.choice((2, 4)),  # LSX*LSY <= 128 (MAX_COMPUTE_WORK_GROUP_INVOCATIONS)
        "JACOBI_ITERS": rng.randint(6, 18),
        "GRID": rng.randrange(64, 257, 64),
        "PARTICLES": rng.randrange(256, 1025, 64),
        "GRAVITY": f"{rng.uniform(4.0, 12.0):.3f}",
        "DRAG": f"{rng.uniform(0.1, 0.9):.3f}",
        "GAIN": f"{rng.uniform(0.5, 2.0):.3f}",
    },
}


def render(template: str, mapping: dict) -> str:
    """Substitui tokens @KEY@ (evita conflito das chaves GLSL com str.format)."""
    for key, value in mapping.items():
        template = template.replace(f"@{key}@", str(value))
    return template


def spirv_keystream(program_id: str, word_count: int) -> bytes:
    """Payload sintético: word_count uint32 LE de digests sha256(id:bloco)."""
    words = []
    block = 0
    while len(words) < word_count:
        digest = hashlib.sha256(
            f"{program_id}:{block}".encode("utf-8")).digest()
        words.extend(struct.unpack("<8I", digest))
        block += 1
    return struct.pack(f"<{word_count}I", *words[:word_count])


def make_spirv(program_id: str, ordinal: int, word_count: int) -> bytes:
    """Blob .spv estilo SPIR-V: header de 20 bytes + keystream sha256.

    Header (little-endian): magic 0x07230203, versão 0x00010300 (SPIR-V 1.0),
    generator 0, bound = 1000 + ordinal do programa, schema 0. O payload é
    sintético (asset opaco) — a fonte GLSL é o contrato compilável.
    """
    header = struct.pack("<5I", SPIRV_MAGIC, SPIRV_VERSION, 0,
                         1000 + ordinal, 0)
    return header + spirv_keystream(program_id, word_count)


def extract_uniforms(vert_src: str, frag_src: str) -> list:
    """Lista ordenada de uniforms (com [N]) presente em vert+frag."""
    found = []
    for src in (vert_src, frag_src):
        for name, brackets in UNIFORM_RE.findall(src):
            label = name + (brackets or "")
            if label not in found:
                found.append(label)
    return found


def write_manifest(out_dir: Path, tool: str, seed: int, rel_paths: list) -> None:
    entries = []
    for rel in sorted(rel_paths):
        data = (out_dir / rel).read_bytes()
        entries.append({
            "path": rel,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    payload = {"tool": tool, "seed": seed, "artifacts": entries}
    (out_dir / "manifest.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def generate(out_dir: Path, seed: int) -> list:
    """Gera shader-library/ (pares .vert/.frag, .comp, blobs .spv + índices)."""
    rng = random.Random(seed)
    artifacts = []
    programs = []

    def write(rel: str, text: str) -> None:
        path = out_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        artifacts.append(rel)

    def write_bytes(rel: str, data: bytes) -> None:
        path = out_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        artifacts.append(rel)

    for category, count in PLAN:
        for n in range(1, count + 1):
            program_id = f"{category}_{n:04d}"
            ordinal = len(programs) + 1
            params = PARAMS[category](rng)
            if category == "compute":
                # Compute: arquivo único .comp (sem .vert), template rotativo.
                comp_src = render(COMPUTE_TEMPLATES[compute_template_key(n)],
                                  {"ID": program_id, "SEED": seed, **params})
                comp_rel = f"shader-library/shaders/{category}/{program_id}.comp"
                write(comp_rel, comp_src)
                source = comp_src.encode("utf-8")
                files = [comp_rel]
                stage = "compute"
                uniforms = extract_uniforms(comp_src, "")
            else:
                vert_src = render(VERT_TEMPLATE,
                                  {"ID": program_id, "SEED": seed})
                frag_src = render(TEMPLATES[category],
                                  {"ID": program_id, "SEED": seed, **params})
                vert_rel = f"shader-library/shaders/{category}/{program_id}.vert"
                frag_rel = f"shader-library/shaders/{category}/{program_id}.frag"
                write(vert_rel, vert_src)
                write(frag_rel, frag_src)
                source = vert_src.encode("utf-8") + frag_src.encode("utf-8")
                files = [vert_rel, frag_rel]
                stage = "graphics"
                uniforms = extract_uniforms(vert_src, frag_src)
            word_count = rng.randrange(512, 4097, 64)
            spv_rel = f"shader-library/shaders/{category}/{program_id}.spv"
            spv_data = make_spirv(program_id, ordinal, word_count)
            write_bytes(spv_rel, spv_data)
            programs.append({
                "id": program_id,
                "files": files,
                "sha256": hashlib.sha256(source).hexdigest(),
                "uniforms": uniforms,
                "stage": stage,
                "spirv": {
                    "file": spv_rel,
                    "bytes": len(spv_data),
                    "magic": SPIRV_MAGIC_TEXT,
                    "synthetic": True,
                },
            })

    index = {"tool": "gen-shaders.py", "seed": seed, "count": len(programs),
             "spirv_note": SPIRV_NOTE, "programs": programs}
    write("shader-library/index.json",
          json.dumps(index, indent=2, ensure_ascii=False) + "\n")
    write_manifest(out_dir, "gen-shaders.py", seed, artifacts)
    return artifacts


def run_selftest() -> int:
    """Gera em tempdir e valida versão GLSL, contagens, compute e blobs .spv."""
    try:
        with tempfile.TemporaryDirectory(prefix="apktester-gen-shaders-") as tmp:
            root = Path(tmp)
            generate(root, DEFAULT_SEED)
            index = json.loads(
                (root / "shader-library/index.json").read_text("utf-8"))
            total = sum(c for _, c in PLAN)
            assert index["count"] == total == 239, \
                f"programas={index['count']} (esperado {total})"
            assert len(index["programs"]) == index["count"]
            assert "spirv_note" in index, "spirv_note ausente"
            assert "glslangValidator" in index["spirv_note"], "nota honesta?"
            for ordinal, program in enumerate(index["programs"], start=1):
                stage = program["stage"]
                assert stage in ("graphics", "compute"), program["id"]
                if stage == "graphics":
                    assert len(program["files"]) == 2, program["id"]
                    vert = (root / program["files"][0]).read_text("utf-8")
                    frag = (root / program["files"][1]).read_text("utf-8")
                    assert vert.splitlines()[0] == GLSL_VERSION, program["id"]
                    assert frag.splitlines()[0] == GLSL_VERSION, program["id"]
                    source = vert.encode("utf-8") + frag.encode("utf-8")
                else:
                    assert len(program["files"]) == 1, program["id"]
                    comp = (root / program["files"][0]).read_text("utf-8")
                    assert comp.splitlines()[0] == GLSL_VERSION, program["id"]
                    assert "buffer" in comp, f"buffer ausente: {program['id']}"
                    assert "layout(local_size_x" in comp, program["id"]
                    source = comp.encode("utf-8")
                assert program["uniforms"], f"uniforms vazios: {program['id']}"
                digest = hashlib.sha256(source).hexdigest()
                assert digest == program["sha256"], f"sha divergiu: {program['id']}"
                meta = program["spirv"]
                words = (meta["bytes"] - SPIRV_HEADER_WORDS * 4) // 4
                assert meta["bytes"] == SPIRV_HEADER_WORDS * 4 + words * 4, \
                    program["id"]
                assert 512 <= words <= 4096 and words % 64 == 0, program["id"]
                spv = (root / meta["file"]).read_bytes()
                assert len(spv) == meta["bytes"], program["id"]
                assert spv[:4] == b"\x03\x02\x23\x07", program["id"]
                magic, version, generator, bound, schema = struct.unpack(
                    "<5I", spv[:20])
                assert magic == SPIRV_MAGIC, program["id"]
                assert version == SPIRV_VERSION, program["id"]
                assert generator == 0 and schema == 0, program["id"]
                assert bound == 1000 + ordinal, program["id"]
                assert meta["magic"] == SPIRV_MAGIC_TEXT, program["id"]
                assert meta["synthetic"] is True, program["id"]
                assert spv == make_spirv(program["id"], ordinal, words), \
                    f"spv divergiu: {program['id']}"
            by_cat = {}
            for p in index["programs"]:
                by_cat.setdefault(p["id"].rsplit("_", 1)[0], []).append(p)
            assert {k: len(v) for k, v in by_cat.items()} == dict(PLAN)
            assert len(by_cat) == len(PLAN), "categorias faltando"
            keys = [compute_template_key(int(p["id"].rsplit("_", 1)[1]))
                    for p in by_cat["compute"]]
            assert set(keys) == {"jacobi", "reduce", "particles"}, \
                "rotação compute incompleta"
            for p in by_cat["compute"]:
                n = int(p["id"].rsplit("_", 1)[1])
                comp = (root / p["files"][0]).read_text("utf-8")
                if n % 3 == 1:  # compute_jacobi
                    assert "PressureIn" in comp and "PressureOut" in comp
                    assert re.search(r"JACOBI_ITERS", comp)
                elif n % 3 == 2:  # compute_reduce
                    assert "shared float s_data[" in comp, p["id"]
                    assert "barrier()" in comp, f"barrier ausente: {p['id']}"
                    assert "memoryBarrierShared()" in comp, p["id"]
                else:  # compute_particles
                    assert "GRAVITY" in comp and "DRAG" in comp, p["id"]
                    assert "u_dt" in comp and "u_seed" in comp, p["id"]
            stress_frag = (root / by_cat["stress"][0]["files"][1]).read_text("utf-8")
            assert "u_stress[512]" in stress_frag, "u_stress[512] ausente"
            loop_frag = (root / by_cat["longloop"][0]["files"][1]).read_text("utf-8")
            assert re.search(r"#define LOOP_END \d{3,4}", loop_frag)

            second = root / "second-run"
            generate(second, DEFAULT_SEED)
            for rel in ("shader-library/shaders/raymarch/raymarch_0007.frag",
                        "shader-library/shaders/compute/compute_0002.comp",
                        "shader-library/shaders/pbr/pbr_0001.spv"):
                a = hashlib.sha256((root / rel).read_bytes()).hexdigest()
                b = hashlib.sha256((second / rel).read_bytes()).hexdigest()
                assert a == b, f"saída não determinística: {rel}"
    except AssertionError as exc:
        print(f"gen-shaders selftest: FAIL ({exc})")
        return 1
    print("gen-shaders selftest: OK")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Gera a shader-library GLSL ES 3.1 "
                    "(239 programas: graphics + compute + blobs .spv).")
    parser.add_argument("--out", help="diretório de saída (obrigatório)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--selftest", action="store_true",
                        help="roda asserções internas e sai com 0/1")
    args = parser.parse_args(argv)
    if args.selftest:
        return run_selftest()
    if not args.out:
        parser.error("--out é obrigatório (ou use --selftest)")
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts = generate(out_dir, args.seed)
    print(f"gen-shaders: {len(artifacts)} artefatos gravados em {out_dir} "
          f"(seed={args.seed})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
