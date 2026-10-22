"""Cliente REST mínimo do GitHub para o APKBot (somente python3 stdlib).

Escopo deliberadamente pequeno: o que o bot precisa para operar labels,
milestones, commits e issues, além de buscar arquivos crus em outros
repositórios (RustyDroid e AOSP). Sem dependências externas.

Comportamento de rede:
- timeout curto configurável (padrão 15 s; o dispatcher injeta o
  ``http_timeout_s`` de bot/bot-config.json);
- 1 retry automático em erro de rede e em HTTP 5xx;
- após esgotar as tentativas, levanta ``BotNetworkError``;
- HTTP 401/403 levanta ``BotAuthError`` (subclasse de ``BotNetworkError``)
  imediatamente — problema de token não se resolve com retry;
- ``raw_get`` e ``get_file_contents`` retornam ``None`` em 404/erro de rede
  e só levantam exceção em falha de autenticação.
"""

import base64
import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://api.github.com"
USER_AGENT = "apkbot"
RETRY_SLEEP_S = 1.0
MAX_LIST_PAGES = 20
AUTH_STATUSES = (401, 403)


class BotNetworkError(Exception):
    """Falha de rede/API após esgotar as tentativas (ou resposta inválida)."""


class BotAuthError(BotNetworkError):
    """Falha de autenticação/autorização (HTTP 401/403) — retry não resolve."""


