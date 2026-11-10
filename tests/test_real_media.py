"""Optional real-media integration tests, executed only on local machines.

Supply files in a local directory via KARAOKE_MEDIA_DIR. No network requests.
Tests render only the first 2 seconds for speed; an additional libass frame
is rendered at 8 seconds so subtitles are actually exercised.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import make_karaoke_videos as builder  # noqa: E402

ASSETS = {
    "landscape.png": "2b9fe33bf5c816e7986b38f67fed0bc442df5b84dce9fd21611ce6971d3af275",
    "portrait.png": "5637ad6be0d9513f5b771de27c1f4da1f2084b018a2bc3a31167a5276c25757d",
    "The_Rangers_Promise_Clear_Rock_Remaster(1).mp3":
        "ad2cc3a7faa8af96decbd71067a7204acbbf204e8e8f141db8202ad56584b7d2",
}

CASES = (
    ("youtube", None, "Hank_wide.ass", (1920, 1080)),
    ("tiktok", None, "Hank_vertical.ass", (1080, 1920)),
    ("instagram", "reels", "Hank_instagram-reels.ass", (1080, 1920)),
    ("instagram", "story", "Hank_instagram-story.ass", (1080, 1920)),
    ("instagram", "feed", "Hank_instagram-feed.ass", (1080, 1350)),
)


class RealMediaIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        value = os.environ.get("KARAOKE_MEDIA_DIR")
        if not value:
            raise unittest.SkipTest("Set KARAOKE_MEDIA_DIR for local real-media tests")
        cls.media = Path(value).expanduser().resolve()
        if not cls.media.is_dir():
            raise unittest.SkipTest(f"Missing local media directory: {cls.media}")
        for name in ASSETS:
            if not (cls.media / name).is_file():
                raise unittest.SkipTest(f"Missing real-media fixture: {cls.media / name}")
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            raise unittest.SkipTest("FFmpeg/FFprobe unavailable")
        builder.validate_ffmpeg_features()

    def test_media_checksums(self):
        for name, expected in ASSETS.items():
            with self.subTest(name=name):
                value = hashlib.sha256((self.media / name).read_bytes()).hexdigest()
                self.assertEqual(value, expected)

    def test_all_five_actual_video_builds(self):
        audio = self.media / "The_Rangers_Promise_Clear_Rock_Remaster(1).mp3"
        with tempfile.TemporaryDirectory(prefix="karaoke-media-test-") as folder:
            output = Path(folder)
            for platform, instagram_format, ass_name, dimensions in CASES:
                args = [
                    "make_karaoke_videos.py",
                    "--audio", str(audio),
                    "--output-dir", str(output),
                    "--name", "test",
                    "--platform", platform,
                    "--image-wide", str(self.media / "landscape.png"),
                    "--image-vertical", str(self.media / "portrait.png"),
                    "--preset", "ultrafast",
                    "--crf", "28",
                    "--overwrite",
                ]
                if platform == "youtube":
                    args.extend(["--ass-wide", str(ROOT / "tests" / "fixtures" / ass_name)])
                elif platform == "tiktok":
                    args.extend(["--ass-vertical", str(ROOT / "tests" / "fixtures" / ass_name)])
                else:
                    args.extend(["--ass-instagram", str(ROOT / "tests" / "fixtures" / ass_name)])
                    args.extend(["--instagram-format", instagram_format])
                with self.subTest(platform=platform, fmt=instagram_format):
                    with patch.object(sys, "argv", args):
                        with patch.object(builder, "audio_duration", return_value=2.0):
                            builder.main()
                    suffix = (f"instagram-{instagram_format}" if instagram_format
                              else platform)
                    result_file = output / f"test-{suffix}.mp4"
                    self.assertTrue(result_file.is_file())
                    probe = subprocess.run(
                        ["ffprobe", "-v", "error", "-select_streams", "v:0",
                         "-show_entries", "stream=width,height",
                         "-of", "csv=p=0", str(result_file)],
                        capture_output=True, text=True, check=True,
                    )
                    self.assertEqual(
                        tuple(int(n) for n in probe.stdout.strip().split(",")),
                        dimensions,
                    )

    def test_subtitles_render_at_95_seconds(self):
        """Move the frame PTS forward, then apply the real ASS filter."""
        with tempfile.TemporaryDirectory(prefix="karaoke-ass-test-") as folder:
            work = Path(folder)
            shutil.copyfile(ROOT / "tests" / "fixtures" / "Hank_wide.ass",
                            work / "lyrics.ass")
            result = subprocess.run(
                ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
                 "-f", "lavfi", "-i", "color=c=black:s=320x180:r=1:d=1",
                 "-vf", "scale=1920:1080,setpts=PTS+8/TB,"
                        "ass=filename=lyrics.ass",
                 "-frames:v", "1", "-f", "null", "-"],
                cwd=work, capture_output=True, text=True, timeout=45,
            )
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
