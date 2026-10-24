#!/usr/bin/env python3
"""Gerador de recursos de strings do APK Tester ("Behemoth").

Fase: A0/A1 — geradores core do repositório. Alimenta o flagship com
res/values/strings.xml (locale padrão "en") e as variantes por locale usadas
pelos probes LANG e pelos testes de RTL/pseudolocale do RustyDroid.

Saída determinística: dado o mesmo --seed, os bytes gerados são idênticos.
Apenas stdlib do python3; nenhum binário é produzido. O manifest.json lista
sha256 de cada artefato (sem timestamps, para reprodutibilidade).

Uso:
    python3 tools/gen-strings.py --out /tmp/out [flags]
    python3 tools/gen-strings.py --selftest
"""

import argparse
import hashlib
import json
import random
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

DEFAULT_SEED = 20261022
DEFAULT_LOCALES = "en,pt-BR,es,ar,he,ja,zh,de,fr,ru,hi,pt"
DEFAULT_BUTTONS = 1200
WORDLIST_SIZE = 1200

# Base do wordlist procedural (sufixos + tiers completam as ~1200 palavras).
BASE_WORDS = [
    "alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel",
    "india", "juliett", "kilo", "lima", "mike", "november", "oscar", "papa",
    "quebec", "romeo", "sierra", "tango", "uniform", "victor", "whiskey",
    "xray", "yankee", "zulu", "amber", "basalt", "cobalt", "dune", "ember",
    "fjord", "garnet", "helix", "ingot", "jasper", "kelvin", "lumen", "nectar",
    "onyx", "pylon", "quartz", "ridge", "sable", "topaz", "umber", "vortex",
]
PRO_SUFFIXES = ["prime", "flux", "nova", "core", "peak", "orbit"]
TIER_SUFFIXES = ["", "ii", "iii", "iv", "v"]

# Strings nomeadas do en (padrão). %1$s/%1$d => posicionais (RTL-safe).
NAMED_STRINGS = [
    ("app_name", "APK Tester — Behemoth"),
    ("button_grid_title", "Button Grid"),
    ("icon_grid_title", "Icon Grid"),
    ("permission_hub_title", "Permissions Hub"),
    ("probe_report_title", "MaxProbe Report"),
    ("probe_running", "Probe running"),
    ("probe_result_ok", "OK"),
    ("probe_result_error", "ERROR"),
    ("probe_duration_ms", "Duration ms"),
    ("probe_net_replay_hint", "Replaying recorded session %1$s"),
    ("probe_module_core", "CORE module"),
    ("probe_module_ui", "UI module"),
    ("probe_module_st", "ST module"),
    ("probe_module_net", "NET module"),
    ("probe_module_sys", "SYS module"),
    ("probe_module_media", "MEDIA module"),
    ("probe_module_lang", "LANG module"),
    ("btn_content_desc", "Button %1$d of %2$d"),
    ("ic_content_desc", "Icon %1$d of %2$d"),
]

