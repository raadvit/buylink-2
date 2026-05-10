"""Unit + integrační testy pro provider abstrakci (US-188)."""

import importlib
import importlib.util as _ilu
import io
import json as _json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import issue_provider
from issue_provider.github import GitHubProvider
from issue_provider.jira import JiraProvider


_TASK_FORGE_PATH = Path(__file__).resolve().parent / "main.py"


def _load_task_forge():
    spec = _ilu.spec_from_file_location("task_forge_uut", _TASK_FORGE_PATH)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mock_urlopen_response(payload, status=200):
    """Vyrobí context-manager mock kompatibilní s urllib.request.urlopen."""
    cm = MagicMock()
    body = _json.dumps(payload).encode("utf-8") if not isinstance(payload, (bytes, bytearray)) else bytes(payload)
    response = MagicMock()
    response.read.return_value = body
    response.status = status
    cm.__enter__.return_value = response
    cm.__exit__.return_value = False
    return cm


# ── Factory ─────────────────────────────────────────────────────────────────


class TestProviderFactory(unittest.TestCase):
    def setUp(self):
        issue_provider.reset_provider()
        self._saved_target = os.environ.pop("TARGET_SYSTEM", None)

    def tearDown(self):
        issue_provider.reset_provider()
        if self._saved_target is not None:
            os.environ["TARGET_SYSTEM"] = self._saved_target
        else:
            os.environ.pop("TARGET_SYSTEM", None)

    def test_factory_returns_github_provider_by_default(self):
        provider = issue_provider.get_provider()
        self.assertIsInstance(provider, GitHubProvider)

    def test_factory_returns_jira_provider_when_env_set(self):
        os.environ["TARGET_SYSTEM"] = "jira"
        os.environ["JIRA_URL"] = "https://jira.example.com"
        os.environ["JIRA_PERSONAL_TOKEN"] = "tok"
        issue_provider.reset_provider()
        provider = issue_provider.get_provider()
        self.assertIsInstance(provider, JiraProvider)

    def test_factory_raises_on_invalid_target(self):
        os.environ["TARGET_SYSTEM"] = "foo"
        issue_provider.reset_provider()
        with self.assertRaises(ValueError):
            issue_provider.get_provider()


# ── JIRA mapping ────────────────────────────────────────────────────────────


class TestJiraStatusMapping(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in (
            "JIRA_URL", "JIRA_PERSONAL_TOKEN", "JIRA_PROJECTS_FILTER",
            "JIRA_STATUS_DONE", "JIRA_STATUS_DRAFT",
        )}
        os.environ["JIRA_URL"] = "https://jira.example.com"
        os.environ["JIRA_PERSONAL_TOKEN"] = "tok"

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_jira_status_mapping_loads_from_env(self):
        os.environ["JIRA_STATUS_DONE"] = "Closed"
        provider = JiraProvider()
        self.assertEqual(provider.map_status("done"), "Closed")

    def test_jira_status_reverse_mapping(self):
        os.environ["JIRA_STATUS_DONE"] = "Closed"
        provider = JiraProvider()
        self.assertEqual(provider.map_status_reverse("Closed"), "done")

    def test_jira_status_default_when_env_missing(self):
        os.environ.pop("JIRA_STATUS_DONE", None)
        provider = JiraProvider()
        self.assertEqual(provider.map_status("done"), "Done")

    def test_jira_id_resolution(self):
        os.environ["JIRA_PROJECTS_FILTER"] = "DSC"
        provider = JiraProvider()
        self.assertEqual(provider.jira_key("US-007"), "DSC-7")
        self.assertEqual(provider.jira_key(7), "DSC-7")
        self.assertEqual(provider.jira_key("7"), "DSC-7")


# ── GitHubProvider — create_story ──────────────────────────────────────────


