#!/usr/bin/env python3
"""Gerador das fontes ButtonGrid + IconGrid do APK Tester ("Behemoth").

Fase: A0/A1 — geradores core. Produz as fontes Kotlin (framework-only, sem
androidx) e os layouts XML da grade de 1200 botões (btn_0001..btn_1200, com
content-desc estável "Button N of 1200" e labels via btn_label_NNNN) e da
grade de 600 ImageViews (ic_0001..ic_0600 -> R.drawable.ic_vector_NNNN).
Cada clique emite uma linha JSON de probe no logcat, tag "MAXPROBE/UI",
no contrato assets/probe/maxprobe-report.schema.json (gerado por gen-assets).

Determinístico por --seed (afeta comentários/ordem estável, não há PRNG de
conteúdo). Apenas stdlib python3; manifest.json com sha256 por artefato.

Uso:
    python3 tools/gen-buttons.py --out /tmp/out [--buttons 1200] [--icons 600]
    python3 tools/gen-buttons.py --selftest
"""

import argparse
import hashlib
import json
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

DEFAULT_SEED = 20261022
DEFAULT_BUTTONS = 1200
DEFAULT_ICONS = 600
NS = "http://schemas.android.com/apk/res/android"
UI_PACKAGE = "dev.apktester.behemoth.ui"
APP_PACKAGE = "dev.apktester.behemoth"
PROBE_TAG = "MAXPROBE/UI"

FRAGMENT_XML_TMPL = """<?xml version="1.0" encoding="utf-8"?>
<!-- Gerado por tools/gen-buttons.py seed={seed} - fixture deterministica -->
<ScrollView xmlns:android="{ns}"
    android:id="@+id/{grid_id}_scroll"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:fillViewport="true">

    <GridLayout
        android:id="@+id/{grid_id}"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:columnCount="{columns}"
        android:useDefaultMargins="true" />
</ScrollView>
"""

ITEM_BUTTON_XML_TMPL = """<?xml version="1.0" encoding="utf-8"?>
<!-- Template de célula do ButtonGrid; os {count} botões reais são criados
     em código (ButtonGridFragment) para manter os ids/labels determinísticos -->
<FrameLayout xmlns:android="{ns}"
    android:layout_width="match_parent"
    android:layout_height="wrap_content">

    <Button
        android:id="@+id/btn_item_template"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:contentDescription="@string/btn_content_desc"
        android:ellipsize="end"
        android:maxLines="1"
        android:tag="btn_item_template" />
</FrameLayout>
"""


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