# Traduções reais das 4 strings principais; demais caem no valor en (técnico).
TRANSLATIONS = {
    "pt-BR": {
        "button_grid_title": "Grade de Botões",
        "icon_grid_title": "Grade de Ícones",
        "permission_hub_title": "Central de Permissões",
        "probe_report_title": "Relatório MaxProbe",
    },
    "es": {
        "button_grid_title": "Cuadrícula de Botones",
        "icon_grid_title": "Cuadrícula de Iconos",
        "permission_hub_title": "Centro de Permisos",
        "probe_report_title": "Informe MaxProbe",
    },
    "de": {
        "button_grid_title": "Schaltflächenraster",
        "icon_grid_title": "Symbolraster",
        "permission_hub_title": "Berechtigungscenter",
        "probe_report_title": "MaxProbe-Bericht",
    },
    "fr": {
        "button_grid_title": "Grille de boutons",
        "icon_grid_title": "Grille d’icônes",
        "permission_hub_title": "Centre des autorisations",
        "probe_report_title": "Rapport MaxProbe",
    },
    "ru": {
        "button_grid_title": "Сетка кнопок",
        "icon_grid_title": "Сетка значков",
        "permission_hub_title": "Центр разрешений",
        "probe_report_title": "Отчёт MaxProbe",
    },
    "ja": {
        "button_grid_title": "ボタングリッド",
        "icon_grid_title": "アイコングリッド",
        "permission_hub_title": "権限ハブ",
        "probe_report_title": "MaxProbe レポート",
    },
    "zh": {
        "button_grid_title": "按钮网格",
        "icon_grid_title": "图标网格",
        "permission_hub_title": "权限中心",
        "probe_report_title": "MaxProbe 报告",
    },
    "hi": {
        "button_grid_title": "बटन ग्रिड",
        "icon_grid_title": "आइकन ग्रिड",
        "permission_hub_title": "अनुमति केंद्र",
        "probe_report_title": "MaxProbe रिपोर्ट",
    },
    "pt": {
        "button_grid_title": "Grelha de Botões",
        "icon_grid_title": "Grelha de Ícones",
        "permission_hub_title": "Central de Permissões",
        "probe_report_title": "Relatório MaxProbe",
    },
    "ar": {
        "button_grid_title": "شبكة الأزرار",
        "icon_grid_title": "شبكة الأيقونات",
        "permission_hub_title": "مركز الأذونات",
        "probe_report_title": "تقرير MaxProbe",
    },
    "he": {
        "button_grid_title": "רשת כפתורים",
        "icon_grid_title": "רשת סמלים",
        "permission_hub_title": "מרכז ההרשאות",
        "probe_report_title": "דוח MaxProbe",
    },
}

RTL_LOCALES = {"ar", "he"}
PSEUDO_EN_XA = "en-rXA"  # pseudolocale acentuado (estilo Android en-XA)
PSEUDO_AR_XB = "ar-rXB"  # pseudolocale RTL de comprimento duplo (ar-XB)

# Mapa en-XA: a->á, b->b-circunflexo etc. (determinístico, sem PRNG).
_ENXA_PAIRS = (
    "aá bḃ cć dď eé fḟ gğ hĥ ií jĵ kḱ lĺ mḿ nń oó pṕ qǫ rŕ sś tť "
    "uú vṽ wẃ xẋ yý zź"
)
ENXA_MAP = {p[0]: p[1:] for p in _ENXA_PAIRS.split()}


