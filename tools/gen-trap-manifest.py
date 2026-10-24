#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen-trap-manifest.py — conjunto de armadilhas exported-audit (APK Tester).

Fonte ÚNICA da fixture exported-audit (parser-torture): a tabela TRAPS abaixo
gera o AndroidManifest.xml, os POJOs Java, traps-report.json e o auditoria
exported-audit-traps.md — zero drift por construção. O fixture-pack (modo
exported-audit) consome o manifesto + src/ desta saída; os contratos
commitados são renderizados pelo tools/gen-torture-contracts.py com os
MESMOS builders.

As violações (exported sem permissão, provider mundialmente acessível,
foregroundServiceType sem a permissão exigida etc.) são INTENCIONAIS: a
fixture existe para o relato de auditoria do RustyDroid (manifest-as-truth,
CORE-12). Instalar em dispositivo real NÃO é o objetivo.

Pacote dev.apktester.fixture.exportedaudit — minSdk 26, targetSdk 36,
versionCode 900036, uses-permission APENAS android.permission.INTERNET.
Os POJOs não importam android.* (javac roda sem android.jar).

Uso:
  python3 tools/gen-trap-manifest.py --out DIR [--seed N]
  python3 tools/gen-trap-manifest.py --selftest
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET

DEFAULT_SEED = 20261022
TOOL = "gen-trap-manifest.py"
PACKAGE = "dev.apktester.fixture.exportedaudit"
PKG_PATH = PACKAGE.replace(".", "/")
MIN_SDK, TARGET_SDK = 26, 36
VERSION_CODE, VERSION_NAME = 900036, "1.0.0"
JAVA_SEED = DEFAULT_SEED
ACTION_OPEN = f"{PACKAGE}.action.OPEN"
AUTH_OPEN = f"{PACKAGE}.open"
AUTH_GRANT = f"{PACKAGE}.grant"

# Tabela TRAPS — fonte única (manifesto, POJOs, auditoria e relato). Ordens
# aqui definem a ordem no manifesto. baseline=True não é armadilha: entra no
# relato como contraprova (o relato NÃO deve apontá-lo como achado).
TRAPS = [
    {
        "id": "T1", "kind": "activity", "class": ".TrapExportedNoPermActivity",
        "exported": True, "baseline": False,
        "issue": "activity exportada sem android:permission",
        "expected_finding": "componente exportado sem permissão de invocação "
                            "— qualquer app pode iniciá-la",
        "comment": "armadilha: activity exportada sem permissão",
    },
    {
        "id": "T2", "kind": "activity", "class": ".TrapLauncherActivity",
        "exported": True, "baseline": True,
        "filters": [{"action": "android.intent.action.MAIN",
                     "categories": ["android.intent.category.LAUNCHER"]}],
        "issue": "nenhum — baseline de launcher",
        "expected_finding": "launcher padrão; o relato NÃO deve apontá-la "
                            "como achado",
        "comment": "baseline: entry point legítimo",
    },
    {
        "id": "T3", "kind": "activity-alias", "class": ".TrapAlias",
        "target_activity": ".TrapLauncherActivity",
        "exported": False, "baseline": False,
        "issue": "alias oculto (exported=false) apontando para activity "
                 "exportada",
        "expected_finding": "divergência alias x alvo: o alias não deve "
                            "herdar a exposição do targetActivity",
        "comment": "armadilha: alias oculto divergente do alvo exportado",
    },
    {
        "id": "T4", "kind": "service", "class": ".TrapExportedService",
        "exported": True, "baseline": False,
        "issue": "service exportado sem android:permission",
        "expected_finding": "serviço exportado sem permissão — qualquer app "
                            "pode bind/start",
        "comment": "armadilha: serviço exportado sem permissão",
    },
    {
        "id": "T5", "kind": "service", "class": ".TrapBoundService",
        "exported": False, "baseline": True,
        "issue": "nenhum — baseline de serviço privado",
        "expected_finding": "serviço privado; o relato NÃO deve apontá-lo "
                            "como achado",
        "comment": "baseline: serviço privativo",
    },
    {
        "id": "T6", "kind": "receiver", "class": ".TrapOpenReceiver",
        "exported": True, "baseline": False,
        "filters": [{"action": ACTION_OPEN, "categories": []}],
        "issue": "receiver aberto por intent-filter (action custom) sem "
                 "android:permission",
        "expected_finding": "receiver implicitamente exportado sem permissão "
                            "de broadcast",
        "comment": "armadilha: receiver aberto",
    },
    {
        "id": "T7", "kind": "provider", "class": ".TrapOpenProvider",
        "exported": True, "baseline": False,
        "authorities": AUTH_OPEN,
        "issue": "provider exportado SEM readPermission/writePermission "
                 "(mundialmente legível e gravável)",
        "expected_finding": "provider exportado sem guarda de leitura/escrita "
                            "— armadilha forte",
        "comment": "armadilha forte: provider mundialmente legível/gravável",
    },
    {
        "id": "T8", "kind": "provider", "class": ".TrapGrantProvider",
        "exported": False, "baseline": False,
        "authorities": AUTH_GRANT,
        "grant_uri_permissions": True, "grant_path_pattern": "/.*",
        "issue": "grantUriPermissions=true com pathPattern amplo /.*",
        "expected_finding": "concessão de URI ampla: acesso delegável a "
                            "qualquer caminho do provider",
        "comment": "armadilha: grant amplo",
    },
    {
        "id": "T9", "kind": "service", "class": ".TrapForegroundTypeService",
        "exported": False, "baseline": False,
        "foreground_service_type": "location",
        "issue": "foregroundServiceType=location sem ACCESS_FINE_LOCATION "
                 "nem FOREGROUND_SERVICE declaradas",
        "expected_finding": "tipo em foreground sem a permissão exigida "
                            "(regra de targetSdk 34+)",
        "comment": "armadilha: foregroundServiceType sem a permissão exigida",
    },
]

