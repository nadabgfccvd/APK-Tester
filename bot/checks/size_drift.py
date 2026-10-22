#!/usr/bin/env python3
"""bot/checks/size_drift.py — tendência de tamanho do flagship + previsão de gate.

O CI (size-gate.yml + tools/size-budget.sh) confere o gate UMA vez, quando o
APK já existe. O APKBot cobre o que o CI não vê: a SÉRIE TEMPORAL.

Fonte: ``contracts/flagship/size-report.csv`` (header
``category,bytes,files,sha256_of_apk``; linha ``total`` ignorada — o total é
recomputado como soma das categorias). Sem rede: 100% arquivo local, sempre
executa (ran=True) enquanto o CSV existir.

Comportamento:
- CSV ausente/ilegível => CheckResult(ran=False, notes=...) — não é falha.
- total == 0 (flagship ausente, A0): aprende a amostra mesmo assim e emite
  Finding "info" ...:total:aguardando-a6 UMA ÚNICA vez (só na primeira
  amostra da história); nenhuma lógica de drift/gate/previsão roda.
- 0 < total < SKELETON_TOTAL_BYTES (1 MB): esqueleto do size-report.csv
  (valores placeholder do A0) — mesmo tratamento do total == 0, mas o aviso
  "aguardando A6" é emitido TODA execução enquanto o esqueleto persistir
  (severidade "info": antes do marco A6 ficar fora da faixa é ESPERADO;
  reafirmar como "regression" aqui seria ruído permanente e congelaria a
  série histórica, pois aprendizado com regressão é proibido).
- total >= SKELETON_TOTAL_BYTES (build real):
  * drift por categoria: |Δ%| > cfg.size_drift_pct (padrão 2.0) vs a ÚLTIMA
    amostra do baseline (state.baselines.size_drift.samples) => Finding
    "drift" ...:{categoria}:drift mostrando bytes antigo → novo;
  * gate: total fora de cfg.size_gate_mb [850, 1000] MB => Finding
    "regression" ...:total:fora-do-gate (o CI já reprova; o bot reafirma);
  * PREVISÃO (o que o CI não faz): com >= cfg.size_forecast_min_samples
    (padrão 5) amostras datadas de total_bytes, ajuste linear por mínimos
    quadrados (dias ordinais vs bytes, stdlib statistics) e projeção de
    10 execuções à frente; se a projeção cruzar qualquer borda do gate =>
    Finding "drift" ...:total:previsao-breach com slope MB/execução, run e
    data previstas do breach e ação sugerida (engenharia de tamanho em A6).

``learn`` devolve {"samples": [história + amostra de hoje]} — o dispatcher
consolida em state.baselines.size_drift.samples com learn_mode "immediate"
(sem confirmação múltipla: a amostra é fato do commit corrente).
"""

import csv
import sys
from datetime import date, datetime
from pathlib import Path
from statistics import fmean

CHECK_ID = "size_drift"

SIZE_REPORT_REL = Path("contracts") / "flagship" / "size-report.csv"
MB = 1024 * 1024
GATE_MB_DEFAULT = (850.0, 1000.0)
DRIFT_PCT_DEFAULT = 2.0
FORECAST_MIN_SAMPLES_DEFAULT = 5
FORECAST_HORIZON_RUNS = 10
DEFAULT_RUN_INTERVAL_DAYS = 1.0
MAX_SERIES_SAMPLES = 90   # teto da série carregada no learn (estado limitado)
# Abaixo disso é esqueleto/placeholder (o flagship real vive na faixa de
# centenas de MB — 6 ordens de grandeza acima do CSV do A0). Entre 1 MB e o
# mínimo do gate é regressão de verdade (build parcial).
SKELETON_TOTAL_BYTES = 1024 * 1024

_CHECKS_DIR = Path(__file__).resolve()
for _p in (_CHECKS_DIR.parents[2], _CHECKS_DIR.parents[1]):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from bot.lib.base import CheckResult, Finding
except ImportError:  # fallback: árvore bot/ sem o pacote "bot" (layout antigo)
    from lib.base import CheckResult, Finding  # type: ignore