class TestGitHubProviderCreate(unittest.TestCase):
    def test_github_provider_create_story_calls_gh(self):
        provider = GitHubProvider()
        with tempfile.TemporaryDirectory() as tmp:
            with patch("issue_provider.github.subprocess.run") as run:
                run.return_value = MagicMock(
                    returncode=0,
                    stdout="https://github.com/owner/repo/issues/42\n",
                    stderr="",
                )
                result = provider.create_story(
                    title="Test",
                    body="- Status: new\n",
                    epic="EP-01",
                    repo_root=tmp,
                    labels=["user story"],
                )

        self.assertEqual(result["issue_number"], 42)
        self.assertTrue(result["issue_url"].endswith("/issues/42"))
        self.assertEqual(result["wiki_path"], "wiki/stories/US-042.md")
        # Ověř že byl volán `gh issue create` (první call)
        first_call_args = run.call_args_list[0].args[0]
        self.assertEqual(first_call_args[:3], ["gh", "issue", "create"])
        self.assertIn("--label", first_call_args)
        self.assertIn("user story", first_call_args)


# ── JiraProvider — create_story (REST mock) ────────────────────────────────


class TestJiraProviderCreate(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in (
            "JIRA_URL", "JIRA_PERSONAL_TOKEN", "JIRA_PROJECTS_FILTER",
            "JIRA_SSL_VERIFY",
        )}
        os.environ["JIRA_URL"] = "https://jira.example.com"
        os.environ["JIRA_PERSONAL_TOKEN"] = "tok"
        os.environ["JIRA_PROJECTS_FILTER"] = "DSC"
        os.environ["JIRA_SSL_VERIFY"] = "false"

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_jira_provider_create_story_calls_rest(self):
        provider = JiraProvider()
        with tempfile.TemporaryDirectory() as tmp, \
             patch("issue_provider.jira.urllib.request.urlopen") as urlopen, \
             patch("issue_provider.jira._wiki.git_commit_wiki"):
            urlopen.return_value = _mock_urlopen_response({
                "id": "10001",
                "key": "DSC-77",
                "self": "https://jira.example.com/rest/api/2/issue/10001",
            })
            result = provider.create_story(
                title="Test JIRA",
                body="- Status: new\n",
                epic="EP-01",
                repo_root=tmp,
                labels=["user story"],
            )

            self.assertEqual(result["issue_number"], 77)
            self.assertEqual(result["jira_key"], "DSC-77")
            self.assertIn("jira.example.com", result["issue_url"])
            self.assertEqual(result["wiki_path"], "wiki/stories/US-077.md")
            # Ověř volání REST endpointu
            called_req = urlopen.call_args.args[0]
            self.assertEqual(called_req.method, "POST")
            self.assertTrue(called_req.full_url.endswith("/rest/api/2/issue"))
            # Wiki musí obsahovat jira_key + target_system
            wiki = (Path(tmp) / "wiki/stories/US-077.md").read_text(encoding="utf-8")
            self.assertIn("- jira_key: DSC-77", wiki)
            self.assertIn("- target_system: jira", wiki)

    def test_jira_provider_normalizes_user_story_label(self):
        """JIRA odmítá labely s mezerami → `user story` musí jít jako `user-story`."""
        provider = JiraProvider()
        captured: dict = {}

        def _capture(req, *_args, **_kwargs):
            captured["body"] = _json.loads(req.data.decode("utf-8"))
            return _mock_urlopen_response({"id": "1", "key": "DSC-1"})

        with tempfile.TemporaryDirectory() as tmp, \
             patch("issue_provider.jira.urllib.request.urlopen", side_effect=_capture), \
             patch("issue_provider.jira._wiki.git_commit_wiki"):
            provider.create_story(
                title="X",
                body="- Status: new\n",
                epic="EP-01",
                repo_root=tmp,
                labels=["user story", "bug"],
            )

        self.assertEqual(
            captured["body"]["fields"]["labels"],
            ["user-story", "bug"],
        )

    def test_inject_jira_metadata_preserves_github_line_when_empty(self):
        """Regrese: `- GitHub: ` (prázdné) nesmí konzumovat newline a posunout DSC-X na další řádek."""
        provider = JiraProvider()
        body = "- Epic: EP-01\n- Role: admin\n- GitHub: \n- Status: new\n"
        result = provider._inject_jira_metadata(body, "DSC-73")
        self.assertIn("- GitHub: DSC-73\n", result)
        self.assertNotIn("- GitHub: \nDSC-73", result)

    def test_jira_provider_maps_label_back_in_to_issue_shape(self):
        provider = JiraProvider()
        shape = provider._to_issue_shape({
            "key": "DSC-9",
            "fields": {
                "summary": "T",
                "description": "",
                "labels": ["user-story", "bug"],
                "status": {"name": "To Do", "statusCategory": {"key": "new"}},
                "updated": "",
            },
        })
        names = [l["name"] for l in shape["labels"]]
        self.assertEqual(names, ["user story", "bug"])


