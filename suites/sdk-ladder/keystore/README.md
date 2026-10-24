# suites/sdk-ladder/keystore/ — assinatura deterministica da escada (A9)

`ladder-test.keystore.b64` e o keystore de TESTE da escada minSdk 9–36,
commitado como TEXTO base64 (mesmo padrão do flagship, A6 — regra "sem
binários no repo" preservada) e decodificado no build para
`app/build/keystore/ladder-test.keystore` (tarefa `decodeKeystore` em
app/build.gradle.kts).

- **Não é segredo**: chave de fixture pública deste repo.
- **Por que commitar (A9/roadmap 6.4):** os 12 degraus eram assinados com
  o `~/.android/debug.keystore` — variável POR HOST. O workflow Release
  anexa esses APKs à release; a assinatura debug de host variável quebra
  (a) a comparabilidade de `sha256sums.txt` entre rebuilds, (b) a
  reprodutibilidade do bundle de release e (c) qualquer verificação de
  assinatura futura que pressuponha uma chave estável. Com o keystore de
  fixture, todo degrau (debug E release) assina com a MESMA chave em
  qualquer máquina — igual ao flagship desde a A6.
- Credenciais (documentadas também no build.gradle.kts):
  - store: PKCS12, senha `ladder2026`
  - alias: `ladder-test`, senha `ladder2026`
  - dname: `CN=Ladder Fixture, OU=APK-Tester, O=nadabgfccvd, L=Sao Paulo, ST=SP, C=BR`
  - RSA 2048, validade 10.950 dias (30 anos), gerado uma única vez com
    `keytool -genkeypair` (janela de geração fixa — commits posteriores não
    alteram o arquivo, logo builds são byte-reproduzíveis entre máquinas).
    sha256 do keystore decodificado:
    `da4b7a30a0a8d23e089f16c5ef17d6826b584577e617eb2b878411abf8b9f80f`.
- Regeneração (só se o arquivo for perdido):
  `keytool -genkeypair -keystore ladder-test.keystore -storetype PKCS12
  -alias ladder-test -keyalg RSA -keysize 2048 -validity 10950
  -storepass ladder2026 -keypass ladder2026
  -dname "CN=Ladder Fixture, OU=APK-Tester, O=nadabgfccvd, L=Sao Paulo,
  ST=SP, C=BR" && base64 -w 76 ladder-test.keystore > ladder-test.keystore.b64`