JAVA_CLASSES = [t for t in TRAPS if t["kind"] != "activity-alias"]
BASELINES = [t for t in TRAPS if t["baseline"]]


def component_counts() -> dict:
    """Contagem por kind na ordem do traps-report.json."""
    counts = {"activities": 0, "activity_alias": 0, "services": 0,
              "receivers": 0, "providers": 0}
    for t in TRAPS:
        key = {"activity": "activities",
               "activity-alias": "activity_alias",
               "service": "services", "receiver": "receivers",
               "provider": "providers"}[t["kind"]]
        counts[key] += 1
    return counts


# ------------------------------------------------------------------ builders
def build_manifest_xml() -> str:
    """AndroidManifest.xml das 9 armadilhas (aapt2-safe, determinístico)."""
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<!-- ARMADILHAS INTENCIONAIS (ver exported-audit-traps.md). Gerado',
        f'     por tools/{TOOL} — NAO editar a mao; regenere com a ferramenta. -->',
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android"',
        f'    package="{PACKAGE}"',
        f'    android:versionCode="{VERSION_CODE}"',
        f'    android:versionName="{VERSION_NAME}">',
        '',
        f'    <uses-sdk android:minSdkVersion="{MIN_SDK}"',
        f'              android:targetSdkVersion="{TARGET_SDK}"/>',
        '',
        '    <uses-permission android:name="android.permission.INTERNET"/>',
        '',
        '    <application android:label="@string/app_name" android:hasCode="true">',
    ]
    for t in TRAPS:
        lines.append(f'        <!-- {t["id"]} — {t["comment"]} -->')
        kind = t["kind"]
        if kind == "activity":
            exported = str(t["exported"]).lower()
            lines.append(f'        <activity android:name="{t["class"]}"'
                         f' android:exported="{exported}">')
            for f in t.get("filters", []):
                lines.append('            <intent-filter>')
                lines.append(f'                <action android:name="{f["action"]}"/>')
                for cat in f["categories"]:
                    lines.append(f'                <category android:name="{cat}"/>')
                lines.append('            </intent-filter>')
            lines.append('        </activity>')
        elif kind == "activity-alias":
            lines.append(f'        <activity-alias android:name="{t["class"]}"')
            lines.append(f'                  android:targetActivity="{t["target_activity"]}"')
            lines.append('                  android:exported="false"/>')
        elif kind == "service":
            fst = t.get("foreground_service_type")
            extra = f' android:foregroundServiceType="{fst}"' if fst else ""
            lines.append(f'        <service android:name="{t["class"]}"'
                         f' android:exported="{str(t["exported"]).lower()}"{extra}/>')
        elif kind == "receiver":
            lines.append(f'        <receiver android:name="{t["class"]}"'
                         f' android:exported="true">')
            for f in t.get("filters", []):
                lines.append('            <intent-filter>')
                lines.append(f'                <action android:name="{f["action"]}"/>')
                for cat in f["categories"]:
                    lines.append(f'                <category android:name="{cat}"/>')
                lines.append('            </intent-filter>')
            lines.append('        </receiver>')
        else:  # provider
            exported = str(t["exported"]).lower()
            lines.append(f'        <provider android:name="{t["class"]}"')
            lines.append(f'                  android:authorities="{t["authorities"]}"')
            if t.get("grant_uri_permissions"):
                lines.append(f'                  android:exported="{exported}"')
                lines.append('                  android:grantUriPermissions="true">')
                lines.append(f'            <grant-uri-permission android:pathPattern="{t["grant_path_pattern"]}"/>')
                lines.append('        </provider>')
            else:
                # T7: SEM readPermission/writePermission — é a armadilha forte.
                lines.append(f'                  android:exported="{exported}"/>')
    lines += ['    </application>', '</manifest>', '']
    return "\n".join(lines)


