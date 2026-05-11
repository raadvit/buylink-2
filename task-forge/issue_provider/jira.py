"""JiraProvider — implementace `IssueProvider` přes JIRA REST API.

Používá `urllib.request` (stdlib, žádné nové dependencies). MCP `mcp-atlassian`
je vyhrazen pro interaktivní Claude Code agenty (clarify/analyze) — Flask runtime
volá REST přímo s Bearer auth (Personal Access Token).

Auth env: `JIRA_URL`, `JIRA_USERNAME` (pro logování / kompatibilitu), `JIRA_PERSONAL_TOKEN`,
`JIRA_SSL_VERIFY` (default `true`).

Status mapping je injektivní (interní → JIRA name), reverzní mapa se buduje z env
při inicializaci provideru. Project prefix čte `JIRA_PROJECTS_FILTER` (default `DSC`).
"""

from __future__ import annotations

import json as _json
import mimetypes
import os
import pathlib
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid as _uuid
from typing import Any

from . import _wiki


_TIMEOUT = 30

# Forward mapa interních statusů → env klíč (jméno JIRA stavu se čte z env při __init__).
_STATUS_ENV_MAP = {
    "draft":             "JIRA_STATUS_DRAFT",
    "conflict-check":    "JIRA_STATUS_CONFLICT_CHECK",
    "ready-for-arch":    "JIRA_STATUS_READY_FOR_ARCH",
    "validated":         "JIRA_STATUS_VALIDATED",
    "in_development":    "JIRA_STATUS_IN_DEVELOPMENT",
    "in-development":    "JIRA_STATUS_IN_DEVELOPMENT",
    "ready_for_review":  "JIRA_STATUS_READY_FOR_REVIEW",
    "ready_for_testing": "JIRA_STATUS_READY_FOR_TESTING",
    "ready-for-testing": "JIRA_STATUS_READY_FOR_TESTING",
    "done":              "JIRA_STATUS_DONE",
    "blocked":           "JIRA_STATUS_BLOCKED",
    "cancelled":         "JIRA_STATUS_CANCELLED",
}

# JIRA labely nesmí obsahovat whitespace. Mapa interní (s mezerami) → JIRA bezpečná podoba.
_LABEL_MAP_INTERNAL_TO_JIRA = {
    "user story": "user-story",
}
_LABEL_MAP_JIRA_TO_INTERNAL = {v: k for k, v in _LABEL_MAP_INTERNAL_TO_JIRA.items()}


def _label_to_jira(label: str) -> str:
    if label in _LABEL_MAP_INTERNAL_TO_JIRA:
        return _LABEL_MAP_INTERNAL_TO_JIRA[label]
    # Defensive: jakýkoli whitespace nahradíme pomlčkou.
    return re.sub(r"\s+", "-", label) if label else label


def _label_from_jira(label: str) -> str:
    return _LABEL_MAP_JIRA_TO_INTERNAL.get(label, label)


_DEFAULT_STATUS_NAMES = {
    "JIRA_STATUS_DRAFT":             "To Do",
    "JIRA_STATUS_CONFLICT_CHECK":    "To Do",
    "JIRA_STATUS_READY_FOR_ARCH":    "To Do",
    "JIRA_STATUS_VALIDATED":         "Selected for Development",
    "JIRA_STATUS_IN_DEVELOPMENT":    "In Progress",
    "JIRA_STATUS_READY_FOR_REVIEW":  "In Review",
    "JIRA_STATUS_READY_FOR_TESTING": "Testing",
    "JIRA_STATUS_DONE":              "Done",
    "JIRA_STATUS_BLOCKED":           "Blocked",
    "JIRA_STATUS_CANCELLED":         "Cancelled",
}


def _jira_to_markdown(body: str) -> str:
    """Konvertuje Jira wiki markup na Markdown (pro lokální wiki soubory)."""
    lines = body.split("\n")
    result = []
    for line in lines:
        if line.startswith("h1. "):
            result.append("# " + line[4:])
        elif line.startswith("h2. "):
            result.append("## " + line[4:])
        elif line.startswith("h3. "):
            result.append("### " + line[4:])
        elif line.startswith(" * "):
            result.append("- " + line[3:])
        elif line.startswith(" - "):
            result.append("- " + line[3:])
        else:
            result.append(line)
    return "\n".join(result)


