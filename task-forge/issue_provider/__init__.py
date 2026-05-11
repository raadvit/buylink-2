"""Issue provider abstraction (US-188).

Aktivní target systém se vybírá podle env proměnné `TARGET_SYSTEM` (`github` | `jira`,
default `github`). Volání `get_provider()` vrátí singleton instance odpovídajícího
provideru. Pro test/runtime přepnutí targetu lze zavolat `reset_provider()`.
"""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

from . import _wiki  # noqa: F401 — re-export pro consumery (např. task-forge.py)


@runtime_checkable
class IssueProvider(Protocol):
    """Kontrakt pro úložiště issues (GitHub / JIRA).

    Návratový shape `create_story` / `update_story` / `list_issues` / `get_issue` musí být
    identický napříč implementacemi (per AC3 US-188), aby UI a Flask endpointy nemusely
    rozlišovat target.
    """

    def create_story(
        self,
        title: str,
        body: str,
        epic: str,
        repo_root: str,
        files=None,
        labels: list[str] | None = None,
    ) -> dict: ...

    def update_story(
        self,
        issue_number: int,
        title: str,
        body: str,
        wiki_path: str,
        repo_root: str,
        files=None,
        epic: str = "",
    ) -> dict: ...

    def attach_files_to_story(
        self,
        issue_number: int,
        wiki_path: str,
        repo_root: str,
        files,
        epic: str = "",
    ) -> None: ...

    def upload_attachment_bytes(
        self,
        issue_number: int,
        filename: str,
        data: bytes,
    ) -> None: ...

    def list_issues(self, state: str) -> list[dict]: ...

    def get_issue(self, issue_number: int) -> dict: ...

    def update_body(self, issue_number: int, body: str) -> None: ...

    def close_issue(self, issue_number: int) -> None: ...

    def transition_status(self, issue_number: int, status: str) -> None: ...

    def archive_issue(self, issue_number: int) -> None: ...


_provider_singleton: IssueProvider | None = None


def _build_provider() -> IssueProvider:
    target = os.environ.get("TARGET_SYSTEM", "github").strip().lower() or "github"
    if target == "github":
        from .github import GitHubProvider

        return GitHubProvider()
    if target == "jira":
        from .jira import JiraProvider

        return JiraProvider()
    raise ValueError(f"Neznámý TARGET_SYSTEM: {target!r} (povoleno: 'github', 'jira')")


def get_provider() -> IssueProvider:
    """Vrátí aktivního providera (lazy singleton, postavený podle `TARGET_SYSTEM`)."""
    global _provider_singleton
    if _provider_singleton is None:
        _provider_singleton = _build_provider()
    return _provider_singleton


def reset_provider() -> None:
    """Vyforsuje rebuild providera z env při dalším `get_provider()` volání.

    Určeno pro testy, které potřebují měnit `TARGET_SYSTEM` mezi případy.
    """
    global _provider_singleton
    _provider_singleton = None


__all__ = ["IssueProvider", "get_provider", "reset_provider"]
