"""Integrační testy pro POST /api/queue a GET /api/session/by-issue."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import store_state
import story_builder
import importlib.util as _ilu

_spec = _ilu.spec_from_file_location(
    "task_forge",
    Path(__file__).resolve().parent / "task-forge.py",
)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
app = _mod.app


def _make_issue_info(status: str = "new", labels: list | None = None) -> dict:
    if labels is None:
        labels = [{"name": "bug"}]
    return {
        "title": "Test bug",
        "labels": labels,
        "body": f"# Test\n\n- Epic: EP-01\n- Status: {status}\n- GitHub: #42\n",
    }


def _make_story_info(status: str = "validated") -> dict:
    return {
        "title": "Test story",
        "labels": [{"name": "user story"}],
        "body": f"# Test story\n\n- Epic: EP-01\n- Status: {status}\n- GitHub: #42\n",
    }


class TestEnqueueEndpointValidation(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_missing_body_returns_400(self):
        resp = self.client.post("/api/queue", content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_missing_issue_number_returns_400(self):
        resp = self.client.post(
            "/api/queue",
            data=json.dumps({"type": "development"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("issue_number", json.loads(resp.data)["error"])

    def test_zero_issue_number_returns_400(self):
        resp = self.client.post(
            "/api/queue",
            data=json.dumps({"issue_number": 0, "type": "development"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_invalid_type_returns_400(self):
        resp = self.client.post(
            "/api/queue",
            data=json.dumps({"issue_number": 42, "type": "magic"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("typ", json.loads(resp.data)["error"])

    def test_missing_type_returns_400(self):
        resp = self.client.post(
            "/api/queue",
            data=json.dumps({"issue_number": 42}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)


class TestEnqueueEndpointExternalErrors(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    @patch.object(story_builder, "_get_issue_info", side_effect=RuntimeError("gh selhalo"))
    def test_github_api_failure_returns_500(self, _):
        resp = self.client.post(
            "/api/queue",
            data=json.dumps({"issue_number": 42, "type": "development"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 500)

    @patch.object(story_builder, "_get_issue_info", return_value=_make_issue_info(status="new"))
    @patch("subprocess.run", return_value=MagicMock(returncode=1, stderr="label error"))
    def test_gh_label_add_failure_returns_502(self, _mock_run, _mock_info):
        resp = self.client.post(
            "/api/queue",
            data=json.dumps({"issue_number": 42, "type": "development"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 502)

    @patch.object(story_builder, "_get_issue_info", return_value=_make_issue_info(status="new"))
    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired("gh", 15))
    def test_gh_timeout_returns_502(self, _mock_run, _mock_info):
        resp = self.client.post(
            "/api/queue",
            data=json.dumps({"issue_number": 42, "type": "development"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 502)

    @patch.object(story_builder, "_get_issue_info", return_value=_make_issue_info(status="new"))
    @patch("subprocess.run", side_effect=FileNotFoundError("gh not found"))
    def test_gh_not_found_returns_502(self, _mock_run, _mock_info):
        resp = self.client.post(
            "/api/queue",
            data=json.dumps({"issue_number": 42, "type": "development"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 502)


class TestEnqueueEndpointBusinessValidation(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    @patch.object(story_builder, "_get_issue_info", return_value={"title": "X", "labels": [{"name": "idea"}], "body": "- Status: new\n"})
    def test_development_non_story_non_bug_returns_400(self, _):
        resp = self.client.post(
            "/api/queue",
            data=json.dumps({"issue_number": 42, "type": "development"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("user story", json.loads(resp.data)["error"])

    @patch.object(story_builder, "_get_issue_info", return_value=_make_issue_info(status="in-development"))
    def test_development_bug_wrong_status_returns_400(self, _):
        resp = self.client.post(
            "/api/queue",
            data=json.dumps({"issue_number": 42, "type": "development"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("new", json.loads(resp.data)["error"])

    @patch.object(story_builder, "_get_issue_info", return_value=_make_story_info(status="draft"))
    def test_development_story_wrong_status_returns_400(self, _):
        resp = self.client.post(
            "/api/queue",
            data=json.dumps({"issue_number": 42, "type": "development"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("dev-plan", json.loads(resp.data)["error"])

    @patch.object(story_builder, "_get_issue_info", return_value=_make_issue_info(status="new"))
    def test_analysis_wiki_not_found_returns_404(self, _):
        resp = self.client.post(
            "/api/queue",
            data=json.dumps({"issue_number": 99999, "type": "analysis"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)


class TestEnqueueEndpointHappyPath(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    @patch.object(story_builder, "_get_issue_info", return_value=_make_issue_info(status="new"))
    @patch("subprocess.run", return_value=MagicMock(returncode=0))
    def test_development_bug_happy_path_returns_200(self, mock_run, _mock_info):
        resp = self.client.post(
            "/api/queue",
            data=json.dumps({"issue_number": 42, "type": "development"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.data)
        self.assertTrue(body.get("ok"))
        # Ověř, že byl zavolán gh issue edit --add-label queue-development
        calls = [str(c) for c in mock_run.call_args_list]
        self.assertTrue(any("queue-development" in c for c in calls))

    @patch.object(story_builder, "_get_issue_info", return_value=_make_story_info(status="validated"))
    @patch("subprocess.run", return_value=MagicMock(returncode=0))
    def test_development_story_happy_path_returns_200(self, mock_run, _mock_info):
        resp = self.client.post(
            "/api/queue",
            data=json.dumps({"issue_number": 42, "type": "development"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(json.loads(resp.data).get("ok"))

    @patch.object(story_builder, "_get_issue_info", return_value=_make_issue_info(status="new"))
    @patch("subprocess.run", return_value=MagicMock(returncode=0))
    def test_analysis_happy_path_returns_200(self, mock_run, _mock_info):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wiki_dir = root / "wiki" / "stories"
            wiki_dir.mkdir(parents=True)
            wiki_file = wiki_dir / "US-042.md"
            wiki_file.write_text("# Test\n- Status: new\n", encoding="utf-8")

            original_root = _mod._REPO_ROOT
            _mod._REPO_ROOT = root
            try:
                resp = self.client.post(
                    "/api/queue",
                    data=json.dumps({"issue_number": 42, "type": "analysis"}),
                    content_type="application/json",
                )
            finally:
                _mod._REPO_ROOT = original_root

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(json.loads(resp.data).get("ok"))
        calls = [str(c) for c in mock_run.call_args_list]
        self.assertTrue(any("queue-analysis" in c for c in calls))


class TestSessionByIssueEndpoint(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_missing_issue_number_returns_400(self):
        resp = self.client.get("/api/session/by-issue")
        self.assertEqual(resp.status_code, 400)

    def test_no_active_session_returns_404(self):
        resp = self.client.get("/api/session/by-issue?issue_number=99999")
        self.assertEqual(resp.status_code, 404)

    def test_active_session_found_returns_200(self):
        sid = "test-session-98765"
        store_state.create_session(sid, {"issue_number": 98765, "wiki_path": "wiki/stories/US-98765.md", "name": "Test"})
        store_state.update_session(sid, status="analyzing")
        try:
            resp = self.client.get("/api/session/by-issue?issue_number=98765")
            self.assertEqual(resp.status_code, 200)
            body = json.loads(resp.data)
            self.assertEqual(body["session_id"], sid)
            self.assertEqual(body["status"], "analyzing")
        finally:
            store_state.update_session(sid, status="done")

    def test_done_session_not_returned(self):
        sid = "test-session-done"
        store_state.create_session(sid, {"issue_number": 43, "wiki_path": "wiki/stories/US-043.md", "name": "Test"})
        store_state.update_session(sid, status="done")
        resp = self.client.get("/api/session/by-issue?issue_number=43")
        self.assertEqual(resp.status_code, 404)

    def test_error_session_not_returned(self):
        sid = "test-session-error"
        store_state.create_session(sid, {"issue_number": 44, "wiki_path": "wiki/stories/US-044.md", "name": "Test"})
        store_state.update_session(sid, status="error")
        resp = self.client.get("/api/session/by-issue?issue_number=44")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
