"""Testy pro _cleanup_memory_for_story — US-161."""

import importlib.util as _ilu
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

_spec = _ilu.spec_from_file_location(
    "task_forge",
    Path(__file__).resolve().parent / "main.py",
)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_cleanup = _mod._cleanup_memory_for_story

_REGISTER_HEADER = (
    "# Story Register\n\n"
    "| id | title | epic | status | reads | writes | depends_on | created_at | updated_at | assigned_dev | pr_url |\n"
    "|---|---|---|---|---|---|---|---|---|---|---|\n"
)

_DOMAIN_CONTENT = (
    "# Domain\n\n"
    "<!-- SECTION: story -->\n## Story\ncontent A\n<!-- /SECTION: story -->\n\n"
    "<!-- SECTION: bug -->\n## Bug\ncontent B\n<!-- /SECTION: bug -->\n\n"
    "<!-- SECTION: session -->\n## Session\ncontent C\n<!-- /SECTION: session -->\n"
)


def _make_register(*rows: str) -> str:
    return _REGISTER_HEADER + "".join(rows)


def _row(us_id: str, writes: str = "none") -> str:
    return f"| {us_id} | Title | EP-01 | draft | none | {writes} | none | 2026-01-01 | 2026-01-01 | none | none |\n"


class TestCleanupNoRegisterEntry(unittest.TestCase):
    def test_no_register_file_does_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_root = Path(tmp)
            with patch.object(_mod, "_REPO_ROOT", fake_root):
                _cleanup(42)  # must not raise

    def test_story_not_in_register_does_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_root = Path(tmp)
            mem = fake_root / ".memory-system" / "V2-shared-truth"
            mem.mkdir(parents=True)
            (mem / "story_register.md").write_text(_make_register(_row("US-099")))
            with patch.object(_mod, "_REPO_ROOT", fake_root):
                _cleanup(42)  # US-042 not in register, must not raise


class TestCleanupRemovesRow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.fake_root = Path(self.tmp)
        self.mem = self.fake_root / ".memory-system" / "V2-shared-truth"
        self.mem.mkdir(parents=True)
        self.register = self.mem / "story_register.md"
        self.domain = self.mem / "domain.md"

    def test_removes_story_row(self):
        self.register.write_text(_make_register(_row("US-042"), _row("US-099")))
        self.domain.write_text(_DOMAIN_CONTENT)
        with patch.object(_mod, "_REPO_ROOT", self.fake_root):
            _cleanup(42)
        content = self.register.read_text()
        self.assertNotIn("US-042", content)
        self.assertIn("US-099", content)

    def test_row_without_writes_none_leaves_domain_intact(self):
        self.register.write_text(_make_register(_row("US-042", "none")))
        self.domain.write_text(_DOMAIN_CONTENT)
        with patch.object(_mod, "_REPO_ROOT", self.fake_root):
            _cleanup(42)
        domain = self.domain.read_text()
        self.assertIn("<!-- SECTION: story -->", domain)
        self.assertIn("<!-- SECTION: bug -->", domain)


class TestCleanupDomainSections(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.fake_root = Path(self.tmp)
        self.mem = self.fake_root / ".memory-system" / "V2-shared-truth"
        self.mem.mkdir(parents=True)
        self.register = self.mem / "story_register.md"
        self.domain = self.mem / "domain.md"
        self.domain.write_text(_DOMAIN_CONTENT)

    def test_removes_exclusive_domain_section(self):
        # US-042 writes domain:story, no other story writes it
        self.register.write_text(_make_register(_row("US-042", "domain:story"), _row("US-099", "domain:bug")))
        with patch.object(_mod, "_REPO_ROOT", self.fake_root):
            _cleanup(42)
        domain = self.domain.read_text()
        self.assertNotIn("<!-- SECTION: story -->", domain)
        self.assertIn("<!-- SECTION: bug -->", domain)
        self.assertIn("<!-- SECTION: session -->", domain)

    def test_preserves_shared_domain_section(self):
        # US-042 writes domain:story, but US-099 also writes domain:story → shared → preserved
        self.register.write_text(_make_register(
            _row("US-042", "domain:story"),
            _row("US-099", "domain:story, domain:bug"),
        ))
        with patch.object(_mod, "_REPO_ROOT", self.fake_root):
            _cleanup(42)
        domain = self.domain.read_text()
        self.assertIn("<!-- SECTION: story -->", domain)

    def test_removes_multiple_exclusive_sections(self):
        self.register.write_text(_make_register(_row("US-042", "domain:story, domain:bug")))
        with patch.object(_mod, "_REPO_ROOT", self.fake_root):
            _cleanup(42)
        domain = self.domain.read_text()
        self.assertNotIn("<!-- SECTION: story -->", domain)
        self.assertNotIn("<!-- SECTION: bug -->", domain)
        self.assertIn("<!-- SECTION: session -->", domain)

    def test_missing_domain_file_does_not_raise(self):
        self.register.write_text(_make_register(_row("US-042", "domain:story")))
        self.domain.unlink()
        with patch.object(_mod, "_REPO_ROOT", self.fake_root):
            _cleanup(42)  # must not raise


if __name__ == "__main__":
    unittest.main()
