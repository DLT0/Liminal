"""Podcast feed manager: RSS/Atom parsing, subscription storage, episode tracking."""

from __future__ import annotations

import json
import logging
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import feedparser
except ImportError:  # Optional — podcast page is suggestion-first (YouTube).
    feedparser = None  # type: ignore[assignment]

from src.settings_store import CONFIG_DIR

import threading

logger = logging.getLogger(__name__)

PODCASTS_FILE = CONFIG_DIR / "podcasts.json"
_podcasts_lock = threading.RLock()


@dataclass
class PodcastEpisode:
    title: str
    description: str = ""
    audio_url: str = ""
    duration: str = "--:--"
    duration_seconds: float = 0.0
    publish_date: str = ""
    guid: str = ""
    image_url: str = ""
    downloaded_path: str = ""
    listened_position: float = 0.0
    play_count: int = 0
    last_played_at: str = ""


@dataclass
class PodcastFeed:
    url: str
    title: str = ""
    author: str = ""
    description: str = ""
    image_url: str = ""
    episodes: list[PodcastEpisode] = field(default_factory=list)


def _load_podcasts_data() -> dict:
    with _podcasts_lock:
        if not PODCASTS_FILE.exists():
            return {"feeds": []}
        try:
            data = json.loads(PODCASTS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "feeds" in data:
                return data
        except (OSError, json.JSONDecodeError):
            pass
        return {"feeds": []}


def _save_podcasts_data(data: dict) -> None:
    with _podcasts_lock:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        temp_file = PODCASTS_FILE.with_suffix(".tmp")
        temp_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temp_file.replace(PODCASTS_FILE)


def _episode_to_dict(ep: PodcastEpisode) -> dict:
    return {
        "title": ep.title,
        "description": ep.description,
        "audio_url": ep.audio_url,
        "duration": ep.duration,
        "duration_seconds": ep.duration_seconds,
        "publish_date": ep.publish_date,
        "guid": ep.guid,
        "image_url": ep.image_url,
        "downloaded_path": ep.downloaded_path,
        "listened_position": ep.listened_position,
        "play_count": ep.play_count,
        "last_played_at": ep.last_played_at,
    }


def _episode_from_dict(data: dict) -> PodcastEpisode:
    return PodcastEpisode(
        title=str(data.get("title", "")),
        description=str(data.get("description", "")),
        audio_url=str(data.get("audio_url", "")),
        duration=str(data.get("duration", "--:--")),
        duration_seconds=float(data.get("duration_seconds", 0.0)),
        publish_date=str(data.get("publish_date", "")),
        guid=str(data.get("guid", "")),
        image_url=str(data.get("image_url", "")),
        downloaded_path=str(data.get("downloaded_path", "")),
        listened_position=float(data.get("listened_position", 0.0)),
        play_count=int(data.get("play_count") or 0),
        last_played_at=str(data.get("last_played_at", "")),
    )



def _feed_to_dict(feed: PodcastFeed) -> dict:
    return {
        "url": feed.url,
        "title": feed.title,
        "author": feed.author,
        "description": feed.description,
        "image_url": feed.image_url,
        "episodes": [_episode_to_dict(ep) for ep in feed.episodes],
    }


def _feed_from_dict(data: dict) -> PodcastFeed:
    episodes = [_episode_from_dict(ep) for ep in data.get("episodes", [])]
    return PodcastFeed(
        url=str(data.get("url", "")),
        title=str(data.get("title", "")),
        author=str(data.get("author", "")),
        description=str(data.get("description", "")),
        image_url=str(data.get("image_url", "")),
        episodes=episodes,
    )


def _format_duration(seconds: float) -> str:
    if seconds <= 0:
        return "--:--"
    total = int(seconds)
    h, m, s = total // 3600, (total % 3600) // 60, total % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _parse_date(date_str: str) -> str:
    """Try to parse a date string into ISO format."""
    if not date_str:
        return ""
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(date_str)
        return dt.isoformat()
    except (ValueError, TypeError):
        pass
    return date_str


def parse_rss_feed(url: str) -> PodcastFeed | None:
    """Fetch and parse an RSS/Atom feed URL into a PodcastFeed."""
    if feedparser is None:
        logger.warning("feedparser not installed; RSS subscribe disabled")
        return None
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Liminal/1.0 Podcast Reader"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
    except Exception as exc:
        logger.warning("Failed to fetch feed %s: %s", url, exc)
        return None

    try:
        parsed = feedparser.parse(content)
    except Exception as exc:
        logger.warning("Failed to parse feed %s: %s", url, exc)
        return None

    if parsed.bozo and not parsed.entries:
        logger.warning("Feed %s is malformed: %s", url, parsed.bozo_exception)
        return None

    feed_info = parsed.feed
    title = feed_info.get("title", url)
    author = feed_info.get("author", "") or feed_info.get("publisher", "")
    description = feed_info.get("subtitle", "") or feed_info.get("description", "")
    image = feed_info.get("image", {}).get("href", "") if isinstance(feed_info.get("image"), dict) else ""
    if not image:
        image = feed_info.get("logo", "") or feed_info.get("icon", "")

    episodes: list[PodcastEpisode] = []
    for entry in parsed.entries:
        audio_url = ""
        duration_seconds = 0.0
        for link in entry.get("links", []):
            if link.get("rel", "") == "enclosure" or link.get("type", "").startswith("audio/"):
                audio_url = link.get("href", "")
                duration_seconds = float(link.get("length", 0)) or 0.0
                break
        if not audio_url:
            # Try alternate audio link detection
            for link in entry.get("links", []):
                href = link.get("href", "")
                if href and any(href.endswith(ext) for ext in (".mp3", ".m4a", ".ogg", ".opus")):
                    audio_url = href
                    break

        if not audio_url:
            continue

        ep_duration = _format_duration(duration_seconds)
        ep_image = ""
        if "image" in entry and isinstance(entry.image, dict):
            ep_image = entry.image.get("href", "")
        if not ep_image and "media_content" in entry:
            for media in entry.media_content:
                if media.get("type", "").startswith("image/"):
                    ep_image = media.get("url", "")
                    break

        episodes.append(PodcastEpisode(
            title=entry.get("title", "Untitled"),
            description=entry.get("summary", "") or entry.get("description", ""),
            audio_url=audio_url,
            duration=ep_duration,
            duration_seconds=duration_seconds,
            publish_date=_parse_date(entry.get("published", "")),
            guid=entry.get("id", audio_url),
            image_url=ep_image or image,
        ))

    return PodcastFeed(
        url=url,
        title=title.strip(),
        author=author.strip(),
        description=description.strip(),
        image_url=image,
        episodes=episodes,
    )


def subscribe(url: str) -> PodcastFeed | None:
    """Add a feed to subscriptions and return parsed data."""
    feed = parse_rss_feed(url)
    if feed is None:
        return None

    data = _load_podcasts_data()
    existing_urls = {f.get("url", "") for f in data["feeds"]}
    if url in existing_urls:
        # Update existing feed
        for i, f in enumerate(data["feeds"]):
            if f.get("url") == url:
                data["feeds"][i] = _feed_to_dict(feed)
                break
    else:
        data["feeds"].append(_feed_to_dict(feed))

    _save_podcasts_data(data)
    return feed


def unsubscribe(url: str) -> None:
    """Remove a feed from subscriptions."""
    data = _load_podcasts_data()
    data["feeds"] = [f for f in data["feeds"] if f.get("url") != url]
    _save_podcasts_data(data)


def load_subscriptions() -> list[PodcastFeed]:
    """Load all subscribed feeds from storage."""
    data = _load_podcasts_data()
    return [_feed_from_dict(f) for f in data.get("feeds", [])]


def refresh_feed(url: str) -> PodcastFeed | None:
    """Re-fetch a feed and merge new episodes with existing ones, preserving download/listen state."""
    fresh = parse_rss_feed(url)
    if fresh is None:
        return None

    data = _load_podcasts_data()
    old_state: dict[str, dict] = {}
    for f in data["feeds"]:
        if f.get("url") == url:
            for ep in f.get("episodes", []):
                guid = ep.get("guid", "")
                if guid:
                    old_state[guid] = {
                        "downloaded_path": ep.get("downloaded_path", ""),
                        "listened_position": ep.get("listened_position", 0.0),
                        "play_count": ep.get("play_count", 0),
                        "last_played_at": ep.get("last_played_at", ""),
                    }
            break

    merged_episodes: list[dict] = []
    for ep in fresh.episodes:
        ep_dict = _episode_to_dict(ep)
        guid = ep_dict["guid"]
        if guid and guid in old_state:
            state = old_state[guid]
            ep_dict["downloaded_path"] = state["downloaded_path"]
            ep_dict["listened_position"] = state["listened_position"]
            ep_dict["play_count"] = state["play_count"]
            ep_dict["last_played_at"] = state["last_played_at"]
        merged_episodes.append(ep_dict)

    for f in data["feeds"]:
        if f.get("url") == url:
            f["episodes"] = merged_episodes
            # Also update feed-level metadata from fresh parse
            fresh_dict = _feed_to_dict(fresh)
            for key in ("title", "author", "description", "image_url"):
                if fresh_dict.get(key):
                    f[key] = fresh_dict[key]
            _save_podcasts_data(data)
            feed = _feed_from_dict(f)
            return feed

    return subscribe(url)


def refresh_all_feeds() -> list[PodcastFeed]:
    """Refresh all subscribed feeds."""
    feeds = load_subscriptions()
    refreshed: list[PodcastFeed] = []
    for feed in feeds:
        result = refresh_feed(feed.url)
        if result is not None:
            refreshed.append(result)
        else:
            refreshed.append(feed)
    return refreshed


def get_all_episodes() -> list[tuple[PodcastFeed, PodcastEpisode]]:
    """Return all episodes from all feeds, sorted by publish date (newest first)."""
    feeds = load_subscriptions()
    results: list[tuple[PodcastFeed, PodcastEpisode]] = []
    for feed in feeds:
        for ep in feed.episodes:
            results.append((feed, ep))
    results.sort(key=lambda x: x[1].publish_date or "", reverse=True)
    return results


def get_downloaded_episodes() -> list[tuple[PodcastFeed, PodcastEpisode]]:
    """Return episodes with downloaded local files."""
    feeds = load_subscriptions()
    results: list[tuple[PodcastFeed, PodcastEpisode]] = []
    for feed in feeds:
        for ep in feed.episodes:
            if ep.downloaded_path and Path(ep.downloaded_path).exists():
                results.append((feed, ep))
    return results


def download_episode(feed_url: str, guid: str, podcasts_dir: Path, downloader, progress_hook=None) -> str | None:
    """Download a podcast episode using the shared Downloader (same mechanism as Suggestions).

    Args:
        feed_url: RSS feed URL the episode belongs to.
        guid: Unique episode identifier.
        podcasts_dir: Directory where podcast files are stored.
        downloader: Downloader instance (from downloader.py).
        progress_hook: Optional callable(dict) for yt-dlp progress updates.

    Returns:
        Path to the downloaded file, or None on failure / no audio_url.
    """
    import asyncio

    data = _load_podcasts_data()
    target_ep: dict | None = None
    for f in data["feeds"]:
        if f.get("url") == feed_url:
            for ep in f.get("episodes", []):
                if ep.get("guid") == guid:
                    target_ep = ep
                    break
            break

    if target_ep is None:
        logger.warning("Episode not found: feed=%s guid=%s", feed_url, guid)
        return None

    existing_path = str(target_ep.get("downloaded_path", ""))
    if existing_path and Path(existing_path).exists():
        return existing_path

    audio_url = str(target_ep.get("audio_url", ""))
    if not audio_url:
        logger.warning("No audio_url for episode guid=%s", guid)
        return None

    try:
        loop = asyncio.new_event_loop()
        try:
            _video_id, file_path = loop.run_until_complete(
                downloader.download(
                    audio_url,
                    "podcast",
                    progress_hook or (lambda d: None),
                )
            )
        finally:
            loop.close()

        if file_path and Path(file_path).exists():
            target_ep["downloaded_path"] = file_path
            _save_podcasts_data(data)
            return file_path
    except Exception:
        logger.exception("Download episode failed: feed=%s guid=%s", feed_url, guid)

    return None


def verify_local_episodes() -> None:
    """Scan all subscribed episodes and clear downloaded_path if the local file is missing."""
    data = _load_podcasts_data()
    modified = False
    for f in data.get("feeds", []):
        for ep in f.get("episodes", []):
            path = str(ep.get("downloaded_path", "")).strip()
            if path and not Path(path).exists():
                ep["downloaded_path"] = ""
                modified = True
    if modified:
        _save_podcasts_data(data)


def update_episode_download(feed_url: str, guid: str, downloaded_path: str) -> bool:
    """Mark an episode as downloaded."""
    data = _load_podcasts_data()
    for f in data["feeds"]:
        if f.get("url") == feed_url:
            for ep in f.get("episodes", []):
                if ep.get("guid") == guid:
                    ep["downloaded_path"] = downloaded_path
                    _save_podcasts_data(data)
                    return True
    return False


def update_episode_progress(guid: str, position: float, duration: float) -> None:
    """Save listened position and duration for an episode by guid."""
    data = _load_podcasts_data()
    updated = False
    for f in data.get("feeds", []):
        for ep in f.get("episodes", []):
            if ep.get("guid") == guid:
                ep["listened_position"] = position
                if duration > 0.0:
                    ep["duration_seconds"] = duration
                updated = True
    if updated:
        _save_podcasts_data(data)


def increment_play_count(guid: str) -> None:
    """Increment play count and update last_played_at for an RSS episode."""
    data = _load_podcasts_data()
    updated = False
    for f in data.get("feeds", []):
        for ep in f.get("episodes", []):
            if ep.get("guid") == guid:
                ep["play_count"] = int(ep.get("play_count") or 0) + 1
                from datetime import datetime, timezone
                ep["last_played_at"] = datetime.now(timezone.utc).isoformat()
                updated = True
    if updated:
        _save_podcasts_data(data)

