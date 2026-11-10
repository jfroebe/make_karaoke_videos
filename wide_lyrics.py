"""Build multi-line, right-side karaoke windows for widescreen videos."""

from __future__ import annotations

import re
from pathlib import Path


DIALOGUE_PREFIX = "Dialogue:"
OVERRIDE_TAG = re.compile(r"\{[^}]*\}")


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


def build_wide_lyrics(source: Path, target: Path, visible: int = 5) -> None:
    """Render neighboring lines continuously while highlighting the active line.

    A new ASS event window is displayed for each original lyric line. The
    active line preserves its original word-level karaoke timing.
    """
    if not 2 <= visible <= 7:
        raise ValueError("Wide lyric window must show between 2 and 7 lines")

    data = source.read_text(encoding="utf-8-sig")
    header: list[str] = []
    lyrics: list[tuple[int, int, str, str]] = []
    for line in data.splitlines():
        if not line.startswith(DIALOGUE_PREFIX):
            header.append(line)
            continue
        fields = line.split(",", 9)
        if len(fields) != 10:
            raise ValueError(f"Malformed ASS Dialogue line: {line[:80]}")
        start, end = _parse_time(fields[1]), _parse_time(fields[2])
        if end <= start:
            raise ValueError("ASS lyric event must have a positive duration")
        lyrics.append((start, end, fields[3], fields[9]))

    if not lyrics:
        raise ValueError("No ASS Dialogue events found for wide lyric layout")

    center_x = 1480
    center_y = 550
    line_step = 96 if visible <= 5 else 76
    first_y = center_y - (visible - 1) * line_step // 2
    result = header[:]
    for i, (start, end, style, _) in enumerate(lyrics):
        window_start = max(0, min(i - visible // 2, len(lyrics) - visible))
        window = lyrics[window_start:window_start + visible]
        for slot, (_, _, _, text) in enumerate(window):
            pos_y = first_y + slot * line_step
            active = window_start + slot == i
            if active:
                prefix = (f"{{\\an5\\pos({center_x},{pos_y})"
                          f"\\fs42\\bord3\\shad1}}")
                rendered = prefix + text
            else:
                plain = OVERRIDE_TAG.sub("", text)
                prefix = (f"{{\\an5\\pos({center_x},{pos_y})"
                          f"\\fs40\\bord2\\shad1\\1c&HFFFFFF&"
                          f"\\alpha&H55&}}")
                rendered = prefix + plain
            result.append(
                "Dialogue: 0,"
                f"{_format_time(start)},{_format_time(end)},"
                f"{style},,0,0,0,,{rendered}"
            )
    target.write_text("\n".join(result) + "\n", encoding="utf-8")
