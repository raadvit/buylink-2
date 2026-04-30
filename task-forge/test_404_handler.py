import importlib.util as _ilu
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

_mocks = {
    "issue_provider": MagicMock(get_provider=MagicMock(return_value=MagicMock())),
    "issue_provider._wiki": MagicMock(),
    "status_history": MagicMock(),
    "store_state": MagicMock(),
    "story_builder": MagicMock(),
    "wiki_chat": MagicMock(),
    "queue_manager": MagicMock(
        AnalysisQueue=MagicMock(return_value=MagicMock()),
        ImplementQueue=MagicMock(return_value=MagicMock()),
    ),
}

with patch.dict("sys.modules", _mocks):
    _spec = _ilu.spec_from_file_location(
        "task_forge",
        Path(__file__).resolve().parent / "task-forge.py",
    )
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    app = _mod.app


class Test404Handler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_unknown_route_returns_404_status(self):
        resp = self.client.get("/neexistujici-stranka")
        self.assertEqual(resp.status_code, 404)

    def test_404_page_contains_expected_text(self):
        resp = self.client.get("/naprosto-neznama-stranka-xyz")
        self.assertEqual(resp.status_code, 404)
        body = resp.data.decode("utf-8")
        self.assertIn("Stránka nenalezena", body)
        self.assertIn("Přejít na hlavní stránku", body)

    def test_api_routes_unaffected(self):
        resp = self.client.get("/api/config")
        self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
