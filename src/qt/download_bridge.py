"""Download queue, worker, and job execution mixin for AppBackend."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, replace
from pathlib import Path

from PyQt6.QtCore import pyqtSlot

from src.downloader import Download403Failed, DownloadCancelled, DownloadFailed, _normalize_video_quality
from src.metadata_store import canonical_source_url, find_video_subtitle_paths, set_metadata

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DownloadJob:
    url: str
    media_type: str
    output_subdir: str
    quality: str = "1080"
    retry_403: bool = False
    source: str = "download_page"  # download_page | shared | suggestion | rss_podcast
    rss_feed_url: str = ""  # Only for rss_podcast source
    rss_guid: str = ""       # Only for rss_podcast source
    dispatch_target: str = "general" # shared | suggestion | general
    owner_model: object = None
    owner_key: str = ""


_LARGE_BATCH_THRESHOLD = 30
_GOOD_NETWORK_BPS = 512 * 1024  # 512 KB/s
_MAX_CONCURRENT_DOWNLOADS = 2


class DownloadMixin:
    """Download queue/worker methods mixed into AppBackend (accesses self as AppBackend at runtime)."""

    # ── Public download slots ────────────────────────────────────────────

    @pyqtSlot(str, str, str)
    def downloadMedia(self, url: str, kind: str, output_subdir: str = "") -> None:
        """Enqueue an audio/video/podcast download; jobs run one at a time."""
        value = url.strip()
        logger.info("[DEBUG downloadMedia] url=%s kind=%s subdir=%s", value[:120], kind, output_subdir)
        if not value:
            self.downloadError.emit("", "URL hoặc video ID không hợp lệ.")
            return
        raw = kind.strip().lower()
        if raw in {"audio", "music"}:
            media_type = "music"
        elif raw in {"podcast"}:
            media_type = "podcast"
        elif raw in {"podcast_video"}:
            media_type = "podcast_video"
        elif raw in {"video"}:
            media_type = "video"
        else:
            media_type = raw
        if media_type not in {"music", "video", "podcast", "podcast_video"}:
            self.downloadError.emit(value, "Loại media không được hỗ trợ.")
            return
        subdir = output_subdir.strip()
        self._enqueue_download(DownloadJob(value, media_type, subdir, self._download_quality))

    @pyqtSlot(str, str, result=bool)
    def removeQueuedDownload(self, url: str, media_kind: str) -> bool:
        """Remove a job that is still waiting in the download queue."""
        value = str(url or "").strip()
        kind = "music" if str(media_kind or "").strip() in {"music", "audio"} else "video"
        if not value:
            return False

        removed: list[DownloadJob] = []
        queue = self._download_queue
        if queue is not None:
            queued_jobs = list(queue._queue)
            kept_jobs = [
                job
                for job in queued_jobs
                if not (job.url == value and job.media_type == kind)
            ]
            removed.extend(
                job for job in queued_jobs
                if job.url == value and job.media_type == kind
            )
            if removed:
                queue._queue.clear()
                queue._queue.extend(kept_jobs)

        deferred = [
            job for job in self._deferred_403_jobs
            if job.url == value and job.media_type == kind
        ]
        if deferred:
            removed.extend(deferred)
            self._deferred_403_jobs = [
                job for job in self._deferred_403_jobs
                if not (job.url == value and job.media_type == kind)
            ]

        if not removed:
            return False

        for job in removed:
            if job.media_type not in {"music", "podcast"}:
                self._pending_video_downloads = max(0, self._pending_video_downloads - 1)
            self._untrack_download_subdir(job.media_type, job.output_subdir)
        self._refresh_download_concurrency()
        return True

    @pyqtSlot()
    def cancelCurrentDownloads(self) -> None:
        """Cancel all in-progress downloads and clear the queue."""
        self.downloader.cancel()
        queue = self._download_queue
        if queue is not None:
            while not queue.empty():
                try:
                    job = queue.get_nowait()
                    if job.media_type not in {"music", "podcast"}:
                        self._pending_video_downloads = max(0, self._pending_video_downloads - 1)
                    self._untrack_download_subdir(job.media_type, job.output_subdir)
                    queue.task_done()
                except asyncio.QueueEmpty:
                    break
        deferred = self._deferred_403_jobs
        for job in deferred:
            if job.media_type not in {"music", "podcast"}:
                self._pending_video_downloads = max(0, self._pending_video_downloads - 1)
            self._untrack_download_subdir(job.media_type, job.output_subdir)
        self._deferred_403_jobs.clear()
        self._refresh_download_concurrency()

    @pyqtSlot(str, str)
    def queueLink(self, url: str, media_type: str) -> None:
        """Resolve a link asynchronously and enqueue all items (video or playlist)."""
        asyncio.create_task(self._queue_link(url, media_type))

    async def _queue_link(self, url: str, media_type: str) -> None:
        value = url.strip()
        if not value:
            self.linkQueueError.emit(value, "URL hoặc video ID không hợp lệ.")
            return
        try:
            resolved = await asyncio.wait_for(
                self.downloader.resolve_link(value, media_type),
                timeout=30,
            )
        except TimeoutError:
            self.linkQueueError.emit(value, "Đọc link quá thời gian chờ (30 giây).")
            return
        except DownloadFailed as exc:
            logger.exception("Link queue resolve failed for %r", value)
            self.linkQueueError.emit(value, str(exc))
            return
        items = self._annotate_search_results(list(resolved.get("items") or []), media_type)
        folder = str(resolved.get("playlist_folder") or "").strip()
        downloadable = [item for item in items if not item.get("in_library")]
        if not downloadable:
            self.linkQueueError.emit(value, "Tất cả mục trong link đã có trong thư viện.")
            return
        kind = "music" if media_type == "music" else "video"
        for item in downloadable:
            item_url = str(item.get("url") or item.get("id") or "").strip()
            if item_url:
                self._enqueue_download(DownloadJob(item_url, kind, folder, self._download_quality))
        self.playlistQueued.emit(folder, media_type, downloadable)

    # ── Download queue internals ────────────────────────────────────────

    def _ensure_download_worker(self) -> asyncio.Queue[DownloadJob]:
        if self._download_queue is None:
            self._download_queue = asyncio.Queue()
        if not self._download_worker_started:
            self._download_worker_started = True
            asyncio.create_task(self._download_worker())
        return self._download_queue

    def _enqueue_download(self, job: DownloadJob) -> None:
        queue = self._ensure_download_worker()
        queue.put_nowait(job)
        if job.media_type not in {"music", "podcast"}:
            self._pending_video_downloads += 1
        self._track_download_subdir(job.media_type, job.output_subdir)
        self._start_library_hotload_timer()
        self._refresh_download_concurrency()

    def _download_backlog_size(self) -> int:
        queue = self._download_queue
        pending = queue.qsize() if queue else 0
        return pending + self._download_jobs_in_progress

    def _network_is_good(self) -> bool:
        return self._download_speed_ema >= _GOOD_NETWORK_BPS

    def _download_concurrency_limit(self) -> int:
        if self._download_backlog_size() <= _LARGE_BATCH_THRESHOLD:
            return 1
        if not self._network_is_good():
            return 1
        return _MAX_CONCURRENT_DOWNLOADS

    def _refresh_download_concurrency(self) -> None:
        limit = self._download_concurrency_limit()
        if limit != self._published_download_concurrency:
            self._published_download_concurrency = limit
            self.downloadConcurrencyChanged.emit()

    def _record_download_speed(self, speed_bps: float) -> None:
        if speed_bps <= 0:
            return
        if self._download_speed_ema <= 0:
            self._download_speed_ema = speed_bps
        else:
            self._download_speed_ema = 0.8 * self._download_speed_ema + 0.2 * speed_bps
        self._refresh_download_concurrency()

    # ── Download job execution ─────────────────────────────────────────

    async def _run_download_job(self, job: DownloadJob) -> None:
        logger.info("[DEBUG _run_download_job] START url=%s type=%s quality=%s", job.url[:120], job.media_type, job.quality)
        self._download_jobs_in_progress += 1
        self._refresh_download_concurrency()
        self._start_library_hotload_timer()
        finished = False
        try:
            self.downloadJobStarted.emit(job.url)
            try:
                video_id, file_path = await self._execute_download(
                    job.url,
                    job.media_type,
                    job.output_subdir,
                    job.quality,
                )
            except DownloadCancelled:
                logger.info("Download cancelled for %r", job.url)
                finished = True
                return
            except Download403Failed as exc:
                if job.retry_403:
                    logger.exception("Media download failed on 403 retry for %r", job.url)
                    self.downloadError.emit(job.url, str(exc))
                    finished = True
                else:
                    logger.warning("HTTP 403 for %r, deferring until batch end", job.url)
                    self._deferred_403_jobs.append(job)
                    self.downloadJobRequeued.emit(job.url)
                return
            except DownloadFailed as exc:
                logger.exception("Media download failed for %r", job.url)
                self.downloadError.emit(job.url, str(exc))
                finished = True
                return

            finished = True
            self.downloadFinished.emit(video_id, file_path)
            resolved_path = str(Path(file_path).resolve())
            set_metadata(
                resolved_path,
                source_id=video_id,
                source_url=canonical_source_url(job.url, video_id=video_id),
                subtitle_path=(
                    find_video_subtitle_paths(Path(resolved_path)) or [None]
                )[0],
            )
            if job.media_type in {"music", "podcast"}:
                self._music_source_ids.add(video_id)
            else:
                self._video_source_ids.add(video_id)
            self._hotload_after_download(job, file_path)
        finally:
            self._download_jobs_in_progress -= 1
            if finished and job.media_type not in {"music", "podcast"}:
                self._pending_video_downloads = max(0, self._pending_video_downloads - 1)
            if finished:
                self._untrack_download_subdir(job.media_type, job.output_subdir)
            self._refresh_download_concurrency()

    async def _download_worker(self) -> None:
        queue = self._ensure_download_worker()
        in_flight: set[asyncio.Task[None]] = set()

        async def reap_one() -> None:
            if not in_flight:
                return
            done, _ = await asyncio.wait(in_flight, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                in_flight.discard(task)
                try:
                    await task
                except Exception:
                    logger.exception("Download task failed unexpectedly")

        async def wait_for_slot() -> None:
            while len(in_flight) >= self._download_concurrency_limit():
                await reap_one()

        try:
            while True:
                await wait_for_slot()

                if queue.empty():
                    if in_flight:
                        await reap_one()
                        continue
                    if self._deferred_403_jobs:
                        pending = self._deferred_403_jobs
                        self._deferred_403_jobs = []
                        for deferred in pending:
                            queue.put_nowait(replace(deferred, retry_403=True))
                        self._refresh_download_concurrency()
                        continue
                    self._download_speed_ema = 0.0
                    self._refresh_download_concurrency()
                    self._stop_library_hotload_timer()
                    self.rescanLibrary()
                    job = await queue.get()
                else:
                    job = await queue.get()

                task = asyncio.create_task(self._run_download_job(job))
                in_flight.add(task)

                def _on_task_done(t: asyncio.Task[None]) -> None:
                    in_flight.discard(t)
                    queue.task_done()

                task.add_done_callback(_on_task_done)
        except Exception:
            logger.exception("Download worker crashed, restarting")
            self._download_worker_started = False
            self._download_queue = None
            self._download_jobs_in_progress = 0
            self._deferred_403_jobs.clear()
            self._refresh_download_concurrency()

    async def _execute_download(
        self,
        url: str,
        media_type: str,
        output_subdir: str = "",
        quality: str = "1080",
        source: str = "",
    ) -> tuple[str, str]:
        active_id = url

        def hook(data: dict) -> None:
            nonlocal active_id
            self.downloader._check_cancelled()
            info = data.get("info_dict") or {}
            new_id = str(info.get("id") or "")
            if new_id and new_id != active_id:
                active_id = new_id
                if source and hasattr(self, '_active_download_source'):
                    self._active_download_source[active_id] = source
            if data.get("status") != "downloading":
                return
            downloaded = float(data.get("downloaded_bytes") or 0)
            total = float(data.get("total_bytes") or data.get("total_bytes_estimate") or 0)
            percent = min(100.0, downloaded / total * 100.0) if total else 0.0
            self.downloadProgress.emit(active_id, percent)
            speed = float(data.get("speed") or 0)
            if speed > 0:
                self._record_download_speed(speed)

        if media_type not in {"music", "video", "podcast", "podcast_video"}:
            raise DownloadFailed("Loại media không được hỗ trợ.")
        logger.info("[DEBUG _execute_download] START url=%s type=%s quality=%s", url[:120], media_type, quality)
        return await self.downloader.download(
            url,
            media_type,
            hook,
            output_subdir=output_subdir or None,
            quality=quality,
        )
