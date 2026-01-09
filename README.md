# viddl

Download YouTube videos in full quality via a simple CLI.

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

Optional flags:

```bash
viddl URL --output-dir ./downloads --filename "%(title)s.%(ext)s" --max-resolution 2160
```

## Notes

- Full quality is achieved by default with `bestvideo+bestaudio/best`.
- You must have permissions to download the content.
- `ffmpeg` must be installed and available on your PATH.
