# viddl

Download videos via a simple CLI.

## Setup (uv)

```bash
uv venv
source .venv/bin/activate
uv sync
```

## Usage

```bash
viddl https://www.youtube.com/watch?v=VIDEO_ID
```

Facebook Reels may require your logged-in browser cookies:

```bash
viddl "https://www.facebook.com/reel/986008017352567" --cookies-from-browser chrome --impersonate chrome
```

Optional flags:

```bash
viddl URL --output-dir ./downloads --filename "%(title)s.%(ext)s" --max-resolution 2160
viddl URL --full-quality
```

Authentication and request options for sites such as Facebook:

```bash
viddl URL --cookies-from-browser chrome
viddl URL --cookies ./cookies.txt
viddl URL --impersonate chrome
```

## Notes

- Downloads are converted to H.264/AAC MP4 by default with FFmpeg so files play in common system players.
- Use `--full-quality` to skip compatibility conversion and keep the absolute best stream, which may use VP9/AV1 and require VLC or another capable player.
- You must have permissions to download the content.
- Some Facebook videos and Reels require cookies from a browser where you are logged in.
- `ffmpeg` and `ffprobe` must be installed and available on your PATH.
