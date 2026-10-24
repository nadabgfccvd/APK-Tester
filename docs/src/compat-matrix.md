# Matriz de compatibilidade — APK Tester x RustyDroid

Esta página é **regenerada a cada execução do
[`engines-nightly.yml`](https://github.com/nadabgfccvd/APK-Tester/blob/main/.github/workflows/engines-nightly.yml)**
pelo
[`scripts/compat-nightly.sh`](https://github.com/nadabgfccvd/APK-Tester/blob/main/scripts/compat-nightly.sh)
contra o answer key `contracts/engines/expected-engines.json`, e publicada
aqui no GH Pages junto com o site mdBook.

## Ver agora

A matriz fresca de cada execução nightly é o **artefato `compat-matrix`**
do run (upload de `docs/compat-matrix.md`) — abra a lista de runs do
[`engines-nightly.yml`](https://github.com/nadabgfccvd/APK-Tester/actions/workflows/engines-nightly.yml),
baixe o artefato do último run verde. Este arquivo é o stub da página no
site: a versão fresca substitui `docs/compat-matrix.md` a cada run
bem-sucedido e é espelhada aqui (sem link para si mesma — a página que
apontava para ela própria era um loop).

> Regra (ADR 0003): detecção não valida payload nem autoriza execução. FAIL
> na matriz é drift de DETECÇÃO vs answer key, não falha de payload.
