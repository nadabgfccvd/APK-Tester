#!/usr/bin/env python3
"""bot/checks/permission_drift.py — drift de permissões vs o AOSP (plataforma).

Verificação que o CI NÃO consegue fazer: o CI só confere o que está no
repositório; o AOSP evolui TODO DIA e não avisa. Este check baixa o
``frameworks/base/core/res/AndroidManifest.xml`` do AOSP (branch master do
espelho aosp-mirror) e compara com a verdade local.

Fonte remota (urllib stdlib, SEM ctx.gh — funciona até sem API do GitHub):
1. ``cfg.aosp_manifest_url`` + ``?format=TEXT`` (resposta base64) — decodifica;
2. fallback: a própria URL sem ``format=TEXT`` (conteúdo bruto);
3. timeout ``cfg.http_timeout_s`` (padrão 30s) e 1 retry por URL.
Qualquer falha de rede => CheckResult(ran=False, notes="sem acesso ao AOSP").
NUNCA lança exceção por problema de rede.

Parse do manifesto: tags ``<permission android:name="android.permission.X"
... android:protectionLevel="...">`` com regex sobre pares de atributos
(tolera ordem/aspas). Guarda ~1000 nomes (inclui @hide/internas).

Verdade local: tabela canônica de ``contracts/flagship/permissions-audit.md``
(linhas que COMEÇAM com ``| android.permission.NOME``). Tabela vazia
(esqueleto A0, documentado) => Finding "info" ...:auditoria:esqueleto-vazio
(contagem AOSP vs 0 locais; preencher em A1) + learn do snapshot AOSP.

Validação de VALORES maxSdkVersion (A9/roadmap 0.5): o AOSP master não usa
maxSdkVersion nos self-uses — o teto das deprecadas vem do nível de
deprecação DOCUMENTADO da plataforma (developer.android.com, "This constant
was deprecated in API level N"; BLUETOOTH/BLUETOOTH_ADMIN: migração oficial
Android 12, novas runtime valem do 31). A tabela EXPECTED_MAX_SDK abaixo é
a segunda fonte independente: o registry (curado em
tools/snapshot-aosp-permissions.py) E o manifesto gerado devem bater com
ela valor a valor; usa-permission-sdk-23 NÃO pode intersectar o conjunto
com teto (declaração dupla — bug de ambiguidade de parser corrigido na A9
para USE_FINGERPRINT); e todo nome com teto precisa existir no AOSP.

Findings (com tabela preenchida):
- "new"        ...:aosp:permissao-nova        (a plataforma evoluiu — flagship acompanha)
- "regression" ...:aosp:permissao-inexistente (string inventada vazou para a auditoria;
                                               lei: invented strings só em parser-torture/unknown-perms)
- "drift"      ...:aosp:manifest-mudou        (sha256 do manifesto AOSP mudou vs baseline)
- "regression" ...:flagship:manifest-fora-da-auditoria (A1+: uses-permission declarado
                                               no manifesto sem linha na auditoria)
- "regression" ...:flagship:maxsdk-valor-errado   (valor diverge do nível documentado)
- "regression" ...:flagship:maxsdk-declaracao-dupla (mesmo nome em uses-permission COM
                                               teto e em uses-permission-sdk-23)
"""

import base64
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

CHECK_ID = "permission_drift"

AOSP_MANIFEST_URL_DEFAULT = (
    "https://raw.githubusercontent.com/aosp-mirror/"
    "platform_frameworks_base/master/core/res/AndroidManifest.xml"
)
HTTP_TIMEOUT_S_DEFAULT = 30
HTTP_RETRIES = 1                    # 1 tentativa extra por URL
MAX_LIST_BODY = 60                  # nomes exibidos por finding (resto contado)
MAX_LEARN_NAMES = 1200              # teto de segurança para learn["aosp_names"]

# Segunda fonte independente para os VALORES de maxSdkVersion das
# uses-permission deprecadas do flagship (A9/roadmap 0.5): nível de
# deprecação documentado da plataforma. O AOSP master não declara
# maxSdkVersion nos self-uses — esta tabela é a referência auditável;
# tools/snapshot-aosp-permissions.py (FLAGSHIP_MAX_SDK) deve bater 1:1.
EXPECTED_MAX_SDK = {
    "android.permission.GET_TASKS": 21,
    "android.permission.PROCESS_OUTGOING_CALLS": 28,
    "android.permission.USE_CREDENTIALS": 22,
    "android.permission.PERSISTENT_ACTIVITY": 15,
    "android.permission.READ_EXTERNAL_STORAGE": 32,
    "android.permission.WRITE_EXTERNAL_STORAGE": 32,
    "android.permission.USE_FINGERPRINT": 28,
    "android.permission.BLUETOOTH": 30,
    "android.permission.BLUETOOTH_ADMIN": 30,
}

