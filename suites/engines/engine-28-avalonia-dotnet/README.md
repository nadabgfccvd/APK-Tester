# engine-28-avalonia-dotnet — Tier B (build real no nightly)

**Engine engine-28 da matriz RustyDroid (Apêndice G): C#/Avalonia.**
Build REAL no `engines-nightly.yml` com pacotes oficiais pinados do NuGet:

- `Avalonia 11.2.2` → `assemblies/Avalonia.Base.dll`,
  `Avalonia.Controls.dll`, `Avalonia.Skia.dll` (lib/net8.0);
- `Avalonia.Android 11.2.2` → `assemblies/Avalonia.Android.dll`
  (lib/net8.0-android34.0);
- `SkiaSharp.NativeAssets.Android 2.88.9` →
  `lib/x86_64/libSkiaSharp.so` (runtimes/android-x64);
- `Microsoft.Android.Runtime.34.android-x64 34.0.154` →
  `lib/x86_64/libmono-android.release.so` (runtime .NET android).

- **Build:** `./build.sh --out dist` (delega a `tools/build-tier-b.py`)
- **Pinos:** avalonia `11.2.2`, skiasharp-native-assets-android `2.88.9`,
  net-android-runtime-x64 `34.0.154`
- **Contrato:** `expected-engines.json` (cópia por diretório, zero drift)
- **minSdk 26 / targetSdk 36** · seed 20261022

## Notas honestas

- Nomes REAIS dos nativos são `libSkiaSharp.so` (S maiúsculo) e
  `libmono-android.release.so` (.NET 8 renomeou o antigo `libmonodroid.so`);
  o answer key canônico foi refinado em A7 contra os artefatos reais.
- Esta é a estratégia "real enxuta" (assemblies/nativos oficiais dos
  pacotes), sem o workload `net8.0-android` completo — documentada para o
  detector (ADR 0003).
