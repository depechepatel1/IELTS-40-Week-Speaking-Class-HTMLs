"""Integration tests for make_interactive.py.

Runs the script on the actual Week_1_Lesson_Plan.html fixture and verifies
the three insertions, idempotency, and that originals stay untouched.

Run:  python -m unittest scripts.test_make_interactive  (from repo root)
  or:  python scripts/test_make_interactive.py
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _run(in_path: str, out_dir: str, *, endpoint="https://test.fcapp.run", bucket="http://test.local"):
    subprocess.check_call(
        [
            sys.executable,
            str(REPO / "scripts" / "make_interactive.py"),
            "--in", in_path,
            "--out", out_dir,
            "--endpoint", endpoint,
            "--bucket-base", bucket,
        ],
        cwd=REPO,
    )


class TestMakeInteractive(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)

    def test_week1_round_trip(self):
        out = self.tmp_path / "out"
        _run("Week_1_Lesson_Plan.html", str(out))
        result = out / "Week_1_Lesson_Plan.html"
        text = result.read_text(encoding="utf-8")
        # All three insertions present
        self.assertIn("<!-- AI-INTERACTIVE-V1 --> CSS */", text)
        self.assertIn("<!-- AI-INTERACTIVE-V1 --> SCRIPT", text)
        self.assertIn("data:font/woff2;base64,", text)
        self.assertIn('id="student-draft"', text)
        self.assertIn('id="polished-output"', text)
        self.assertIn('class="lines-overlay-host"', text)
        # Endpoint substituted, no leftover placeholder
        self.assertIn("https://test.fcapp.run", text)
        self.assertNotIn("__AI_ENDPOINT__", text)
        self.assertNotIn("__PRONUNCIATIONS_URL__", text)
        self.assertNotIn("__LESSON_KEY__", text)
        self.assertNotIn("__CAVEAT_400_BASE64__", text)
        self.assertNotIn("__INDIE_FLOWER_400_BASE64__", text)
        # Original `.lines` divs in .draft-page are preserved (wrapped, not replaced)
        self.assertGreaterEqual(text.count('<div class="lines"'), 2)

    def test_idempotent(self):
        out = self.tmp_path / "out"
        _run("Week_1_Lesson_Plan.html", str(out))
        first = (out / "Week_1_Lesson_Plan.html").read_bytes()
        _run("Week_1_Lesson_Plan.html", str(out))
        second = (out / "Week_1_Lesson_Plan.html").read_bytes()
        self.assertEqual(first, second, "Re-running must produce byte-identical output")

    def test_originals_untouched(self):
        src = REPO / "Week_1_Lesson_Plan.html"
        before = src.read_bytes()
        out = self.tmp_path / "out"
        _run("Week_1_Lesson_Plan.html", str(out))
        after = src.read_bytes()
        self.assertEqual(before, after)

    def test_lesson_key_propagates(self):
        out = self.tmp_path / "out"
        _run("Week_1_Lesson_Plan.html", str(out))
        text = (out / "Week_1_Lesson_Plan.html").read_text(encoding="utf-8")
        # __LESSON_KEY__ should be replaced with the file stem
        self.assertIn("Week_1_Lesson_Plan", text)
        self.assertNotIn("__LESSON_KEY__", text)

    def test_skip_files_dont_match_pattern(self):
        """The script only matches Week_*_Lesson_Plan.html; other files ignored."""
        src = self.tmp_path / "src"
        src.mkdir()
        (src / "intro_packet.html").write_text("<html></html>", encoding="utf-8")
        out = self.tmp_path / "out"
        _run(str(src), str(out))  # 0 files processed
        self.assertFalse((out / "intro_packet.html").exists())


if __name__ == "__main__":
    unittest.main()
