"""Unit tests for the FORMAT_TIERS retry loop in downloader.py."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, call

from src.downloader import (
    DownloadFailed,
    FORMAT_TIERS,
)


def test_format_tiers_order():
    """FORMAT_TIERS must be ordered highest → lowest quality."""
    assert len(FORMAT_TIERS) == 3
    assert "bv*" in FORMAT_TIERS[0]  # Max quality with mp4 preference
    assert "height<=1080" in FORMAT_TIERS[1]  # 1080p fallback
    assert FORMAT_TIERS[2] == "bestaudio/best"  # Audio-only final fallback


def test_format_tiers_all_distinct():
    """Each tier must be a unique format string."""
    assert len(set(FORMAT_TIERS)) == len(FORMAT_TIERS)


class TestFormatTierRetry:
    """Tests for the FORMAT_TIERS retry loop inside blocking_download."""

    def _make_downloader(self):
        from src.downloader import Downloader
        from pathlib import Path
        import tempfile

        tmp = tempfile.mkdtemp()
        return Downloader(
            music_dir=Path(tmp) / "music",
            video_dir=Path(tmp) / "video",
        )

    def _mock_ydl_success(self, extract_info_mock, video_id="test123"):
        """Make yt_dlp.YoutubeDL.extract_info return successfully."""
        info = {"id": video_id, "title": "Test Video", "ext": "mp4"}
        extract_info_mock.return_value = info

        ydl_instance = MagicMock()
        ydl_instance.prepare_filename.return_value = "/tmp/test_video.mp4"
        return ydl_instance, info

    def _setup_retry_mocks(self, extract_info_mock, side_effects):
        """
        Configure extract_info to raise successive exceptions, then succeed.
        side_effects: list of (exception or info_dict) for each call.
        """
        ydl_instance = MagicMock()
        ydl_instance.prepare_filename.return_value = "/tmp/test_video.mp4"
        ydl_instance.extract_info.side_effect = side_effects
        return ydl_instance

    @patch("yt_dlp.YoutubeDL")
    @patch("yt_dlp.cookies.extract_cookies_from_browser")
    def test_tier1_fails_tier2_succeeds(
        self, mock_cookies, mock_ydl_class,
    ):
        """Tier 0 fails with format-not-available → Tier 1 succeeds."""
        from yt_dlp.utils import DownloadError

        downloader = self._make_downloader()

        success_info = {"id": "abc123", "title": "Test", "ext": "mkv"}
        fail_error = DownloadError(
            "ERROR: [youtube] abc123: Requested format is not available"
        )

        # Tier 0 fails, Tier 1 succeeds
        ydl_instance = MagicMock()
        ydl_instance.prepare_filename.return_value = "/tmp/test.mkv"
        ydl_instance.extract_info.side_effect = [fail_error, success_info]
        mock_ydl_class.return_value = ydl_instance

        progress_calls = []

        video_id, file_path = downloader.download(
            "https://www.youtube.com/watch?v=abc123",
            "video",
            progress_hook=progress_calls.append,
            cookies_browser="",
        )

        assert video_id == "abc123"
        # extract_info called twice: tier 0 failed, tier 1 succeeded
        assert ydl_instance.extract_info.call_count == 2

    @patch("yt_dlp.YoutubeDL")
    @patch("yt_dlp.cookies.extract_cookies_from_browser")
    def test_tier1_and_tier2_fail_tier3_succeeds(
        self, mock_cookies, mock_ydl_class,
    ):
        """Tier 0 and Tier 1 fail → Tier 2 (audio-only) succeeds."""
        from yt_dlp.utils import DownloadError

        downloader = self._make_downloader()

        success_info = {"id": "abc123", "title": "Test", "ext": "mp3"}
        fail_error = DownloadError(
            "ERROR: [youtube] abc123: Requested format is not available"
        )

        ydl_instance = MagicMock()
        ydl_instance.prepare_filename.return_value = "/tmp/test.mp3"
        ydl_instance.extract_info.side_effect = [
            fail_error,  # tier 0 "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/best[ext=mp4]/best"
            fail_error,  # tier 1 "best[height<=1080]"
            success_info,  # tier 2 "bestaudio/best"
        ]
        mock_ydl_class.return_value = ydl_instance

        progress_calls = []

        video_id, file_path = downloader.download(
            "https://www.youtube.com/watch?v=abc123",
            "video",
            progress_hook=progress_calls.append,
            cookies_browser="",
        )

        assert video_id == "abc123"
        # All three tiers attempted, third succeeded
        assert ydl_instance.extract_info.call_count == 3

    @patch("yt_dlp.YoutubeDL")
    @patch("yt_dlp.cookies.extract_cookies_from_browser")
    def test_non_retryable_error_raised_immediately(
        self, mock_cookies, mock_ydl_class,
    ):
        """Network/video-private errors should NOT retry through tiers."""
        from yt_dlp.utils import DownloadError

        downloader = self._make_downloader()

        fail_error = DownloadError(
            "ERROR: [youtube] abc123: Video unavailable. This video is private"
        )

        ydl_instance = MagicMock()
        ydl_instance.extract_info.side_effect = fail_error
        mock_ydl_class.return_value = ydl_instance

        with pytest.raises(DownloadFailed) as exc_info:
            downloader.download(
                "https://www.youtube.com/watch?v=abc123",
                "video",
                progress_hook=lambda d: None,
                cookies_browser="",
            )

        assert "private" not in str(exc_info.value).lower()
        # Only one attempt — no retry for non-format errors
        assert ydl_instance.extract_info.call_count == 1

    @patch("yt_dlp.YoutubeDL")
    @patch("yt_dlp.cookies.extract_cookies_from_browser")
    def test_all_tiers_exhausted_raises_clear_error(
        self, mock_cookies, mock_ydl_class,
    ):
        """When all 3 tiers fail, raise DownloadFailed with helpful message."""
        from yt_dlp.utils import DownloadError

        downloader = self._make_downloader()

        fail_error = DownloadError(
            "ERROR: [youtube] abc123: Requested format is not available"
        )

        ydl_instance = MagicMock()
        ydl_instance.extract_info.side_effect = [
            fail_error,
            fail_error,
            fail_error,
        ]
        mock_ydl_class.return_value = ydl_instance

        with pytest.raises(DownloadFailed) as exc_info:
            downloader.download(
                "https://www.youtube.com/watch?v=abc123",
                "video",
                progress_hook=lambda d: None,
                cookies_browser="",
            )

        msg = str(exc_info.value)
        assert "cookie" in msg.lower() or "yt-dlp" in msg.lower()
        assert ydl_instance.extract_info.call_count == 3

    @patch("yt_dlp.YoutubeDL")
    @patch("yt_dlp.cookies.extract_cookies_from_browser")
    def test_on_fallback_callback_invoked(
        self, mock_cookies, mock_ydl_class,
    ):
        """on_fallback must be called each time a tier fails."""
        from yt_dlp.utils import DownloadError

        downloader = self._make_downloader()

        success_info = {"id": "abc123", "title": "Test", "ext": "mkv"}
        fail_error = DownloadError(
            "ERROR: [youtube] abc123: Requested format is not available"
        )

        ydl_instance = MagicMock()
        ydl_instance.prepare_filename.return_value = "/tmp/test.mkv"
        ydl_instance.extract_info.side_effect = [
            fail_error,
            fail_error,
            success_info,
        ]
        mock_ydl_class.return_value = ydl_instance

        fallback_log = []

        video_id, file_path = downloader.download(
            "https://www.youtube.com/watch?v=abc123",
            "video",
            progress_hook=lambda d: None,
            cookies_browser="",
            on_fallback=fallback_log.append,
        )

        assert len(fallback_log) == 2  # tier 1, then tier 2
        # Each callback receives the format string being tried next
        assert "1080" in fallback_log[0]  # tier 1
        assert "bestaudio" in fallback_log[1]  # tier 2

    @patch("yt_dlp.YoutubeDL")
    @patch("yt_dlp.cookies.extract_cookies_from_browser")
    def test_audio_like_skips_tiers(
        self, mock_cookies, mock_ydl_class,
    ):
        """Music/podcast (audio_like=True) must NOT iterate FORMAT_TIERS."""
        downloader = self._make_downloader()

        success_info = {"id": "song1", "title": "Song", "ext": "mp3"}
        ydl_instance = MagicMock()
        ydl_instance.prepare_filename.return_value = "/tmp/song.mp3"
        ydl_instance.extract_info.return_value = success_info
        mock_ydl_class.return_value = ydl_instance

        video_id, file_path = downloader.download(
            "https://www.youtube.com/watch?v=song1",
            "music",
            progress_hook=lambda d: None,
        )

        assert video_id == "song1"
        # Only one call — no tier loop for music
        assert ydl_instance.extract_info.call_count == 1