_TAG_PERMISSION_RE = re.compile(r"<permission\s([^>]*?)/?>")
_ATTR_NAME_RE = re.compile(r"android:name\s*=\s*[\"']([^\"']+)[\"']")
_ATTR_LEVEL_RE = re.compile(r"android:protectionLevel\s*=\s*[\"']([^\"']+)[\"']")
_USES_PERM_RE = re.compile(
    r"<uses-permission(?:-sdk-23)?\s+[^>]*?"
    r"android:name\s*=\s*[\"']([^\"']+)[\"']", re.S)
# Elemento <uses-permission> completo (para extrair name + maxSdkVersion,
# em qualquer ordem de atributos) e o conjunto sdk-23 do manifesto gerado.
_USES_PERM_TAG_RE = re.compile(r"<uses-permission\s([^>]*?)/?>", re.S)
_USES_PERM_SDK23_TAG_RE = re.compile(r"<uses-permission-sdk-23\s([^>]*?)/?>", re.S)
_ATTR_MAXSDK_RE = re.compile(r"android:maxSdkVersion\s*=\s*[\"'](\d+)[\"']")
# Linha da tabela canônica: primeiro célula é o nome completo da permissão.
_AUDIT_ROW_RE = re.compile(r"^\|\s*(android\.permission\.[A-Z0-9_]+)\s*\|", re.M)

_CHECKS_DIR = Path(__file__).resolve()
for _p in (_CHECKS_DIR.parents[2], _CHECKS_DIR.parents[1]):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from bot.lib.base import CheckResult, Finding
except ImportError:  # fallback: árvore bot/ sem o pacote "bot" (layout antigo)
    from lib.base import CheckResult, Finding  # type: ignore


# ------------------------------------------------------------------ helpers
def _http_get(url: str, timeout: int, retries: int = HTTP_RETRIES):
    """GET best-effort; retorna bytes ou None (nunca lança)."""
    last_err = None
    for _attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "apkbot/permission-drift"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:  # rede, DNS, HTTP, timeout — tudo tolerado
            last_err = exc
    _ = last_err  # diagnóstico fica no notes; não vaza traceback
    return None


def _fetch_aosp(url: str, timeout: int):
    """Base64 (?format=TEXT) com fallback para o bruto; bytes ou None."""
    sep = "&" if "?" in url else "?"
    blob = _http_get(url + sep + "format=TEXT", timeout)
    if blob:
        try:
            return base64.b64decode(blob, validate=True)
        except Exception:
            pass  # cai para o bruto abaixo
    return _http_get(url, timeout)


def _parse_aosp(xml_text: str):
    """{nome: protectionLevel} das <permission> android.permission.* (ordenado)."""
    perms = {}
    for attrs in _TAG_PERMISSION_RE.findall(xml_text):
        m = _ATTR_NAME_RE.search(attrs)
        if not m:
            continue
        name = m.group(1)
        if not name.startswith("android.permission."):
            continue
        lv = _ATTR_LEVEL_RE.search(attrs)
        perms[name] = lv.group(1) if lv else ""
    return {k: perms[k] for k in sorted(perms)}


def _parse_audit(repo: Path):
    """Nomes na tabela canônica da auditoria; None se arquivo ausente."""
    path = repo / "contracts" / "flagship" / "permissions-audit.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return _AUDIT_ROW_RE.findall(text)


def _parse_flagship_manifest(repo: Path):
    """uses-permission* declarados no manifesto do flagship (ou None)."""
    path = repo / "suites" / "flagship" / "AndroidManifest.xml"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return _USES_PERM_RE.findall(text)


def _parse_manifest_maxsdk(repo: Path):
    """({nome: maxSdk}, {sdk-23 nomes}) do manifesto do flagship; (None, None)
    se o arquivo não existe. Tolera ordem de atributos; ignora tags sem nome.
    """
    path = repo / "suites" / "flagship" / "AndroidManifest.xml"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None, None
    maxsdk = {}
    for attrs in _USES_PERM_TAG_RE.findall(text):
        name_m = _ATTR_NAME_RE.search(attrs)
        if not name_m:
            continue
        max_m = _ATTR_MAXSDK_RE.search(attrs)
        if max_m:
            maxsdk[name_m.group(1)] = int(max_m.group(1))
    sdk23 = set()
    for attrs in _USES_PERM_SDK23_TAG_RE.findall(text):
        name_m = _ATTR_NAME_RE.search(attrs)
        if name_m:
            sdk23.add(name_m.group(1))
    return maxsdk, sdk23