JAVA_TEMPLATE = '''package {package};

/** {tid} — {comment} (gerado por tools/gen-trap-manifest.py; fonte única
 *  da tabela TRAPS — NAO editar a mao). POJO sem imports android.*: javac
 *  roda sem android.jar; a verdade de componentes é o manifesto (CORE-12). */
public final class {cls} {{

    public static final int SEED = {seed};

    public String role() {{
        return "{role}";
    }}

    public String fixture() {{
        return "exported-audit";
    }}

    public String trap() {{
        return "{tid}";
    }}

    public int checksum() {{
        int h = SEED;
        for (char c : trap().toCharArray()) {{
            h = 31 * h + c;
        }}
        return h;
    }}
}}
'''


def java_sources() -> dict:
    """Um POJO por classe real (o alias não precisa de classe)."""
    out = {}
    for t in JAVA_CLASSES:
        out[f"src/{PKG_PATH}/{t['class'].lstrip('.')}.java"] = \
            JAVA_TEMPLATE.format(package=PACKAGE, tid=t["id"],
                                 comment=t["comment"],
                                 cls=t["class"].lstrip("."),
                                 role=t["kind"], seed=JAVA_SEED)
    return out


def build_report_json() -> str:
    """traps-report.json — contagens + as 9 entradas com issue/achado esperado."""
    doc = {
        "schema_version": 1,
        "generated_by": f"tools/{TOOL}",
        "seed": DEFAULT_SEED,
        "package": PACKAGE,
        "min_sdk": MIN_SDK,
        "target_sdk": TARGET_SDK,
        "components": component_counts(),
        "traps": [{"id": t["id"], "class": t["class"], "kind": t["kind"],
                   "issue": t["issue"], "expected_finding": t["expected_finding"]}
                  for t in TRAPS],
        "baselines": len(BASELINES),
    }
    return json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def build_audit_md() -> str:
    """exported-audit-traps.md — auditoria PT-BR das 9 armadilhas."""
    lines = []
    add = lines.append
    add("# Exported Audit — armadilhas de manifesto (fixture exported-audit)")
    add("")
    add(f"Gerado por `tools/{TOOL}` (seed {DEFAULT_SEED}) a partir da MESMA")
    add("tabela TRAPS que emite o manifesto e os POJOs — zero drift.")
    add("")
    add("> **AVISO:** as violações abaixo são **INTENCIONAIS**. A fixture")
    add("> existe para o relato de auditoria do RustyDroid")
    add("> (manifest-as-truth, CORE-12). Instalar em dispositivo real NÃO é")
    add("> o objetivo — e as permissões ausentes são parte do gabarito.")
    add("")
    add(f"Pacote `{PACKAGE}` · minSdk {MIN_SDK} · targetSdk {TARGET_SDK} · "
        f"versionCode {VERSION_CODE} · uses-permission: apenas "
        "`android.permission.INTERNET`.")
    add("")
    add("| ID | Componente | O que está errado | O que o relato do RustyDroid DEVE apontar |")
    add("|---|---|---|---|")
    for t in TRAPS:
        comp = f"{t['kind']} `{t['class']}`"
        wrong = t["issue"] if not t["baseline"] else f"(baseline) {t['issue']}"
        add(f"| {t['id']} | {comp} | {wrong} | {t['expected_finding']} |")
    add("")
    add(f"São {len(TRAPS)} componentes: {len(TRAPS) - len(BASELINES)} "
        f"armadilhas + {len(BASELINES)} baselines (T2, T5) de contraprova.")
    add("")
    add("## Zero drift")
    add("")
    add(f"Manifesto, POJOs, `traps-report.json` e esta auditoria saem da MESMA "
        f"tabela TRAPS em `tools/{TOOL}`. O CI compara o relato do RustyDroid "
        "com `traps-report.json` (9 entradas, sendo 2 baselines que NÃO devem "
        "virar achados). Regenerar: `python3 tools/gen-trap-manifest.py --out <dir>`.")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ generate