def build_button_fragment(buttons: int, columns: int) -> str:
    """Gera ui/ButtonGridFragment.kt: 1200 botões criados em código."""
    lines = [
        f"package {UI_PACKAGE}",
        "",
        "import android.app.Fragment",
        "import android.os.Bundle",
        "import android.os.SystemClock",
        "import android.util.Log",
        "import android.view.LayoutInflater",
        "import android.view.View",
        "import android.view.ViewGroup",
        "import android.widget.Button",
        "import android.widget.GridLayout",
        "import android.widget.ScrollView",
        "",
        "/**",
        " * ButtonGrid: 1200 botões determinísticos (fixture de automação AG-01/AG-02).",
        " * Gerado por tools/gen-buttons.py — NÃO editar manualmente; reexecute o gerador.",
        " * Ids lógicos estáveis btn_0001..btn_1200 (tag) + view.id numérico ID_BASE + i.",
        " * Labels vêm de @string/btn_label_NNNN (tools/gen-strings.py).",
        " * Probe: linha JSON no logcat, tag MAXPROBE/UI (contrato maxprobe-report).",
        " */",
        "class ButtonGridFragment : Fragment() {",
        "",
        "    companion object {",
f'        const val TAG = "{PROBE_TAG}"',
        f"        const val BUTTON_COUNT = {buttons}",
        f"        const val GRID_COLUMNS = {columns}",
        "        const val ID_BASE = 0x7F0B0000",
        "",
        "        // Um id lógico por linha: diff estável no git e grep fácil.",
        "        val BUTTON_IDS: Array<String> = arrayOf(",
    ]
    for i in range(1, buttons + 1):
        comma = "," if i < buttons else ""
        lines.append(f'            "btn_{i:04d}"{comma}')
    lines += [
        "        )",
        "    }",
        "",
        "    override fun onCreateView(",
        "        inflater: LayoutInflater,",
        "        container: ViewGroup?,",
        "        savedInstanceState: Bundle?",
        "    ): View {",
        '        val ctx = activity ?: error("ButtonGridFragment requer Activity")',
        "        val grid = GridLayout(ctx)",
        "        grid.columnCount = GRID_COLUMNS",
        "        grid.useDefaultMargins = true",
        "        for (i in 0 until BUTTON_COUNT) {",
        "            val logicalId = BUTTON_IDS[i]",
        "            val button = Button(ctx)",
        "            button.id = ID_BASE + i + 1",
        "            button.tag = logicalId",
        "            button.setAllCaps(false)",
        '            button.contentDescription = String.format("Button %d of %d",',
        "                i + 1, BUTTON_COUNT)",
        '            val labelRes = resources.getIdentifier(logicalId, "string",',
        "                ctx.packageName)",
        "            button.text = if (labelRes != 0) resources.getString(labelRes)",
        "                else logicalId",
        "            button.setOnClickListener { v -> emitProbe(v) }",
        "            val rowSpec = GridLayout.spec(GridLayout.UNDEFINED, 1.0f)",
        "            val colSpec = GridLayout.spec(GridLayout.UNDEFINED, 1.0f)",
        "            button.layoutParams = GridLayout.LayoutParams(rowSpec, colSpec)",
        "            grid.addView(button)",
        "        }",
        "        val scroll = ScrollView(ctx)",
        "        scroll.layoutParams = ViewGroup.LayoutParams(",
        "            ViewGroup.LayoutParams.MATCH_PARENT,",
        "            ViewGroup.LayoutParams.MATCH_PARENT)",
        "        scroll.addView(grid)",
        "        return scroll",
        "    }",
        "",
        "    /** Emite a linha JSON de probe {id,module_id,domain,api,result,duration_ms}. */",
        "    private fun emitProbe(view: View) {",
        "        val startedAt = SystemClock.elapsedRealtime()",
        "        val durationMs = SystemClock.elapsedRealtime() - startedAt",
        '        val line = "{\\"id\\":\\"" + view.tag + "\\",\\"module_id\\":\\"UI\\"," +',
        '            "\\"domain\\":\\"widgets\\",\\"api\\":\\"Button.onClick\\"," +',
        '            "\\"result\\":\\"OK\\",\\"error\\":null,\\"duration_ms\\":" +',
        '            durationMs + "}"',
        "        Log.i(TAG, line)",
        "    }",
        "}",
        "",
    ]
    return "\n".join(lines)


