"""Integrační testy pro GET /api/issues/{id} — výběr pokročilejšího statusu z provider/wiki."""

import importlib.util as _ilu
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent))

_spec = _ilu.spec_from_file_location(
    "task_forge",
    Path(__file__).resolve().parent / "main.py",
)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
app = _mod.app


def _provider_issue(status: str = "new") -> dict:
    body = (
        "# Test story\n\n"
        f"- Status: {status}\n"
        "- Epic: EP-01\n"
        "- Role: admin\n"
    )
    return {
        "number": 42,
        "title": "Test story",
        "labels": [{"name": "user story"}],
        "state": "OPEN",
        "updatedAt": "2026-04-28T12:00:00Z",
        "body": body,
    }


class TestGetIssueAdvancedStatus(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def _provider_mock(self, gh_status: str):
        provider = MagicMock()
        provider.get_issue.return_value = _provider_issue(gh_status)
        return provider

    # --- BUG FIX: provider má `ready_for_testing`, wiki má `draft` → vrátit `ready_for_testing` ---

    def test_provider_more_advanced_than_wiki_returns_provider_status(self):
        wiki_content = "- Status: draft\n- Epic: EP-01\n"
        with patch.object(_mod, "get_provider", return_value=self._provider_mock("ready_for_testing")), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_text", return_value=wiki_content):
            resp = self.client.get("/api/issues/42")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["story_status"], "ready_for_testing")
        self.assertEqual(data["status"], "ready_for_testing")

    # --- Wiki má pokročilejší status než provider → vrátit wiki status ---

    def test_wiki_more_advanced_than_provider_returns_wiki_status(self):
        wiki_content = "- Status: clarify\n- Epic: EP-01\n"
        with patch.object(_mod, "get_provider", return_value=self._provider_mock("new")), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_text", return_value=wiki_content):
            resp = self.client.get("/api/issues/42")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["story_status"], "clarify")
        self.assertEqual(data["status"], "clarify")

    # --- Oba zdroje mají stejný status → vrátit ho ---

    def test_both_sources_same_status(self):
        wiki_content = "- Status: ready_for_testing\n- Epic: EP-01\n"
        with patch.object(_mod, "get_provider", return_value=self._provider_mock("ready_for_testing")), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_text", return_value=wiki_content):
            resp = self.client.get("/api/issues/42")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["story_status"], "ready_for_testing")

    # --- Wiki nemá status → použít status z provideru ---

    def test_fallback_to_provider_when_wiki_has_no_status(self):
        wiki_content = "# Test story\n\n## Co se zobrazuje\nNěco.\n"
        with patch.object(_mod, "get_provider", return_value=self._provider_mock("validated")), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_text", return_value=wiki_content):
            resp = self.client.get("/api/issues/42")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["story_status"], "validated")

    # --- Wiki neexistuje → použít status z provideru ---

    def test_fallback_to_provider_when_no_wiki(self):
        with patch.object(_mod, "get_provider", return_value=self._provider_mock("draft")), \
             patch("pathlib.Path.exists", return_value=False):
            resp = self.client.get("/api/issues/42")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["story_status"], "draft")

    # --- External dependency failure: 404 ---

    def test_provider_not_found_returns_404(self):
        provider = MagicMock()
        provider.get_issue.side_effect = FileNotFoundError("Issue nenalezena.")
        with patch.object(_mod, "get_provider", return_value=provider):
            resp = self.client.get("/api/issues/42")
        self.assertEqual(resp.status_code, 404)

    # --- External dependency failure: 502 ---

    def test_provider_runtime_error_returns_502(self):
        provider = MagicMock()
        provider.get_issue.side_effect = RuntimeError("JIRA spojení selhalo")
        with patch.object(_mod, "get_provider", return_value=provider):
            resp = self.client.get("/api/issues/42")
        self.assertEqual(resp.status_code, 502)

    # --- Wiki má `needs-clarify`, provider má `draft` → vrátit `needs-clarify` ---

    def test_wiki_needs_clarify_wins_over_provider_draft(self):
        wiki_content = "- Status: needs-clarify\n- Epic: EP-01\n"
        with patch.object(_mod, "get_provider", return_value=self._provider_mock("draft")), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_text", return_value=wiki_content):
            resp = self.client.get("/api/issues/42")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["story_status"], "needs-clarify")


if __name__ == "__main__":
    unittest.main()
