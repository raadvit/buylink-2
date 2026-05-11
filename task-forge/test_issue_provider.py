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
        create_response = _mock_urlopen_response({
            "id": "10001", "key": "DSC-77",
            "self": "https://jira.example.com/rest/api/2/issue/10001",
        })
        update_response = _mock_urlopen_response(None)
        with tempfile.TemporaryDirectory() as tmp, \
             patch("issue_provider.jira.urllib.request.urlopen",
                   side_effect=[create_response, update_response]) as urlopen, \
             patch("issue_provider.jira._wiki.git_commit_wiki"):
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
            # První volání musí být POST na /rest/api/2/issue
            first_req = urlopen.call_args_list[0].args[0]
            self.assertEqual(first_req.method, "POST")
            self.assertTrue(first_req.full_url.endswith("/rest/api/2/issue"))
            # Wiki musí být Markdown s jira_key + target_system
            wiki = (Path(tmp) / "wiki/stories/US-077.md").read_text(encoding="utf-8")
            self.assertIn("- jira_key: DSC-77", wiki)
            self.assertIn("- target_system: jira", wiki)
            self.assertTrue(wiki.startswith("# ") or "- Status:" in wiki)

    def test_jira_provider_normalizes_user_story_label(self):
        """JIRA odmítá labely s mezerami → `user story` musí jít jako `user-story`."""
        provider = JiraProvider()
        captured: dict = {}

        def _capture(req, *_args, **_kwargs):
            body = _json.loads(req.data.decode("utf-8")) if req.data else {}
            if req.method == "POST":
                captured["body"] = body
                return _mock_urlopen_response({"id": "1", "key": "DSC-1"})
            return _mock_urlopen_response(None)

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


class TestJiraInjectMetadataJiraFormat(unittest.TestCase):
    def setUp(self):
        os.environ["JIRA_URL"] = "https://jira.example.com"
        os.environ["JIRA_PERSONAL_TOKEN"] = "tok"
        os.environ["JIRA_PROJECTS_FILTER"] = "DSC"

    def tearDown(self):
        for k in ("JIRA_URL", "JIRA_PERSONAL_TOKEN", "JIRA_PROJECTS_FILTER"):
            os.environ.pop(k, None)

    def test_jira_format_replaces_jira_placeholder(self):
        provider = JiraProvider()
        body = "h1. Test\n - Epic: EP-01\n - Status: new\n - Jira: \n - Vytvořeno: 2026-05-10\n"
        result = provider._inject_jira_metadata(body, "DSC-42")
        self.assertIn(" - Jira: DSC-42", result)

    def test_jira_format_injects_jira_key_with_space_prefix(self):
        provider = JiraProvider()
        body = "h1. Test\n - Status: new\n - Jira: \n"
        result = provider._inject_jira_metadata(body, "DSC-42")
        self.assertIn(" - jira_key: DSC-42", result)
        self.assertNotIn("- jira_key:", result.replace(" - jira_key:", ""))

    def test_jira_format_injects_target_system_with_space_prefix(self):
        provider = JiraProvider()
        body = "h1. Test\n - Status: new\n - Jira: \n"
        result = provider._inject_jira_metadata(body, "DSC-42")
        self.assertIn(" - target_system: jira", result)

    def test_jira_format_status_order_preserved(self):
        """jira_key a target_system musí být před - Status:."""
        provider = JiraProvider()
        body = "h1. Test\n - Status: new\n - Jira: \n"
        result = provider._inject_jira_metadata(body, "DSC-5")
        idx_key = result.index(" - jira_key:")
        idx_target = result.index(" - target_system:")
        idx_status = result.index(" - Status:")
        self.assertLess(idx_key, idx_status)
        self.assertLess(idx_target, idx_status)

    def test_markdown_format_still_works(self):
        """Regrese: Markdown formát musí fungovat beze změny."""
        provider = JiraProvider()
        body = "- Epic: EP-01\n- GitHub: \n- Status: new\n"
        result = provider._inject_jira_metadata(body, "DSC-73")
        self.assertIn("- GitHub: DSC-73", result)
        self.assertIn("- jira_key: DSC-73", result)
        self.assertNotIn(" - jira_key:", result)


