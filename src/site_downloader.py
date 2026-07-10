"""Download all videos from a Google Sites page.

Scans every subpage, expands all sections, extracts YouTube video IDs,
and downloads them organized by page name.

Usage:
    python -m src.site_downloader
"""

from __future__ import annotations

import asyncio
import logging
import re
import subprocess
from pathlib import Path

from playwright.async_api import async_playwright

from src.config import VIDEO_DIR

logger = logging.getLogger(__name__)

BASE_URL = "https://sites.google.com/view/whoviansvietnam"
RE_YT = re.compile(r'(?:youtube\.com/embed/|youtube\.com/watch\?v=|youtu\.be/|youtube\.com/v/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})')
RE_YT_META = re.compile(r'"videoId"\s*[=:]\s*"([a-zA-Z0-9_-]{11})"')
RE_YT_PARAM = re.compile(r'[?&]v=([a-zA-Z0-9_-]{11})')


def _find_yt_ids(text: str) -> set[str]:
    ids: set[str] = set()
    for pat in (RE_YT, RE_YT_META, RE_YT_PARAM):
        for m in pat.finditer(text):
            ids.add(m.group(1))
    return ids


async def expand_all(page) -> None:
    """Click every clickable element to trigger lazy content."""
    for _ in range(3):
        await page.evaluate("""
            () => {
                document.querySelectorAll('[jsaction], [role=\"button\"], button, summary, .hDrhEe, [tabindex=\"0\"]').forEach(el => {
                    try { el.click(); } catch(e) {}
                });
            }
        """)
        await asyncio.sleep(0.5)


async def process_page(browser, path: str) -> set[str]:
    """Render a page and extract all YouTube video IDs."""
    url = f"{BASE_URL}/{path}"
    page = await browser.new_page()
    page.set_default_timeout(30000)
    ids: set[str] = set()

    try:
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(3)
        await expand_all(page)
        await asyncio.sleep(2)

        # Get full page content after expansion
        html = await page.content()
        ids.update(_find_yt_ids(html))

        # Search in all element attributes
        attrs = await page.evaluate("""
            () => {
                const found = [];
                document.querySelectorAll('*').forEach(el => {
                    for (const attr of el.attributes || []) {
                        if (attr.value) found.push(attr.value);
                    }
                    if (el.shadowRoot) {
                        el.shadowRoot.querySelectorAll('*').forEach(sh => {
                            for (const attr of sh.attributes || []) {
                                if (attr.value) found.push(attr.value);
                            }
                        });
                    }
                });
                return found.join('\\n');
            }
        """)
        ids.update(_find_yt_ids(attrs))
    except Exception as e:
        logger.warning("  %s: %s", path, e)
    finally:
        await page.close()

    return ids


async def download_video(video_id: str, subdir: str, index: int, total: int) -> bool:
    """Download a YouTube video into a subdirectory."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    out = VIDEO_DIR / subdir
    out.mkdir(parents=True, exist_ok=True)

    print(f"  [{index}/{total}] {video_id}...", end=" ", flush=True)
    cmd = [
        "yt-dlp",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "-o", str(out / "%(title)s.%(ext)s"),
        "--no-warnings",
        "--ignore-errors",
        url,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        err = stderr.decode()[:150] if stderr else "?"
        print(f"FAILED: {err}")
        return False
    print("OK")
    return True


async def main_async() -> None:
    logging.basicConfig(level=logging.WARNING)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)

        # Step 1: discover subpages
        print("Scanning site structure...")
        root = await browser.new_page()
        await root.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        slugs: set[str] = set()
        links = await root.evaluate("""
            () => Array.from(document.querySelectorAll('a[href*=\"whoviansvietnam\"]'))
                .map(a => a.getAttribute('href'))
                .filter(h => h && !h.includes('#'))
                .map(h => h.replace(/\\/$/, '').split('/').pop())
                .filter(s => s && s !== 'trang-ch%E1%BB%A7' && !s.startsWith('http'))
        """)
        slugs.update(links)
        await root.close()

        all_slugs = sorted(slugs)
        print(f"Found {len(all_slugs)} page(s) to scan")
        if not all_slugs:
            all_slugs = ["trang-ch%E1%BB%A7", "doctor-who-2005", "doctor-who-classic",
                         "t%E1%BA%ADp-%C4%91%E1%BA%B7c-bi%E1%BB%87t", "t%E1%BA%ADp-phim-kh%C3%A1c",
                         "torchwood", "the-sarah-jane-adventures", "class", "game-doctor-who"]

        # Step 2: extract video IDs per page
        page_videos: dict[str, set[str]] = {}
        all_ids: set[str] = set()

        for slug in all_slugs:
            print(f"  Scanning {slug}...", end=" ", flush=True)
            ids = await process_page(browser, slug)
            page_videos[slug] = ids
            all_ids.update(ids)
            print(f"{len(ids)} video(s)")

        await browser.close()

    total = len(all_ids)
    if total == 0:
        print("\nNo videos found. The site may use dynamically loaded embeds.")
        print("Consider providing YouTube playlist links or channel URLs instead.")
        return

    # Step 3: download
    print(f"\nDownloading {total} unique video(s) to {VIDEO_DIR}")
    idx = 0
    for slug in sorted(page_videos):
        for vid in sorted(page_videos[slug]):
            idx += 1
            await download_video(vid, slug, idx, total)

    print(f"\nDone! {total} video(s) downloaded.")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
