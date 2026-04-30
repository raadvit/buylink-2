"""Integrační testy pro POST /api/implement (US-041)."""

import json
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Přidej task-forge do sys.path
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


def _make_issue_info(status: str = "validated", labels: list | None = None) -> dict:
    if labels is None:
        labels = [{"name": "user story"}]
    return {
        "title": "Test story",
        "labels": labels,
        "body": (
            "# Test story\n\n"
            "## Metadata\n"
            f"- Epic: Test\n"
            f"- Status: {status}\n"
            "- GitHub: #42\n"
        ),
    }


class TestImplementEndpoint(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    # --- validace vstupu ---

    def test_missing_body_returns_400(self):
        resp = self.client.post("/api/implement", content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_missing_issue_number_returns_400(self):
        resp = self.client.post(
            "/api/implement",
            data=json.dumps({"issue_number": 0}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        body = json.loads(resp.data)
        self.assertIn("issue_number", body["error"])

    def test_invalid_issue_number_returns_400(self):
        resp = self.client.post(
            "/api/implement",
            data=json.dumps({"issue_number": "abc"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    # --- GitHub API selhání při načítání issue ---

    @patch.object(story_builder, "_get_issue_info", side_effect=RuntimeError("gh CLI chyba"))
    def test_github_api_failure_on_fetch_returns_500(self, _mock):
        resp = self.client.post(
            "/api/implement",
            data=json.dumps({"issue_number": 42}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 500)
        body = json.loads(resp.data)
        self.assertIn("error", body)

    # --- bezpečnostní check — typ issue ---

    @patch.object(story_builder, "_get_issue_info",
                  return_value={"title": "X", "labels": [{"name": "idea"}], "body": "- Status: new\n"})
    def test_non_story_non_bug_returns_400(self, _mock):
        resp = self.client.post(
            "/api/implement",
            data=json.dumps({"issue_number": 42}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        body = json.loads(resp.data)
        self.assertIn("user story", body["error"])

    # --- bezpečnostní check — stav story ---

    @patch.object(story_builder, "_get_issue_info",
                  return_value=_make_issue_info(status="draft", labels=[{"name": "user story"}]))
    def test_wrong_status_returns_400(self, _mock):
        resp = self.client.post(
            "/api/implement",
            data=json.dumps({"issue_number": 42}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        body = json.loads(resp.data)
        self.assertIn("dev-plan", body["error"])

    @patch.object(story_builder, "_get_issue_info",
                  return_value=_make_issue_info(status="in-development"))
    def test_already_in_development_returns_400(self, _mock):
        resp = self.client.post(
            "/api/implement",
            data=json.dumps({"issue_number": 42}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    # --- GitHub API selhání při aktualizaci stavu — non-fatal, vrátí 202 ---

    @patch("subprocess.run", return_value=MagicMock(returncode=0))
    @patch.object(story_builder, "_get_issue_info",
                  return_value=_make_issue_info(status="validated", labels=[{"name": "user story"}]))
    @patch.object(story_builder, "update_issue_status_in_development",
                  side_effect=RuntimeError("gh issue edit selhal: 422"))
    def test_github_update_failure_still_returns_202(self, _mock_update, _mock_info, _mock_run):
        resp = self.client.post(
            "/api/implement",
            data=json.dumps({"issue_number": 42}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 202)

    # --- happy path: validated ---

    @patch("subprocess.run", return_value=MagicMock(returncode=0))
    @patch.object(story_builder, "_get_issue_info",
                  return_value=_make_issue_info(status="validated"))
    @patch.object(story_builder, "update_issue_status_in_development")
    @patch.object(story_builder, "launch_implement_agent")
    def test_happy_path_validated_returns_202(self, mock_launch, mock_update, _mock_info, _mock_run):
        # launch_implement_agent běží v threadu — zablokujeme event aby byl výsledek deterministický
        called = threading.Event()
        def _fake_launch(session_id, issue_number, s):
            called.set()
        mock_launch.side_effect = _fake_launch

        resp = self.client.post(
            "/api/implement",
            data=json.dumps({"issue_number": 42}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 202)
        body = json.loads(resp.data)
        self.assertTrue(body.get("success"))
        self.assertIn("session_id", body)
        called.wait(timeout=2)
        mock_update.assert_called_once()
        mock_launch.assert_called_once()

    # --- happy path: ready-for-arch ---

    @patch("subprocess.run", return_value=MagicMock(returncode=0))
    @patch.object(story_builder, "_get_issue_info",
                  return_value=_make_issue_info(status="ready-for-arch"))
    @patch.object(story_builder, "update_issue_status_in_development")
    @patch.object(story_builder, "launch_implement_agent")
    def test_happy_path_ready_for_arch_returns_202(self, mock_launch, _mock_update, _mock_info, _mock_run):
        resp = self.client.post(
            "/api/implement",
            data=json.dumps({"issue_number": 99}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 202)
        body = json.loads(resp.data)
        self.assertTrue(body.get("success"))

    # --- atomicita: při chybě GitHub se agent nespustí (queue worker chybu zachytí) ---

    @patch("subprocess.run", return_value=MagicMock(returncode=0))
    @patch.object(story_builder, "_get_issue_info",
                  return_value=_make_issue_info(status="validated", labels=[{"name": "user story"}]))
    @patch.object(story_builder, "update_issue_status_in_development",
                  side_effect=RuntimeError("GitHub API nedostupné"))
    @patch.object(story_builder, "launch_implement_agent")
    def test_atomic_no_agent_on_github_failure(self, mock_launch, _mock_update, _mock_info, _mock_run):
        import time
        resp = self.client.post(
            "/api/implement",
            data=json.dumps({"issue_number": 42}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 202)
        time.sleep(0.1)  # queue worker dostane čas na zpracování
        mock_launch.assert_not_called()


class TestUpdateIssueStatusInDevelopment(unittest.TestCase):
    """Unit testy pro story_builder.update_issue_status_in_development."""

    def test_updates_status_in_wiki_and_calls_gh(self, tmp_path=None):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp_dir:
            stories_dir = Path(tmp_dir) / "wiki" / "stories"
            stories_dir.mkdir(parents=True)
            wiki_file = stories_dir / "US-042.md"
            wiki_file.write_text(
                "# Test\n\n## Metadata\n- Status: validated\n- GitHub: #42\n",
                encoding="utf-8",
            )
            wiki_path = "wiki/stories/US-042.md"

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stderr="")
                story_builder.update_issue_status_in_development(42, wiki_path, tmp_dir)

            updated = wiki_file.read_text(encoding="utf-8")
            self.assertIn("- Status: in-development", updated)
            self.assertNotIn("- Status: validated", updated)
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            self.assertIn("gh", args)
            self.assertIn("issue", args)
            self.assertIn("edit", args)

    def test_raises_on_gh_failure(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            stories_dir = Path(tmp_dir) / "wiki" / "stories"
            stories_dir.mkdir(parents=True)
            wiki_file = stories_dir / "US-001.md"
            wiki_file.write_text("- Status: validated\n", encoding="utf-8")

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stderr="Unauthorized")
                with self.assertRaises(RuntimeError) as ctx:
                    story_builder.update_issue_status_in_development(1, "wiki/stories/US-001.md", tmp_dir)
            self.assertIn("selhal", str(ctx.exception))

    def test_raises_on_timeout(self):
        import tempfile, subprocess
        with tempfile.TemporaryDirectory() as tmp_dir:
            stories_dir = Path(tmp_dir) / "wiki" / "stories"
            stories_dir.mkdir(parents=True)
            (stories_dir / "US-001.md").write_text("- Status: validated\n", encoding="utf-8")

            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("gh", 30)):
                with self.assertRaises(RuntimeError) as ctx:
                    story_builder.update_issue_status_in_development(1, "wiki/stories/US-001.md", tmp_dir)
            self.assertIn("timeout", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
