"""Ebook reader — text extraction, page rendering, positions, notes.

For PDF: renders each page as an image via PyMuPDF for display in QML.
For EPUB/TXT: splits text into fixed-size pages.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

from src.config import BOOK_EXTS

logger = logging.getLogger(__name__)

POSITIONS_FILE = Path.home() / ".config" / "liminal" / "book_positions.json"
NOTES_FILE = Path.home() / ".config" / "liminal" / "book_notes.json"
PAGE_CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "liminal" / "book_pages"
LINES_PER_PAGE = 40  # for text-based books


def _page_cache_path(book_path: str, page_num: int, zoom: float = 1.0) -> Path:
    key = hashlib.md5(book_path.encode()).hexdigest()
    zoom_suffix = f"_z{int(zoom * 100)}" if zoom != 1.0 else ""
    return PAGE_CACHE_DIR / key / f"page_{page_num:04d}{zoom_suffix}.png"


# ── PDF page rendering ──────────────────────────────────────────

def render_page(path: str, page_num: int, zoom: float = 1.0) -> str | None:
    """Render a single PDF page as a PNG image, return file path or None."""
    try:
        import fitz
    except ImportError:
        return None

    cache_path = _page_cache_path(path, page_num, zoom)
    if cache_path.exists():
        return str(cache_path)

    try:
        doc = fitz.open(path)
        if page_num < 0 or page_num >= len(doc):
            doc.close()
            return None
        page = doc.load_page(page_num)
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(cache_path))
        doc.close()
        return str(cache_path)
    except Exception as e:
        logger.warning("Failed to render page %d: %s", page_num, e)
        return None


def get_page_count(path: str) -> int:
    """Return total page count for a PDF."""
    try:
        import fitz
        doc = fitz.open(path)
        count = len(doc)
        doc.close()
        return count
    except Exception:
        return 0


# ── Text extraction ─────────────────────────────────────────────

def extract_text(path: str) -> dict:
    """Extract text content from an ebook file.

    Returns dict with keys:
      - title: str
      - author: str
      - chapters: list[{"title": str, "content": str}]
      - page_count: int (for PDF, total pages)
      - is_pdf: bool
      - error: str (if any)
    """
    p = Path(path)
    ext = p.suffix.lower()

    try:
        if ext == ".pdf":
            result = _extract_pdf(p)
            result["page_count"] = get_page_count(path)
            result["is_pdf"] = True
            return result
        elif ext == ".epub":
            result = _extract_epub(p)
            result["is_pdf"] = False
            return result
        elif ext == ".txt":
            result = _extract_txt(p)
            result["is_pdf"] = False
            return result
        else:
            return {"title": p.stem, "author": "", "chapters": [], "error": "Unsupported format", "is_pdf": False}
    except Exception as e:
        logger.exception("Failed to extract %s", path)
        return {"title": p.stem, "author": "", "chapters": [], "error": str(e), "is_pdf": False}


def _split_into_pages(text: str, lines_per_page: int = LINES_PER_PAGE) -> list[str]:
    """Split text into fixed-size pages."""
    lines = text.split("\n")
    pages = []
    for i in range(0, len(lines), lines_per_page):
        pages.append("\n".join(lines[i:i + lines_per_page]))
    return pages


def _extract_txt(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    chapters = []
    current: list[str] = []
    title = path.stem

    for line in lines:
        stripped = line.strip()
        if re.match(r'^(chapter|chương|bài|phần)\s+\d+|^#+\s', stripped, re.IGNORECASE):
            if current:
                chapters.append({"title": title, "content": "\n".join(current)})
                current = []
            title = stripped
        current.append(line)

    if current:
        chapters.append({"title": title, "content": "\n".join(current)})
    if not chapters:
        chapters.append({"title": path.stem, "content": text})

    # Split each chapter into pages
    for ch in chapters:
        ch["pages"] = _split_into_pages(ch["content"])

    return {"title": path.stem, "author": "", "chapters": chapters}


def _extract_epub(path: Path) -> dict:
    try:
        import ebooklib
        from ebooklib import epub
    except ImportError:
        return _extract_epub_fallback(path)

    book = epub.read_epub(str(path))
    title = book.get_metadata("DC", "title")[0][0] if book.get_metadata("DC", "title") else path.stem
    author = book.get_metadata("DC", "creator")[0][0] if book.get_metadata("DC", "creator") else ""

    chapters = []
    for item in book.get_items():
        if item.get_type() == 9:
            content = item.get_body_content().decode("utf-8", errors="replace")
            text = re.sub(r'<[^>]+>', ' ', content)
            text = re.sub(r'\s+', ' ', text).strip()
            chapter_title = item.get_name() or path.stem
            if text.strip():
                pages = _split_into_pages(text)
                chapters.append({"title": chapter_title, "content": text, "pages": pages})

    return {"title": title, "author": author, "chapters": chapters or [{"title": path.stem, "content": "(No extractable text)", "pages": []}]}


def _extract_epub_fallback(path: Path) -> dict:
    import zipfile
    text_parts = []
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.endswith((".xhtml", ".html", ".htm", ".xml")):
                raw = z.read(name).decode("utf-8", errors="replace")
                text = re.sub(r'<[^>]+>', ' ', raw)
                text = re.sub(r'\s+', ' ', text).strip()
                if text:
                    text_parts.append(text)
    content = "\n\n".join(text_parts) if text_parts else "(Empty book)"
    pages = _split_into_pages(content)
    return {"title": path.stem, "author": "",
            "chapters": [{"title": path.stem, "content": content, "pages": pages}]}


def _extract_pdf(path: Path) -> dict:
    try:
        import fitz
    except ImportError:
        return {"title": path.stem, "author": "", "chapters": [], "error": "No PDF library available"}

    try:
        doc = fitz.open(str(path))
        title = doc.metadata.get("title", "") or path.stem
        author = doc.metadata.get("author", "") or ""

        chapters = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text()
            chapters.append({
                "title": f"Trang {page_num + 1}",
                "content": text,
                "pages": [text],  # each PDF page = one display page
            })

        doc.close()
        return {"title": title, "author": author, "chapters": chapters or [{"title": path.stem, "content": "(No text)", "pages": []}]}
    except Exception as e:
        return {"title": path.stem, "author": "", "chapters": [], "error": str(e)}


# ── Reading positions ────────────────────────────────────────────

def _ensure_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("{}")


def _load_json(path: Path) -> dict:
    _ensure_file(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_json(path: Path, data: dict) -> None:
    _ensure_file(path)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def get_position(book_path: str) -> dict:
    """Return saved position: {chapter_index, page_index, percent, scroll_y}."""
    data = _load_json(POSITIONS_FILE)
    return data.get(book_path, {"chapter_index": 0, "page_index": 0, "percent": 0.0, "scroll_y": 0})


def save_position(book_path: str, chapter_index: int, page_index: int, percent: float, scroll_y: int = 0) -> None:
    data = _load_json(POSITIONS_FILE)
    data[book_path] = {
        "chapter_index": chapter_index,
        "page_index": page_index,
        "percent": percent,
        "scroll_y": scroll_y,
    }
    _save_json(POSITIONS_FILE, data)


# ── Notes / Highlights ───────────────────────────────────────────

def get_notes(book_path: str) -> list[dict]:
    data = _load_json(NOTES_FILE)
    return data.get(book_path, [])


def add_note(book_path: str, chapter_index: int, page_index: int, text: str, color: str = "#ffeb3b") -> dict:
    import time
    data = _load_json(NOTES_FILE)
    notes = data.get(book_path, [])
    note = {
        "id": f"{int(time.time())}_{len(notes)}",
        "chapter_index": chapter_index,
        "page_index": page_index,
        "text": text,
        "color": color,
        "created_at": time.time(),
    }
    notes.append(note)
    data[book_path] = notes
    _save_json(NOTES_FILE, data)
    return note


def delete_note(book_path: str, note_id: str) -> None:
    data = _load_json(NOTES_FILE)
    notes = data.get(book_path, [])
    data[book_path] = [n for n in notes if n.get("id") != note_id]
    _save_json(NOTES_FILE, data)


def update_note(book_path: str, note_id: str, text: str) -> None:
    data = _load_json(NOTES_FILE)
    notes = data.get(book_path, [])
    for n in notes:
        if n.get("id") == note_id:
            n["text"] = text
    data[book_path] = notes
    _save_json(NOTES_FILE, data)
