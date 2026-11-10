# make_karaoke_videos

Generate finished karaoke lyric videos using **Python 3**, **FFmpeg**, background artwork, a finished audio recording, and synchronized **ASS karaoke subtitles**. Render for YouTube, Instagram Reels/Stories/Feed, and TikTok without any third-party Python packages.

## Requirements

- Python 3.10 or newer
- FFmpeg and FFprobe installed and on your `PATH`
- FFmpeg compiled with **libass** (`ass` video filter) and **libx264** (H.264 encoder)
- An audio file, background image(s), and karaoke `.ass` subtitle file(s)

### macOS: use `ffmpeg-full` when required

First check whether your current FFmpeg supports ASS subtitles and H.264 encoding:

```bash
command -v ffmpeg
ffmpeg -hide_banner -filters | grep -E '(^|[[:space:]])ass[[:space:]]'
ffmpeg -hide_banner -encoders | grep libx264
```

If the ASS filter is missing (or you receive `No such filter: 'ass'`), install a build that includes **libass**:

```bash
brew install ffmpeg-full
```

Homebrew may install `ffmpeg-full` separately from the currently selected `ffmpeg`. Make sure the **full** executable takes priority for both `ffmpeg` and `ffprobe` when running the video builder:

```bash
export PATH="$(brew --prefix ffmpeg-full)/bin:$PATH"
rehash
command -v ffmpeg
ffmpeg -hide_banner -filters | grep -E '(^|[[:space:]])ass[[:space:]]'
ffmpeg -hide_banner -encoders | grep libx264
```

If both checks succeed, run the video builder from that same Terminal session. To persist this PATH change for zsh, add the export line to `~/.zshrc`:

```bash
echo 'export PATH="$(brew --prefix ffmpeg-full)/bin:$PATH"' >> ~/.zshrc
```

Open a fresh terminal or run `source ~/.zshrc`. **Installing `ffmpeg-full` alone is insufficient if a different FFmpeg executable remains first on PATH.** If the regular FFmpeg already provides the `ass` filter and `libx264`, you do not need to install `ffmpeg-full`.