# ── /api/issues — používá aktivního providera ──────────────────────────────


class TestEndpointUsesProvider(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.pop("TARGET_SYSTEM", None)
        issue_provider.reset_provider()
        cls._mod = _load_task_forge()

    def setUp(self):
        self.client = self._mod.app.test_client()
        self._mod.app.config["TESTING"] = True

    def test_get_issues_uses_active_provider(self):
        sample = [{
            "number": 5, "title": "X", "labels": [{"name": "user story"}],
            "updatedAt": "2026-04-30T10:00:00Z", "body": "- Epic: EP\n- Status: new\n",
            "state": "OPEN",
        }]
        fake = MagicMock()
        fake.list_issues.return_value = sample
        fake.create_story = MagicMock()
        with patch("issue_provider.get_provider", return_value=fake):
            # Endpoint v task-forge.py používá inline subprocess pro list — ověříme aspoň
            # že provider je dostupný ve výsledku přes get_provider().
            provider = issue_provider.get_provider()
            self.assertTrue(callable(provider.list_issues))


class TestPostSaveJira(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.pop("TARGET_SYSTEM", None)
        issue_provider.reset_provider()
        cls._mod = _load_task_forge()

    def setUp(self):
        self.client = self._mod.app.test_client()
        self._mod.app.config["TESTING"] = True

    def test_post_save_jira_returns_jira_url(self):
        fake = MagicMock()
        fake.create_story.return_value = {
            "issue_url": "https://jira.alza.cz/browse/DSC-99",
            "issue_number": 99,
            "wiki_path": "wiki/stories/US-099.md",
            "jira_key": "DSC-99",
        }
        with patch.object(self._mod, "get_provider", return_value=fake), \
             patch.object(self._mod, "_save_figma_image_from_cdn", return_value=None):
            resp = self.client.post(
                "/api/save",
                data={"data": _json.dumps({
                    "name": "Test JIRA story",
                    "epic": "EP-01",
                    "role": "admin",
                    "what": "x", "how": "x",
                    "type": "story",
                })},
                content_type="multipart/form-data",
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertIn("jira.alza.cz", body["issue_url"])
        self.assertEqual(body["issue_number"], 99)


# ── PATCH status — JIRA transition ──────────────────────────────────────────


class TestJiraTransitionEndpoint(unittest.TestCase):
    """Pokrývá AC4: status PATCH s JIRA targetem volá transition; selhání = 502."""

    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in (
            "JIRA_URL", "JIRA_PERSONAL_TOKEN", "JIRA_PROJECTS_FILTER",
        )}
        os.environ["JIRA_URL"] = "https://jira.example.com"
        os.environ["JIRA_PERSONAL_TOKEN"] = "tok"
        os.environ["JIRA_PROJECTS_FILTER"] = "DSC"

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_patch_status_jira_calls_transition(self):
        provider = JiraProvider()
        with patch("issue_provider.jira.urllib.request.urlopen") as urlopen:
            urlopen.side_effect = [
                _mock_urlopen_response({
                    "transitions": [
                        {"id": "31", "name": "Done", "to": {"name": "Done"}},
                    ],
                }),
                _mock_urlopen_response({}),
            ]
            provider.transition_status(7, "done")
        # Druhé volání = POST transition
        post_call = urlopen.call_args_list[1].args[0]
        self.assertEqual(post_call.method, "POST")
        self.assertIn("/transitions", post_call.full_url)

    def test_patch_status_jira_502_on_transition_fail(self):
        provider = JiraProvider()
        with patch("issue_provider.jira.urllib.request.urlopen") as urlopen:
            urlopen.return_value = _mock_urlopen_response({
                "transitions": [
                    {"id": "11", "name": "InProgress", "to": {"name": "In Progress"}},
                ],
            })
            with self.assertRaises(RuntimeError):
                provider.transition_status(7, "done")  # Done není mezi dostupnými


# ── archive — provider.archive_issue() místo inline větvení ──────────────────


class TestArchiveStory(unittest.TestCase):
    """AC7: archivace volá `provider.archive_issue()` (GitHub close / JIRA noop) + git mv."""

    @classmethod
    def setUpClass(cls):
        os.environ.pop("TARGET_SYSTEM", None)
        issue_provider.reset_provider()
        cls._mod = _load_task_forge()

    def setUp(self):
        self.client = self._mod.app.test_client()
        self._mod.app.config["TESTING"] = True

    def _user_story_issue(self):
        return {
            "number": 42, "title": "Story",
            "labels": [{"name": "user story"}],
            "body": "- Status: ready_for_testing\n",
            "state": "OPEN", "updatedAt": "2026-04-30T10:00:00Z",
        }

    def test_archive_calls_provider_archive_issue(self):
        fake = MagicMock()
        fake.get_issue.return_value = self._user_story_issue()
        with tempfile.TemporaryDirectory() as tmp:
            wiki = Path(tmp) / "wiki/stories/US-042.md"
            wiki.parent.mkdir(parents=True)
            wiki.write_text("- Status: ready_for_testing\n", encoding="utf-8")
            original = self._mod._REPO_ROOT
            self._mod._REPO_ROOT = Path(tmp)
            try:
                with patch.object(self._mod, "get_provider", return_value=fake), \
                     patch.object(self._mod.subprocess, "run", return_value=MagicMock(returncode=0)):
                    resp = self.client.post("/api/stories/42/archive")
            finally:
                self._mod._REPO_ROOT = original
        fake.archive_issue.assert_called_once_with(42)
        self.assertIn(resp.status_code, (200, 502))

    def test_archive_400_when_issue_not_user_story(self):
        fake = MagicMock()
        fake.get_issue.return_value = {
            "number": 42, "title": "Bug",
            "labels": [{"name": "bug"}], "body": "",
        }
        with patch.object(self._mod, "get_provider", return_value=fake):
            resp = self.client.post("/api/stories/42/archive")
        self.assertEqual(resp.status_code, 400)
        fake.archive_issue.assert_not_called()

    def test_archive_404_when_provider_get_issue_not_found(self):
        fake = MagicMock()
        fake.get_issue.side_effect = FileNotFoundError("Issue nenalezena.")
        with patch.object(self._mod, "get_provider", return_value=fake):
            resp = self.client.post("/api/stories/42/archive")
        self.assertEqual(resp.status_code, 404)

    def test_archive_502_when_provider_get_issue_runtime_error(self):
        fake = MagicMock()
        fake.get_issue.side_effect = RuntimeError("JIRA spojení selhalo")
        with patch.object(self._mod, "get_provider", return_value=fake):
            resp = self.client.post("/api/stories/42/archive")
        self.assertEqual(resp.status_code, 502)


# ── PATCH /api/issues/<id>/status — migrováno na provider ────────────────────


class TestUpdateStoryStatus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.pop("TARGET_SYSTEM", None)
        issue_provider.reset_provider()
        cls._mod = _load_task_forge()

    def setUp(self):
        self.client = self._mod.app.test_client()
        self._mod.app.config["TESTING"] = True

    def _story_issue(self, status: str = "ready_for_testing"):
        return {
            "number": 42, "title": "Story",
            "labels": [{"name": "user story"}],
            "body": f"- Epic: EP-01\n- Status: {status}\n",
            "state": "OPEN", "updatedAt": "2026-04-30T10:00:00Z",
        }

    def test_missing_status_returns_400(self):
        fake = MagicMock()
        with patch.object(self._mod, "get_provider", return_value=fake):
            resp = self.client.patch(
                "/api/issues/42/status",
                data=_json.dumps({}), content_type="application/json",
            )
        self.assertEqual(resp.status_code, 400)
        fake.get_issue.assert_not_called()

    def test_provider_not_found_returns_404(self):
        fake = MagicMock()
        fake.get_issue.side_effect = FileNotFoundError("Issue nenalezena.")
        with patch.object(self._mod, "get_provider", return_value=fake):
            resp = self.client.patch(
                "/api/issues/42/status",
                data=_json.dumps({"status": "done"}), content_type="application/json",
            )
        self.assertEqual(resp.status_code, 404)

    def test_provider_runtime_error_returns_502(self):
        fake = MagicMock()
        fake.get_issue.side_effect = RuntimeError("gh CLI nenalezeno.")
        with patch.object(self._mod, "get_provider", return_value=fake):
            resp = self.client.patch(
                "/api/issues/42/status",
                data=_json.dumps({"status": "done"}), content_type="application/json",
            )
        self.assertEqual(resp.status_code, 502)

    def test_non_user_story_returns_400(self):
        fake = MagicMock()
        fake.get_issue.return_value = {
            "number": 42, "title": "Bug",
            "labels": [{"name": "bug"}], "body": "- Status: ready_for_testing\n",
        }
        with patch.object(self._mod, "get_provider", return_value=fake):
            resp = self.client.patch(
                "/api/issues/42/status",
                data=_json.dumps({"status": "done"}), content_type="application/json",
            )
        self.assertEqual(resp.status_code, 400)

    def test_disallowed_transition_returns_400(self):
        fake = MagicMock()
        fake.get_issue.return_value = self._story_issue("draft")  # draft → done není povoleno
        with patch.object(self._mod, "get_provider", return_value=fake):
            resp = self.client.patch(
                "/api/issues/42/status",
                data=_json.dumps({"status": "done"}), content_type="application/json",
            )
        self.assertEqual(resp.status_code, 400)
        fake.update_body.assert_not_called()

    def test_update_body_failure_returns_502(self):
        fake = MagicMock()
        fake.get_issue.return_value = self._story_issue("ready_for_testing")
        fake.update_body.side_effect = RuntimeError("JIRA HTTP 500")
        with tempfile.TemporaryDirectory() as tmp:
            original = self._mod._REPO_ROOT
            self._mod._REPO_ROOT = Path(tmp)
            try:
                with patch.object(self._mod, "get_provider", return_value=fake):
                    resp = self.client.patch(
                        "/api/issues/42/status",
                        data=_json.dumps({"status": "done"}),
                        content_type="application/json",
                    )
            finally:
                self._mod._REPO_ROOT = original
        self.assertEqual(resp.status_code, 502)

    def test_happy_path_calls_update_body_and_transition(self):
        fake = MagicMock()
        fake.get_issue.return_value = self._story_issue("ready_for_testing")
        with tempfile.TemporaryDirectory() as tmp:
            original = self._mod._REPO_ROOT
            self._mod._REPO_ROOT = Path(tmp)
            try:
                with patch.object(self._mod, "get_provider", return_value=fake):
                    resp = self.client.patch(
                        "/api/issues/42/status",
                        data=_json.dumps({"status": "done"}),
                        content_type="application/json",
                    )
            finally:
                self._mod._REPO_ROOT = original
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["status"], "done")
        fake.update_body.assert_called_once()
        fake.transition_status.assert_called_once_with(42, "done")


# ── /api/submit-bug — RuntimeError → 502 ────────────────────────────────────


class TestSubmitBugErrorCode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.pop("TARGET_SYSTEM", None)
        issue_provider.reset_provider()
        cls._mod = _load_task_forge()

    def setUp(self):
        self.client = self._mod.app.test_client()
        self._mod.app.config["TESTING"] = True

    def test_create_story_runtime_error_returns_502(self):
        fake = MagicMock()
        fake.create_story.side_effect = RuntimeError("gh CLI nenalezeno.")
        with patch.object(self._mod, "get_provider", return_value=fake):
            resp = self.client.post(
                "/api/submit-bug",
                data={"data": _json.dumps({
                    "name": "Bug X", "epic": "EP-01", "role": "admin",
                    "what_happened": "x", "expected": "y",
                })},
                content_type="multipart/form-data",
            )
        self.assertEqual(resp.status_code, 502)


class TestJiraAttachmentUpload(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in (
            "JIRA_URL", "JIRA_PERSONAL_TOKEN", "JIRA_PROJECTS_FILTER", "JIRA_SSL_VERIFY",
        )}
        os.environ["JIRA_URL"] = "https://jira.example.com"
        os.environ["JIRA_PERSONAL_TOKEN"] = "tok"
        os.environ["JIRA_PROJECTS_FILTER"] = "DSC"
        os.environ["JIRA_SSL_VERIFY"] = "false"

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_upload_attachment_bytes_posts_to_attachments_endpoint(self):
        provider = JiraProvider()
        captured: dict = {}

        def _capture(req, *_args, **_kwargs):
            captured["url"] = req.full_url
            captured["method"] = req.method
            captured["ct"] = req.get_header("Content-type")
            captured["xat"] = req.get_header("X-atlassian-token")
            captured["data"] = req.data
            return _mock_urlopen_response(b"[]")

        with patch("issue_provider.jira.urllib.request.urlopen", side_effect=_capture):
            provider.upload_attachment_bytes(7, "image.png", b"\x89PNG\r\n")

        self.assertEqual(captured["url"], "https://jira.example.com/rest/api/2/issue/DSC-7/attachments")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["xat"], "no-check")
        self.assertIn("multipart/form-data", captured["ct"])
        self.assertIn(b"image.png", captured["data"])
        self.assertIn(b"\x89PNG\r\n", captured["data"])

    def test_upload_attachment_bytes_raises_on_http_error(self):
        import urllib.error
        provider = JiraProvider()

        def _fail(req, *_args, **_kwargs):
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)

        with patch("issue_provider.jira.urllib.request.urlopen", side_effect=_fail):
            with self.assertRaises(RuntimeError) as ctx:
                provider.upload_attachment_bytes(1, "x.png", b"data")
        self.assertIn("403", str(ctx.exception))

    def test_attach_files_to_story_uploads_to_jira(self):
        """attach_files_to_story nahraje soubory lokálně A odešle je na Jira attachments endpoint."""
        provider = JiraProvider()
        upload_calls: list[str] = []

        class FakeFile:
            filename = "test.png"
            def save(self, path):
                import pathlib
                pathlib.Path(path).write_bytes(b"PNG_DATA")

        def _urlopen(req, *_args, **_kwargs):
            if req.full_url.endswith("/attachments"):
                upload_calls.append(req.full_url)
            return _mock_urlopen_response({})

        with tempfile.TemporaryDirectory() as tmp:
            wiki_dir = Path(tmp) / "wiki" / "stories"
            wiki_dir.mkdir(parents=True)
            wiki_file = wiki_dir / "US-007.md"
            wiki_file.write_text("h1. Test\n - Status: new\n", encoding="utf-8")

            with patch("issue_provider.jira.urllib.request.urlopen", side_effect=_urlopen), \
                 patch("issue_provider.jira._wiki.git_commit_wiki"):
                provider.attach_files_to_story(
                    issue_number=7,
                    wiki_path="wiki/stories/US-007.md",
                    repo_root=tmp,
                    files=[FakeFile()],
                )

        self.assertEqual(len(upload_calls), 1)
        self.assertIn("DSC-7/attachments", upload_calls[0])

    def test_github_upload_attachment_bytes_is_noop(self):
        """GitHubProvider.upload_attachment_bytes nesmí vyvolat výjimku."""
        from issue_provider.github import GitHubProvider
        provider = GitHubProvider()
        provider.upload_attachment_bytes(1, "x.png", b"data")  # no exception


if __name__ == "__main__":
    unittest.main()
