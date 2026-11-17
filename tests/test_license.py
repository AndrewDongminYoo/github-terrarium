"""Repository license contract."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LicenseTests(unittest.TestCase):
    def test_license_file_is_mit_with_the_selected_notice(self):
        text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertTrue(
            text.startswith("MIT License\n\nCopyright (c) 2026 Dongmin Yu\n")
        )
        self.assertIn("Permission is hereby granted, free of charge,", text)
        self.assertIn('THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY', text)


if __name__ == "__main__":
    unittest.main()
