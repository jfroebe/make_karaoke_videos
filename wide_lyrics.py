"""Compatibility wrapper for the standalone karaoke video builder.

The canonical implementation lives in make_karaoke_videos.py so users can
install only that script in ~/bin.
"""

from make_karaoke_videos import build_wide_lyrics

__all__ = ["build_wide_lyrics"]