class GitHubAPI:
    """Cliente minimalista da API REST do GitHub para um repositório base."""

    def __init__(self, base_repo, token=None, timeout=15.0):
        self.base_repo = base_repo
        # Token explícito tem precedência; senão, ambiente (GH_TOKEN|GITHUB_TOKEN).
        self.token = token or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
        self.timeout = float(timeout)

    # ------------------------------------------------------------------
    # Baixo nível
    # ------------------------------------------------------------------
    def _headers(self, extra=None):
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if extra:
            headers.update(extra)
        return headers

    def _send(self, method, url, data=None, headers=None):
        """Uma transação HTTP com 1 retry em erro de rede/5xx.

        Retorna ``(status, body_bytes)``. HTTP 401/403 levanta
        ``BotAuthError``; rede/5xx persistentes levantam ``BotNetworkError``;
        os demais 4xx retornam normalmente (o chamador decide — ex.: 404/422).
        """
        last_error = ""
        for attempt in (1, 2):
            try:
                req = urllib.request.Request(url, data=data, method=method,
                                             headers=headers or {})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return resp.getcode(), resp.read()
            except urllib.error.HTTPError as exc:
                if exc.code in AUTH_STATUSES:
                    raise BotAuthError(
                        f"HTTP {exc.code} em {method} {url} (verifique GH_TOKEN/GITHUB_TOKEN)"
                    ) from exc
                if exc.code >= 500:
                    last_error = f"HTTP {exc.code}"
                    if attempt == 1:
                        time.sleep(RETRY_SLEEP_S)
                        continue
                    raise BotNetworkError(
                        f"HTTP {exc.code} persistente em {method} {url} após retry") from exc
                return exc.code, exc.read()
            except (urllib.error.URLError, socket.timeout, ConnectionError, TimeoutError, OSError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt == 1:
                    time.sleep(RETRY_SLEEP_S)
                    continue
        raise BotNetworkError(f"falha de rede em {method} {url} após retry ({last_error})")

    @staticmethod
    def _decode_json(body):
        try:
            return json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None

    def _api_url(self, path):
        """Aceita caminho curto (``labels``), absoluto (``/repos/...``) ou URL completa."""
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if path.startswith("/repos/"):
            return f"{API_BASE}{path}"
        return f"{API_BASE}/repos/{self.base_repo}/{path.lstrip('/')}"

    def _repo_url(self, suffix):
        return f"{API_BASE}/repos/{self.base_repo}/{suffix.lstrip('/')}"

    # ------------------------------------------------------------------
    # Primitivas
    # ------------------------------------------------------------------
    def get_json(self, path, default=None):
        """GET + JSON; 404 retorna ``default``; outros erros levantam BotNetworkError."""
        url = self._api_url(path)
        status, body = self._send("GET", url, headers=self._headers())
        if status == 200:
            payload = self._decode_json(body)
            return payload if payload is not None else default
        if status == 404:
            return default
        raise BotNetworkError(f"GET {url} => HTTP {status}")

    def post(self, path, data):
        """POST JSON; retorna ``(status, payload_ou_None)``."""
        payload_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
        status, body = self._send("POST", self._api_url(path), data=payload_bytes,
                                  headers=self._headers({"Content-Type": "application/json"}))
        return status, self._decode_json(body)

    def patch(self, path, data):
        """PATCH JSON; retorna ``(status, payload_ou_None)``."""
        payload_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
        status, body = self._send("PATCH", self._api_url(path), data=payload_bytes,
                                  headers=self._headers({"Content-Type": "application/json"}))
        return status, self._decode_json(body)

    def _list_all(self, suffix, params=None):
        """Listagem paginada (per_page=100); status != 200 levanta BotNetworkError."""
        query = dict(params or {})
        items = []
        for page in range(1, MAX_LIST_PAGES + 1):
            query["page"] = page
            query["per_page"] = 100
            url = f"{self._repo_url(suffix)}?{urllib.parse.urlencode(query)}"
            status, body = self._send("GET", url, headers=self._headers())
            if status != 200:
                raise BotNetworkError(f"listagem {suffix} => HTTP {status}")
            batch = self._decode_json(body)
            if not isinstance(batch, list):
                raise BotNetworkError(f"listagem {suffix} => resposta inesperada")
            items.extend(batch)
            if len(batch) < 100:
                break
        return items

    def raw_get(self, url):
        """GET cru de qualquer URL; retorna bytes ou None (404/erro de rede).

        Só levanta exceção em problema de autenticação (``BotAuthError``).
        """
        try:
            status, body = self._send("GET", url, headers=self._headers({"Accept": "*/*"}))
        except BotAuthError:
            raise
        except BotNetworkError:
            return None
        return body if status == 200 else None

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------
    def list_labels(self):
        """Labels do repositório base (lista de dicts)."""
        return self._list_all("labels")

    def create_label(self, name, color, description=""):
        """Cria a label; True se criada (201) ou já existia (422)."""
        status, _ = self.post("labels", {"name": name, "color": color, "description": description})
        return status in (200, 201, 422)

    def ensure_label(self, name, color, description=""):
        """Garante a label: tenta criar; em 422/ausência confirma via listagem."""
        try:
            if self.create_label(name, color, description):
                return True
        except BotAuthError:
            raise
        except BotNetworkError:
            pass
        try:
            return any(label.get("name") == name for label in self.list_labels())
        except BotAuthError:
            raise
        except BotNetworkError:
            return False

    # ------------------------------------------------------------------
    # Milestones e commits
    # ------------------------------------------------------------------
    def list_milestones(self):
        """Milestones (todos os estados) do repositório base."""
        return self._list_all("milestones", {"state": "all"})

    def list_commits(self, per_page):
        """Commits mais recentes (limite de 100 por chamada)."""
        count = max(1, min(int(per_page), 100))
        url = f"{self._repo_url('commits')}?per_page={count}"
        status, body = self._send("GET", url, headers=self._headers())
        if status != 200:
            raise BotNetworkError(f"list_commits => HTTP {status}")
        payload = self._decode_json(body)
        return payload if isinstance(payload, list) else []

    def get_commit(self, sha):
        """Detalhe de um commit (dict) ou None em 404."""
        return self.get_json(f"commits/{sha}")

    # ------------------------------------------------------------------
    # Issues
    # ------------------------------------------------------------------
    def create_issue(self, title, body, labels=None):
        """Cria issue; retorna o payload (dict com number/html_url) ou levanta erro."""
        status, payload = self.post("issues", {"title": title, "body": body,
                                               "labels": list(labels or [])})
        if status != 201 or not isinstance(payload, dict):
            raise BotNetworkError(f"create_issue => HTTP {status}")
        return payload

    def add_issue_comment(self, number, body):
        """Comenta em um issue; retorna o payload do comentário ou levanta erro."""
        status, payload = self.post(f"issues/{number}/comments", {"body": body})
        if status != 201 or not isinstance(payload, dict):
            raise BotNetworkError(f"add_issue_comment(#{number}) => HTTP {status}")
        return payload

    def update_issue(self, number, **fields):
        """Atualiza o issue (state/title etc.); retorna o payload atualizado."""
        allowed = {key: value for key, value in fields.items()
                   if key in ("state", "title", "body", "labels", "milestone")}
        status, payload = self.patch(f"issues/{number}", allowed)
        if status != 200 or not isinstance(payload, dict):
            raise BotNetworkError(f"update_issue(#{number}) => HTTP {status}")
        return payload

    def list_issues(self, state="open", labels=""):
        """Issues do repositório (PRs filtrados fora), por estado e/ou labels."""
        params = {"state": state}
        if labels:
            params["labels"] = labels
        items = self._list_all("issues", params)
        return [item for item in items if "pull_request" not in item]

    # ------------------------------------------------------------------
    # Arquivos em outros repositórios
    # ------------------------------------------------------------------
    def get_file_contents(self, repo_owner, repo, path, ref, host="github"):
        """Conteúdo textual de um arquivo em outro repositório.

        host="github": https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}
        host="gerrit": https://{base_gerrit}/{repo}/+/refs/heads/{ref}/{path}?format=TEXT
        (resposta base64 — formato do android.googlesource.com; para o AOSP,
        passe ``repo_owner`` como a URL base, ex.: "https://android.googlesource.com").

        Retorna ``str`` ou ``None`` (404/erro de rede/conteúdo não textual);
        só levanta exceção em falha de autenticação (``BotAuthError``).
        """
        clean_path = str(path).lstrip("/")
        if host == "gerrit":
            base = repo_owner if str(repo_owner).startswith("http") else f"https://{repo_owner}"
            url = f"{base}/{repo}/+/refs/heads/{ref}/{clean_path}?format=TEXT"
            raw = self.raw_get(url)
            if raw is None:
                return None
            try:
                return base64.b64decode(raw).decode("utf-8", errors="replace")
            except (ValueError, UnicodeDecodeError):
                return None
        url = f"https://raw.githubusercontent.com/{repo_owner}/{repo}/{ref}/{clean_path}"
        raw = self.raw_get(url)
        if raw is None:
            return None
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("utf-8", errors="replace")