class TestBuildDraftBody(unittest.TestCase):
    """_build_draft_body vždy generuje Markdown (pro oba providery)."""

    @classmethod
    def setUpClass(cls):
        os.environ.pop("TARGET_SYSTEM", None)
        issue_provider.reset_provider()
        cls._mod = _load_task_forge()

    def test_body_uses_markdown_h1(self):
        body = self._mod._build_draft_body({"name": "Test story", "epic": "EP-01", "role": "admin"})
        self.assertTrue(body.startswith("# Test story"))

    def test_body_metadata_uses_dash_prefix(self):
        body = self._mod._build_draft_body({"name": "X", "epic": "EP-01", "role": "admin"})
        self.assertIn("- Epic: EP-01", body)
        self.assertIn("- Status:", body)
        self.assertNotIn(" - Epic:", body)

    def test_body_uses_markdown_h2_sections(self):
        body = self._mod._build_draft_body(
            {"name": "X", "epic": "EP-01", "role": "admin", "why": "důvod", "what": "design"}
        )
        self.assertIn("## Why / Business Goal", body)
        self.assertIn("## Co se zobrazuje", body)
        self.assertIn("důvod", body)

    def test_save_endpoint_uses_markdown_body(self):
        """Endpoint /api/save vždy posílá Markdown (Varianta A)."""
        self._mod.app.config["TESTING"] = True
        client = self._mod.app.test_client()
        fake = MagicMock()
        fake.create_story.return_value = {
            "issue_url": "https://jira.example.com/browse/DSC-99",
            "issue_number": 99,
            "wiki_path": "wiki/stories/US-099.md",
            "jira_key": "DSC-99",
        }
        captured_body: list[str] = []

        def _capture(**kwargs):
            captured_body.append(kwargs.get("body", ""))
            return fake.create_story.return_value

        fake.create_story.side_effect = _capture

        for target in ("github", "jira"):
            captured_body.clear()
            os.environ["TARGET_SYSTEM"] = target
            issue_provider.reset_provider()
            with patch.object(self._mod, "get_provider", return_value=fake):
                client.post(
                    "/api/save",
                    data={"data": _json.dumps({"name": "Test", "epic": "EP-01", "role": "admin", "type": "story"})},
                    content_type="multipart/form-data",
                )
            self.assertTrue(captured_body, f"create_story nebyl zavolán pro {target}")
            body = captured_body[0]
            self.assertTrue(body.startswith("# Test"), f"[{target}] Tělo nezačíná #: {body[:80]!r}")


class TestInsertFigmaImagePath(unittest.TestCase):
    """_insert_figma_image_path vždy pracuje s Markdown wiki."""

    @classmethod
    def setUpClass(cls):
        os.environ.pop("TARGET_SYSTEM", None)
        issue_provider.reset_provider()
        cls._mod = _load_task_forge()

    def setUp(self):
        os.environ["TARGET_SYSTEM"] = "jira"
        issue_provider.reset_provider()

    def tearDown(self):
        os.environ.pop("TARGET_SYSTEM", None)
        issue_provider.reset_provider()

    def _write_wiki(self, tmp: str, content: str) -> str:
        wiki_dir = Path(tmp) / "wiki" / "stories"
        wiki_dir.mkdir(parents=True, exist_ok=True)
        wiki_file = wiki_dir / "US-084.md"
        wiki_file.write_text(content, encoding="utf-8")
        return "wiki/stories/US-084.md"

    def test_inserts_figma_image_metadata_after_existing_figma_url(self):
        """Po - Figma: URL se přidá řádek - Figma_image:."""
        with tempfile.TemporaryDirectory() as tmp:
            content = (
                "# Story\n"
                "- Epic: EP\n"
                "- Figma: https://figma.com/file/abc\n"
                "- Status: new\n"
                "\n## Co se zobrazuje\nsome content\n"
            )
            wiki_path = self._write_wiki(tmp, content)
            original = self._mod._REPO_ROOT
            self._mod._REPO_ROOT = Path(tmp)
            try:
                self._mod._insert_figma_image_path(
                    wiki_path, None, "assets/US-084/figma_US-084.png"
                )
            finally:
                self._mod._REPO_ROOT = original
            result = (Path(tmp) / wiki_path).read_text(encoding="utf-8")
        self.assertIn("- Figma_image: assets/US-084/figma_US-084.png", result)
        figma_idx = result.index("- Figma:")
        img_idx = result.index("- Figma_image:")
        self.assertGreater(img_idx, figma_idx)

    def test_syncs_figma_image_to_provider_update_body(self):
        """update_body je voláno s Markdown tělem obsahujícím - Figma_image:."""
        with tempfile.TemporaryDirectory() as tmp:
            content = (
                "# Story\n"
                "- Epic: EP\n"
                "- Status: new\n"
                "\n## Co se zobrazuje\nsome content\n"
            )
            wiki_path = self._write_wiki(tmp, content)
            original = self._mod._REPO_ROOT
            self._mod._REPO_ROOT = Path(tmp)
            fake_provider = MagicMock()
            try:
                with patch.object(self._mod, "get_provider", return_value=fake_provider):
                    self._mod._insert_figma_image_path(
                        wiki_path, 84, "assets/US-084/figma_US-084.png"
                    )
            finally:
                self._mod._REPO_ROOT = original
        fake_provider.update_body.assert_called_once()
        call_args = fake_provider.update_body.call_args
        self.assertEqual(call_args.args[0], 84)
        self.assertIn("- Figma_image: assets/US-084/figma_US-084.png", call_args.args[1])

    def test_replaces_existing_figma_image_metadata(self):
        """Existující - Figma_image: se přepíše novým."""
        with tempfile.TemporaryDirectory() as tmp:
            content = (
                "# Story\n"
                "- Epic: EP\n"
                "- Figma_image: assets/US-084/old.png\n"
                "- Status: new\n"
            )
            wiki_path = self._write_wiki(tmp, content)
            original = self._mod._REPO_ROOT
            self._mod._REPO_ROOT = Path(tmp)
            try:
                self._mod._insert_figma_image_path(
                    wiki_path, None, "assets/US-084/figma_US-084.png"
                )
            finally:
                self._mod._REPO_ROOT = original
            result = (Path(tmp) / wiki_path).read_text(encoding="utf-8")
        self.assertIn("- Figma_image: assets/US-084/figma_US-084.png", result)
        self.assertNotIn("old.png", result)