def _markdown_to_jira(body: str) -> str:
    """Konvertuje Markdown na Jira wiki markup (pro JIRA API).

    Metadata před první ## sekcí → ' - prefix'; obsah v sekcích → ' * prefix'.
    Pokud Figma_image metadata existuje a je Design sekce, vloží thumbnail.
    Inline konverze: **bold** → *bold*, číslované seznamy, inline kód.
    """
    lines = body.split("\n")
    result = []
    in_metadata = True
    for i, line in enumerate(lines):
        if i == 0 and line.startswith("# "):
            result.append("h1. " + line[2:])
        elif line.startswith("## "):
            in_metadata = False
            result.append("h2. " + line[3:])
        elif line.startswith("### "):
            result.append("h3. " + line[4:])
        elif re.match(r"^\d+\. ", line) and not in_metadata:
            # Číslovaný seznam → Jira ordered list
            result.append("# " + re.sub(r"^\d+\. ", "", line))
        elif line.startswith("- ") and in_metadata:
            result.append(" - " + line[2:])
        elif line.startswith("- ") and not in_metadata:
            result.append(" * " + line[2:])
        else:
            result.append(line)
    jira_body = "\n".join(result)
    # **bold** → *bold*
    jira_body = re.sub(r"\*\*([^*\n]+)\*\*", r"*\1*", jira_body)
    # `inline code` → {{code}}
    jira_body = re.sub(r"`([^`\n]+)`", r"{{\1}}", jira_body)
    # Figma thumbnail
    figma_m = re.search(r"(?m)^ - Figma_image:\s*(.+)$", jira_body)
    if figma_m and re.search(r"h2\. Design", jira_body):
        img_name = pathlib.Path(figma_m.group(1).strip()).name
        thumbnail = f"!{img_name}|thumbnail!"
        if thumbnail not in jira_body:
            jira_body = re.sub(
                r"(h2\. Design[^\n]*\n)",
                rf"\1 - {thumbnail}\n",
                jira_body, count=1,
            )
    return jira_body


