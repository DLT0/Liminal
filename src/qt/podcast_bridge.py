"""Podcast suggestion and episode management mixin for AppBackend."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from PyQt6.QtCore import pyqtSlot

from src.downloader import Download403Failed, DownloadFailed, extract_youtube_id
from src import podcast_library
from src import suggestions_manager
from src.models import PlaybackStatus
from src.metadata_store import get_watched_progress as _get_wp

logger = logging.getLogger(__name__)


def _compute_watched_percent(path: str) -> float:
    pos, dur = _get_wp(path)
    if dur > 0 and pos > 0:
        return min(100.0, pos / dur * 100.0)
    return 0.0


_EPISODE_RE = re.compile(
    r"\b(?:Ep|EP|ep|T[âậạ]p|Episode|EPISODE|Season\s*\d+\s*Ep?)\s*\.?\s*(\d+)\b",
    re.IGNORECASE,
)


def _extract_episode_from_title(title: str) -> int:
    """Try to extract episode number from title when the episode field is 0."""
    if not title:
        return 0
    m = _EPISODE_RE.search(title)
    if m:
        try:
            return int(m.group(1))
        except (ValueError, IndexError):
            pass
    return 0


def _parse_created_at(created_at_str: str) -> float:
    """Parse created_at string into a Unix timestamp. Handles ISO 8601, JS Date.toString(), and RFC 2822."""
    if not created_at_str or not created_at_str.strip():
        return 0.0
    s = created_at_str.strip()
    # Strip trailing parenthetical (e.g. " (Coordinated Universal Time)")
    s = re.sub(r"\s*\(.*\)\s*$", "", s).strip()
    # Try ISO 8601 first
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        pass
    # Try RFC 2822 / JS Date.toString() format
    try:
        return parsedate_to_datetime(s).timestamp()
    except (ValueError, TypeError):
        pass
    return 0.0


ACCENT_COLORS = [
    "#6366f1", "#8b5cf6", "#ec4899", "#f43f5e", "#f97316",
    "#eab308", "#22c55e", "#14b8a6", "#06b6d4", "#3b82f6",
]


class PodcastMixin:
    """Podcast methods mixed into AppBackend (accesses self as AppBackend at runtime)."""

    # ── Suggestions ──────────────────────────────────────────────────────

    def apply_suggestions(self, items: list[dict]) -> None:
        """Push suggestion feed rows into podcast/video suggestion models."""
        for item in items:
            if not isinstance(item, dict):
                continue
            sid = str(item.get("id") or "")
            if not sid:
                continue
            local = podcast_library.get_path_for_suggestion(sid)
            if local:
                item["local_path"] = local
                item["download_status"] = "done"
                item["download_percent"] = 100.0
                item["is_downloading"] = False
            else:
                cached_path = suggestions_manager.get_local_path(sid)
                if cached_path and Path(cached_path).exists():
                    item["local_path"] = cached_path
                    item["download_status"] = "done"
                    item["download_percent"] = 100.0
                    item["is_downloading"] = False
        seen_ids: set[str] = set()
        deduped: list[dict] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("id") or "").strip()
            if item_id and item_id not in seen_ids:
                seen_ids.add(item_id)
                deduped.append(dict(item))
        self._all_suggestions = deduped
        self._suggestion_categories = suggestions_manager.get_cached_categories()
        self._video_sections = suggestions_manager.get_cached_sections()
        self._rebuild_suggestion_models()
        self._refresh_podcast_downloaded_from_library()
        self.suggestionsChanged.emit()

    def _suggestion_to_model(self, item: dict) -> dict:
        media_kind = str(item.get("media_kind") or "audio").lower()
        content_type = str(item.get("content_type") or "podcast").lower()
        author = str(item.get("author") or "").strip()

        item_categories = item.get("categories") or []
        first_category = item_categories[0] if item_categories else ""
        item_category_labels = item.get("category_labels") or []
        category_label_str = ", ".join(item_category_labels) if item_category_labels else ""

        season = max(0, int(item.get("season") or 0) or 0)
        episode = max(0, int(item.get("episode") or 0) or 0)
        if episode == 0:
            episode = _extract_episode_from_title(str(item.get("title") or ""))
        sort_order = max(0, int(item.get("sort_order") or 0) or 0)
        ep_label = ""
        if episode > 0:
            if season > 1:
                ep_label = f"S{season}E{episode}"
            else:
                ep_label = f"Tập {episode}"
        parts = [p for p in (ep_label, author) if p]
        subtitle = " · ".join(parts) if parts else (
            "Shorts" if content_type == "shorts"
            else ("Podcast" if content_type == "podcast" else "Video")
        )
        image = str(item.get("local_thumbnail") or item.get("thumbnail_url") or "")
        source_url = str(item.get("source_url") or "")
        local_path = str(item.get("local_path") or "").strip()
        if local_path and not Path(local_path).exists():
            local_path = ""
        status = str(item.get("download_status") or "pending")
        if local_path:
            status = "done"
        wp = _compute_watched_percent(local_path) if local_path else 0.0
        return {
            "title": str(item.get("title") or ""),
            "subtitle": subtitle,
            "artist": author,
            "image": image,
            "path": local_path,
            "audio_only": media_kind == "audio",
            "url": source_url,
            "duration": "",
            "track_id": str(item.get("id") or source_url),
            "is_remote": not bool(local_path),
            "download_percent": 100.0 if status == "done" else float(item.get("download_percent") or 0.0),
            "download_status": status,
            "is_downloading": bool(item.get("is_downloading")) or status == "downloading",
            "is_collection": False,
            "kind": content_type,
            "child_count": 0,
            "preview_images": [],
            "season": season,
            "episode": episode,
            "sort_order": sort_order,
            "watched_percent": wp,
            "category": first_category,
            "category_label": "",
            "categories": item_categories,
            "category_labels": item_category_labels,
            "playlist_id": item.get("playlist_id"),
            "tags": list(item.get("tags") or []),
            "suggestion_id": str(item.get("id") or ""),
            "media_kind": media_kind,
            "content_type": content_type,
            "source_url": source_url,
            "description": str(item.get("description") or ""),
        }

    @staticmethod
    def _suggestion_sort_key(item: dict) -> tuple:
        season = max(1, int(item.get("season") or 1) or 1)
        episode = max(0, int(item.get("episode") or 0) or 0)
        if episode == 0:
            episode = _extract_episode_from_title(str(item.get("title") or ""))
        sort_order = max(0, int(item.get("sort_order") or 0) or 0)
        ts = _parse_created_at(str(item.get("created_at") or ""))
        return (
            season,
            episode,
            0 if sort_order > 0 else 1,
            sort_order,
            ts,
            str(item.get("title") or ""),
        )

    def _rebuild_suggestion_models(self) -> None:
        filter_id = self._podcast_category_filter
        is_fixed_category = (
            filter_id not in {"", "all"}
            and any(c.get("id", "") == filter_id for c in self._suggestion_categories)
        )
        podcast_raw = [
            item
            for item in self._all_suggestions
            if str(item.get("content_type") or "") == "podcast"
            and (
                filter_id in {"", "all"}
                or (
                    is_fixed_category
                    and filter_id in (item.get("tags") or [])
                )
                or (
                    not is_fixed_category
                    and filter_id in (item.get("categories") or [])
                )
            )
        ]
        podcast_raw.sort(key=self._suggestion_sort_key)
        podcast_items = [self._suggestion_to_model(item) for item in podcast_raw]
        video_items = [
            self._suggestion_to_model(item)
            for item in self._all_suggestions
            if str(item.get("content_type") or "") == "video"
        ]
        shorts_items = [
            self._suggestion_to_model(item)
            for item in self._all_suggestions
            if str(item.get("content_type") or "") == "shorts"
        ]
        self._podcast_suggestions_model.set_items(podcast_items)
        self._video_suggestions_model.set_items(video_items)
        self._shorts_suggestions_model.set_items(shorts_items)
        if self._podcast_playlist_id:
            self._refresh_podcast_playlist_model()

    def _refresh_podcast_playlist_model(self) -> None:
        category_id = self._podcast_playlist_id
        if not category_id:
            self._podcast_playlist_model.set_items([])
            return
        rows = [
            item
            for item in self._all_suggestions
            if str(item.get("content_type") or "") == "podcast"
            and category_id in (item.get("categories") or [])
        ]
        rows.sort(key=self._suggestion_sort_key)
        model_rows = [self._suggestion_to_model(item) for item in rows]
        self._podcast_playlist_model.set_items(model_rows)
        if model_rows:
            self._podcast_playlist_image = str(model_rows[0].get("image") or "")
            label = str(model_rows[0].get("category_label") or "").strip()
            if label:
                self._podcast_playlist_title = label

    # ── Podcast playlist slots ───────────────────────────────────────────

    @pyqtSlot(str)
    def openPodcastPlaylist(self, category_id: str) -> None:
        cid = (category_id or "").strip().lower()
        if not cid:
            return
        rows = [
            item
            for item in self._all_suggestions
            if str(item.get("content_type") or "") == "podcast"
            and cid in (item.get("categories") or [])
        ]
        if not rows:
            return
        rows.sort(key=self._suggestion_sort_key)
        label = str(rows[0].get("category_label") or cid).strip() or cid
        self._podcast_playlist_id = cid
        self._podcast_playlist_title = label
        self._podcast_playlist_image = str(rows[0].get("local_thumbnail") or rows[0].get("thumbnail_url") or "")
        self._refresh_podcast_playlist_model()
        self.libraryNavigationChanged.emit()

    @pyqtSlot()
    def closePodcastPlaylist(self) -> None:
        self._podcast_playlist_id = ""
        self._podcast_playlist_title = ""
        self._podcast_playlist_image = ""
        self._podcast_playlist_model.set_items([])
        self.libraryNavigationChanged.emit()

    def _set_podcast_playlist_ai_loading(self, loading: bool) -> None:
        self._podcast_playlist_ai_loading = loading
        self.podcastPlaylistAiSortLoadingChanged.emit()

    @pyqtSlot()
    def requestAiPodcastPlaylistSort(self) -> None:
        asyncio.create_task(self._request_ai_podcast_playlist_sort())

    async def _request_ai_podcast_playlist_sort(self) -> None:
        category_id = self._podcast_playlist_id
        if not category_id:
            self.podcastPlaylistAiSortError.emit("Mở danh sách phát để dùng AI sắp xếp.")
            return
        rows = [
            dict(item)
            for item in self._all_suggestions
            if str(item.get("content_type") or "") == "podcast"
            and category_id in (item.get("categories") or [])
        ]
        if len(rows) < 2:
            self.podcastPlaylistAiSortError.emit("Cần ít nhất 2 tập để sắp xếp.")
            return
        title = self._podcast_playlist_title or category_id
        self._set_podcast_playlist_ai_loading(True)
        try:
            from src import share_manager

            sorted_rows = await share_manager.ai_sort_podcast_playlist(
                playlist_title=title,
                rows=rows,
            )
            await share_manager.persist_podcast_playlist_order(sorted_rows)
            by_id = {str(r.get("id") or ""): r for r in sorted_rows}
            for item in self._all_suggestions:
                sid = str(item.get("id") or "")
                updated = by_id.get(sid)
                if not updated:
                    continue
                item["sort_order"] = int(updated.get("sort_order") or 0)
                item["season"] = int(updated.get("season") or 1)
                item["episode"] = int(updated.get("episode") or 0)
                if updated.get("title"):
                    item["title"] = str(updated.get("title") or item.get("title") or "")
            try:
                suggestions_manager._write_local_file(
                    {
                        "items": self._all_suggestions,
                        "categories": suggestions_manager.get_cached_categories(),
                        "sections": suggestions_manager.get_cached_sections(),
                    }
                )
            except Exception:
                logger.debug("Could not write local suggestions cache after playlist sort")
            self._rebuild_suggestion_models()
            self.podcastPlaylistAiSortFinished.emit()
            self.suggestionsChanged.emit()
            self.libraryNavigationChanged.emit()
        except ValueError as exc:
            self.podcastPlaylistAiSortError.emit(str(exc))
        except Exception:
            logger.exception("AI podcast playlist sort failed")
            self.podcastPlaylistAiSortError.emit("AI sắp xếp thất bại.")
        finally:
            self._set_podcast_playlist_ai_loading(False)

    @pyqtSlot(int)
    def downloadPodcastPlaylistEpisode(self, index: int) -> None:
        """Watch now: download in background then auto-play."""
        item = self._podcast_playlist_model.item_at(index)
        if item is None:
            return
        path = str(item.get("path") or "").strip()
        if item.get("download_status") == "done" and path and Path(path).exists():
            self._play_podcast_suggestion_item(item)
            return
        suggestion_id = str(item.get("suggestion_id") or item.get("track_id") or "")
        if suggestion_id:
            self._watch_now_pending.add(suggestion_id)
        self._download_suggestion_at(self._podcast_playlist_model, index)

    @pyqtSlot(int)
    def playPodcastPlaylistEpisode(self, index: int) -> None:
        item = self._podcast_playlist_model.item_at(index)
        if item is None:
            return
        path = str(item.get("path") or "").strip()
        if path and Path(path).exists():
            self._play_podcast_suggestion_item(item)
            return
        self.downloadPodcastPlaylistEpisode(index)

    @pyqtSlot(str)
    def setPodcastCategoryFilter(self, category_id: str) -> None:
        value = (category_id or "all").strip().lower() or "all"
        if value == self._podcast_category_filter:
            return
        self._podcast_category_filter = value
        self._rebuild_suggestion_models()
        self.podcastCategoryFilterChanged.emit()

    @pyqtSlot(int)
    def downloadPodcastSuggestion(self, index: int) -> None:
        """Watch now: download in background then auto-play."""
        item = self._podcast_suggestions_model.item_at(index)
        if item is None:
            return
        path = str(item.get("path") or "").strip()
        if item.get("download_status") == "done" and path and Path(path).exists():
            self._play_podcast_suggestion_item(item)
            return
        # Mark as watch-now so we auto-play on completion
        suggestion_id = str(item.get("suggestion_id") or item.get("track_id") or "")
        if suggestion_id:
            self._watch_now_pending.add(suggestion_id)
        self._download_suggestion_at(self._podcast_suggestions_model, index)

    @pyqtSlot(int)
    def playPodcastSuggestion(self, index: int) -> None:
        item = self._podcast_suggestions_model.item_at(index)
        if item is None:
            return
        path = str(item.get("path") or "").strip()
        if path and Path(path).exists():
            self._play_podcast_suggestion_item(item)
            return
        self.downloadPodcastSuggestion(index)

    def _play_podcast_suggestion_item(self, item: dict) -> None:
        path = str(item.get("path") or "").strip()
        if not path or not Path(path).exists():
            return
        play_item = {
            **item,
            "path": path,
            "is_remote": False,
            "audio_only": bool(item.get("audio_only", True)),
            "url": path,
        }
        self._is_podcast_media = True
        self.podcastPlaybackSpeedChanged.emit()
        self._set_playback_queue([play_item])
        self._play_item(play_item)

    @pyqtSlot(int)
    def downloadVideoSuggestion(self, index: int) -> None:
        self._download_suggestion_at(self._video_suggestions_model, index)

    @pyqtSlot(int)
    def downloadShortsSuggestion(self, index: int) -> None:
        self._download_suggestion_at(self._shorts_suggestions_model, index)

    def _download_suggestion_at(self, model, index: int) -> None:
        item = model.item_at(index)
        if item is None:
            return
        path = str(item.get("path") or "").strip()
        if item.get("download_status") == "done" and path and Path(path).exists():
            return
        source_url = str(item.get("url") or item.get("source_url") or "").strip()
        if not source_url:
            self.downloadError.emit("", "Đề xuất thiếu link tải.")
            return
        suggestion_id = str(item.get("suggestion_id") or item.get("track_id") or "")
        media_kind = str(item.get("media_kind") or "audio").lower()
        content_type = str(item.get("content_type") or "").lower()
        if content_type == "podcast":
            kind = "podcast" if media_kind == "audio" else "podcast_video"
        else:
            kind = "music" if media_kind == "audio" else "video"
        item["is_downloading"] = True
        item["download_status"] = "downloading"
        item["download_percent"] = 0.0
        model.update_download_state(
            str(item.get("track_id") or ""),
            percent=0.0,
            status="downloading",
            is_downloading=True,
        )
        if suggestion_id:
            suggestions_manager.persist_download_state(
                suggestion_id,
                status="downloading",
                percent=0.0,
                is_downloading=True,
            )
            for raw in self._all_suggestions:
                if str(raw.get("id") or "") == suggestion_id:
                    raw["download_status"] = "downloading"
                    raw["download_percent"] = 0.0
                    raw["is_downloading"] = True
                    break
        self.downloadMedia(source_url, kind, "")

    def _find_suggestion_by_key(self, key: str) -> dict | None:
        needle = (key or "").strip()
        if not needle:
            return None
        for item in self._all_suggestions:
            if str(item.get("id") or "") == needle:
                return item
            source_url = str(item.get("source_url") or "").strip()
            if source_url == needle:
                return item
            yt_id = extract_youtube_id(source_url) if source_url else ""
            if yt_id and yt_id == needle:
                return item
        return None

    def _patch_suggestion_download(
        self,
        key: str,
        *,
        percent: float | None = None,
        status: str | None = None,
        is_downloading: bool | None = None,
    ) -> None:
        item = self._find_suggestion_by_key(key)
        if item is None:
            return
        if percent is not None:
            item["download_percent"] = float(percent)
        if status is not None:
            item["download_status"] = status
        if is_downloading is not None:
            item["is_downloading"] = bool(is_downloading)
        suggestion_id = str(item.get("id") or "")
        if suggestion_id:
            suggestions_manager.persist_download_state(
                suggestion_id,
                status=item.get("download_status"),
                percent=item.get("download_percent"),
                is_downloading=item.get("is_downloading"),
            )
        track_id = suggestion_id
        for model in (
            self._podcast_suggestions_model,
            self._video_suggestions_model,
            self._shorts_suggestions_model,
            self._podcast_playlist_model,
            self._podcast_category_detail_model,
            self._podcast_episode_model,
        ):
            model.update_download_state(
                track_id,
                percent=item.get("download_percent"),
                status=item.get("download_status"),
                is_downloading=item.get("is_downloading"),
            )
        if hasattr(self, "suggestionsChanged"):
            self.suggestionsChanged.emit()

    def _on_suggestion_download_started(self, key: str) -> None:
        self._patch_suggestion_download(key, status="downloading", is_downloading=True)

    def _on_suggestion_download_progress(self, key: str, percent: float) -> None:
        self._patch_suggestion_download(key, percent=percent, status="downloading", is_downloading=True)

    def _on_suggestion_download_finished(self, key: str, file_path: str) -> None:
        item = self._find_suggestion_by_key(key)
        path = str(file_path or "").strip()
        suggestion_id = ""
        if item is not None and path and Path(path).exists():
            content_type = str(item.get("content_type") or "").lower()
            suggestion_id = str(item.get("id") or "")
            if content_type == "podcast":
                try:
                    item_categories = item.get("categories") or []
                    first_category = item_categories[0] if item_categories else ""
                    item_category_labels = item.get("category_labels") or []
                    first_category_label = item_category_labels[0] if item_category_labels else ""
                    podcast_library.register_download(
                        suggestion_id=suggestion_id,
                        title=str(item.get("title") or ""),
                        author=str(item.get("author") or ""),
                        path=path,
                        media_kind=str(item.get("media_kind") or "audio"),
                        category=first_category,
                        category_label=first_category_label,
                        thumbnail=str(item.get("local_thumbnail") or item.get("thumbnail_url") or ""),
                        source_url=str(item.get("source_url") or ""),
                        description=str(item.get("description") or ""),
                        last_played_at=datetime.now(timezone.utc).isoformat(),
                        play_count=1,
                    )
                except ValueError as exc:
                    logger.warning("Podcast library register failed: %s", exc)
            item["local_path"] = path
            suggestions_manager.persist_download_state(
                suggestion_id,
                status="done",
                percent=100.0,
                is_downloading=False,
                local_path=path,
            )
        self._patch_suggestion_download(key, percent=100.0, status="done", is_downloading=False)
        self._rebuild_suggestion_models()
        self._refresh_podcast_downloaded_from_library()

        # Auto-play if this was a watch-now request
        sid = suggestion_id or key
        if sid in self._watch_now_pending:
            self._watch_now_pending.discard(sid)
            if item is not None and path and Path(path).exists():
                play_item = {
                    **item,
                    "path": path,
                    "local_path": path,
                    "is_remote": False,
                    "audio_only": bool(item.get("audio_only", True)),
                    "url": path,
                    "download_status": "done",
                    "download_percent": 100.0,
                    "is_downloading": False,
                }
                self._is_podcast_media = True
                self.podcastPlaybackSpeedChanged.emit()
                self._set_playback_queue([play_item])
                self._play_item(play_item)
                # Schedule cleanup: track this file for later deletion
                self._track_watch_now_file(path, sid)

    def _on_suggestion_download_error(self, key: str, _message: str) -> None:
        self._patch_suggestion_download(key, status="error", is_downloading=False)

    def _refresh_podcast_downloaded_from_library(self) -> None:
        """Fill podcastDownloadedModel from watched podcast history (cached metadata)."""
        dl_items: list[dict] = []
        for idx, entry in enumerate(podcast_library.list_watched()):
            path = str(entry.get("path") or "")
            media_kind = str(entry.get("media_kind") or "audio")
            has_file = bool(path) and Path(path).exists()
            dl_items.append({
                "title": str(entry.get("title") or Path(path).stem if path else ""),
                "subtitle": str(entry.get("author") or entry.get("category_label") or "Podcast"),
                "artist": str(entry.get("author") or ""),
                "image": str(entry.get("thumbnail") or ""),
                "path": path if has_file else "",
                "canonical_path": str(entry.get("suggestion_id") or path),
                "url": path if has_file else str(entry.get("source_url") or ""),
                "track_id": str(entry.get("suggestion_id") or path),
                "duration": "",
                "accent": ACCENT_COLORS[idx % len(ACCENT_COLORS)],
                "audio_only": media_kind != "video",
                "is_remote": not has_file,
                "is_collection": False,
                "kind": "podcast",
                "child_count": 0,
                "preview_images": [],
                "download_percent": 100.0 if has_file else 0.0,
                "download_status": "done" if has_file else "watched",
                "is_downloading": False,
                "watched_percent": _compute_watched_percent(path) if has_file else 0.0,
                "suggestion_id": str(entry.get("suggestion_id") or ""),
                "media_kind": media_kind,
                "content_type": "podcast",
                "source_url": str(entry.get("source_url") or ""),
                "last_played_at": str(entry.get("last_played_at") or ""),
            })
        self._podcast_downloaded_model.set_items(dl_items)

    def _load_podcasts(self) -> None:
        """Load podcast suggestion downloads and refresh UI."""
        self._refresh_podcast_downloaded_from_library()


    @pyqtSlot(float)
    def setPodcastPlaybackSpeed(self, speed: float) -> None:
        speed = max(0.5, min(4.0, speed))
        if speed == self._podcast_playback_speed:
            return
        self._podcast_playback_speed = speed
        self._player.set_speed(speed)
        self.podcastPlaybackSpeedChanged.emit()

    @pyqtSlot(float)
    def seekPodcastRelative(self, seconds: float) -> None:
        self._player.seek_relative(seconds)

    def _reset_podcast_media_state(self) -> None:
        if self._is_podcast_media:
            self._is_podcast_media = False
            self._podcast_playback_speed = 1.0
            self._player.set_speed(1.0)
            self.podcastPlaybackSpeedChanged.emit()

    # ── Watch-now cleanup ─────────────────────────────────────────────────

    _WATCH_CLEANUP_DELAY = 1800  # 30 minutes

    def _track_watch_now_file(self, file_path: str, suggestion_id: str) -> None:
        """Track a watch-now file for deferred cleanup after playback ends."""
        self._cancel_watch_cleanup(suggestion_id)
        task = asyncio.create_task(self._watch_cleanup_timer(file_path, suggestion_id))
        self._watch_now_cleanup_tasks[suggestion_id] = task

    def _cancel_watch_cleanup(self, suggestion_id: str) -> None:
        task = self._watch_now_cleanup_tasks.pop(suggestion_id, None)
        if task and not task.done():
            task.cancel()

    async def _watch_cleanup_timer(self, file_path: str, suggestion_id: str) -> None:
        """Wait for playback to end + delay, then delete the cached file."""
        try:
            # Wait until current podcast playback ends
            while self._is_podcast_media and self._player.state.status in (PlaybackStatus.PLAYING, PlaybackStatus.PAUSED):
                await asyncio.sleep(5)
            # Additional delay after playback ends
            await asyncio.sleep(self._WATCH_CLEANUP_DELAY)
            # Don't delete if it's currently being played again
            current_path = (self._player.state.path or "").strip()
            if current_path and Path(current_path).resolve() == Path(file_path).resolve():
                return
            podcast_library.remove_file_keep_metadata(suggestion_id)
            self._refresh_podcast_downloaded_from_library()
            self._rebuild_suggestion_models()
        except asyncio.CancelledError:
            pass
        finally:
            self._watch_now_cleanup_tasks.pop(suggestion_id, None)
