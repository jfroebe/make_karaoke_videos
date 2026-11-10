"""Regression tests for the widescreen five-line lyric window."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from make_karaoke_videos import build_wide_lyrics


ROOT = Path(__file__).resolve().parents[1]
HANK_ASS = ROOT / "tests" / "fixtures" / "Hank_wide.ass"


class WideLyricTests(unittest.TestCase):
    def test_five_line_windows_preserve_word_highlights(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "lyrics.ass"
            build_wide_lyrics(HANK_ASS, dest, visible=5)
            data = dest.read_text(encoding="utf-8")
            source = HANK_ASS.read_text(encoding="utf-8")
            original = [line for line in source.splitlines()
                        if line.startswith("Dialogue:")]
            generated = [line for line in data.splitlines()
                         if line.startswith("Dialogue:")]
            self.assertEqual(len(original), 44)
            self.assertEqual(len(generated), len(original) * 5)
            self.assertIn(r"\pos(1480,", data)
            self.assertEqual(data.count(r"\k"), source.count(r"\kf"))
            self.assertNotIn(r"\kf", data)
            self.assertIn(r"\move(1480,", data)
            self.assertIn(r"\fad(", data)
            # Context text should not animate karaoke tags.
            self.assertEqual(sum(r"\k" in line for line in generated), 44)
            # First lyric starts early, not 90 seconds in.
            self.assertTrue(generated[0].startswith("Dialogue: 0,0:00:05.46,"))

    def test_two_to_seven_lines_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            for count in range(2, 8):
                with self.subTest(count=count):
                    dest = Path(tmp) / f"lyrics-{count}.ass"
                    build_wide_lyrics(HANK_ASS, dest, visible=count)
                    generated = sum(
                        line.startswith("Dialogue:")
                        for line in dest.read_text().splitlines()
                    )
                    self.assertEqual(generated, 44 * count)

    def test_scroll_is_configurable(self):
        with tempfile.TemporaryDirectory() as tmp:
            still = Path(tmp) / "still.ass"
            moving = Path(tmp) / "moving.ass"
            build_wide_lyrics(HANK_ASS, still, scroll_ms=0)
            build_wide_lyrics(HANK_ASS, moving, scroll_ms=750)
            self.assertNotIn(r"\move(", still.read_text())
            self.assertIn(",750)", moving.read_text())

    def test_invalid_window_sizes(self):
        with tempfile.TemporaryDirectory() as tmp:
            for count in (0, 1, 8):
                with self.subTest(count=count):
                    with self.assertRaises(ValueError):
                        build_wide_lyrics(
                            HANK_ASS, Path(tmp) / "out.ass", visible=count
                        )

    def test_invalid_scroll_durations(self):
        with tempfile.TemporaryDirectory() as tmp:
            for value in (-1, 2001):
                with self.subTest(value=value):
                    with self.assertRaises(ValueError):
                        build_wide_lyrics(HANK_ASS, Path(tmp) / "out.ass",
                                          scroll_ms=value)

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg not installed")
    def test_ffmpeg_renders_generated_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "lyrics.ass"
            build_wide_lyrics(HANK_ASS, dest, visible=5)
            command = [
                "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
                "-f", "lavfi", "-i", "color=c=black:s=640x360:r=1:d=1",
                "-vf", "scale=1920:1080,setpts=PTS+8/TB,"
                       "ass=filename=lyrics.ass",
                "-frames:v", "1", "-f", "null", "-",
            ]
            result = subprocess.run(
                command, cwd=tmp, capture_output=True, text=True, timeout=45
            )
            if "No such filter: 'ass'" in result.stderr:
                self.skipTest("FFmpeg is missing libass")
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