Use [elysy_to_karaoke_ass](https://github.com/jfroebe/elysy_to_karaoke_ass) to generate the properly timed ASS files from ELYSY's Enhanced SRT or JSON exports.

## Quick start: render all three platforms

```bash
python3 make_karaoke_videos.py \
  --audio "song.mp3" \
  --image-wide "background-wide.png" \
  --image-vertical "background-vertical.png" \
  --ass-wide "lyrics-wide.ass" \
  --ass-vertical "lyrics-vertical.ass" \
  --ass-instagram "lyrics-instagram-reels.ass" \
  --name "my-song" \
  --output-dir "./videos"
```

Output:

```text
videos/
├── my-song-youtube.mp4
├── my-song-instagram-reels.mp4
└── my-song-tiktok.mp4
```

All outputs contain H.264 video, AAC audio, and **burned-in karaoke subtitles**. Video length is derived from the audio using FFprobe. MP4 files are optimized for web playback (`+faststart`).

## YouTube: multi-line karaoke lyrics (default)

The **YouTube landscape renderer displays five lyric lines at a time** on the right side of the artwork. Lines **glide upward** when the active line changes; surrounding lyrics are subdued white. Each sung word switches to its full highlighted color when that word begins (ASS `\\k` timing, rather than a progressive `\\kf` fill). This takes advantage of the lyric area without overwhelming the poster or covering the portraits on the left.

Use `--wide-lines 5` (the default) or choose 2–7 lines:

```bash
python3 make_karaoke_videos.py --platform youtube \
  --audio song.mp3 --image-wide landscape.png \
  --ass-wide Hank_wide.ass --wide-lines 5 \\
  --wide-scroll-ms 350 --overwrite
```

Set `--wide-scroll-ms 350` for the default 350 ms transition, increase it for slower movement, or use `--wide-scroll-ms 0` to disable animated scrolling. Set `--wide-lines 1` to render the original ASS file without changing its layout. Instagram and TikTok retain their existing ASS layouts. The script generates the scrolling/multi-line layout temporarily during video rendering; your original `Hank_wide.ass` file is unchanged.

## Whole-word highlighting for vertical video

TikTok, Instagram Reels, Instagram Stories and Instagram Feed now highlight each **entire word** at its timed onset. During rendering, progressive karaoke `\\kf` tags and outline karaoke `\\ko` tags are converted to whole-word `\\k` tags in a **temporary copy** of the ASS file. Timing, original subtitle files, positioning and line breaks stay unchanged.

Use the updated script in `~/bin` and rerender with `--overwrite`. YouTube retains its five-line smooth-scrolling layout.

## Platform sizes

| Platform | `--platform` | `--instagram-format` | Size / aspect |
| --- | --- | --- | --- |
| YouTube | `youtube` | — | 1920 × 1080 (16:9) |
| TikTok | `tiktok` | — | 1080 × 1920 (9:16) |
| Instagram Reels | `instagram` | `reels` (default) | 1080 × 1920 (9:16) |
| Instagram Stories | `instagram` | `story` | 1080 × 1920 (9:16) |
| Instagram Feed | `instagram` | `feed` | 1080 × 1350 (4:5) |

### Render just one platform

You do **not** need to supply unrelated YouTube artwork and subtitles when rendering only TikTok or Instagram:

```bash
# YouTube (lyrics can be placed on the right of landscape artwork)
python3 make_karaoke_videos.py --platform youtube \
  --audio song.mp3 --image-wide background-wide.png --ass-wide lyrics-wide.ass

# TikTok
python3 make_karaoke_videos.py --platform tiktok \
  --audio song.mp3 --image-vertical background-vertical.png \
  --ass-vertical lyrics-vertical.ass

# Instagram Reels
python3 make_karaoke_videos.py --platform instagram --instagram-format reels \
  --audio song.mp3 --image-vertical background-vertical.png \
  --ass-instagram lyrics-instagram-reels.ass

# Instagram Stories
python3 make_karaoke_videos.py --platform instagram --instagram-format story \
  --audio song.mp3 --image-vertical background-vertical.png \
  --ass-instagram lyrics-instagram-story.ass

# Instagram Feed (4:5)
python3 make_karaoke_videos.py --platform instagram --instagram-format feed \
  --audio song.mp3 --image-instagram background-feed.png \
  --ass-instagram lyrics-instagram-feed.ass
```

When rendering all platforms, include all three ASS files. If a dedicated portrait image is omitted, the script can reuse the wide image, but a purpose-composed portrait background is strongly recommended.

### Hank example

```bash
python3 make_karaoke_videos.py \
  --audio "The_Rangers_Promise.mp3" \
  --image-wide "Hank-landscape.png" \
  --image-vertical "Hank-portrait.png" \
  --ass-wide "Hank_wide.ass" \
  --ass-vertical "Hank_vertical.ass" \
  --ass-instagram "Hank_instagram-reels.ass" \
  --name "The_Rangers_Promise" --output-dir "./videos"
```

In the landscape image, keep Hank's portraits on the **left** and empty space on the **right**, matching the placement of the ELYSY `wide` karaoke ASS preset.

## Options

| Option | Default | What it does |
| --- | --- | --- |
| `--audio` | required | MP3, WAV, M4A or another FFmpeg-readable audio file |
| `--image-wide` | required for YouTube | 16:9 artwork |
| `--image-vertical` | optional | 9:16 portrait artwork; falls back to wide image |
| `--image-instagram` | optional | Instagram-specific artwork; falls back to portrait |
| `--ass-wide` | required for YouTube | ASS subtitles generated with ELYSY `wide` profile |
| `--ass-vertical` | required for TikTok | ASS subtitles generated with ELYSY `vertical` profile |
| `--ass-instagram` | required for Instagram | ASS subtitles matching the Instagram format |
| `--platform` | `all` | `all`, `youtube`, `instagram`, or `tiktok` |
| `--instagram-format` | `reels` | `reels`, `story`, or `feed` |
| `--output-dir` | `videos` | Directory for rendered MP4 files |
| `--name` | Audio filename | Output filename prefix |
| `--fit` | `cover` | `cover` fills/crops; `contain` letterboxes instead |
| `--fps` | `30` | Frame rate: 24, 25, 30, or 60 |
| `--crf` | `19` | Video quality (0–51, lower means higher quality) |
| `--preset` | `medium` | libx264 speed/efficiency preset |
| `--wide-lines` | `5` | YouTube lyric window size (2–7 lines); `1` preserves the original ASS layout |
| `--wide-scroll-ms` | `350` | Scroll transition duration in milliseconds (0–2000); 0 disables movement |
| `--overwrite` | off | Overwrite existing outputs |

Full help: `python3 make_karaoke_videos.py --help`.

## Notes and troubleshooting

- **Video layout:** The video builder scales/crops artwork to the requested platform size. It doesn't reposition ASS subtitles; positioning comes from the subtitle converter's profile.
- **Safe zones:** Instagram and TikTok place UI controls over parts of the video. Preview on a phone before publishing; use the matching Instagram-specific ASS preset.
- **FFmpeg ASS filter parsing:** Use the current script, which specifies `ass=filename=lyrics.ass` explicitly to avoid ambiguous FFmpeg option parsing. If an older version fails with `No option name near 'lyrics.ass'`, update your local script and try again.
- **Missing ASS subtitle filter:** If you see `No such filter: 'ass'`, your active FFmpeg lacks libass. Follow the `ffmpeg-full` instructions above, then confirm `command -v ffmpeg` points to the intended binary.
- **Spaces in paths:** Wrap paths in quotes. The script copies subtitle files to an isolated temporary directory to avoid FFmpeg filter escaping issues.
- **Existing output:** The script stops instead of overwriting MP4 files unless `--overwrite` is specified.
- **Missing files:** It prints a concise `Error:` message with a nonzero exit status, not a Python traceback.
- **Audio:** Do lyric alignment with the **final** song file first so the timing matches the rendered soundtrack.
- **Platform exports:** This creates MP4 video files; it does **not** upload them to YouTube, Instagram, or TikTok.

## Verified Hank karaoke fixtures (corrected English alignment)

Five **real ASS fixtures** are checked in under `tests/fixtures/`, regenerated from the corrected ELYSY Enhanced SRT at `tests/fixtures/The_Rangers_Promise_Clear_Rock_Remaster_enhanced-SRT_corrected.srt`. Select **English** in ELYSY and avoid extra blank lines or inconsistent whitespace when aligning English vocals.

| Fixture | Video profile | Karaoke lyric lines |
| --- | --- | ---: |
| `Hank_wide.ass` | YouTube, 1920 × 1080 | 44 |
| `Hank_vertical.ass` | TikTok, 1080 × 1920 | 44 |
| `Hank_instagram-reels.ass` | Reels, 1080 × 1920 | 45 |
| `Hank_instagram-story.ass` | Stories, 1080 × 1920 | 45 |
| `Hank_instagram-feed.ass` | Feed, 1080 × 1350 | 45 |

All five preserve **181 karaoke word tags**, begin at **00:00:05.46** and finish at approximately **00:02:42.31** (including the final caption hold). The earlier files incorrectly started at 1:30 because of an ELYSY language/alignment issue. Local FFmpeg/libass rendering was validated for all five corrected files, including against the supplied artwork during the first verse.

To reproduce the fixtures, run the `elysy_to_karaoke_ass.py` converter from [jfroebe/elysy_to_karaoke_ass](https://github.com/jfroebe/elysy_to_karaoke_ass) with each corresponding `--profile`. Example:

```bash
python3 elysy_to_karaoke_ass.py \
  tests/fixtures/The_Rangers_Promise_Clear_Rock_Remaster_enhanced-SRT_corrected.srt \
  --profile wide --output tests/fixtures/Hank_wide.ass
```

## Development and local testing

All tests and FFmpeg integration checks should run on the local META environment (`chatgpt-dev` / `chatgpt-build-02`), **not GitHub-hosted runners**. No GitHub Actions workflow is included.

```bash
python3 -m py_compile make_karaoke_videos.py
python3 -m unittest discover -s tests -v
ffmpeg -hide_banner -filters | grep ' ass '
ffmpeg -hide_banner -encoders | grep libx264
```

Functional smoke tests should render very short audio with sample artwork and ASS subtitles, then inspect the output sizes with FFprobe. The initial development checks used an available local execution runtime; **direct testing on the META hosts was not available in that session**.
