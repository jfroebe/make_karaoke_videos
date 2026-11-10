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

    def test_ffmpeg_explicit_ass_filename_filter(self):
        """Smoke-test the exact ASS filter syntax used by the renderer."""
        import shutil

        if shutil.which("ffmpeg") is None:
            self.skipTest("FFmpeg is unavailable")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "lyrics.ass"
            path.write_text(
                "[Script Info]\\n".replace("\\n", "\n")
                + "ScriptType: v4.00+\n"
                + "PlayResX: 1920\nPlayResY: 1080\n"
                + "[V4+ Styles]\n"
                + "Format: Name, Fontname, Fontsize, PrimaryColour, "
                + "SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
                + "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
                + "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, "
                + "MarginV, Encoding\n"
                + "Style: Default,Arial,50,&H00FFFFFF,&H000000FF,"
                + "&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,"
                + "10,10,50,1\n"
                + "[Events]\n"
                + "Format: Layer, Start, End, Style, Name, MarginL, "
                + "MarginR, MarginV, Effect, Text\n"
                + "Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,Hello\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error",
                 "-f", "lavfi", "-i", "color=s=320x180:r=1",
                 "-vf", "ass=filename=lyrics.ass",
                 "-frames:v", "1", "-f", "null", "-"],
                cwd=folder, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_uploaded_hank_subtitles(self):
        """Real exported ASS files preserve word timing and expected sizes."""
        import re

        fixtures = {
            "Hank_wide.ass": (1920, 1080),
            "Hank_vertical.ass": (1080, 1920),
            "Hank_instagram-reels.ass": (1080, 1920),
            "Hank_instagram-story.ass": (1080, 1920),
            "Hank_instagram-feed.ass": (1080, 1350),
        }
        for name, size in fixtures.items():
            with self.subTest(file=name):
                data = (ROOT / "tests" / "fixtures" / name).read_text(
                    encoding="utf-8-sig"
                )
                self.assertIn(f"PlayResX: {size[0]}", data)
                self.assertIn(f"PlayResY: {size[1]}", data)
                self.assertEqual(sum(line.startswith("Dialogue:")
                                     for line in data.splitlines()),
                                 44 if name in ("Hank_wide.ass", "Hank_vertical.ass")
                                 else 45)
                self.assertEqual(len(re.findall(r"\\kf\d+", data)), 181)
                self.assertIn("0:00:05.46", data)
                self.assertIn("0:02:42.31", data)

    def test_uploaded_hank_ass_ffmpeg_filters(self):
        """Smoke-render the corrected subtitles with libass on the local machine."""
        import shutil

        if shutil.which("ffmpeg") is None:
            self.skipTest("FFmpeg unavailable")
        names = {
            "Hank_wide.ass": (1920, 1080),
            "Hank_vertical.ass": (1080, 1920),
            "Hank_instagram-reels.ass": (1080, 1920),
            "Hank_instagram-story.ass": (1080, 1920),
            "Hank_instagram-feed.ass": (1080, 1350),
        }
        with tempfile.TemporaryDirectory() as folder:
            scratch = Path(folder)
            for name, (width, height) in names.items():
                with self.subTest(file=name):
                    shutil.copyfile(
                        ROOT / "tests" / "fixtures" / name,
                        scratch / "lyrics.ass",
                    )
                    result = subprocess.run(
                        ["ffmpeg", "-hide_banner", "-loglevel", "error",
                         "-threads", "2", "-f", "lavfi", "-i",
                         "color=c=black:s=256x256:r=1:d=1",
                         "-vf",
                         f"scale={width}:{height},"
                         "setpts=PTS+8/TB,ass=filename=lyrics.ass",
                         "-frames:v", "1", "-f", "null", "-"],
                        cwd=scratch, capture_output=True, text=True,
                        timeout=45,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_vertical_whole_word_highlighting_preserves_timing(self):
        """All real vertical fixtures retain 181 words and original layout."""
        from make_karaoke_videos import build_whole_word_lyrics

        names = (
            "Hank_vertical.ass",
            "Hank_instagram-reels.ass",
            "Hank_instagram-story.ass",
            "Hank_instagram-feed.ass",
        )
        for name in names:
            with self.subTest(file=name):
                original = ROOT / "tests" / "fixtures" / name
                with tempfile.TemporaryDirectory() as folder:
                    output = Path(folder) / "lyrics.ass"
                    build_whole_word_lyrics(original, output)
                    before = original.read_text(encoding="utf-8-sig")
                    after = output.read_text(encoding="utf-8")
                    self.assertEqual(before.count(r"\kf"), 181)
                    self.assertEqual(after.count(r"\k"), 181)
                    self.assertNotIn(r"\kf", after)
                    self.assertEqual(before.replace(r"\kf", r"\k"), after)

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