# ------------------------------------------------------------------ helpers
def _read_report(repo: Path):
    """(categorias {nome: bytes}, sha) do CSV; None se ausente/ilegível."""
    path = repo / SIZE_REPORT_REL
    try:
        with path.open(newline="", encoding="utf-8") as fh:
            rows = [r for r in csv.reader(fh) if r and any(c.strip() for c in r)]
    except (OSError, csv.Error):
        return None
    if len(rows) < 2:
        return None
    header = [c.strip().lower() for c in rows[0]]
    try:
        i_cat = header.index("category")
        i_bytes = header.index("bytes")
    except ValueError:
        return None
    categories = {}
    for row in rows[1:]:
        if len(row) <= max(i_cat, i_bytes):
            continue
        cat = row[i_cat].strip()
        if not cat or cat.lower() == "total":
            continue
        try:
            categories[cat] = int(float(row[i_bytes]))
        except ValueError:
            continue
    return categories


def _ordinal(iso: str):
    """ISO (date ou datetime, com/sem Z) -> dia ordinal; None se inválido."""
    if not isinstance(iso, str) or not iso.strip():
        return None
    txt = iso.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(txt).date().toordinal()
    except ValueError:
        try:
            return date.fromisoformat(txt[:10]).toordinal()
        except ValueError:
            return None


def _fit(xs, ys):
    """Mínimos quadrados simples; (slope, intercept) ou None se degenerado."""
    if len(xs) < 2:
        return None
    mx, my = fmean(xs), fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx <= 0:
        return None
    return sxy / sxx, my - (sxy / sxx) * mx


def _history(baseline: dict):
    """Amostras válidas do baseline: [(ordinal, total_bytes)] ordenadas."""
    out = []
    samples = baseline.get("samples")
    if isinstance(samples, list):
        for s in samples:
            if not isinstance(s, dict):
                continue
            ord_day = _ordinal(s.get("date", ""))
            total = s.get("total_bytes")
            if ord_day is not None and isinstance(total, (int, float)):
                out.append((ord_day, float(total)))
    out.sort()
    return out


def _fmt_mb(nbytes: float) -> str:
    return f"{nbytes / MB:,.1f} MB".replace(",", ".")


def _fmt_int(n) -> str:
    return f"{int(n):,}".replace(",", ".")


