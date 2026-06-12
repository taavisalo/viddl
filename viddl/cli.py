import argparse
import os
import re
import shlex
import sys
from pathlib import Path
from shutil import which

from yt_dlp import YoutubeDL
from yt_dlp.cookies import SUPPORTED_BROWSERS, SUPPORTED_KEYRINGS
from yt_dlp.networking.impersonate import ImpersonateTarget
from yt_dlp.postprocessor.common import PostProcessor
from yt_dlp.postprocessor.ffmpeg import FFmpegPostProcessor


SYSTEM_COMPATIBLE_VIDEO_CODECS = {"h264"}
SYSTEM_COMPATIBLE_AUDIO_CODECS = {"aac"}
SYSTEM_COMPATIBLE_PIXEL_FORMATS = {"yuv420p"}


def parse_cookies_from_browser(
    value: str,
) -> tuple[str, str | None, str | None, str | None]:
    match = re.fullmatch(
        r"""(?x)
        (?P<name>[^+:]+)
        (?:\s*\+\s*(?P<keyring>[^:]+))?
        (?:\s*:\s*(?!:)(?P<profile>.+?))?
        (?:\s*::\s*(?P<container>.+))?
        """,
        value,
    )
    if match is None:
        raise argparse.ArgumentTypeError(
            "expected BROWSER[+KEYRING][:PROFILE][::CONTAINER]"
        )

    browser_name, keyring, profile, container = match.group(
        "name", "keyring", "profile", "container"
    )
    browser_name = browser_name.lower()
    if browser_name not in SUPPORTED_BROWSERS:
        supported = ", ".join(sorted(SUPPORTED_BROWSERS))
        raise argparse.ArgumentTypeError(
            f'unsupported browser "{browser_name}". Supported browsers: {supported}'
        )

    if keyring is not None:
        keyring = keyring.upper()
        if keyring not in SUPPORTED_KEYRINGS:
            supported = ", ".join(map(str.lower, sorted(SUPPORTED_KEYRINGS)))
            raise argparse.ArgumentTypeError(
                f'unsupported keyring "{keyring.lower()}". Supported keyrings: {supported}'
            )

    return browser_name, profile, keyring, container


def parse_impersonate_target(value: str) -> ImpersonateTarget:
    try:
        return ImpersonateTarget.from_str(value.lower())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def is_facebook_url(url: str) -> bool:
    return bool(re.match(r"https?://(?:[\w.-]+\.)?facebook\.com/", url))


def metadata_is_system_compatible(metadata: dict, filepath: str) -> bool:
    if Path(filepath).suffix.lower() != ".mp4":
        return False

    streams = metadata.get("streams") or []
    video_stream = next(
        (stream for stream in streams if stream.get("codec_type") == "video"),
        None,
    )
    audio_streams = [
        stream for stream in streams if stream.get("codec_type") == "audio"
    ]

    if video_stream is None:
        return True

    video_codec = video_stream.get("codec_name")
    pixel_format = video_stream.get("pix_fmt")
    audio_codecs = {stream.get("codec_name") for stream in audio_streams}

    return (
        video_codec in SYSTEM_COMPATIBLE_VIDEO_CODECS
        and pixel_format in SYSTEM_COMPATIBLE_PIXEL_FORMATS
        and audio_codecs <= SYSTEM_COMPATIBLE_AUDIO_CODECS
    )


def should_make_system_compatible(args: argparse.Namespace) -> bool:
    return not args.audio_only and not args.full_quality


