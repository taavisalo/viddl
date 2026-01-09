import argparse
import sys
from pathlib import Path
from shutil import which

from yt_dlp import YoutubeDL


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="viddl",
        description="Download YouTube videos in full quality.",
    )
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory to save downloads (default: current directory)",
    )
    parser.add_argument(
        "--filename",
        default="%(title)s.%(ext)s",
        help="Output filename template (default: %(title)s.%(ext)s)",
    )
    parser.add_argument(
        "--max-resolution",
        type=int,
        default=None,
        help="Cap video resolution height (e.g., 1080, 2160)",
    )
    parser.add_argument(
        "--audio-only",
        action="store_true",
        help="Download audio only",
    )
    return parser


def build_ydl_opts(args: argparse.Namespace) -> dict:
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.audio_only:
        format_selector = "bestaudio/best"
        postprocessors = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "0",
            }
        ]
    else:
        if args.max_resolution:
            format_selector = (
                f"bestvideo[height<={args.max_resolution}]+bestaudio/best[height<={args.max_resolution}]"
            )
        else:
            format_selector = "bestvideo+bestaudio/best"
        postprocessors = []

    return {
        "format": format_selector,
        "outtmpl": str(output_dir / args.filename),
        "postprocessors": postprocessors,
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
        "js_runtimes": {"node": {}},
        "remote_components": ["ejs:github"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if which("ffmpeg") is None:
        print("ffmpeg is required but was not found on PATH.", file=sys.stderr)
        return 1

    opts = build_ydl_opts(args)
    try:
        with YoutubeDL(opts) as ydl:
            ydl.download([args.url])
    except Exception as exc:  # noqa: BLE001
        print(f"Download failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
