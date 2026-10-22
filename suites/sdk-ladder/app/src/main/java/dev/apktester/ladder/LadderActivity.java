package dev.apktester.ladder;

import android.app.Activity;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.util.Log;
import android.widget.TextView;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;

/**
 * Activity do degrau: coleta os fatos do proprio pacote, cruza com o asset
 * gerado ladder/rungs.json (a fonte da mesma RUNGS que gera os flavors e o
 * answer key) e grava ladder-report.json no filesDir.
 *
 * Disciplina minSdk 9: leitura de asset com loop de buffer de bytes (API 1),
 * cruzamento do degrau por indexOf (sem org.json, que e API 11+; o asset e
 * gerado por tools/gen-ladder.py — formato de maquina, sem escapes, por isso
 * um parser minimo deliberado e suficiente), minSdkVersion/targetSdkVersion
 * do ApplicationInfo apenas com guarda Build.VERSION.SDK_INT >= 24 (o campo
 * so existe a partir dai; abaixo disso usa o valor do asset) e sem
 * timestamps no relatorio (determinismo do repositorio).
 */
public class LadderActivity extends Activity {

    private static final String TAG = "LADDER";

    /** Asset gerado pela mesma RUNGS do answer key (contrato da suíte). */
    private static final String ASSET_RUNGS = "ladder/rungs.json";

    /** Prefixo fixo do applicationId de todos os degraus. */
    private static final String ID_PREFIX = "dev.apktester.ladder.";

    /** As 4 classes componentes declaradas no manifesto de cada degrau. */
    private static final String[] COMPONENT_CLASSES = {
        "LadderActivity", "LadderService", "LadderReceiver", "LadderProvider",
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_ladder);

        String json = readRungsAsset();
        String packageName = getPackageName();
        String flavor = flavorName(packageName);
        String logTag = "LADDER/" + flavor;

        // Prova de leitura best-effort do relatorio anterior (log apenas —
        // o conteudo do relatorio novo nunca depende do anterior).
        String previous = LadderReport.readFile(getFilesDir(),
                LadderReport.REPORT_FILE);
        Log.i(logTag, previous != null
                ? "relatorio anterior presente nesta instalacao"
                : "primeira execucao nesta instalacao");

        // Ancora no objeto do degrau: o applicationId do pacote aparece
        // exatamente uma vez no asset (valor entre aspas, sem prefixos
        // ambiguos — os sabores usam 2 digitos fixos).
        int anchor = json.indexOf("\"" + packageName + "\"");
        String expectation = "DESCONHECIDO";
        int assetMinSdk = -1;
        int assetTargetSdk = -1;
        if (anchor >= 0) {
            // Todos os campos do objeto ficam a menos de ~400 caracteres da
            // ancora (ordem alfabetica das chaves garantida pelo gerador).
            expectation = findStringValue(json, "rustydroid", anchor,
                    expectation);
            assetMinSdk = findIntValue(json, "min_sdk", anchor, -1);
            assetTargetSdk = findIntValue(json, "target_sdk", anchor, -1);
        } else {
            Log.w(logTag, "degrau nao encontrado no asset: " + packageName);
        }

        // Fatos do pacote (getPackageInfo simples, API 1).
        int versionCode = 0;
        String versionName = "";
        try {
            PackageInfo pkg = getPackageManager()
                    .getPackageInfo(packageName, 0);
            versionCode = pkg.versionCode;
            versionName = pkg.versionName == null ? "" : pkg.versionName;
        } catch (PackageManager.NameNotFoundException e) {
            Log.w(logTag, "getPackageInfo falhou: " + e.getMessage());
        }

        // minSdk/targetSdk declarados: do ApplicationInfo (API 24+) ou, por
        // guarda explicita, do asset gerado (mesma fonte dos flavors).
        int sdkInt = Build.VERSION.SDK_INT;
        int minSdkDeclared;
        int targetSdk;
        if (sdkInt >= 24) {
            ApplicationInfo appInfo = getApplicationInfo();
            minSdkDeclared = appInfo.minSdkVersion;
            targetSdk = appInfo.targetSdkVersion;
        } else {
            minSdkDeclared = assetMinSdk;
            targetSdk = assetTargetSdk;
        }