def build_icon_fragment(icons: int, columns: int) -> str:
    """Gera ui/IconGridFragment.kt: 600 ImageViews -> R.drawable.ic_vector_NNNN."""
    lines = [
        f"package {UI_PACKAGE}",
        "",
        f"import {APP_PACKAGE}.R",
        "import android.app.Fragment",
        "import android.os.Bundle",
        "import android.os.SystemClock",
        "import android.util.Log",
        "import android.view.LayoutInflater",
        "import android.view.View",
        "import android.view.ViewGroup",
        "import android.widget.GridLayout",
        "import android.widget.ImageView",
        "import android.widget.ScrollView",
        "",
        "/**",
        " * IconGrid: 600 ImageViews determinísticos (fixture de automação AG-01/AG-02).",
        " * Gerado por tools/gen-buttons.py — NÃO editar manualmente; reexecute o gerador.",
        " * Ids lógicos ic_0001..ic_0600 (tag) + view.id numérico ID_BASE + i.",
        " * Cada ImageView faz setImageResource(R.drawable.ic_vector_NNNN) (gen-icons).",
        " */",
        "class IconGridFragment : Fragment() {",
        "",
        "    companion object {",
f'        const val TAG = "{PROBE_TAG}"',
        f"        const val ICON_COUNT = {icons}",
        f"        const val GRID_COLUMNS = {columns}",
        "        const val ID_BASE = 0x7F0C0000",
        "",
        "        // Um id lógico por linha: diff estável no git e grep fácil.",
        "        val ICON_IDS: Array<String> = arrayOf(",
    ]
    for i in range(1, icons + 1):
        comma = "," if i < icons else ""
        lines.append(f'            "ic_{i:04d}"{comma}')
    lines.append("        )")
    lines.append("")
    lines.append("        // Referências diretas a R.drawable: resolução estática garantida.")
    lines.append("        val ICON_RES_IDS: IntArray = intArrayOf(")
    for start in range(1, icons + 1, 3):
        chunk = [f"R.drawable.ic_vector_{n:04d}"
                 for n in range(start, min(start + 3, icons + 1))]
        tail = "," if start + 3 <= icons else ""
        lines.append("            " + ", ".join(chunk) + tail)
    lines += [
        "        )",
        "    }",
        "",
        "    override fun onCreateView(",
        "        inflater: LayoutInflater,",
        "        container: ViewGroup?,",
        "        savedInstanceState: Bundle?",
        "    ): View {",
        '        val ctx = activity ?: error("IconGridFragment requer Activity")',
        "        val grid = GridLayout(ctx)",
        "        grid.columnCount = GRID_COLUMNS",
        "        grid.useDefaultMargins = true",
        "        for (i in 0 until ICON_COUNT) {",
        "            val image = ImageView(ctx)",
        "            image.id = ID_BASE + i + 1",
        "            image.tag = ICON_IDS[i]",
        "            image.scaleType = ImageView.ScaleType.FIT_CENTER",
        '            image.contentDescription = String.format("Icon %d of %d",',
        "                i + 1, ICON_COUNT)",
        "            image.setImageResource(ICON_RES_IDS[i])",
        "            image.setOnClickListener { v -> emitProbe(v) }",
        "            val rowSpec = GridLayout.spec(GridLayout.UNDEFINED, 1.0f)",
        "            val colSpec = GridLayout.spec(GridLayout.UNDEFINED, 1.0f)",
        "            image.layoutParams = GridLayout.LayoutParams(rowSpec, colSpec)",
        "            grid.addView(image)",
        "        }",
        "        val scroll = ScrollView(ctx)",
        "        scroll.layoutParams = ViewGroup.LayoutParams(",
        "            ViewGroup.LayoutParams.MATCH_PARENT,",
        "            ViewGroup.LayoutParams.MATCH_PARENT)",
        "        scroll.addView(grid)",
        "        return scroll",
        "    }",
        "",
        "    /** Emite a linha JSON de probe {id,module_id,domain,api,result,duration_ms}. */",
        "    private fun emitProbe(view: View) {",
        "        val startedAt = SystemClock.elapsedRealtime()",
        "        val durationMs = SystemClock.elapsedRealtime() - startedAt",
        '        val line = "{\\"id\\":\\"" + view.tag + "\\",\\"module_id\\":\\"UI\\"," +',
        '            "\\"domain\\":\\"widgets\\",\\"api\\":\\"ImageView.onClick\\"," +',
        '            "\\"result\\":\\"OK\\",\\"error\\":null,\\"duration_ms\\":" +',
        '            durationMs + "}"',
        "        Log.i(TAG, line)",
        "    }",
        "}",
        "",
    ]
    return "\n".join(lines)


def generate(out_dir: Path, seed: int, buttons: int, icons: int) -> list:
    """Grava os 5 artefatos ui/ + manifest.json; devolve caminhos relativos."""
    artifacts = []

    def write(rel: str, text: str) -> None:
        path = out_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        artifacts.append(rel)

    write("ui/ButtonGridFragment.kt", build_button_fragment(buttons, 4))
    write("ui/IconGridFragment.kt", build_icon_fragment(icons, 8))
    write("ui/res/layout/fragment_button_grid.xml", FRAGMENT_XML_TMPL.format(
        seed=seed, ns=NS, grid_id="button_grid", columns=4))
    write("ui/res/layout/fragment_icon_grid.xml", FRAGMENT_XML_TMPL.format(
        seed=seed, ns=NS, grid_id="icon_grid", columns=8))
    write("ui/res/layout/grid_item_button.xml", ITEM_BUTTON_XML_TMPL.format(
        seed=seed, ns=NS, count=buttons))
    write_manifest(out_dir, "gen-buttons.py", seed, artifacts)
    return artifacts


