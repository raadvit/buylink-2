"""Integrační testy pro endpointy migrované na issue_provider (US-188).

Pokrývá:
- GET /api/issues (list) přes `provider.list_issues`
- PATCH /api/bugs/<id>/status přes `provider.get_issue` + `update_body` + `transition_status`
"""

import importlib.util as _ilu
import json as _json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent))

_spec = _ilu.spec_from_file_location(
    "task_forge",
    Path(__file__).resolve().parent / "task-forge.py",
)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
app = _mod.app


# ── GET /api/issues (list) ──────────────────────────────────────────────────


class TestListIssuesEndpoint(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_list_uses_provider_and_parses_metadata(self):
        provider = MagicMock()
        provider.list_issues.return_value = [{
            "number": 7,
            "title": "Test bug",
            "labels": [{"name": "bug"}],
            "updatedAt": "2026-04-30T10:00:00Z",
            "body": "- Epic: EP-01\n- Status: new\n",
            "state": "OPEN",
        }]
        with patch.object(_mod, "get_provider", return_value=provider):
            resp = self.client.get("/api/issues?state=open")

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], 7)
        self.assertEqual(data[0]["type"], "bug")
        self.assertEqual(data[0]["epic"], "EP-01")
        self.assertEqual(data[0]["story_status"], "new")
        provider.list_issues.assert_called_once_with("open")

    def test_list_normalizes_invalid_state(self):
        provider = MagicMock()
        provider.list_issues.return_value = []
        with patch.object(_mod, "get_provider", return_value=provider):
            resp = self.client.get("/api/issues?state=garbage")

        self.assertEqual(resp.status_code, 200)
        provider.list_issues.assert_called_once_with("open")

    def test_list_provider_runtime_error_returns_502(self):
        provider = MagicMock()
        provider.list_issues.side_effect = RuntimeError("JIRA HTTP 500")
        with patch.object(_mod, "get_provider", return_value=provider):
            resp = self.client.get("/api/issues")
        self.assertEqual(resp.status_code, 502)
        self.assertIn("JIRA HTTP 500", resp.get_json()["error"])


# ── PATCH /api/bugs/<id>/status ─────────────────────────────────────────────


def _bug_issue(status: str = "new") -> dict:
    body = (
        "# Bug\n\n"
        "- Epic: EP-01\n"
        "- Role: admin\n"
        f"- Status: {status}\n"
    )
    return {
        "number": 71,
        "title": "Test bug",
        "labels": [{"name": "bug"}],
        "updatedAt": "2026-04-30T10:00:00Z",
        "body": body,
        "state": "OPEN",
    }


class TestUpdateBugStatus(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def _patch_targets(self, provider):
        # Vyhneme se reálným write operacím na disku.
        return [
            patch.object(_mod, "get_provider", return_value=provider),
            patch("pathlib.Path.exists", return_value=False),
        ]

    def test_missing_body_returns_400(self):
        provider = MagicMock()
        with patch.object(_mod, "get_provider", return_value=provider):
            resp = self.client.patch("/api/bugs/71/status",
                                     data="", content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_invalid_status_returns_400(self):
        provider = MagicMock()
        with patch.object(_mod, "get_provider", return_value=provider):
            resp = self.client.patch("/api/bugs/71/status",
                                     data=_json.dumps({"status": "garbage"}),
                                     content_type="application/json")
        self.assertEqual(resp.status_code, 400)
        provider.get_issue.assert_not_called()

    def test_provider_not_found_returns_404(self):
        provider = MagicMock()
        provider.get_issue.side_effect = FileNotFoundError("Bug nenalezen.")
        with patch.object(_mod, "get_provider", return_value=provider):
            resp = self.client.patch("/api/bugs/71/status",
                                     data=_json.dumps({"status": "done"}),
                                     content_type="application/json")
        self.assertEqual(resp.status_code, 404)

    def test_provider_get_issue_runtime_error_returns_502(self):
        provider = MagicMock()
        provider.get_issue.side_effect = RuntimeError("JIRA spojení selhalo")
        with patch.object(_mod, "get_provider", return_value=provider):
            resp = self.client.patch("/api/bugs/71/status",
                                     data=_json.dumps({"status": "done"}),
                                     content_type="application/json")
        self.assertEqual(resp.status_code, 502)

    def test_non_bug_returns_400(self):
        provider = MagicMock()
        provider.get_issue.return_value = {
            "number": 71, "title": "Story",
            "labels": [{"name": "user story"}], "body": "- Status: new\n",
        }
        with patch.object(_mod, "get_provider", return_value=provider):
            resp = self.client.patch("/api/bugs/71/status",
                                     data=_json.dumps({"status": "done"}),
                                     content_type="application/json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("není typu 'bug'", resp.get_json()["error"])

    def test_disallowed_transition_returns_400(self):
        provider = MagicMock()
        provider.get_issue.return_value = _bug_issue("done")  # done → new není povoleno
        with patch.object(_mod, "get_provider", return_value=provider):
            resp = self.client.patch("/api/bugs/71/status",
                                     data=_json.dumps({"status": "new"}),
                                     content_type="application/json")
        self.assertEqual(resp.status_code, 400)
        provider.update_body.assert_not_called()

    def test_update_body_failure_returns_502(self):
        provider = MagicMock()
        provider.get_issue.return_value = _bug_issue("new")
        provider.update_body.side_effect = RuntimeError("gh issue edit selhal")
        for p in self._patch_targets(provider):
            p.start()
        try:
            resp = self.client.patch("/api/bugs/71/status",
                                     data=_json.dumps({"status": "in_development"}),
                                     content_type="application/json")
        finally:
            patch.stopall()
        self.assertEqual(resp.status_code, 502)

    def test_happy_path_in_development_calls_update_body_only(self):
        provider = MagicMock()
        provider.get_issue.return_value = _bug_issue("new")
        for p in self._patch_targets(provider):
            p.start()
        try:
            resp = self.client.patch("/api/bugs/71/status",
                                     data=_json.dumps({"status": "in_development"}),
                                     content_type="application/json")
        finally:
            patch.stopall()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["status"], "in_development")
        provider.update_body.assert_called_once()
        # Status v těle musí být přepsaný na nový.
        called_body = provider.update_body.call_args[0][1]
        self.assertIn("- Status: in_development", called_body)
        # Žádný transition (in_development není done).
        provider.transition_status.assert_not_called()

    def test_happy_path_done_triggers_transition(self):
        provider = MagicMock()
        # `done` přechod je povolen pouze z `ready_for_testing` (viz _BUG_STATUS_TRANSITIONS).
        provider.get_issue.return_value = _bug_issue("ready_for_testing")
        for p in self._patch_targets(provider):
            p.start()
        try:
            resp = self.client.patch("/api/bugs/71/status",
                                     data=_json.dumps({"status": "done"}),
                                     content_type="application/json")
        finally:
            patch.stopall()
        self.assertEqual(resp.status_code, 200)
        provider.update_body.assert_called_once()
        provider.transition_status.assert_called_once_with(71, "done")


if __name__ == "__main__":
    unittest.main()