        String report = LadderReport.buildReport(packageName, versionCode,
                versionName, minSdkDeclared, sdkInt, targetSdk,
                COMPONENT_CLASSES, expectation);
        boolean written = LadderReport.writeFile(getFilesDir(),
                LadderReport.REPORT_FILE, report);

        StringBuilder facts = new StringBuilder(256);
        facts.append("package=").append(packageName).append('\n');
        facts.append("versionCode=").append(versionCode).append('\n');
        facts.append("versionName=").append(versionName).append('\n');
        facts.append("minSdk=").append(minSdkDeclared).append('\n');
        facts.append("SDK do sistema=").append(sdkInt).append('\n');
        facts.append("targetSdk=").append(targetSdk).append('\n');
        facts.append("esperado no RustyDroid=").append(expectation);

        TextView title = (TextView) findViewById(R.id.rung_title);
        title.setText(getString(R.string.rung_label));
        TextView factsView = (TextView) findViewById(R.id.rung_facts);
        factsView.setText(facts.toString());

        Log.i(logTag, "minSdk=" + minSdkDeclared + " sdk=" + sdkInt
                + " targetSdk=" + targetSdk + " rustydroid=" + expectation
                + " relatorio=" + (written ? "gravado" : "falhou"));
    }

    /**
     * Le o asset ladder/rungs.json para String: loop de buffer de bytes com
     * APIs de API 1 (sem java.nio.file, sem objetos Charset). Qualquer
     * falha vira string vazia + Log.w (erro estruturado, nunca crash).
     */
    private String readRungsAsset() {
        InputStream in = null;
        try {
            in = getAssets().open(ASSET_RUNGS);
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            byte[] buffer = new byte[4096];
            int read;
            while ((read = in.read(buffer)) >= 0) {
                bytes.write(buffer, 0, read);
            }
            return new String(bytes.toByteArray(), "UTF-8");
        } catch (Exception e) {
            Log.w(TAG, "asset " + ASSET_RUNGS + " indisponivel: "
                    + e.getMessage());
            return "";
        } finally {
            if (in != null) {
                try {
                    in.close();
                } catch (Exception e) {
                    Log.w(TAG, "fechamento do asset falhou: " + e.getMessage());
                }
            }
        }
    }

    /**
     * Localiza o valor (indice apos aspas inicial) de "\"chave\":" a partir
     * de fromIndex, tolerando espacos apos os dois pontos; -1 quando
     * ausente. Parser minimo deliberado: o asset e gerado por
     * tools/gen-ladder.py (formato de maquina confiavel).
     */
    private static int findValueStart(String json, String key, int fromIndex) {
        String needle = "\"" + key + "\":";
        int at = json.indexOf(needle, fromIndex);
        if (at < 0) {
            return -1;
        }
        int i = at + needle.length();
        while (i < json.length() && json.charAt(i) == ' ') {
            i++;
        }
        return i;
    }

    /**
     * Le um valor string do asset a partir de fromIndex; devolve o fallback
     * quando a chave nao existe ou o formato nao e o esperado.
     */
    static String findStringValue(String json, String key, int fromIndex,
            String fallback) {
        int start = findValueStart(json, key, fromIndex);
        if (start < 0 || start >= json.length()
                || json.charAt(start) != '"') {
            return fallback;
        }
        int end = json.indexOf('"', start + 1);
        if (end < 0) {
            return fallback;
        }
        return json.substring(start + 1, end);
    }

    /**
     * Le um valor inteiro do asset a partir de fromIndex; devolve o
     * fallback quando a chave nao existe ou o valor nao e numero.
     */
    static int findIntValue(String json, String key, int fromIndex,
            int fallback) {
        int start = findValueStart(json, key, fromIndex);
        if (start < 0) {
            return fallback;
        }
        int end = start;
        while (end < json.length()) {
            char c = json.charAt(end);
            if (c == '-' || (c >= '0' && c <= '9')) {
                end++;
            } else {
                break;
            }
        }
        if (end == start) {
            return fallback;
        }
        try {
            return Integer.parseInt(json.substring(start, end));
        } catch (NumberFormatException e) {
            return fallback;
        }
    }

    /** Nome do flavor = sufixo do applicationId apos o prefixo da escada. */
    private static String flavorName(String packageName) {
        if (packageName.startsWith(ID_PREFIX)) {
            return packageName.substring(ID_PREFIX.length());
        }
        return packageName;
    }
}