def run_selftest() -> int:
    """Gera em tempdir e valida: 1200 btn ids, 600 ic ids, sem androidx."""
    try:
        with tempfile.TemporaryDirectory(prefix="apktester-gen-buttons-") as tmp:
            root = Path(tmp)
            generate(root, DEFAULT_SEED, DEFAULT_BUTTONS, DEFAULT_ICONS)
            btn_kt = (root / "ui/ButtonGridFragment.kt").read_text("utf-8")
            ic_kt = (root / "ui/IconGridFragment.kt").read_text("utf-8")

            btn_ids = re.findall(r'"(btn_\d{4})"', btn_kt)
            assert len(btn_ids) == DEFAULT_BUTTONS, f"btn ids={len(btn_ids)}"
            assert len(set(btn_ids)) == DEFAULT_BUTTONS, "btn ids duplicados"
            assert btn_ids[0] == "btn_0001" and btn_ids[-1] == "btn_1200"
            assert "Button %d of %d" in btn_kt, "content-desc estável ausente"
            assert "MAXPROBE/UI" in btn_kt and "btn_label_" in btn_kt

            ic_ids = re.findall(r'"(ic_\d{4})"', ic_kt)
            assert len(ic_ids) == DEFAULT_ICONS, f"ic ids={len(ic_ids)}"
            assert len(set(ic_ids)) == DEFAULT_ICONS, "ic ids duplicados"
            refs = re.findall(r"R\.drawable\.ic_vector_\d{4}", ic_kt)
            assert len(refs) == DEFAULT_ICONS, f"refs R.drawable={len(refs)}"
            assert "setImageResource" in ic_kt

            for kt in (btn_kt, ic_kt):
                assert "androidx" not in kt, "androidx proibido (framework-only)"
                assert "import android." in kt
            for rel in ("ui/res/layout/fragment_button_grid.xml",
                        "ui/res/layout/fragment_icon_grid.xml",
                        "ui/res/layout/grid_item_button.xml"):
                parsed = ET.fromstring((root / rel).read_text("utf-8"))
                assert parsed.tag in ("ScrollView", "FrameLayout"), parsed.tag

            second = root / "second-run"
            generate(second, DEFAULT_SEED, DEFAULT_BUTTONS, DEFAULT_ICONS)
            for rel in ("ui/ButtonGridFragment.kt", "ui/IconGridFragment.kt"):
                a = hashlib.sha256((root / rel).read_bytes()).hexdigest()
                b = hashlib.sha256((second / rel).read_bytes()).hexdigest()
                assert a == b, f"saída não determinística: {rel}"
    except AssertionError as exc:
        print(f"gen-buttons selftest: FAIL ({exc})")
        return 1
    print("gen-buttons selftest: OK")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Gera ButtonGrid/IconGrid (Kotlin framework-only + layouts).")
    parser.add_argument("--out", help="diretório de saída (obrigatório)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--buttons", type=int, default=DEFAULT_BUTTONS,
                        help="quantidade de botões (default 1200)")
    parser.add_argument("--icons", type=int, default=DEFAULT_ICONS,
                        help="quantidade de ImageViews (default 600)")
    parser.add_argument("--selftest", action="store_true",
                        help="roda asserções internas e sai com 0/1")
    args = parser.parse_args(argv)
    if args.selftest:
        return run_selftest()
    if not args.out:
        parser.error("--out é obrigatório (ou use --selftest)")
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts = generate(out_dir, args.seed, args.buttons, args.icons)
    print(f"gen-buttons: {len(artifacts)} artefatos gravados em {out_dir} "
          f"(seed={args.seed})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
