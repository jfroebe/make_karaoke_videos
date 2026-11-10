"""Local tests for the karaoke video builder (no GitHub-hosted runners)."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from make_karaoke_videos import PROFILES, scale_filter  # noqa: E402


class KaraokeBuilderTests(unittest.TestCase):
    def test_cover_and_contain(self):
        self.assertIn("crop=1920:1080", scale_filter(1920, 1080, "cover"))
        self.assertIn("pad=1080:1920", scale_filter(1080, 1920, "contain"))

    def test_platform_dimensions(self):
        self.assertEqual((PROFILES["youtube"].width, PROFILES["youtube"].height),
                         (1920, 1080))
        self.assertEqual((PROFILES["tiktok"].width, PROFILES["tiktok"].height),
                         (1080, 1920))
        self.assertEqual((PROFILES["instagram"].width, PROFILES["instagram"].height),
                         (1080, 1920))

    def test_missing_file_without_traceback(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "make_karaoke_videos.py"),
             "--audio", "/does-not-exist.wav", "--platform", "youtube",
             "--image-wide", "missing.png", "--ass-wide", "missing.ass"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Error:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_tiktok_only_does_not_require_wide_assets(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name in ("audio.wav", "vertical.png", "vertical.ass"):
                (root / name).write_bytes(b"placeholder")
            result = subprocess.run(
                [sys.executable, str(ROOT / "make_karaoke_videos.py"),
                 "--audio", str(root / "audio.wav"),
                 "--image-vertical", str(root / "vertical.png"),
                 "--ass-vertical", str(root / "vertical.ass"),
                 "--platform", "tiktok", "--output-dir", str(root / "videos")],
                capture_output=True, text=True,
            )
            self.assertNotIn("YouTube needs", result.stderr)
            self.assertNotIn("Landscape image not found", result.stderr)

    def test_instagram_only_does_not_require_wide_assets(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name in ("audio.wav", "vertical.png", "reels.ass"):
                (root / name).write_bytes(b"placeholder")
            result = subprocess.run(
                [sys.executable, str(ROOT / "make_karaoke_videos.py"),
                 "--audio", str(root / "audio.wav"),
                 "--image-vertical", str(root / "vertical.png"),
                 "--ass-instagram", str(root / "reels.ass"),
                 "--platform", "instagram",
                 "--output-dir", str(root / "videos")],
                capture_output=True, text=True,
            )
            self.assertNotIn("YouTube needs", result.stderr)
            self.assertNotIn("Landscape image not found", result.stderr)


if __name__ == "__main__":
    unittest.main()