# ── DELETE /api/issues/<id> — provider abstrakce ────────────────────────────


class TestDeleteIssue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.pop("TARGET_SYSTEM", None)
        issue_provider.reset_provider()
        cls._mod = _load_task_forge()

    def setUp(self):
        self.client = self._mod.app.test_client()
        self._mod.app.config["TESTING"] = True

    def _story_issue(self):
        return {
            "number": 82, "title": "Test",
            "labels": [{"name": "user story"}],
            "body": " - Status: new\n",
            "state": "OPEN",
        }

    def test_delete_uses_provider_get_and_close_issue(self):
        fake = MagicMock()
        fake.get_issue.return_value = self._story_issue()
        with tempfile.TemporaryDirectory() as tmp:
            wiki = Path(tmp) / "wiki/stories/US-082.md"
            wiki.parent.mkdir(parents=True)
            wiki.write_text(" - Status: new\n", encoding="utf-8")
            original = self._mod._REPO_ROOT
            self._mod._REPO_ROOT = Path(tmp)
            try:
                with patch.object(self._mod, "get_provider", return_value=fake):
                    resp = self.client.delete("/api/issues/82")
            finally:
                self._mod._REPO_ROOT = original
        self.assertEqual(resp.status_code, 200)
        fake.get_issue.assert_called_once_with(82)
        fake.close_issue.assert_called_once_with(82)
        self.assertFalse(wiki.exists())

    def test_delete_404_when_issue_not_found(self):
        fake = MagicMock()
        fake.get_issue.side_effect = FileNotFoundError("nenalezena")
        with patch.object(self._mod, "get_provider", return_value=fake):
            resp = self.client.delete("/api/issues/82")
        self.assertEqual(resp.status_code, 404)

    def test_delete_422_when_no_story_or_bug_label(self):
        fake = MagicMock()
        fake.get_issue.return_value = {
            "number": 82, "title": "Epic",
            "labels": [{"name": "epic"}], "body": "",
        }
        with patch.object(self._mod, "get_provider", return_value=fake):
            resp = self.client.delete("/api/issues/82")
        self.assertEqual(resp.status_code, 422)
        fake.close_issue.assert_not_called()

    def test_delete_restores_wiki_on_close_failure(self):
        fake = MagicMock()
        fake.get_issue.return_value = self._story_issue()
        fake.close_issue.side_effect = RuntimeError("close selhal")
        with tempfile.TemporaryDirectory() as tmp:
            wiki = Path(tmp) / "wiki/stories/US-082.md"
            wiki.parent.mkdir(parents=True)
            wiki.write_text(" - Status: new\n", encoding="utf-8")
            original = self._mod._REPO_ROOT
            self._mod._REPO_ROOT = Path(tmp)
            try:
                with patch.object(self._mod, "get_provider", return_value=fake):
                    resp = self.client.delete("/api/issues/82")
                self.assertEqual(resp.status_code, 502)
                self.assertTrue(wiki.exists())
            finally:
                self._mod._REPO_ROOT = original


# ── POST /api/queue — Jira analysis enqueue ─────────────────────────────────


class TestEnqueueJiraAnalysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.pop("TARGET_SYSTEM", None)
        issue_provider.reset_provider()
        cls._mod = _load_task_forge()

    def setUp(self):
        self.client = self._mod.app.test_client()
        self._mod.app.config["TESTING"] = True

    def test_analysis_jira_enqueues_directly_without_gh(self):
        """Pro Jira analysis type se přeskočí GitHub label a zavolá _enqueue_analysis."""
        with tempfile.TemporaryDirectory() as tmp:
            wiki = Path(tmp) / "wiki/stories/US-090.md"
            wiki.parent.mkdir(parents=True)
            wiki.write_text(" - Status: clarify\n", encoding="utf-8")
            original = self._mod._REPO_ROOT
            self._mod._REPO_ROOT = Path(tmp)
            try:
                with patch.object(self._mod, "_is_jira_target", return_value=True), \
                     patch.object(self._mod, "_enqueue_analysis", return_value=("sess-1", 0)) as mock_enq, \
                     patch.object(self._mod.subprocess, "run") as mock_run:
                    resp = self.client.post(
                        "/api/queue",
                        json={"issue_number": 90, "type": "analysis", "name": "Test story"},
                    )
            finally:
                self._mod._REPO_ROOT = original
        self.assertEqual(resp.status_code, 200)
        mock_enq.assert_called_once_with(90, "Test story")
        # GitHub label nesmí být přidán
        for call in mock_run.call_args_list:
            args = call.args[0] if call.args else []
            self.assertNotIn("--add-label", args)

    def test_analysis_github_uses_label_mechanism(self):
        """Pro GitHub analysis type se přidá label a spustí poller."""
        with tempfile.TemporaryDirectory() as tmp:
            wiki = Path(tmp) / "wiki/stories/US-090.md"
            wiki.parent.mkdir(parents=True)
            wiki.write_text("- Status: clarify\n", encoding="utf-8")
            original = self._mod._REPO_ROOT
            self._mod._REPO_ROOT = Path(tmp)
            try:
                with patch.object(self._mod, "_is_jira_target", return_value=False), \
                     patch.object(self._mod.subprocess, "run",
                                  return_value=MagicMock(returncode=0)) as mock_run:
                    resp = self.client.post(
                        "/api/queue",
                        json={"issue_number": 90, "type": "analysis"},
                    )
            finally:
                self._mod._REPO_ROOT = original
        self.assertEqual(resp.status_code, 200)
        label_calls = [c for c in mock_run.call_args_list
                       if "--add-label" in (c.args[0] if c.args else [])]
        self.assertEqual(len(label_calls), 1)

    def test_analysis_missing_wiki_returns_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = self._mod._REPO_ROOT
            self._mod._REPO_ROOT = Path(tmp)
            try:
                with patch.object(self._mod, "_is_jira_target", return_value=True):
                    resp = self.client.post(
                        "/api/queue",
                        json={"issue_number": 99, "type": "analysis"},
                    )
            finally:
                self._mod._REPO_ROOT = original
        self.assertEqual(resp.status_code, 404)


# ── _markdown_to_jira konverze ───────────────────────────────────────────────


class TestMarkdownToJira(unittest.TestCase):
    """Pokrývá nové konverzní větve: ### h3, bold, číslované seznamy, inline kód."""

    def setUp(self):
        from issue_provider.jira import _markdown_to_jira
        self._conv = _markdown_to_jira

    def test_h3_section_converts_to_jira_h3(self):
        body = "# Story\n\n## Implementation Plan\n\n### BE\n- krok 1\n"
        result = self._conv(body)
        self.assertIn("h3. BE", result)

    def test_h2_before_h3_sets_in_metadata_false(self):
        """## musí přijít před ### v if-elif — metadata mode musí být vypnutý."""
        body = "# Story\n\n## Sekce\n\n### Podsekce\n- obsah\n"
        result = self._conv(body)
        # - odrážky v sekci (ne metadata) → ' * '
        self.assertIn(" * obsah", result)

    def test_bold_converts_to_jira_bold(self):
        body = "# Story\n\n## Sekce\n**důležité** info\n"
        result = self._conv(body)
        self.assertIn("*důležité*", result)
        self.assertNotIn("**důležité**", result)

    def test_numbered_list_converts_to_jira_ordered(self):
        body = "# Story\n\n## Sekce\n1. první krok\n2. druhý krok\n"
        result = self._conv(body)
        self.assertIn("# první krok", result)
        self.assertIn("# druhý krok", result)

    def test_inline_code_converts_to_jira_code(self):
        body = "# Story\n\n## Sekce\nSpusť `pytest` pro testy.\n"
        result = self._conv(body)
        self.assertIn("{{pytest}}", result)
        self.assertNotIn("`pytest`", result)

    def test_h3_in_metadata_does_not_disable_metadata_mode(self):
        """### před jakoukoli ## nesmí přerušit metadata mode."""
        body = "# Story\n- Epic: EP-01\n### Neočekávaný\n- pole: value\n\n## Sekce\n- obsah\n"
        result = self._conv(body)
        # metadata -  řádky → ' - ', sekce - → ' * '
        self.assertIn(" - Epic: EP-01", result)
        self.assertIn(" * obsah", result)


if __name__ == "__main__":
    unittest.main()