class SystemCompatibleVideoPP(FFmpegPostProcessor):
    @PostProcessor._restrict_to(video=True, audio=False, images=False, simulated=False)
    def run(self, info: dict) -> tuple[list[str], dict]:
        filepath = info.get("filepath")
        if not filepath:
            return [], info

        metadata = self.get_metadata_object(filepath)
        if metadata_is_system_compatible(metadata, filepath):
            self.to_screen("Already system-compatible H.264/AAC MP4")
            return [], info

        original_path = Path(filepath)
        final_path = original_path.with_suffix(".mp4")
        temp_path = original_path.with_name(
            f".{original_path.stem}.viddl-compatible.tmp.mp4"
        )

        self.to_screen(
            "Converting to system-compatible H.264/AAC MP4; "
            f"Destination: {final_path}"
        )
        self.run_ffmpeg(
            str(original_path),
            str(temp_path),
            [
                "-map",
                "0:v:0",
                "-map",
                "0:a?",
                "-map_metadata",
                "0",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-tag:v",
                "avc1",
                "-c:a",
                "aac",
                "-b:a",
                "160k",
            ],
        )

        os.replace(temp_path, final_path)
        files_to_delete = []
        if final_path != original_path:
            files_to_delete.append(str(original_path))

        info["filepath"] = str(final_path)
        info["ext"] = "mp4"
        info["format"] = "mp4"
        return files_to_delete, info


def print_download_error(args: argparse.Namespace, exc: Exception) -> None:
    print(f"Download failed: {exc}", file=sys.stderr)

    if not is_facebook_url(args.url) or "Cannot parse data" not in str(exc):
        return

    if args.cookiefile or args.cookies_from_browser:
        print(
            "Facebook could not expose downloadable video data with the supplied "
            "cookies. Confirm the Reel is playable in that browser/profile.",
            file=sys.stderr,
        )
        return

    print(
        "Facebook Reels often require a logged-in browser session. Try:",
        file=sys.stderr,
    )
    print(
        f"viddl {shlex.quote(args.url)} --cookies-from-browser chrome --impersonate chrome",
        file=sys.stderr,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="viddl",
        description="Download videos with yt-dlp.",
    )
    parser.add_argument("url", help="Video URL")
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory to save downloads (default: current directory)",
    )
    parser.add_argument(
        "--filename",
        default="%(title)s.%(ext)s",
        help="Output filename template (default: %%(title)s.%%(ext)s)",
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
    parser.add_argument(
        "--full-quality",
        action="store_true",
        help=(
            "Skip compatibility conversion and keep the highest available stream"
        ),
    )
    parser.add_argument(
        "--cookies",
        dest="cookiefile",
        help="Netscape cookies file to use for sites that require login",
    )
    parser.add_argument(
        "--cookies-from-browser",
        type=parse_cookies_from_browser,
        metavar="BROWSER[+KEYRING][:PROFILE][::CONTAINER]",
        help=(
            "Load cookies from a browser, e.g. chrome, safari, firefox, "
            "or chrome:Profile 1"
        ),
    )
    parser.add_argument(
        "--impersonate",
        type=parse_impersonate_target,
        metavar="CLIENT[:OS]",
        help="Impersonate a browser client for requests, e.g. chrome or safari",
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

    opts = {
        "format": format_selector,
        "outtmpl": str(output_dir / args.filename),
        "postprocessors": postprocessors,
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
        "js_runtimes": {"node": {}},
        "remote_components": ["ejs:github"],
    }

    if should_make_system_compatible(args):
        opts["format_sort"] = [
            "vcodec:h264",
            "lang",
            "quality",
            "res",
            "fps",
            "hdr:12",
            "acodec:aac",
        ]

    if args.cookiefile:
        opts["cookiefile"] = str(Path(args.cookiefile).expanduser().resolve())
    if args.cookies_from_browser:
        opts["cookiesfrombrowser"] = args.cookies_from_browser
    if args.impersonate is not None:
        opts["impersonate"] = args.impersonate

    return opts


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    missing_tools = [tool for tool in ("ffmpeg", "ffprobe") if which(tool) is None]
    if missing_tools:
        print(
            f"{', '.join(missing_tools)} required but not found on PATH.",
            file=sys.stderr,
        )
        return 1

    opts = build_ydl_opts(args)
    try:
        with YoutubeDL(opts) as ydl:
            if should_make_system_compatible(args):
                ydl.add_post_processor(SystemCompatibleVideoPP(ydl), when="after_move")
            ydl.download([args.url])
    except Exception as exc:  # noqa: BLE001
        print_download_error(args, exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
