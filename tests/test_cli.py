import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from viddl.cli import (
    build_parser,
    build_ydl_opts,
    metadata_is_system_compatible,
    parse_cookies_from_browser,
    print_download_error,
    should_make_system_compatible,
)


class CliTests(unittest.TestCase):
    def test_help_renders_filename_template(self) -> None:
        help_text = build_parser().format_help()

        self.assertIn("%(title)s.%(ext)s", help_text)

    def test_parse_cookies_from_browser(self) -> None:
        self.assertEqual(
            parse_cookies_from_browser("chrome:Profile 1"),
            ("chrome", "Profile 1", None, None),
        )

    def test_build_ydl_opts_includes_facebook_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cookies = Path(tmpdir) / "cookies.txt"
            args = build_parser().parse_args(
                [
                    "https://www.facebook.com/reel/986008017352567",
                    "--output-dir",
                    tmpdir,
                    "--cookies",
                    str(cookies),
                    "--cookies-from-browser",
                    "chrome",
                    "--impersonate",
                    "chrome",
                ]
            )

            opts = build_ydl_opts(args)

        self.assertEqual(opts["cookiefile"], str(cookies.resolve()))
        self.assertEqual(opts["cookiesfrombrowser"], ("chrome", None, None, None))
        self.assertEqual(str(opts["impersonate"]), "chrome")
        self.assertIn("vcodec:h264", opts["format_sort"])
        self.assertEqual(opts["postprocessors"], [])
        self.assertTrue(should_make_system_compatible(args))

    def test_full_quality_keeps_original_best_stream_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            args = build_parser().parse_args(
                [
                    "https://www.youtube.com/watch?v=VIDEO_ID",
                    "--output-dir",
                    tmpdir,
                    "--full-quality",
                ]
            )

            opts = build_ydl_opts(args)

        self.assertEqual(opts["format"], "bestvideo+bestaudio/best")
        self.assertNotIn("format_sort", opts)
        self.assertEqual(opts["postprocessors"], [])
        self.assertFalse(should_make_system_compatible(args))

    def test_metadata_detects_system_compatible_mp4(self) -> None:
        metadata = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "pix_fmt": "yuv420p",
                },
                {"codec_type": "audio", "codec_name": "aac"},
            ]
        }

        self.assertTrue(metadata_is_system_compatible(metadata, "Video.mp4"))

    def test_metadata_rejects_vp9_mp4(self) -> None:
        metadata = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "vp9",
                    "pix_fmt": "yuv420p",
                },
                {"codec_type": "audio", "codec_name": "aac"},
            ]
        }

        self.assertFalse(metadata_is_system_compatible(metadata, "Video.mp4"))

    def test_facebook_parse_error_suggests_cookies(self) -> None:
        args = build_parser().parse_args(
            ["https://www.facebook.com/reel/986008017352567"]
        )
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            print_download_error(args, RuntimeError("Cannot parse data"))

        self.assertIn("--cookies-from-browser chrome", stderr.getvalue())
        self.assertIn("--impersonate chrome", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
