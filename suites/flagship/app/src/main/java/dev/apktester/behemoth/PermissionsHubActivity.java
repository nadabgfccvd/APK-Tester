package dev.apktester.behemoth;

import android.app.Activity;
import android.content.pm.PermissionInfo;
import android.graphics.Typeface;
import android.os.Build;
import android.os.Bundle;
import android.os.SystemClock;
import android.util.Log;
import android.util.TypedValue;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import dev.apktester.behemoth.probe.ProbeCatalog;
import dev.apktester.behemoth.probe.ProbeReporter;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Permissions Hub: um botao por permissao declarada no manifesto do
 * Behemoth (1006 permissoes de plataforma no snapshot AOSP da A1).
 *
 * A fonte e o asset permissions/permissions.tsv (gerado por
 * tools/gen-flagship-manifest.py), com colunas name, base_level, group,
 * maxSdkVersion e hide. As secoes seguem a ordem de protecao normal,
 * dangerous (sub-agrupado por grupo), signature, internal, role, system,
 * module e quaisquer tokens novos no fim, em ordem alfabetica.
 *
 * O toque em cada botao classifica a permissao via
 * PackageManager.getPermissionInfo (probe CORE-PM-001) e, para permissoes
 * dangerous em API 23+, dispara requestPermissions — permissoes
 * signature/@hide sao fixtures de classificacao e nunca serao concedidas
 * em dispositivo real (lei documentada no APK_TESTER_PROMPT).
 */
public class PermissionsHubActivity extends Activity {

    private static final String TAG = "MAXPROBE/CORE";

    /** Codigo de requisicao fixo do requestPermissions das permissoes dangerous. */
    private static final int REQUEST_CODE = 42;

    /** Ordem canonica das secoes por nivel de protecao. */
    private static final String[] SECTION_ORDER = {
        "normal", "dangerous", "signature", "internal", "role", "system", "module",
    };

    /** Linha do TSV de permissoes (colunas separadas por tabulacao). */
    private static final class PermissionRow {
        final String name;
        final String baseLevel;
        final String group;
        final String maxSdk;
        final String hideFlag;

        PermissionRow(String name, String baseLevel, String group,
                String maxSdk, String hideFlag) {
            this.name = name;
            this.baseLevel = baseLevel;
            this.group = group;
            this.maxSdk = maxSdk;
            this.hideFlag = hideFlag;
        }

        /** Nome curto sem o prefixo android.permission. */
        String shortName() {
            String prefix = "android.permission.";
            return name.startsWith(prefix) ? name.substring(prefix.length()) : name;
        }
    }

