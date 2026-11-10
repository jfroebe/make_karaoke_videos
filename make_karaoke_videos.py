#!/usr/bin/env python3
"""Render karaoke videos from an audio track, still image(s), and ASS subtitles.

Creates videos for YouTube (16:9), Instagram (Reels/Stories 9:16 or Feed
4:5), and TikTok (9:16). Python standard library + FFmpeg/FFprobe only.
"""

from __future__ import annotations

import argparse
import re
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
    parser.add_argument("--wide-lines", type=int, default=5,
                        help="Visible lyric lines for YouTube (1 keeps original ASS layout)")
    parser.add_argument("--wide-scroll-ms", type=int, default=350,
                        help="Wide lyric transition time in milliseconds (0 to disable)")
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


def validate_ffmpeg_features() -> None:
    """Fail early when the installed FFmpeg cannot render ASS karaoke."""
    filters = run_checked(["ffmpeg", "-hide_banner", "-filters"])
    if not any(len(parts) >= 2 and parts[1] == "ass"
               for line in filters.splitlines()
               if (parts := line.split())):
        raise ValueError(
            "This FFmpeg build does not include the 'ass' subtitle filter "
            "(libass). On macOS, install 'brew install ffmpeg-full' and "
            "ensure its ffmpeg executable is first on PATH. "
            "Verify with: ffmpeg -hide_banner -filters | grep ass"
        )
    encoders = run_checked(["ffmpeg", "-hide_banner", "-encoders"])
    if not any(line.split()[1] == "libx264" for line in encoders.splitlines()
               if len(line.split()) >= 2):
        raise ValueError(
            "This FFmpeg build does not include the 'libx264' encoder. "
            "Install an FFmpeg build with libx264 support."
        )


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
        if label == "youtube" and args.wide_lines > 1:
            build_wide_lyrics(ass, temp / "lyrics.ass", visible=args.wide_lines,
                              scroll_ms=args.wide_scroll_ms)
        elif label in ("tiktok", "instagram"):
            build_whole_word_lyrics(ass, temp / "lyrics.ass")
        else:
            shutil.copyfile(ass, temp / "lyrics.ass")
        vf = f"{scale_filter(width, height, args.fit)},ass=filename=lyrics.ass"
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


DIALOGUE_PREFIX = "Dialogue:"
OVERRIDE_TAG = re.compile(r"\{[^}]*\}")
FILL_TAG = re.compile(r"\\kf(?=\d)", re.IGNORECASE)


def build_whole_word_lyrics(source: Path, target: Path) -> None:
    """Change karaoke fill to entire-word highlighting for vertical videos.

    Convert ASS karaoke \\kf (progressive fill) and \\ko (outline) timing
    to \\k (whole-word) timing without changing the duration, styles,
    positioning or any other event content.
    """
    data = source.read_text(encoding="utf-8-sig")
    lines = []
    for line in data.splitlines(keepends=True):
        if line.startswith("Dialogue:"):
            line = re.sub(r"\\(?:kf|ko)(?=\d)", r"\\k", line, flags=re.I)
        lines.append(line)
    target.write_text("".join(lines), encoding="utf-8")


def _parse_time(value: str) -> int:
    """Convert ASS timestamp to centiseconds."""
    hours, minutes, rest = value.split(":")
    seconds, centiseconds = rest.split(".")
    return ((int(hours) * 3600 + int(minutes) * 60 + int(seconds))
            * 100 + int(centiseconds))


def _format_time(value: int) -> str:
    """Convert centiseconds to ASS timestamp."""
    value = max(value, 0)
    hours, remainder = divmod(value, 360000)
    minutes, remainder = divmod(remainder, 6000)
    seconds, centiseconds = divmod(remainder, 100)
    return f"{hours}:{minutes:02}:{seconds:02}.{centiseconds:02}"


