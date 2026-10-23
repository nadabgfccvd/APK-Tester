# Matriz de compatibilidade — APK Tester x RustyDroid

Esta página é **regenerada a cada execução do [`engines-nightly.yml`]
(.github/workflows/engines-nightly.yml)** pelo
[`scripts/compat-nightly.sh`](../scripts/compat-nightly.sh) contra o answer
key `contracts/engines/expected-engines.json`, e publicada aqui no GH Pages
junto com o site mdBook.

## Ver agora

A matriz fresca está em [`compat-matrix.md`](compat-matrix.md) **após a
última execução nightly bem-sucedida**; enquanto isso, a versão commitada
deste stub indica que o nightly ainda não rodou desde o último deploy (ou o
deploy falhou — verifique o job `docs-pages`).

> Regra (ADR 0003): detecção não valida payload nem autoriza execução. FAIL
> na matriz é drift de DETECÇÃO vs answer key, não falha de payload.