def build_wordlist(seed: int) -> list:
    """Constrói o wordlist de 1200 palavras únicas (palavra+sufixo+tier)."""
    rng = random.Random(seed)
    words, seen = [], set()
    idx = 0
    while len(words) < WORDLIST_SIZE:
        base = BASE_WORDS[idx % len(BASE_WORDS)]
        sfx = PRO_SUFFIXES[(idx // len(BASE_WORDS)) % len(PRO_SUFFIXES)]
        tier_idx = idx // (len(BASE_WORDS) * len(PRO_SUFFIXES))
        tier = TIER_SUFFIXES[tier_idx % len(TIER_SUFFIXES)]
        word = f"{base}_{sfx}" + (f"_{tier}" if tier else "")
        if word not in seen:
            seen.add(word)
            words.append(word)
        idx += 1
    rng.shuffle(words)
    return words


def build_labels(count: int, words: list) -> list:
    """Pares de palavras determinísticos; 1ª palavra única por índice."""
    labels = []
    total = len(words)
    for i in range(count):
        a = words[i % total]
        b = words[(i * 31 + 7) % total]
        labels.append(f"{a} {b}".replace("_", " ").title())
    return labels


def locale_dir(locale: str) -> str:
    """Converte 'pt-BR' -> 'values-pt-rBR' e 'en-rXA' -> 'values-en-rXA'."""
    parts = locale.split("-")
    if len(parts) == 2:
        lang, region = parts[0], parts[1]
        if len(region) == 3 and region.startswith("r") and region[1:].isupper():
            region = region[1:]
        return f"values-{lang}-r{region.upper()}"
    return f"values-{locale}"


def locale_named(locale: str) -> dict:
    """Mapa nomeado->valor do locale, com wrapping RTL-safe quando RTL."""
    rtl = locale in RTL_LOCALES
    trans = TRANSLATIONS.get(locale, {})
    named = {}
    for key, default in NAMED_STRINGS:
        value = trans.get(key, default)
        named[key] = f"\u202b{value}\u202c" if rtl else value
    return named


def apply_pseudo_en_xa(value: str) -> str:
    accented = "".join(ENXA_MAP.get(ch, ch) for ch in value)
    return f"[{accented}]"


def apply_pseudo_ar_xb(value: str) -> str:
    return f"\u202b{value} {value}\u202c"


def build_strings_xml(seed: int, named: dict, labels: list) -> str:
    """Serializa strings.xml com escape XML correto (saxutils.escape)."""
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        f"<!-- Generated by tools/gen-strings.py seed={seed} — deterministic -->",
        "<resources>",
    ]
    for name, value in named.items():
        lines.append(f'    <string name="{name}">{escape(value)}</string>')
    for i, label in enumerate(labels, start=1):
        lines.append(f'    <string name="btn_label_{i:04d}">{escape(label)}</string>')
    lines.append("</resources>")
    lines.append("")
    return "\n".join(lines)


def build_locale_properties(seed: int, named: dict) -> str:
    """Serializa strings.properties do locale (assets/locales/<tag>/).

    Mesmos pares chave/valor do values-<locale>/strings.xml, em formato
    Java Properties (UTF-8). O :app/:compose leem este asset em runtime
    (R2.3 do AUDIT_ROADMAP_V2: a categoria "locales" do size-report passa
    a ter bytes REAIS e usados, nao apenas resources.arsc).
    """
    lines = [
        f"# Generated by tools/gen-strings.py seed={seed} — deterministic",
        "# espelho do values-<locale> correspondente (strings.xml)",
    ]
    for name, value in named.items():
        lines.append(f"{name}={value}")
    lines.append("")
    return "\n".join(lines)


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


def generate(out_dir: Path, seed: int, locales: list, buttons: int,
             pseudolocale: bool) -> list:
    """Gera toda a árvore res/values; devolve a lista de caminhos relativos."""
    words = build_wordlist(seed)
    artifacts = []

    def write(rel: str, text: str) -> None:
        path = out_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        artifacts.append(rel)

    def labels_for(locale: str, is_default: bool) -> list:
        out = []
        for label in build_labels(buttons, words):
            value = label if is_default else f"{label} [{locale}]"
            out.append(f"\u202b{value}\u202c" if locale in RTL_LOCALES else value)
        return out

    default_locale = locales[0] if locales else "en"
    named_default = locale_named(default_locale)
    write("res/values/strings.xml", build_strings_xml(
        seed, named_default, labels_for(default_locale, True)))

    for locale in locales[1:]:
        write(f"res/{locale_dir(locale)}/strings.xml", build_strings_xml(
            seed, locale_named(locale), labels_for(locale, False)))

    # R2.3 (AUDIT_ROADMAP_V2): assets/locales/<tag>/strings.properties —
    # os NAMED_STRINGS localizados como asset REAL e USADO em runtime
    # (:app EngineProbeActivity + :compose ComposeProbeActivity leem este
    # arquivo; a categoria "locales" do size-report passa a ter bytes).
    write("assets/locales/en/strings.properties",
          build_locale_properties(seed, named_default))
    for locale in locales[1:]:
        write(f"assets/locales/{locale}/strings.properties",
              build_locale_properties(seed, locale_named(locale)))

    if pseudolocale:
        enxa_named = {k: apply_pseudo_en_xa(v) for k, v in named_default.items()}
        enxa_labels = [apply_pseudo_en_xa(v) for v in labels_for("en", True)]
        write(f"res/{locale_dir(PSEUDO_EN_XA)}/strings.xml", build_strings_xml(
            seed, enxa_named, enxa_labels))
        ar_named = locale_named("ar")
        arxb_labels = [apply_pseudo_ar_xb(v) for v in labels_for("ar", False)]
        write(f"res/{locale_dir(PSEUDO_AR_XB)}/strings.xml", build_strings_xml(
            seed, ar_named, arxb_labels))

    write_manifest(out_dir, "gen-strings.py", seed, artifacts)
    return artifacts


def run_selftest() -> int:
    """Gera em tempdir, reparseia com ElementTree e valida contagens/RTL."""
    try:
        with tempfile.TemporaryDirectory(prefix="apktester-gen-strings-") as tmp:
            root = Path(tmp)
            locales = [s.strip() for s in DEFAULT_LOCALES.split(",") if s.strip()]
            generate(root, DEFAULT_SEED, locales, DEFAULT_BUTTONS, True)

            text = (root / "res/values/strings.xml").read_text(encoding="utf-8")
            entries = ET.fromstring(text).findall("string")
            names = {e.attrib["name"]: (e.text or "") for e in entries}
            assert names["app_name"] == "APK Tester — Behemoth", "app_name divergiu"
            btn_keys = [k for k in names if k.startswith("btn_label_")]
            assert len(btn_keys) == DEFAULT_BUTTONS, f"labels={len(btn_keys)}"
            assert len(set(names[k] for k in btn_keys)) == DEFAULT_BUTTONS, \
                "labels de botão não são únicos"
            assert len(entries) == len(NAMED_STRINGS) + DEFAULT_BUTTONS, \
                f"total de strings={len(entries)}"
            assert "probe_running" in names and "probe_net_replay_hint" in names, \
                "probe_* ausentes"
            assert "'" not in text.replace("&apos;", ""), "apóstrofo cru no XML"

            for locale in locales[1:]:
                rel = f"res/{locale_dir(locale)}/strings.xml"
                ET.fromstring((root / rel).read_text(encoding="utf-8"))
            ar_text = (root / "res/values-ar/strings.xml").read_text(encoding="utf-8")
            assert "\u202b" in ar_text, "wrapping RTL ausente em values-ar"
            xa_rel = f"res/{locale_dir(PSEUDO_EN_XA)}/strings.xml"
            xa_text = (root / xa_rel).read_text(encoding="utf-8")
            assert "[Á" in xa_text or "[A" in xa_text, "pseudo en-rXA ausente"
            xb_rel = f"res/{locale_dir(PSEUDO_AR_XB)}/strings.xml"
            ET.fromstring((root / xb_rel).read_text(encoding="utf-8"))

            for locale in ("en",) + tuple(locales[1:]):
                rel = f"assets/locales/{locale}/strings.properties"
                props = (root / rel).read_text(encoding="utf-8")
                assert "app_name=" in props, f"app_name ausente: {rel}"
            pt_props = (root / "assets/locales/pt-BR/strings.properties"
                        ).read_text(encoding="utf-8")
            assert "Grade de Bot" in pt_props, \
                "traducao pt-BR ausente do asset"

            second = root / "second-run"
            generate(second, DEFAULT_SEED, locales, DEFAULT_BUTTONS, True)
            det_rels = (
                "res/values/strings.xml", "res/values-pt-rBR/strings.xml",
                "assets/locales/en/strings.properties",
                "assets/locales/pt-BR/strings.properties")
            for rel in det_rels:
                a = hashlib.sha256((root / rel).read_bytes()).hexdigest()
                b = hashlib.sha256((second / rel).read_bytes()).hexdigest()
                assert a == b, f"saída não determinística: {rel}"
    except AssertionError as exc:
        print(f"gen-strings selftest: FAIL ({exc})")
        return 1
    print("gen-strings selftest: OK")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Gera strings.xml do flagship (locales + pseudolocales).")
    parser.add_argument("--out", help="diretório de saída (obrigatório)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--locales", default=DEFAULT_LOCALES,
                        help="lista separada por vírgulas (1ª = default)")
    parser.add_argument("--buttons", type=int, default=DEFAULT_BUTTONS,
                        help="quantidade de btn_label_NNNN (default 1200)")
    parser.add_argument("--pseudolocale", action="store_true",
                        help="adiciona values-en-rXA e values-ar-rXB")
    parser.add_argument("--selftest", action="store_true",
                        help="roda asserções internas e sai com 0/1")
    args = parser.parse_args(argv)
    if args.selftest:
        return run_selftest()
    if not args.out:
        parser.error("--out é obrigatório (ou use --selftest)")
    locales = [s.strip() for s in args.locales.split(",") if s.strip()]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts = generate(out_dir, args.seed, locales, args.buttons,
                         args.pseudolocale)
    print(f"gen-strings: {len(artifacts)} artefatos gravados em {out_dir} "
          f"(seed={args.seed})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