    /** Comparator alfabetico por nome completo da permissao. */
    private static final Comparator<PermissionRow> BY_NAME =
            new Comparator<PermissionRow>() {
                @Override
                public int compare(PermissionRow left, PermissionRow right) {
                    return left.name.compareTo(right.name);
                }
            };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_permissions_hub);
        LinearLayout list = (LinearLayout) findViewById(R.id.hub_list);
        long startedAt = SystemClock.uptimeMillis();
        List<PermissionRow> rows = loadRows();
        buildSections(list, rows);
        Log.i(TAG, "hub montado com " + rows.size() + " permissoes em "
                + (SystemClock.uptimeMillis() - startedAt) + " ms");
    }

    /** Le o asset TSV pulando comentarios; falhas devolvem lista parcial. */
    private List<PermissionRow> loadRows() {
        List<PermissionRow> rows = new ArrayList<PermissionRow>();
        BufferedReader reader = null;
        try {
            reader = new BufferedReader(new InputStreamReader(
                    getAssets().open("permissions/permissions.tsv"), "UTF-8"));
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.length() == 0 || line.startsWith("#")) {
                    continue;
                }
                String[] cols = line.split("\t", -1);
                if (cols.length < 5) {
                    continue;
                }
                rows.add(new PermissionRow(cols[0], cols[1], cols[2], cols[3], cols[4]));
            }
        } catch (IOException e) {
            Log.w(TAG, "falha ao ler permissions.tsv: " + e.getMessage());
        } finally {
            if (reader != null) {
                try {
                    reader.close();
                } catch (IOException e) {
                    Log.w(TAG, "fechamento do TSV falhou: " + e.getMessage());
                }
            }
        }
        return rows;
    }

    /** Monta as secoes na ordem canonica e anexa header + botoes ao hub. */
    private void buildSections(LinearLayout list, List<PermissionRow> rows) {
        Map<String, List<PermissionRow>> byLevel =
                new LinkedHashMap<String, List<PermissionRow>>();
        for (PermissionRow row : rows) {
            String level = row.baseLevel.length() == 0 ? "normal" : row.baseLevel;
            List<PermissionRow> bucket = byLevel.get(level);
            if (bucket == null) {
                bucket = new ArrayList<PermissionRow>();
                byLevel.put(level, bucket);
            }
            bucket.add(row);
        }
        List<String> levels = new ArrayList<String>();
        for (String known : SECTION_ORDER) {
            if (byLevel.containsKey(known)) {
                levels.add(known);
            }
        }
        List<String> extras = new ArrayList<String>(byLevel.keySet());
        extras.removeAll(levels);
        Collections.sort(extras);
        levels.addAll(extras);
        for (String level : levels) {
            addSection(list, level, byLevel.get(level));
        }
    }

    /** Uma secao: header com contagem, sub-grupos (dangerous) e botoes. */
    private void addSection(LinearLayout list, String level, List<PermissionRow> rows) {
        list.addView(buildHeader(level + " (" + rows.size() + ")", true));
        if ("dangerous".equals(level)) {
            addDangerousSubgroups(list, rows);
        } else {
            Collections.sort(rows, BY_NAME);
            for (PermissionRow row : rows) {
                list.addView(buildPermissionButton(row));
            }
        }
    }

    /** Secao dangerous dividida por grupo de permissao (ordem alfabetica). */
    private void addDangerousSubgroups(LinearLayout list, List<PermissionRow> rows) {
        Map<String, List<PermissionRow>> byGroup =
                new LinkedHashMap<String, List<PermissionRow>>();
        for (PermissionRow row : rows) {
            String group = row.group.length() == 0 ? "(sem grupo)" : row.group;
            List<PermissionRow> bucket = byGroup.get(group);
            if (bucket == null) {
                bucket = new ArrayList<PermissionRow>();
                byGroup.put(group, bucket);
            }
            bucket.add(row);
        }
        List<String> groups = new ArrayList<String>(byGroup.keySet());
        Collections.sort(groups);
        for (String group : groups) {
            List<PermissionRow> bucket = byGroup.get(group);
            list.addView(buildHeader(group + " (" + bucket.size() + ")", false));
            Collections.sort(bucket, BY_NAME);
            for (PermissionRow row : bucket) {
                list.addView(buildPermissionButton(row));
            }
        }
    }

    /** Header de secao (bold, maior) ou de sub-grupo. */
    private TextView buildHeader(String text, boolean section) {
        TextView header = new TextView(this);
        header.setText(text);
        header.setTextSize(TypedValue.COMPLEX_UNIT_SP, section ? 15 : 13);
        header.setTypeface(null, Typeface.BOLD);
        header.setPadding(dp(4), dp(section ? 14 : 8), dp(4), dp(4));
        return header;
    }

    /** Botao da permissao com marcadores de maxSdkVersion e @hide. */
    private Button buildPermissionButton(final PermissionRow row) {
        Button button = new Button(this);
        button.setText(row.shortName() + markers(row));
        button.setContentDescription(row.name);
        button.setTextSize(TypedValue.COMPLEX_UNIT_SP, 11);
        button.setSingleLine(true);
        button.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                inspectPermission(row);
            }
        });
        return button;
    }

    /** Marcadores textuais derivados do TSV ([maxSdk N] e [@hide]). */
    private String markers(PermissionRow row) {
        StringBuilder sb = new StringBuilder();
        if (row.maxSdk.length() > 0) {
            sb.append(" [maxSdk ").append(row.maxSdk).append(']');
        }
        if ("hide".equals(row.hideFlag)) {
            sb.append(" [@hide]");
        }
        return sb.toString();
    }

    /**
     * Classificacao da permissao: getPermissionInfo + decodificacao do
     * protectionLevel, registrada como probe CORE-PM-001. Para permissoes
     * dangerous em API 23+ tambem dispara o dialogo de concessao.
     */
    private void inspectPermission(PermissionRow row) {
        long startedAt = SystemClock.uptimeMillis();
        boolean ok;
        String error = null;
        String protection;
        try {
            PermissionInfo info =
                    getPackageManager().getPermissionInfo(row.name, 0);
            protection = describeProtection(info.protectionLevel);
            ok = true;
        } catch (Exception e) {
            ok = false;
            error = e.getMessage() == null ? e.getClass().getName() : e.getMessage();
            protection = "indisponivel (" + error + ")";
        }
        long durationMs = SystemClock.uptimeMillis() - startedAt;
        ProbeReporter.record(this, ProbeCatalog.CORE_PM_001, ok,
                ok ? null : error, durationMs);
        Log.i(TAG, "CORE-PM-001 " + row.name + " -> " + protection);
        // requestPermissions existe na Activity a partir da API 23; o guard
        // evita o toque em metodo ausente no flavor classic (minSdk 9).
        if ("dangerous".equals(row.baseLevel) && Build.VERSION.SDK_INT >= 23) {
            requestPermissions(new String[] { row.name }, REQUEST_CODE);
        }
    }

    /** Decodifica protectionLevel em texto estavel para o log do probe. */
    private String describeProtection(int level) {
        int base = level & 0x0f;
        String text;
        if (base == PermissionInfo.PROTECTION_NORMAL) {
            text = "normal";
        } else if (base == PermissionInfo.PROTECTION_DANGEROUS) {
            text = "dangerous";
        } else if (base == PermissionInfo.PROTECTION_SIGNATURE) {
            text = "signature";
        } else if (base == PermissionInfo.PROTECTION_SIGNATURE_OR_SYSTEM) {
            text = "signatureOrSystem";
        } else if (base == 4) {
            text = "internal";
        } else {
            text = "0x" + Integer.toHexString(base);
        }
        if ((level & PermissionInfo.PROTECTION_FLAG_SYSTEM) != 0) {
            text += "|system";
        }
        if ((level & PermissionInfo.PROTECTION_FLAG_DEVELOPMENT) != 0) {
            text += "|development";
        }
        if ((level & PermissionInfo.PROTECTION_FLAG_APPOP) != 0) {
            text += "|appop";
        }
        int flagsRestantes = level & ~(0x0f
                | PermissionInfo.PROTECTION_FLAG_SYSTEM
                | PermissionInfo.PROTECTION_FLAG_DEVELOPMENT
                | PermissionInfo.PROTECTION_FLAG_APPOP);
        if (flagsRestantes != 0) {
            text += "|0x" + Integer.toHexString(flagsRestantes);
        }
        return text;
    }

    /** Converte dp em pixels inteiros com as metricas atuais. */
    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }
}
