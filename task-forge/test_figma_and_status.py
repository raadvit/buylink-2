"""Integrační testy pro figma image save (US-182) a update_issue_status_in_development."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import story_builder
import importlib.util as _ilu

_spec = _ilu.spec_from_file_location(
    "task_forge",
    Path(__file__).resolve().parent / "main.py",
)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
app = _mod.app
_insert_figma_image_path = _mod._insert_figma_image_path


# ── update_issue_status_in_development ───────────────────────────────────────

class TestUpdateIssueStatusNoDuplicates(unittest.TestCase):
    """Bug US-182: opakované volání nesmí přidat duplicitní - Status: řádky."""

    def _make_wiki(self, status: str, extra_status_lines: int = 0) -> str:
        lines = [
            "# Test story",
            "",
            "- Epic: EP-01 Task-forge",
            "- Role: admin",
            "- GitHub: #182",
            f"- Status: {status}",
        ]
        for _ in range(extra_status_lines):
            lines.append(f"- Status: {status}")
        lines += ["", "## Co se stalo", "test"]
        return "\n".join(lines)

    def _count_status_lines(self, content: str) -> int:
        return sum(1 for line in content.splitlines() if line.startswith("- Status:"))

    def test_single_call_replaces_status(self):
        wiki_content = self._make_wiki("new")
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(story_builder, "get_provider") as mock_get_provider,
        ):
            wiki_path = Path(tmp) / "wiki/stories/US-182.md"
            wiki_path.parent.mkdir(parents=True)
            wiki_path.write_text(wiki_content)
            mock_provider = MagicMock()
            mock_get_provider.return_value = mock_provider

            story_builder.update_issue_status_in_development(
                182, "wiki/stories/US-182.md", tmp
            )

            result = wiki_path.read_text()
            self.assertEqual(self._count_status_lines(result), 1)
            self.assertIn("- Status: in-development", result)
            mock_provider.update_body.assert_called_once()

    def test_repeated_calls_no_duplicates(self):
        wiki_content = self._make_wiki("new")
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(story_builder, "get_provider") as mock_get_provider,
        ):
            wiki_path = Path(tmp) / "wiki/stories/US-182.md"
            wiki_path.parent.mkdir(parents=True)
            wiki_path.write_text(wiki_content)
            mock_get_provider.return_value = MagicMock()

            for _ in range(3):
                story_builder.update_issue_status_in_development(
                    182, "wiki/stories/US-182.md", tmp
                )

            result = wiki_path.read_text()
            self.assertEqual(self._count_status_lines(result), 1)
            self.assertIn("- Status: in-development", result)

    def test_repairs_existing_duplicates(self):
        wiki_content = self._make_wiki("in-development", extra_status_lines=2)
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(story_builder, "get_provider") as mock_get_provider,
        ):
            wiki_path = Path(tmp) / "wiki/stories/US-182.md"
            wiki_path.parent.mkdir(parents=True)
            wiki_path.write_text(wiki_content)
            mock_get_provider.return_value = MagicMock()

            story_builder.update_issue_status_in_development(
                182, "wiki/stories/US-182.md", tmp
            )

            result = wiki_path.read_text()
            self.assertEqual(self._count_status_lines(result), 1)


# ── _insert_figma_image_path ─────────────────────────────────────────────────

class TestInsertFigmaImagePath(unittest.TestCase):
    """Bug US-182: figma_image_path musí být vložen bez ztráty GitHub čísla."""

    def _insert(self, wiki_content: str, saved_path: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            wiki_rel = "wiki/stories/US-099.md"
            wiki_path = Path(tmp) / wiki_rel
            wiki_path.parent.mkdir(parents=True)
            wiki_path.write_text(wiki_content)

            original = _mod._REPO_ROOT
            _mod._REPO_ROOT = Path(tmp)
            with patch.object(_mod, "get_provider", return_value=MagicMock()):
                try:
                    _insert_figma_image_path(wiki_rel, 99, saved_path)
                finally:
                    _mod._REPO_ROOT = original

            return wiki_path.read_text()

    def test_inserts_after_figma_url(self):
        wiki = (
            "# Test\n\n- GitHub: #99\n- Status: new\n"
            "- Figma: https://figma.com/test\n\n## Popis\ntext\n"
        )
        result = self._insert(wiki, "assets/US-099/figma_US-099.png")
        self.assertIn("- Figma_image: assets/US-099/figma_US-099.png", result)
        self.assertIn("- GitHub: #99", result)
        self.assertIn("- Figma: https://figma.com/test", result)

    def test_updates_existing_figma_image(self):
        wiki = (
            "# Test\n\n- GitHub: #99\n- Status: new\n"
            "- Figma: https://figma.com/test\n"
            "- Figma_image: assets/US-099/old.png\n"
        )
        result = self._insert(wiki, "assets/US-099/figma_US-099.png")
        self.assertIn("- Figma_image: assets/US-099/figma_US-099.png", result)
        self.assertNotIn("old.png", result)
        self.assertEqual(result.count("- Figma_image:"), 1)

    def test_preserves_github_number(self):
        wiki = "# Test\n\n- GitHub: #99\n- Status: new\n- Figma: https://f.com\n"
        result = self._insert(wiki, "assets/US-099/figma_US-099.png")
        self.assertIn("- GitHub: #99", result)

    def test_inserts_before_section_when_no_figma_url(self):
        wiki = "# Test\n\n- GitHub: #99\n- Status: new\n\n## Popis\ntext\n"
        result = self._insert(wiki, "assets/US-099/figma_US-099.png")
        self.assertIn("- Figma_image: assets/US-099/figma_US-099.png", result)
        self.assertIn("- GitHub: #99", result)


# ── /api/save — figma CDN happy path ─────────────────────────────────────────

class TestSaveEndpointFigmaImage(unittest.TestCase):
    """/api/save musí uložit figma_image_path do wiki po vytvoření issue."""

    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_figma_image_saved_to_wiki(self):
        with tempfile.TemporaryDirectory() as tmp:
            wiki_path = Path(tmp) / "wiki/stories/US-001.md"
            wiki_path.parent.mkdir(parents=True)
            wiki_path.write_text(
                "# Story\n\n- GitHub: #1\n- Status: new\n- Figma: https://figma.com/x\n"
            )

            fake_provider = MagicMock()
            fake_provider.create_story.return_value = {
                "issue_url": "https://github.com/test/repo/issues/1",
                "issue_number": 1,
                "wiki_path": "wiki/stories/US-001.md",
            }

            original = _mod._REPO_ROOT
            _mod._REPO_ROOT = Path(tmp)
            with (
                patch.object(_mod, "_save_figma_image_from_cdn", return_value="assets/US-001/figma_US-001.png"),
                patch.object(_mod, "get_provider", return_value=fake_provider),
                patch.object(_mod.subprocess, "run", return_value=MagicMock(returncode=0)),
            ):
                try:
                    resp = self.client.post(
                        "/api/save",
                        data={"data": json.dumps({
                            "name": "Test story",
                            "epic": "EP-01 Task-forge",
                            "role": "admin",
                            "why": "test", "what": "test", "how": "test",
                            "type": "story",
                            "figma_image_cdn_url": "https://s3.figma.com/img/x",
                        })},
                        content_type="multipart/form-data",
                    )
                finally:
                    _mod._REPO_ROOT = original

            self.assertEqual(resp.status_code, 200)
            wiki_content = wiki_path.read_text()
            self.assertIn("- Figma_image: assets/US-001/figma_US-001.png", wiki_content)
            self.assertIn("- GitHub: #1", wiki_content)

    def test_missing_figma_cdn_still_returns_200(self):
        fake_provider = MagicMock()
        fake_provider.create_story.return_value = {
            "issue_url": "https://github.com/test/repo/issues/2",
            "issue_number": 2,
            "wiki_path": "wiki/stories/US-002.md",
        }
        with (
            patch.object(_mod, "_save_figma_image_from_cdn", return_value=None),
            patch.object(_mod, "get_provider", return_value=fake_provider),
        ):
            resp = self.client.post(
                "/api/save",
                data={"data": json.dumps({
                    "name": "Test story 2",
                    "epic": "EP-01 Task-forge",
                    "role": "admin",
                    "why": "x", "what": "x", "how": "x",
                    "type": "story",
                    "figma_image_cdn_url": "https://s3.figma.com/img/y",
                })},
                content_type="multipart/form-data",
            )
        self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
