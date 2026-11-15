import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agents.env import load_env


class LoadEnvTests(unittest.TestCase):
    def load(self, text, existing=None):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text(text, encoding="utf-8")
            with mock.patch.dict(os.environ, existing or {}):
                for name in ("T_ONE", "T_TWO", "T_THREE", "T_FOUR", "T_FIVE", "T_EMPTY"):
                    os.environ.pop(name, None) if name not in (existing or {}) else None
                load_env(path)
                return {k: v for k, v in os.environ.items() if k.startswith("T_")}

    def test_parses_values_quotes_export_and_comments(self):
        loaded = self.load(
            "# comment\n\nT_ONE=plain\nT_TWO=\"quoted value\"\nexport T_THREE='single'\n"
            "T_FOUR=trailing # note\nT_FIVE = spaced \n"
        )

        self.assertEqual(
            loaded,
            {
                "T_ONE": "plain",
                "T_TWO": "quoted value",
                "T_THREE": "single",
                "T_FOUR": "trailing",
                "T_FIVE": "spaced",
            },
        )

    def test_empty_values_are_skipped(self):
        self.assertNotIn("T_EMPTY", self.load("T_EMPTY=\n"))

    def test_existing_environment_wins(self):
        loaded = self.load("T_ONE=from-file\n", existing={"T_ONE": "from-shell"})

        self.assertEqual(loaded["T_ONE"], "from-shell")

    def test_missing_file_is_ignored(self):
        load_env(Path("/no/such/.env"))


if __name__ == "__main__":
    unittest.main()