def generate(out_dir: str) -> dict:
    outputs = {"AndroidManifest.xml": build_manifest_xml(),
               "exported-audit-traps.md": build_audit_md(),
               "traps-report.json": build_report_json()}
    outputs.update(java_sources())
    artifacts = []
    for rel in sorted(outputs):
        full = os.path.join(out_dir, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(outputs[rel])
        data = outputs[rel].encode("utf-8")
        artifacts.append({"path": rel, "bytes": len(data),
                          "sha256": hashlib.sha256(data).hexdigest()})
    ledger = {"tool": f"tools/{TOOL}", "seed": DEFAULT_SEED,
              "note": "gerado; NAO editar a mao — regenere com a ferramenta",
              "artifacts": artifacts}
    with open(os.path.join(out_dir, "manifest.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(ledger, ensure_ascii=False, indent=2,
                            sort_keys=True) + "\n")
    return outputs


def selftest() -> int:
    """Duas gerações byte-idênticas + estrutura do manifesto + coerência."""
    tmp = tempfile.mkdtemp(prefix="apktester-traps-")
    try:
        a = generate(os.path.join(tmp, "a"))
        b = generate(os.path.join(tmp, "b"))
        for rel, text in a.items():
            assert text == b[rel], f"determinismo quebrado em {rel}"

        ns = "{http://schemas.android.com/apk/res/android}"
        root = ET.fromstring(a["AndroidManifest.xml"])
        assert root.tag == "manifest"
        assert root.attrib["package"] == PACKAGE
        app = root.find("application")
        assert app is not None and app.attrib[f"{ns}hasCode"] == "true"
        tags = {}
        exported_by_class = {}
        for child in app:
            tag = child.tag
            tags[tag] = tags.get(tag, 0) + 1
            exported_by_class[child.attrib[f"{ns}name"]] = \
                child.attrib.get(f"{ns}exported")
        assert tags == {"activity": 2, "activity-alias": 1, "service": 3,
                        "receiver": 1, "provider": 2}, f"tags {tags}"

        perms = [c.attrib[f"{ns}name"] for c in root.findall("uses-permission")]
        assert perms == ["android.permission.INTERNET"], f"perms {perms}"

        # Armadilhas específicas no XML bruto (o parser genérico não cobre).
        raw = a["AndroidManifest.xml"]
        assert 'android:targetActivity=".TrapLauncherActivity"' in raw
        assert 'android:foregroundServiceType="location"' in raw
        assert 'android:grantUriPermissions="true"' in raw
        assert '<grant-uri-permission android:pathPattern="/.*"/>' in raw
        assert raw.count('android:readPermission') == 0, \
            "T7 não pode ter guarda de leitura"
        assert raw.count('android:writePermission') == 0
        assert exported_by_class[".TrapOpenProvider"] == "true"
        assert exported_by_class[".TrapAlias"] == "false"
        assert exported_by_class[".TrapBoundService"] == "false"

        report = json.loads(a["traps-report.json"])
        assert len(report["traps"]) == 9
        assert report["components"] == component_counts()
        assert report["components"] == {"activities": 2, "activity_alias": 1,
                                        "services": 3, "receivers": 1,
                                        "providers": 2}
        assert report["baselines"] == 2
        assert [t["id"] for t in report["traps"]] == \
            [f"T{i}" for i in range(1, 10)]

        md = a["exported-audit-traps.md"]
        for t in TRAPS:
            assert t["id"] in md and t["class"].lstrip(".") in md, \
                f"{t['id']} ausente do audit"
        assert "INTENCIONAIS" in md

        java = {k: v for k, v in a.items() if k.startswith("src/")}
        assert len(java) == len(JAVA_CLASSES) == 8
        for rel, text in java.items():
            assert "import android" not in text, f"{rel} importa android.*"
            assert "public String trap()" in text
        print(f"[{TOOL}] selftest OK: manifesto com {len(TRAPS)} componentes "
              f"({len(BASELINES)} baselines), 8 POJOs sem android.*, "
              "report/audit coerentes, 2 gerações byte-idênticas")
        return 0
    except AssertionError as exc:
        print(f"[{TOOL}] selftest FALHOU: {exc}", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Armadilhas exported-audit (APK Tester, parser-torture).")
    ap.add_argument("--out", help="diretório de saída (manifesto + src/ + "
                                  "auditoria + report)")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED,
                    help=f"semente determinística (padrão: {DEFAULT_SEED})")
    ap.add_argument("--selftest", action="store_true",
                    help="auto-validação em tmp e sai")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.out:
        ap.error("--out é obrigatório (ou use --selftest)")
    outputs = generate(args.out)
    print(f"[{TOOL}] {len(outputs)} arquivos em {args.out}: manifesto com "
          f"{len(TRAPS)} componentes ({len(TRAPS) - len(BASELINES)} armadilhas "
          f"+ {len(BASELINES)} baselines), {len(JAVA_CLASSES)} POJOs, "
          "traps-report.json e exported-audit-traps.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