class JiraProvider:
    """Provider nad JIRA REST API. Aktivní pokud `TARGET_SYSTEM=jira`."""

    def __init__(self) -> None:
        self.base_url = os.environ.get("JIRA_URL", "").rstrip("/")
        self.username = os.environ.get("JIRA_USERNAME", "")
        self.token = os.environ.get("JIRA_PERSONAL_TOKEN", "")
        ssl_verify_raw = os.environ.get("JIRA_SSL_VERIFY", "true").strip().lower()
        self.ssl_verify = ssl_verify_raw not in ("false", "0", "no", "off")
        self.project = os.environ.get("JIRA_PROJECTS_FILTER", "DSC").strip() or "DSC"

        # Status forward + reverse mapa (interní → JIRA name)
        self.status_map: dict[str, str] = {}
        for internal, env_key in _STATUS_ENV_MAP.items():
            value = os.environ.get(env_key, _DEFAULT_STATUS_NAMES.get(env_key, ""))
            if value:
                self.status_map[internal] = value
        # Reverzní mapa (JIRA name → interní). Pokud více interních ukazuje na stejný JIRA
        # name, vyhrává deterministicky podle definovaného pořadí v `_STATUS_ENV_MAP`.
        self.status_map_reverse: dict[str, str] = {}
        priority_order = list(_STATUS_ENV_MAP.keys())
        for internal in priority_order:
            jira_name = self.status_map.get(internal)
            if jira_name and jira_name not in self.status_map_reverse:
                self.status_map_reverse[jira_name] = internal

    # ── Public mapping helpers (testovatelné) ──────────────────────────────

    def map_status(self, internal: str) -> str | None:
        """Interní status → JIRA status name. None pokud neznámý."""
        return self.status_map.get(internal)

    def map_status_reverse(self, jira_name: str) -> str | None:
        """JIRA status name → interní status. None pokud neznámý."""
        return self.status_map_reverse.get(jira_name)

    def jira_key(self, issue_number: int | str) -> str:
        """`US-007` / `7` → `DSC-7` (per `JIRA_PROJECTS_FILTER`)."""
        if isinstance(issue_number, str):
            m = re.search(r"(\d+)$", issue_number)
            if not m:
                raise ValueError(f"Nepodařilo se extrahovat číslo z '{issue_number}'")
            n = int(m.group(1))
        else:
            n = int(issue_number)
        return f"{self.project}-{n}"

    # ── REST helper ────────────────────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        query: dict | None = None,
    ) -> Any:
        if not self.base_url:
            raise RuntimeError("JIRA_URL není nakonfigurováno.")
        if not self.token:
            raise RuntimeError("JIRA_PERSONAL_TOKEN není nakonfigurováno.")

        url = self.base_url + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        data = _json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url=url, data=data, method=method, headers=headers)

        ctx: ssl.SSLContext | None = None
        if not self.ssl_verify and url.lower().startswith("https"):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT, context=ctx) as resp:
                raw = resp.read()
                if not raw:
                    return None
                try:
                    return _json.loads(raw.decode("utf-8"))
                except Exception:
                    return raw.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode("utf-8", errors="replace")
            except Exception:
                detail = ""
            if e.code == 404:
                raise FileNotFoundError(f"JIRA 404 {path}: {detail or e.reason}")
            raise RuntimeError(f"JIRA HTTP {e.code} {path}: {detail or e.reason}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"JIRA spojení selhalo {path}: {e.reason}")

    # ── attachment upload ──────────────────────────────────────────────────

    def _upload_attachment(self, jira_key: str, filename: str, data: bytes) -> None:
        """Nahraje soubor jako přílohu Jira ticketu přes multipart/form-data."""
        boundary = _uuid.uuid4().hex
        ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {ctype}\r\n"
            "\r\n"
        ).encode("utf-8") + data + f"\r\n--{boundary}--\r\n".encode("utf-8")

        url = f"{self.base_url}/rest/api/2/issue/{jira_key}/attachments"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Atlassian-Token": "no-check",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }
        req = urllib.request.Request(url=url, data=body, method="POST", headers=headers)

        ctx: ssl.SSLContext | None = None
        if not self.ssl_verify and url.lower().startswith("https"):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT, context=ctx) as resp:
                resp.read()
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode("utf-8", errors="replace")
            except Exception:
                detail = ""
            raise RuntimeError(f"JIRA attachment upload HTTP {e.code} ({filename}): {detail or e.reason}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"JIRA attachment upload selhalo ({filename}): {e.reason}")

    def upload_attachment_bytes(self, issue_number: int, filename: str, data: bytes) -> None:
        """Nahraje bytes jako přílohu Jira ticketu."""
        self._upload_attachment(self.jira_key(issue_number), filename, data)

    # ── shape mapper ───────────────────────────────────────────────────────

    def _to_issue_shape(self, j_issue: dict) -> dict:
        """JIRA issue → kompatibilní shape s `gh issue view --json …`."""
        key = j_issue.get("key", "")
        m = re.search(r"(\d+)$", key)
        number = int(m.group(1)) if m else 0
        fields = j_issue.get("fields", {}) or {}
        title = fields.get("summary", "") or ""
        body = fields.get("description") or ""
        labels_raw = fields.get("labels") or []
        labels = [{"name": _label_from_jira(str(l))} for l in labels_raw]
        status_obj = fields.get("status") or {}
        jira_status_name = status_obj.get("name", "") or ""
        gh_state = "OPEN"
        cat = (status_obj.get("statusCategory") or {}).get("key", "")
        if cat == "done":
            gh_state = "CLOSED"
        updated = fields.get("updated", "") or ""
        return {
            "number": number,
            "title": title,
            "labels": labels,
            "updatedAt": updated,
            "body": body,
            "state": gh_state,
            "jira_key": key,
            "jira_status": jira_status_name,
        }

    # ── IssueProvider impl ────────────────────────────────────────────────

    def create_story(
        self,
        title: str,
        body: str,
        epic: str,
        repo_root: str,
        files=None,
        labels: list[str] | None = None,
    ) -> dict:
        # body je vždy Markdown (z _build_draft_body()); lokální wiki = Markdown, Jira API = Jira markup
        root = pathlib.Path(repo_root)
        stories_dir = root / "wiki" / "stories"
        stories_dir.mkdir(parents=True, exist_ok=True)

        issuetype = "Bug" if labels and "bug" in labels else "Story"
        fields: dict[str, Any] = {
            "project": {"key": self.project},
            "summary": title,
            "description": _markdown_to_jira(body),
            "issuetype": {"name": issuetype},
        }
        if labels:
            fields["labels"] = [_label_to_jira(l) for l in labels]

        try:
            created = self._request("POST", "/rest/api/2/issue", body={"fields": fields})
        except FileNotFoundError as e:
            raise RuntimeError(f"JIRA project not found: {e}")

        if not isinstance(created, dict) or "key" not in created:
            raise RuntimeError(f"Neplatná odpověď JIRA create issue: {created!r}")

        jira_key = created["key"]
        m = re.search(r"(\d+)$", jira_key)
        if not m:
            raise RuntimeError(f"Nepodařilo se zparsovat klíč JIRA: {jira_key}")
        issue_number = int(m.group(1))
        story_id = f"US-{issue_number:03d}"
        wiki_path = stories_dir / f"{story_id}.md"

        # Inject Jira metadata do Markdown body; lokální wiki = Markdown
        updated_body = self._inject_jira_metadata(body, jira_key)
        wiki_path.write_text(updated_body, encoding="utf-8")

        final_body = updated_body
        if files:
            assets_dir, md_prefix = _wiki.assets_info(root, story_id, epic)
            saved = _wiki.save_files_to_assets(files, assets_dir)
            if saved:
                final_body = updated_body + _wiki.attachments_section(saved, md_prefix)
                wiki_path.write_text(final_body, encoding="utf-8")
                for fname in saved:
                    try:
                        self._upload_attachment(jira_key, fname, (assets_dir / fname).read_bytes())
                    except Exception as e:
                        print(f"[jira] Varování: příloha {fname} nebyla nahrána: {e}", file=sys.stderr)

        # Aktualizuj Jira ticket s metadaty (a příp. attachmenty) — konverze Markdown → Jira markup
        try:
            self._request(
                "PUT", f"/rest/api/2/issue/{jira_key}",
                body={"fields": {"description": _markdown_to_jira(final_body)}},
            )
        except Exception as e:
            print(f"[jira] Varování: update description selhal: {e}", file=sys.stderr)

        relative_wiki_path = str(wiki_path.relative_to(root))
        _wiki.git_commit_wiki(relative_wiki_path, root, f"[{story_id}] wiki: vytvoření story")
        _wiki.delete_if_done(wiki_path, root, updated_body)

        issue_url = f"{self.base_url}/browse/{jira_key}"
        return {
            "issue_url": issue_url,
            "issue_number": issue_number,
            "wiki_path": relative_wiki_path,
            "jira_key": jira_key,
        }

    def update_story(
        self,
        issue_number: int,
        title: str,
        body: str,
        wiki_path: str,
        repo_root: str,
        files=None,
        epic: str = "",
    ) -> dict:
        # body je vždy Markdown; lokální wiki = Markdown, Jira API = Jira markup
        root = pathlib.Path(repo_root)
        full_path = (root / wiki_path).resolve()
        if not full_path.is_relative_to(root.resolve()):
            raise ValueError(f"wiki_path vede mimo repo root: {wiki_path}")
        story_id = pathlib.Path(wiki_path).stem
        jira_key = self.jira_key(issue_number)

        body = self._inject_jira_metadata(body, jira_key)

        existing_attachments = ""
        if full_path.exists():
            existing_attachments = _wiki.extract_existing_attachments(
                full_path.read_text(encoding="utf-8")
            )

        final_body = body + existing_attachments

        if files:
            assets_dir, md_prefix = _wiki.assets_info(root, story_id, epic)
            saved = _wiki.save_files_to_assets(files, assets_dir)
            if saved:
                new_links = "\n".join(
                    f"- [{fname}]({md_prefix}/{fname})" for fname in saved
                )
                if existing_attachments:
                    final_body = body + existing_attachments.rstrip() + "\n" + new_links
                else:
                    final_body = body + _wiki.attachments_section(saved, md_prefix)
                for fname in saved:
                    try:
                        self._upload_attachment(jira_key, fname, (assets_dir / fname).read_bytes())
                    except Exception as e:
                        print(f"[jira] Varování: příloha {fname} nebyla nahrána: {e}", file=sys.stderr)

        # Lokální wiki = Markdown; Jira API dostane konvertovaný Jira markup
        full_path.write_text(final_body, encoding="utf-8")

        try:
            self._request(
                "PUT", f"/rest/api/2/issue/{jira_key}",
                body={"fields": {"summary": title, "description": _markdown_to_jira(final_body)}},
            )
        except FileNotFoundError as e:
            raise RuntimeError(f"JIRA issue {jira_key} nenalezena: {e}")

        _wiki.git_commit_wiki(wiki_path, root, f"[{story_id}] wiki: aktualizace")
        _wiki.delete_if_done(full_path, root, final_body)
        return {
            "issue_url": f"{self.base_url}/browse/{jira_key}",
            "issue_number": int(issue_number),
            "wiki_path": wiki_path,
            "jira_key": jira_key,
        }

    def attach_files_to_story(
        self,
        issue_number: int,
        wiki_path: str,
        repo_root: str,
        files,
        epic: str = "",
    ) -> None:
        root = pathlib.Path(repo_root)
        full_path = root / wiki_path
        story_id = pathlib.Path(wiki_path).stem
        jira_key = self.jira_key(issue_number)

        if not full_path.exists():
            raise RuntimeError(f"Wiki soubor nenalezen: {wiki_path}")

        assets_dir, md_prefix = _wiki.assets_info(root, story_id, epic)
        saved = _wiki.save_files_to_assets(files, assets_dir)
        if not saved:
            return

        current_content = full_path.read_text(encoding="utf-8")
        existing_att = _wiki.extract_existing_attachments(current_content)
        new_links = "\n".join(f"- [{fname}]({md_prefix}/{fname})" for fname in saved)

        if existing_att:
            base = current_content[: current_content.rfind(existing_att)]
            final_content = base.rstrip() + existing_att.rstrip() + "\n" + new_links + "\n"
        else:
            final_content = current_content.rstrip() + "\n\n## Přílohy\n" + new_links + "\n"

        full_path.write_text(final_content, encoding="utf-8")

        try:
            self._request(
                "PUT", f"/rest/api/2/issue/{jira_key}",
                body={"fields": {"description": _markdown_to_jira(final_content)}},
            )
        except Exception as e:
            print(f"[jira] Varování: nepodařilo se aktualizovat description: {e}", file=sys.stderr)

        for fname in saved:
            try:
                self._upload_attachment(jira_key, fname, (assets_dir / fname).read_bytes())
            except Exception as e:
                print(f"[jira] Varování: příloha {fname} nebyla nahrána: {e}", file=sys.stderr)

    def list_issues(self, state: str) -> list[dict]:
        if state not in ("open", "closed", "all"):
            state = "open"
        jql_parts = [f"project = {self.project}"]
        if state == "open":
            jql_parts.append("statusCategory != Done")
        elif state == "closed":
            jql_parts.append("statusCategory = Done")
        jql = " AND ".join(jql_parts)

        try:
            data = self._request(
                "POST", "/rest/api/2/search",
                body={
                    "jql": jql,
                    "fields": ["summary", "labels", "status", "updated", "description"],
                    "maxResults": 200,
                },
            )
        except FileNotFoundError as e:
            raise RuntimeError(f"JIRA project not found: {e}")

        issues = (data or {}).get("issues", []) if isinstance(data, dict) else []
        return [self._to_issue_shape(issue) for issue in issues]

    def get_issue(self, issue_number: int) -> dict:
        jira_key = self.jira_key(issue_number)
        data = self._request("GET", f"/rest/api/2/issue/{jira_key}")
        if not isinstance(data, dict):
            raise RuntimeError(f"Neplatná odpověď JIRA get issue: {data!r}")
        return self._to_issue_shape(data)

    def update_body(self, issue_number: int, body: str) -> None:
        # body je vždy Markdown; konvertujeme na Jira markup před odesláním do API
        jira_key = self.jira_key(issue_number)
        try:
            self._request(
                "PUT", f"/rest/api/2/issue/{jira_key}",
                body={"fields": {"description": _markdown_to_jira(body)}},
            )
        except FileNotFoundError as e:
            raise RuntimeError(f"JIRA issue {jira_key} nenalezena: {e}")

    def close_issue(self, issue_number: int) -> None:
        self.transition_status(issue_number, "done")

    def archive_issue(self, issue_number: int) -> None:
        # JIRA archivace je řízená přímo v JIRA workflow — Task-forge necháme issue být
        # a archivujeme jen lokální wiki. (Zachováváme původní chování ze starého kódu.)
        return None

    def transition_status(self, issue_number: int, status: str) -> None:
        jira_key = self.jira_key(issue_number)
        target_name = self.map_status(status)
        if not target_name:
            raise RuntimeError(f"Neznámý interní status pro JIRA mapping: {status!r}")

        try:
            data = self._request("GET", f"/rest/api/2/issue/{jira_key}/transitions")
        except FileNotFoundError as e:
            raise RuntimeError(f"JIRA issue {jira_key} nenalezena: {e}")

        transitions = (data or {}).get("transitions", []) if isinstance(data, dict) else []
        transition_id: str | None = None
        for t in transitions:
            tname = ((t.get("to") or {}).get("name") or t.get("name") or "").strip()
            if tname.lower() == target_name.lower():
                transition_id = str(t.get("id"))
                break
        if not transition_id:
            available = ", ".join(
                ((t.get("to") or {}).get("name") or t.get("name") or "?") for t in transitions
            ) or "(žádné)"
            raise RuntimeError(
                f"JIRA: transition na '{target_name}' není dostupná pro {jira_key}. "
                f"Dostupné: {available}"
            )

        self._request(
            "POST", f"/rest/api/2/issue/{jira_key}/transitions",
            body={"transition": {"id": transition_id}},
        )

    # ── helpers ────────────────────────────────────────────────────────────

    def _inject_jira_metadata(self, body: str, jira_key: str) -> str:
        """Přidá `jira_key` a `target_system` do metadat wiki.

        Podporuje Markdown formát (`- Status:`) i Jira markup formát (` - Status:`).
        """
        is_jira_fmt = bool(re.match(r"\s*h1\.", body))
        pfx = " - " if is_jira_fmt else "- "
        status_marker = f"{pfx}Status:"

        if is_jira_fmt:
            # Jira markup: nahradíme placeholder " - Jira: " za key
            body = re.sub(r"(?m)^ - Jira:[ \t]*.*$", f" - Jira: {jira_key}", body, count=1)
        else:
            # Markdown: nahradíme "- GitHub: " za key
            body = re.sub(r"(?m)^(- GitHub:[ \t]*).*$", rf"\g<1>{jira_key}", body, count=1)

        jira_key_line = f"{pfx}jira_key:"
        if jira_key_line in body:
            body = re.sub(
                rf"(?m)^{re.escape(jira_key_line)}.*$",
                f"{jira_key_line} {jira_key}", body, count=1,
            )
        else:
            if status_marker in body:
                body = body.replace(status_marker, f"{jira_key_line} {jira_key}\n{status_marker}", 1)
            else:
                body = body.rstrip() + f"\n{jira_key_line} {jira_key}\n"

        target_line = f"{pfx}target_system:"
        if target_line in body:
            body = re.sub(
                rf"(?m)^{re.escape(target_line)}.*$",
                f"{target_line} jira", body, count=1,
            )
        else:
            if status_marker in body:
                body = body.replace(status_marker, f"{target_line} jira\n{status_marker}", 1)
            else:
                body = body.rstrip() + f"\n{target_line} jira\n"
        return body