def _cap(names, limit=MAX_LIST_BODY):
    names = list(names)
    if len(names) <= limit:
        return names, 0
    return names[:limit], len(names) - limit


def _cap_block(title, names, limit=MAX_LIST_BODY):
    shown, extra = _cap(names, limit)
    lines = "\n".join(f"- `{n}`" for n in shown)
    if extra:
        lines += f"\n- … e mais {extra} (lista completa no diff/learn)"
    return f"\n\n**{title}** ({len(names)}):\n{lines}" if names else ""


# ---------------------------------------------------------------------- run
def run(ctx) -> CheckResult:
    repo = Path(str(ctx.repo_path))
    findings = []

    timeout = int(ctx.cfg.get("http_timeout_s") or HTTP_TIMEOUT_S_DEFAULT)
    url = ctx.cfg.get("aosp_manifest_url") or AOSP_MANIFEST_URL_DEFAULT

    # 1) Rede primeiro: qualquer falha => pulada (nunca exceção).
    raw = _fetch_aosp(url, timeout)
    if not raw:
        return CheckResult(check=CHECK_ID, findings=[], learn={},
                           ran=False,
                           notes="sem acesso ao AOSP (rede indisponível ou "
                                 "timeout): verificação pulada")
    xml_text = raw.decode("utf-8", "replace")
    aosp = _parse_aosp(xml_text)
    aosp_sha = hashlib.sha256(raw).hexdigest()
    aosp_names = list(aosp.keys())

    # 2) Verdade local (arquivo do repositório).
    audit_names = _parse_audit(repo)
    audit_missing = audit_names is None

    # 3) Drift do manifesto AOSP vs baseline (cross-time memory).
    baseline = (ctx.state.get("baselines") or {}).get(CHECK_ID, {}) \
        if isinstance(ctx.state, dict) else {}
    old_sha = baseline.get("aosp_sha256")
    if old_sha and old_sha != aosp_sha:
        findings.append(Finding(
            check=CHECK_ID, target="aosp:frameworks/base/core/res/AndroidManifest.xml",
            severity="drift",
            title="Manifesto de permissões do AOSP mudou",
            body_md=(
                "O sha256 do `AndroidManifest.xml` do AOSP (branch master do "
                "espelho) mudou desde a última execução do bot:\n\n"
                f"- baseline: `{old_sha}`\n- atual: `{aosp_sha}`\n\n"
                "Ação: re-revisar a auditoria de permissões do flagship "
                "(contratos/flagship/permissions-audit.md) — permissões novas, "
                "reprovadas ou com protectionLevel alterado precisam refletir "
                "no answer key antes do gate de A1/A6."),
            fingerprint=f"{CHECK_ID}:aosp:manifest-mudou"))

    learn = {
        "aosp_names": aosp_names[:MAX_LEARN_NAMES],
        "aosp_sha256": aosp_sha,
        "aosp_count": len(aosp_names),
    }

    # 3.5) Validação de VALORES maxSdkVersion (A9/roadmap 0.5) — roda sempre
    #      (independe da tabela de auditoria): registry curado + manifesto
    #      gerado vs a tabela documentada EXPECTED_MAX_SDK.
    learn["maxsdk_checked"] = 0
    try:
        reg_usage = json.loads(
            (repo / "contracts" / "flagship" / "permissions-registry.json")
            .read_text(encoding="utf-8")).get("flagship_usage") or {}
    except (OSError, ValueError, AttributeError):
        reg_usage = {}
    reg_max = reg_usage.get("max_sdk_version") or {}
    man_max, man_sdk23 = _parse_manifest_maxsdk(repo)

    if reg_max or (man_max is not None):
        divergent = []
        for name in sorted(set(EXPECTED_MAX_SDK) | set(reg_max)):
            expected = EXPECTED_MAX_SDK.get(name)
            actual = reg_max.get(name)
            if expected != actual:
                divergent.append(
                    f"- `{name}`: registry={actual!r}, documentado={expected!r}")
        if divergent:
            findings.append(Finding(
                check=CHECK_ID,
                target="tools/snapshot-aosp-permissions.py (FLAGSHIP_MAX_SDK)",
                severity="regression",
                title="maxSdkVersion do registry diverge do nível documentado",
                body_md=(
                    "A tabela curada `FLAGSHIP_MAX_SDK` (refletida em "
                    "`contracts/flagship/permissions-registry.json` → "
                    "`flagship_usage.max_sdk_version`) diverge do nível de "
                    "deprecação documentado da plataforma (segunda fonte "
                    "independente `EXPECTED_MAX_SDK` deste check — "
                    "A9/roadmap 0.5). O AOSP master não declara "
                    "maxSdkVersion nos self-uses: o teto das deprecadas é "
                    "curado e DEVE bater com a documentação:\n\n"
                    + "\n".join(divergent) +
                    "\n\nCorrigir a FONTE (`tools/snapshot-aosp-permissions.py`) "
                    "e regenerar a cadeia (registry → manifesto → auditorias)."),
                fingerprint=f"{CHECK_ID}:flagship:maxsdk-valor-errado"))
        learn["maxsdk_checked"] = len(reg_max) or len(EXPECTED_MAX_SDK)

    if man_max is not None:
        learn["manifest_maxsdk"] = len(man_max)
        learn["manifest_sdk23"] = len(man_sdk23 or set())
        # manifesto gerado == registry (o gerador copia a tabela; drift aqui
        # é manifesto editado à mão ou gerador desatualizado)
        if reg_max and man_max != reg_max:
            rows = []
            for name in sorted(set(reg_max) | set(man_max)):
                if reg_max.get(name) != man_max.get(name):
                    rows.append(f"- `{name}`: manifesto={man_max.get(name)!r}, "
                                f"registry={reg_max.get(name)!r}")
            findings.append(Finding(
                check=CHECK_ID,
                target="suites/flagship/AndroidManifest.xml",
                severity="regression",
                title="maxSdkVersion do manifesto diverge do registry",
                body_md=(
                    "O manifesto gerado declara maxSdkVersion diferente do "
                    "registry canônico (fonte única "
                    "`tools/gen-flagship-manifest.py`) — manifesto editado à "
                    "mão ou cadeia desatualizada:\n\n" + "\n".join(rows) +
                    "\n\nRegenere com "
                    "`python3 tools/gen-flagship-manifest.py --out .`"),
                fingerprint=f"{CHECK_ID}:flagship:maxsdk-manifesto-diverge"))
        # declaração dupla: mesmo nome com teto no uses-permission E presente
        # no uses-permission-sdk-23 (bug USE_FINGERPRINT corrigido na A9)
        if man_sdk23:
            dup = sorted(set(man_max) & set(man_sdk23))
            if dup:
                findings.append(Finding(
                    check=CHECK_ID,
                    target="suites/flagship/AndroidManifest.xml",
                    severity="regression",
                    title="Declaração dupla uses-permission/sdk-23 com teto",
                    body_md=(
                        "Permissão declarada DUAS vezes: no elemento comum "
                        "COM maxSdkVersion e no `uses-permission-sdk-23` — "
                        "par ambíguo para parsers (o conflito deliberado da "
                        "suite é o cleartext, documentado no manifest-audit). "
                        "Declarar UMA vez (teto no elemento comum) ou "
                        "documentar como conflito deliberado:\n\n" +
                        "\n".join(f"- `{n}`" for n in dup)),
                    fingerprint=f"{CHECK_ID}:flagship:maxsdk-declaracao-dupla"))
        # todo nome com teto precisa existir no AOSP (string inventada)
        fantasma = sorted(set(man_max) - set(aosp_names))
        if fantasma:
            findings.append(Finding(
                check=CHECK_ID,
                target="suites/flagship/AndroidManifest.xml",
                severity="regression",
                title="maxSdkVersion em permissão inexistente no AOSP",
                body_md=(
                    "uses-permission com maxSdkVersion para nome que NÃO "
                    "existe no AOSP — string inventada vazou (lei: só em "
                    "parser-torture/unknown-perms):\n\n" +
                    "\n".join(f"- `{n}`" for n in fantasma)),
                fingerprint=f"{CHECK_ID}:flagship:maxsdk-permissao-inexistente"))

    # 4) Auditoria esqueleto/ausente => info, sem lógica de drift de nomes.
    if audit_missing or not audit_names:
        why = ("arquivo contracts/flagship/permissions-audit.md não encontrado"
               if audit_missing else
               "tabela canônica vazia (esqueleto A0, documentado)")
        body = (
            f"A auditoria de permissões do flagship ainda não tem linhas: "
            f"{why}. O AOSP declara hoje **{len(aosp_names)}** permissões "
            "android.permission.* (inclui @hide/internas). Preencher a tabela "
            "canônica em **A1** — name, protectionLevel, group, maxSdkVersion "
            "e flag @hide; strings inventadas NUNCA entram aqui "
            "(vivem só em parser-torture/unknown-perms).")
        manifest_declared = _parse_flagship_manifest(repo)
        if manifest_declared is not None:
            plat = {n for n in manifest_declared
                    if n.startswith("android.permission.")}
            custom = len(manifest_declared) - len(plat)
            body += (f"\n\nO manifesto `suites/flagship/AndroidManifest.xml` "
                     f"já declara {len(plat)} permissões de plataforma "
                     f"(+{custom} custom) aguardando auditoria.")
            learn["flagship_declared_platform"] = len(plat)
            learn["flagship_declared_custom"] = custom
        findings.append(Finding(
            check=CHECK_ID, target="contracts/flagship/permissions-audit.md",
            severity="info",
            title="Auditoria de permissões é esqueleto — preencher em A1",
            body_md=body,
            fingerprint=f"{CHECK_ID}:auditoria:esqueleto-vazio"))
        notes = (f"AOSP: {len(aosp_names)} permissões (sha {aosp_sha[:12]}…); "
                 f"auditoria local: 0 nomes ({why})")
        return CheckResult(check=CHECK_ID, findings=findings, learn=learn,
                           ran=True, notes=notes)

    # 5) Tabela preenchida: compara conjuntos.
    local_set = set(audit_names)
    aosp_set = set(aosp_names)

    novas = sorted(aosp_set - local_set)
    if novas:
        body = (
            "Permissões que existem no AOSP e AUSENTEM da auditoria local — "
            "a plataforma evoluiu, o flagship precisa acompanhar "
            "(declarar no manifesto + linha na auditoria, com protectionLevel/"
            "group/maxSdk/@hide corretos):" +
            _cap_block("Novas no AOSP", novas))
        findings.append(Finding(
            check=CHECK_ID, target="contracts/flagship/permissions-audit.md",
            severity="new",
            title=f"{len(novas)} permissões AOSP fora da auditoria do flagship",
            body_md=body,
            fingerprint=f"{CHECK_ID}:aosp:permissao-nova"))

    inexistentes = sorted(local_set - aosp_set)
    if inexistentes:
        body = (
            "Permissões na auditoria local que NÃO existem no AOSP — string "
            "inventada vazou para a auditoria. Lei do repositório: strings "
            "inventadas vivem EXCLUSIVAMENTE em "
            "`suites/parser-torture/unknown-perms/`; corrigir a auditoria "
            "(ou registrar o nome correto no AOSP de referência):" +
            _cap_block("Inexistentes no AOSP", inexistentes))
        findings.append(Finding(
            check=CHECK_ID, target="contracts/flagship/permissions-audit.md",
            severity="regression",
            title=f"{len(inexistentes)} permissões inventadas na auditoria",
            body_md=body,
            fingerprint=f"{CHECK_ID}:aosp:permissao-inexistente"))

    # 6) Flagship manifesto (A1+) vs auditoria.
    declared = _parse_flagship_manifest(repo)
    if declared is not None:
        plat = {n for n in declared if n.startswith("android.permission.")}
        fora = sorted(plat - local_set)
        if fora:
            body = (
                "Permissões declaradas em `suites/flagship/AndroidManifest.xml` "
                "(`uses-permission`/`uses-permission-sdk-23`) sem linha "
                "correspondente na auditoria — o manifesto está fora da "
                "auditoria (answer key deve cobrir 100% do que é declarado):" +
                _cap_block("Declaradas e não auditadas", fora))
            findings.append(Finding(
                check=CHECK_ID, target="suites/flagship/AndroidManifest.xml",
                severity="regression",
                title="Manifesto do flagship declara permissões fora da auditoria",
                body_md=body,
                fingerprint=f"{CHECK_ID}:flagship:manifest-fora-da-auditoria"))
        learn["flagship_declared_platform"] = len(plat)
        learn["flagship_declared_custom"] = len(declared) - len(plat)

    notes = (f"AOSP: {len(aosp_names)} permissões (sha {aosp_sha[:12]}…); "
             f"auditoria local: {len(local_set)} nomes")
    return CheckResult(check=CHECK_ID, findings=findings, learn=learn,
                       ran=True, notes=notes)
