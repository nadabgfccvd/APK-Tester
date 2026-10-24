package dev.apktester.behemoth.composeprobe

import android.content.Context
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.util.Locale
import java.util.Properties

/**
 * R2.2 (AUDIT_ROADMAP_V2) — UMA tela Compose real no flagship.
 *
 * Fonte da verdade do texto: `assets/locales/<locale>/strings.properties`
 * (mesmos pares chave/valor gerados por tools/gen-strings.py para os
 * res/values-<locale> — R2.3: a categoria "locales" do size-report passa
 * a ter bytes reais E usados). Fallback determinístico: pt-BR -> pt -> en
 * -> propriedades vazias.
 */
class ComposeProbeActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val labels = loadLocaleLabels(this)
        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    ProbeScreen(labels)
                }
            }
        }
    }

    private fun loadLocaleLabels(context: Context): Properties {
        val tag = Locale.getDefault().toString().replace('_', '-')
        val candidates = when {
            tag.startsWith("pt-BR", ignoreCase = true) ->
                listOf("pt-BR", "pt", "en")
            tag.startsWith("pt", ignoreCase = true) -> listOf("pt", "en")
            else -> listOf(tag, "en")
        }
        val props = Properties()
        for (candidate in candidates) {
            try {
                context.assets.open("locales/$candidate/strings.properties")
                    .use { props.load(it) }
                break
            } catch (_: Exception) {
                // locale ausente no pacote — tenta o próximo da cadeia
            }
        }
        return props
    }
}

@Composable
private fun ProbeScreen(labels: Properties) {
    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            text = labels.getProperty("app_name", "APK Tester — Behemoth"),
            fontSize = 22.sp,
        )
        Text(
            text = labels.getProperty("probe_module_core", "CORE module"),
            fontSize = 16.sp,
        )
        Text(
            text = "Compose real (R2.2) — material3 via BOM 2024.10.01",
            fontSize = 14.sp,
        )
    }
}