# ---------------------------------------------------------------------- run
def run(ctx) -> CheckResult:
    repo = Path(str(ctx.repo_path))
    findings = []

    gate_lo, gate_hi = GATE_MB_DEFAULT
    raw_gate = ctx.cfg.get("size_gate_mb")
    lo = hi = None
    if isinstance(raw_gate, dict):                      # {"min": 850, "max": 1000}
        lo, hi = raw_gate.get("min"), raw_gate.get("max")
    elif isinstance(raw_gate, (list, tuple)) and len(raw_gate) == 2:
        lo, hi = raw_gate[0], raw_gate[1]
    try:
        lo_f, hi_f = float(lo), float(hi)
        if 0 < lo_f < hi_f:
            gate_lo, gate_hi = lo_f, hi_f
    except (TypeError, ValueError):
        pass
    drift_pct = float(ctx.cfg.get("size_drift_pct") or DRIFT_PCT_DEFAULT)
    min_samples = int(ctx.cfg.get("size_forecast_min_samples")
                      or FORECAST_MIN_SAMPLES_DEFAULT)

    categories = _read_report(repo)
    if categories is None:
        return CheckResult(check=CHECK_ID, findings=[], learn={},
                           ran=False,
                           notes=f"{SIZE_REPORT_REL} ausente ou ilegível: "
                                 "verificação pulada")

    total = sum(categories.values())
    sample = {"date": ctx.now, "total_bytes": total,
              "categories": dict(sorted(categories.items()))}

    baseline = (ctx.state.get("baselines") or {}).get(CHECK_ID, {}) \
        if isinstance(ctx.state, dict) else {}
    hist_raw = []
    if isinstance(baseline, dict):
        raw_samples = baseline.get("samples")
        if isinstance(raw_samples, list):
            hist_raw = [s for s in raw_samples if isinstance(s, dict)]
    hist = _history(baseline) if isinstance(baseline, dict) else []
    # deep_merge do dispatcher SUBSTITUI listas: a série histórica precisa ser
    # carregada para frente pelo próprio check (história + amostra de hoje).
    def _learn_samples(new_sample):
        return {"samples": (hist_raw + [new_sample])[-MAX_SERIES_SAMPLES:]}

    # Flagship ausente (A0): aprende, avisa UMA vez, sem drift/gate/previsão.
    if total == 0:
        learn = _learn_samples(sample)
        if not hist:
            findings.append(Finding(
                check=CHECK_ID, target=str(SIZE_REPORT_REL),
                severity="info",
                title="Flagship ausente — size-report.csv zerado (aguardando A6)",
                body_md=(
                    "`contracts/flagship/size-report.csv` contém apenas zeros: "
                    "o flagship \"Behemoth\" ainda não foi construído. A "
                    "engenharia de tamanho até o gate "
                    f"[{_fmt_int(gate_lo)}, {_fmt_int(gate_hi)}] MB "
                    "acontece no marco **A6**; até lá nenhuma lógica de "
                    "drift ou previsão é aplicada. Esta mensagem é emitida "
                    "uma única vez (primeira amostra da série)."),
                fingerprint=f"{CHECK_ID}:total:aguardando-a6"))
        return CheckResult(check=CHECK_ID, findings=findings, learn=learn,
                           ran=True, learn_mode="immediate",
                           notes="flagship ausente (total=0); amostra "
                                 "aprendida; sem lógica de drift")

    learn = _learn_samples(sample)

    if total >= SKELETON_TOTAL_BYTES and hist:
        last_cat = {}
        last_samples = (baseline or {}).get("samples") or []
        if isinstance(last_samples, list) and last_samples:
            prev = last_samples[-1]
            if isinstance(prev, dict) and isinstance(prev.get("categories"), dict):
                last_cat = prev["categories"]
        for cat in sorted(categories):
            new_b = categories[cat]
            old_b = last_cat.get(cat, 0)
            if old_b > 0:
                pct = (new_b - old_b) / old_b * 100.0
                crossed = abs(pct) > drift_pct
                delta_txt = f"{pct:+.2f}%"
            elif new_b > 0:
                crossed = True
                delta_txt = "categoria nova (baseline 0)"
            else:
                continue  # 0 -> 0
            if crossed:
                findings.append(Finding(
                    check=CHECK_ID, target=f"size:{cat}",
                    severity="drift",
                    title=f"Categoria '{cat}' driftou além do limiar",
                    body_md=(
                        f"Entre a última amostra registrada e agora, a "
                        f"categoria `{cat}` foi de "
                        f"**{_fmt_int(old_b)} → {_fmt_int(new_b)} bytes** "
                        f"({delta_txt}), acima do limiar de "
                        f"{drift_pct:.2f}%. Verificar geradores da categoria "
                        "(tools/gen-*.py) e reconciliar o size-report.csv "
                        "antes do próximo build do flagship."),
                    fingerprint=f"{CHECK_ID}:{cat}:drift"))

    # 2) Gate (reafirma o que o CI reprova). Esqueleto (total < 1 MB) é
    #    "info" aguardando A6 — ver docstring; fora do gate com build real é
    #    "regression".
    if not (gate_lo * MB <= total <= gate_hi * MB):
        lado = "abaixo do mínimo" if total < gate_lo * MB else "acima do máximo"
        if total < SKELETON_TOTAL_BYTES:
            findings.append(Finding(
                check=CHECK_ID, target=str(SIZE_REPORT_REL),
                severity="info",
                title="Total do flagship abaixo do gate — aguardando A6",
                body_md=(
                    "`contracts/flagship/size-report.csv` contém apenas o "
                    f"esqueleto do A0 (total atual: {_fmt_int(total)} bytes). "
                    "A engenharia de tamanho até o gate "
                    f"[{_fmt_mb(gate_lo * MB)}, {_fmt_mb(gate_hi * MB)}] "
                    "acontece no marco **A6**; até lá, ficar abaixo do mínimo "
                    "é ESPERADO e não é regressão. O CI (size-gate.yml) já "
                    "reprova o gate quando houver APK real; esta mensagem "
                    "mantém o registro e NÃO congela a série histórica "
                    "(severidade info permite o aprendizado da amostra)."),
                fingerprint=f"{CHECK_ID}:total:aguardando-a6"))
        else:
            findings.append(Finding(
                check=CHECK_ID, target="size:total",
                severity="regression",
                title="Total do flagship fora do size gate",
                body_md=(
                    f"Total atual: **{_fmt_mb(total)}** ({_fmt_int(total)} bytes) "
                    f"— {lado} do gate [{_fmt_mb(gate_lo * MB)}, "
                    f"{_fmt_mb(gate_hi * MB)}]. O CI (size-gate.yml) já reprova "
                    "isso; o bot reafirma para o registro histórico. Com build "
                    "real (total >= 1 MB) e fora da faixa, é regressão de "
                    "verdade: revisar gen-textures/gen-audio/gen-meshes e a "
                    "compressão antes do release."),
                fingerprint=f"{CHECK_ID}:total:fora-do-gate"))

    # 3) Previsão de breach (o que o CI NÃO faz).
    series = hist + [(_ordinal(ctx.now) or 0, float(total))]
    series = [(d, t) for d, t in series if d > 0]
    if len(series) >= min_samples:
        xs = [d for d, _ in series]
        ys = [t for _, t in series]
        fit = _fit(xs, ys)
        if fit is not None:
            slope, intercept = fit
            deltas = [b - a for a, b in zip(xs, xs[1:]) if b > a]
            interval = fmean(deltas) if deltas else DEFAULT_RUN_INTERVAL_DAYS
            if interval <= 0:
                interval = DEFAULT_RUN_INTERVAL_DAYS
            last_x = xs[-1]
            breach = None  # (k, y, direção)
            for k in range(1, FORECAST_HORIZON_RUNS + 1):
                y = intercept + slope * (last_x + k * interval)
                if y > gate_hi * MB:
                    breach = (k, y, "acima do máximo")
                    break
                if y < gate_lo * MB:
                    breach = (k, y, "abaixo do mínimo")
                    break
            if breach is not None:
                k, y, direcao = breach
                data_prev = date.fromordinal(
                    max(1, round(last_x + k * interval))).isoformat()
                slope_mb_run = slope * interval / MB
                findings.append(Finding(
                    check=CHECK_ID, target="size:total",
                    severity="drift",
                    title="Previsão: total do flagship cruzará o size gate",
                    body_md=(
                        f"Série com {len(series)} amostras de `total_bytes`; "
                        "ajuste linear (mínimos quadrados) dá slope de "
                        f"**{slope_mb_run:+.2f} MB por execução** "
                        f"({_fmt_int(slope)} bytes/dia).\n\n"
                        f"Projetando {FORECAST_HORIZON_RUNS} execuções à "
                        f"frente (intervalo médio de {interval:.1f} dias "
                        "entre execuções), o total cruza a borda "
                        f"{'superior' if 'máximo' in direcao else 'inferior'} "
                        f"do gate em **{k} execução(ões)** — previsão de "
                        f"**{data_prev}** com total projetado de "
                        f"**{_fmt_mb(y)}** ({direcao} de "
                        f"[{_fmt_mb(gate_lo * MB)}, {_fmt_mb(gate_hi * MB)}])."
                        "\n\nAção: antecipar a engenharia de tamanho do "
                        "marco A6 (ajustar gen-textures/gen-audio/gen-meshes, "
                        "revisar compressão e categorias do size-report.csv) "
                        "ANTES do breach — o gate só reage quando o APK já "
                        "está fora da faixa; esta previsão existe para dar "
                        "tempo de corrigir."),
                    fingerprint=f"{CHECK_ID}:total:previsao-breach"))

    notes = (f"total={_fmt_int(total)} bytes em {len(categories)} categorias; "
             f"série histórica: {len(series)} amostras válidas")
    # "immediate": a amostra de hoje é fato do commit corrente (o CSV é
    # determinístico) — a série é carregada para frente pelo próprio check;
    # confirmação por igualdade de payload nunca convergiria.
    return CheckResult(check=CHECK_ID, findings=findings, learn=learn,
                       ran=True, learn_mode="immediate", notes=notes)