def build_wide_lyrics(source: Path, target: Path, visible: int = 5,
                      scroll_ms: int = 350) -> None:
    """Build smooth-moving lyric windows with whole-word karaoke highlights.

    Each successive window animates shared lines from their previous positions
    over scroll_ms milliseconds. ASS \\k highlights a whole word at its onset,
    unlike \\kf, which progressively fills the word as it is sung.
    """
    if not 2 <= visible <= 7:
        raise ValueError("Wide lyric window must show between 2 and 7 lines")
    if not 0 <= scroll_ms <= 2000:
        raise ValueError("--wide-scroll-ms must be between 0 and 2000")

    data = source.read_text(encoding="utf-8-sig")
    header = []
    lyrics = []
    in_events = False
    for line in data.splitlines():
        if line.strip().lower() == "[events]":
            in_events = True
        if not (in_events and line.startswith(DIALOGUE_PREFIX)):
            header.append(line)
            continue
        fields = line.split(",", 9)
        if len(fields) != 10:
            raise ValueError(f"Malformed ASS Dialogue line: {line[:80]}")
        start, end = _parse_time(fields[1]), _parse_time(fields[2])
        if end <= start:
            raise ValueError("ASS lyric event must have a positive duration")
        if lyrics and start < lyrics[-1][0]:
            raise ValueError("ASS lyrics must be sorted by start time")
        lyrics.append((start, end, fields[3], fields[9]))

    if not lyrics:
        raise ValueError("No ASS Dialogue events found for wide lyric layout")

    center_x = 1480
    line_step = 96 if visible <= 5 else 76
    first_y = 550 - (visible - 1) * line_step // 2
    result = header[:]
    total = len(lyrics)
    for i, (start, end, style, _) in enumerate(lyrics):
        segment_end = lyrics[i + 1][0] if i + 1 < total else end
        if segment_end <= start:
            continue
        window_start = max(0, min(i - visible // 2, total - visible))
        previous_start = max(
            0, min(i - 1 - visible // 2, total - visible)
        )
        transition = min(scroll_ms, (segment_end - start) * 10)
        for slot, j in enumerate(range(window_start, min(total, window_start + visible))):
            _, _, _, text = lyrics[j]
            y = first_y + slot * line_step
            prev_y = first_y + (j - previous_start) * line_step
            movement = (f"\\move({center_x},{prev_y},{center_x},{y},"
                        f"0,{transition})" if prev_y != y and transition
                        else f"\\pos({center_x},{y})")
            active = j == i
            if active:
                # \k switches the entire word to the primary color at onset.
                rendered = FILL_TAG.sub(r"\\k", text)
                appearance = r"\fs42\bord3\shad1"
            else:
                rendered = OVERRIDE_TAG.sub("", text)
                appearance = (r"\fs40\bord2\shad1"
                              r"\1c&HFFFFFF&\alpha&H55&")
            fade = (f"\\fad({min(180, transition)},0)"
                    if j >= previous_start + visible and transition else "")
            next_start = max(
                0, min(i + 1 - visible // 2, total - visible)
            )
            if j < next_start and transition:
                fade = f"\\fad(0,{min(180, transition)})"
            override = f"{{\\an5{movement}{appearance}{fade}}}"
            result.append(
                "Dialogue: 0,"
                f"{_format_time(start)},{_format_time(segment_end)},"
                f"{style},,0,0,0,,{override}{rendered}"
            )
    target.write_text("\n".join(result) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    if not 1 <= args.wide_lines <= 7:
        raise ValueError("--wide-lines must be between 1 and 7")
    if not 0 <= args.wide_scroll_ms <= 2000:
        raise ValueError("--wide-scroll-ms must be between 0 and 2000")
    if not (0 <= args.crf <= 51):
        raise ValueError("--crf must be between 0 and 51")
    for executable in ("ffmpeg", "ffprobe"):
        if not shutil.which(executable):
            raise ValueError(f"{executable} is not installed or not on PATH")
    validate_ffmpeg_features()
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