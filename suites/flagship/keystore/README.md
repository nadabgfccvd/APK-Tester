# suites/flagship/keystore/ — assinatura release deterministica (A6)

`behemoth-test.keystore.b64` e o keystore de TESTE do flagship "Behemoth",
commitado como TEXTO base64 (respeitando a regra "sem binarios no repo") e
decodificado no build para `app/build/keystore/behemoth-test.keystore`
(tarefa `decodeKeystore` em app/build.gradle.kts).

- **Nao e segredo**: chave de fixture publica deste repo.
- Credenciais (documentadas tambem no build.gradle.kts):
  - store: PKCS12, senha `behemoth2026`
  - alias: `behemoth-test`, senha `behemoth2026`
  - dname: `CN=Behemoth Fixture, OU=APK-Tester, O=nadabgfccvd, L=Sao Paulo, ST=SP, C=BR`
  - RSA 2048, validade 10.950 dias (30 anos), gerado uma unica vez com
    `keytool -genkeypair` (janela de geracao fixa — commits posteriores nao
    alteram o arquivo, logo builds sao byte-reproduziveis entre maquinas).
- Por que commitar: a alternativa `~/.android/debug.keystore` varia por host,
  o que quebraria a prova de determinismo (A8: dois builds release byte a
  byte identicos) e o `sha256_of_apk` do size-report.csv.
- Regeneracao (so se o arquivo for perdido):
  `keytool -genkeypair -keystore behemoth-test.keystore -storetype PKCS12
  -alias behemoth-test -keyalg RSA -keysize 2048 -validity 10950
  -storepass behemoth2026 -keypass behemoth2026
  -dname "CN=Behemoth Fixture, OU=APK-Tester, O=nadabgfccvd, L=Sao Paulo,
  ST=SP, C=BR" && base64 -w 76 behemoth-test.keystore > behemoth-test.keystore.b64`
