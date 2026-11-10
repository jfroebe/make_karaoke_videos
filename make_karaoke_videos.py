#!/usr/bin/env python3
"""Render karaoke videos from an audio track, still image(s), and ASS subtitles.

Creates videos for YouTube (16:9), Instagram (Reels/Stories 9:16 or Feed
4:5), and TikTok (9:16). Python standard library + FFmpeg/FFprobe only.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VideoProfile:
    width: int
    height: int
    ass_attr: str
    image_attr: str


PROFILES = {
    "youtube": VideoProfile(1920, 1080, "ass_wide", "image_wide"),
    "tiktok": VideoProfile(1080, 1920, "ass_vertical", "image_vertical"),
    "instagram": VideoProfile(1080, 1920, "ass_instagram", "image_instagram"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build YouTube, Instagram and TikTok karaoke videos from ASS lyrics.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--audio", type=Path, required=True, help="Final MP3/WAV/M4A audio")
    parser.add_argument("--image-wide", type=Path,
                        help="Landscape background (prefer 16:9)")
    parser.add_argument("--image-vertical", type=Path,
                        help="Portrait background (prefer 9:16); defaults to wide image")
    parser.add_argument("--image-instagram", type=Path,
                        help="Instagram-specific background; defaults to vertical")
    parser.add_argument("--ass-wide", type=Path,
                        help="ASS file generated using --profile wide")
    parser.add_argument("--ass-vertical", type=Path,
                        help="ASS file for TikTok, generated using --profile vertical")
    parser.add_argument("--ass-instagram", type=Path,
                        help="ASS file using the matching instagram-reels/story/feed profile")
    parser.add_argument("--platform", choices=("all", "youtube", "instagram", "tiktok"),
                        default="all", help="Which videos to make")
    parser.add_argument("--instagram-format", choices=("reels", "story", "feed"),
                        default="reels", help="Instagram output format")
    parser.add_argument("--output-dir", type=Path, default=Path("videos"),
                        help="Destination folder")
    parser.add_argument("--name", default=None,
                        help="Output filename prefix (defaults to audio stem)")
    parser.add_argument("--fit", choices=("cover", "contain"), default="cover",
                        help="Cover crops to fill; contain uses black letterboxing")
    parser.add_argument("--fps", type=int, choices=(24, 25, 30, 60), default=30)
    parser.add_argument("--crf", type=int, default=19, help="H.264 quality (lower is better)")
    parser.add_argument("--preset", default="medium",
                        choices=("ultrafast", "superfast", "veryfast", "faster", "fast",
                                 "medium", "slow", "slower"))
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing videos")
    return parser.parse_args()


def check_file(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"{label} not found: {path}")
    return resolved


def run_checked(command: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(command, cwd=cwd, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            check=False)
    if result.returncode:
        excerpt = "\n".join(result.stderr.strip().splitlines()[-12:])
        raise RuntimeError(f"FFmpeg command failed (exit {result.returncode}):\n{excerpt}")
    return result.stdout.strip()


def audio_duration(path: Path) -> float:
    value = run_checked([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ])
    try:
        seconds = float(value)
    except ValueError as exc:
        raise ValueError(f"Cannot read audio duration: {path}") from exc
    if seconds <= 0:
        raise ValueError("Audio duration must be positive")
    return seconds


def scale_filter(width: int, height: int, fit: str) -> str:
    if fit == "cover":
        return (f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},setsar=1")
    return (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1")


def render(label: str, image: Path, audio: Path, ass: Path, target: Path,
           width: int, height: int, args: argparse.Namespace, duration: float) -> None:
    # Copy ASS to a plain filename in a private working directory. This avoids
    # FFmpeg filtergraph escaping problems with spaces, colons and apostrophes.
    with tempfile.TemporaryDirectory(prefix="karaoke-ass-") as work:
        temp = Path(work)
        shutil.copyfile(ass, temp / "lyrics.ass")
        vf = f"{scale_filter(width, height, args.fit)},ass=lyrics.ass"
        command = [
            "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
            "-y" if args.overwrite else "-n",
            "-loop", "1", "-framerate", str(args.fps), "-i", str(image),
            "-i", str(audio),
            "-map", "0:v:0", "-map", "1:a:0",
            "-vf", vf,
            "-c:v", "libx264", "-preset", args.preset,
            "-crf", str(args.crf), "-pix_fmt", "yuv420p",
            "-r", str(args.fps),
            "-c:a", "aac", "-b:a", "256k",
            "-movflags", "+faststart",
            "-t", f"{duration:.3f}",
            "-shortest", str(target),
        ]
        print(f"Rendering {label}: {width}x{height} -> {target}", flush=True)
        run_checked(command, cwd=temp)
    print(f"Created: {target}", flush=True)


def main() -> None:
    args = parse_args()
    if not (0 <= args.crf <= 51):
        raise ValueError("--crf must be between 0 and 51")
    for executable in ("ffmpeg", "ffprobe"):
        if not shutil.which(executable):
            raise ValueError(f"{executable} is not installed or not on PATH")
    chosen = (tuple(PROFILES) if args.platform == "all" else (args.platform,))
    audio = check_file(args.audio, "Audio file")
    if "youtube" in chosen and (not args.image_wide or not args.ass_wide):
        raise ValueError("YouTube needs --image-wide and --ass-wide")
    if "tiktok" in chosen and not args.image_vertical and not args.image_wide:
        raise ValueError("TikTok needs --image-vertical or --image-wide")
    if "instagram" in chosen and not any((args.image_instagram,
                                           args.image_vertical,
                                           args.image_wide)):
        raise ValueError("Instagram needs --image-instagram, --image-vertical or --image-wide")
    wide = check_file(args.image_wide, "Landscape image") if args.image_wide else None
    ass_wide = (check_file(args.ass_wide, "YouTube ASS subtitle file")
                if args.ass_wide else None)
    vertical = (check_file(args.image_vertical, "Portrait image")
                if args.image_vertical else wide)
    instagram_image = (check_file(args.image_instagram, "Instagram image")
                       if args.image_instagram else vertical)
    ass_vertical = (check_file(args.ass_vertical, "TikTok ASS subtitle file")
                    if args.ass_vertical else None)
    ass_instagram = (check_file(args.ass_instagram, "Instagram ASS subtitle file")
                     if args.ass_instagram else None)
    if "tiktok" in chosen and ass_vertical is None:
        raise ValueError("TikTok needs --ass-vertical (use the ELYSY 'vertical' profile)")
    if "instagram" in chosen and ass_instagram is None:
        raise ValueError("Instagram needs --ass-instagram (use an Instagram ASS profile)")
    if "instagram" in chosen and args.instagram_format == "feed":
        instagram_height = 1350
    else:
        instagram_height = 1920
    prefix = args.name or audio.stem
    if not prefix.strip() or any(char in prefix for char in '/\\'):
        raise ValueError("--name must be a nonempty filename prefix without slashes")
    outdir = args.output_dir.expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    plans = {
        "youtube": (wide, ass_wide, 1920, 1080, outdir / f"{prefix}-youtube.mp4"),
        "instagram": (instagram_image, ass_instagram, 1080, instagram_height,
                      outdir / f"{prefix}-instagram-{args.instagram_format}.mp4"),
        "tiktok": (vertical, ass_vertical, 1080, 1920,
                   outdir / f"{prefix}-tiktok.mp4"),
    }
    if not args.overwrite:
        existing = [str(plans[p][-1]) for p in chosen if plans[p][-1].exists()]
        if existing:
            raise ValueError("Output already exists (use --overwrite): " + ", ".join(existing))
    duration = audio_duration(audio)
    print(f"Audio duration: {duration:.2f}s")
    for platform in chosen:
        image, ass, width, height, destination = plans[platform]
        render(platform, image, audio, ass, destination,
               width, height, args, duration)
    print(f"Done: {len(chosen)} video(s) written to {outdir}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None