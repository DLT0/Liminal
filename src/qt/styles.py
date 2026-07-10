"""Dark-theme QSS stylesheet for Liminal — mirrored from the Textual CSS.

Music accent  #a78bfa (purple)
Video accent  #7eb8f7 (blue)
Background    #0d0d0d
Surface       #0f0f0f / #0a0a0a
"""

STYLESHEET = """
/* ── Global ── */
QMainWindow {
    background: #0d0d0d;
}
QWidget {
    background: #0d0d0d;
    color: #e0e0e0;
    font-family: "Noto Sans", "Segoe UI", sans-serif;
    font-size: 13px;
}

/* ── Sidebar ── */
#sidebar {
    background: #0a0a0a;
    border-right: 1px solid #181818;
    min-width: 180px;
    max-width: 180px;
}
#sidebar QPushButton {
    background: transparent;
    color: #666;
    border: none;
    padding: 10px 16px;
    text-align: left;
    font-size: 14px;
    border-radius: 4px;
    margin: 2px 8px;
}
#sidebar QPushButton:hover {
    color: #ddd;
    background: #111;
}
#sidebar QPushButton:checked {
    color: #fff;
    background: #1a1a1a;
    font-weight: bold;
}
#sidebar #nav-music:checked { color: #a78bfa; }
#sidebar #nav-video:checked { color: #7eb8f7; }
#sidebar #sidebar-spacer {
    background: transparent;
}
#sidebar #track-count-label {
    color: #444;
    padding: 8px 16px;
    font-size: 12px;
    background: transparent;
}

/* ── Home screen ── */
#home-title {
    font-size: 42px;
    font-weight: bold;
    color: #e8e8e8;
}
#home-tagline {
    font-size: 14px;
    color: #333;
    margin-bottom: 32px;
}
#home-btn-video {
    background: #111;
    color: #7eb8f7;
    border: 2px solid #1e3a5f;
    border-radius: 8px;
    padding: 14px 48px;
    font-size: 18px;
    font-weight: bold;
}
#home-btn-video:hover {
    background: #121e2e;
    border-color: #2e5a9f;
    color: #a8d4ff;
}
#home-btn-music {
    background: #111;
    color: #a78bfa;
    border: 2px solid #2d1f5e;
    border-radius: 8px;
    padding: 14px 48px;
    font-size: 18px;
    font-weight: bold;
}
#home-btn-music:hover {
    background: #161224;
    border-color: #5b3fa8;
    color: #c4b0ff;
}
#home-footer {
    color: #2a2a2a;
    font-size: 12px;
    margin-top: 32px;
}

/* ── Content area ── */
#content-header {
    color: #888;
    font-size: 13px;
    font-weight: bold;
    padding: 8px 16px;
    background: #0d0d0d;
    border-bottom: 1px solid #141414;
}

/* ── Search input ── */
QLineEdit {
    background: #1a1a1a;
    border: 1px solid #282828;
    border-radius: 6px;
    color: #ccc;
    padding: 8px 12px;
    font-size: 14px;
    selection-background-color: #a78bfa;
}
QLineEdit:focus {
    border-color: #a78bfa;
    color: #fff;
}

/* ── Track/Video table ── */
QTableWidget {
    background: #0d0d0d;
    border: none;
    gridline-color: #141414;
    selection-background-color: #1a1a2e;
    selection-color: #a78bfa;
    alternate-background-color: #0f0f0f;
}
QTableWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #111;
}
QTableWidget::item:hover {
    background: #141414;
}
QTableWidget::item:selected {
    background: #1a1a2e;
    color: #a78bfa;
}
QHeaderView::section {
    background: #0a0a0a;
    color: #666;
    border: none;
    border-bottom: 1px solid #181818;
    padding: 8px 12px;
    font-size: 12px;
    font-weight: bold;
    text-transform: uppercase;
}

/* ── Now‑playing bar ── */
#nowplaying {
    background: #0f0f0f;
    border-top: 1px solid #1a1a1a;
    min-height: 90px;
    max-height: 90px;
}
#np-title {
    color: #fff;
    font-size: 14px;
    font-weight: bold;
    background: transparent;
}
#np-artist {
    color: #888;
    font-size: 12px;
    background: transparent;
}
#np-controls QPushButton {
    background: transparent;
    color: #888;
    border: none;
    font-size: 18px;
    padding: 4px 8px;
    border-radius: 4px;
}
#np-controls QPushButton:hover {
    color: #fff;
    background: #1a1a1a;
}
#np-controls #btn-play {
    color: #fff;
    font-size: 22px;
}
#np-controls #btn-play:hover {
    background: #222;
}
#np-controls #btn-shuffle[active="true"],
#np-controls #btn-loop[active="true"] {
    color: #a78bfa;
}

/* ── Volume ── */
#vol-icon {
    color: #888;
    font-size: 16px;
    background: transparent;
}

/* ── Sliders (progress + volume) ── */
QSlider::groove:horizontal {
    border: none;
    height: 4px;
    background: #222;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #a78bfa;
    border: none;
    width: 12px;
    height: 12px;
    margin: -4px 0;
    border-radius: 6px;
}
QSlider::handle:horizontal:hover {
    background: #c4b0ff;
}
QSlider::sub-page:horizontal {
    background: #a78bfa;
    border-radius: 2px;
}
QSlider::add-page:horizontal {
    background: #222;
    border-radius: 2px;
}

/* Volume slider shorter */
#vol-slider {
    min-width: 80px;
    max-width: 80px;
}

/* Progress time labels */
.prog-time {
    color: #888;
    font-size: 11px;
    background: transparent;
    min-width: 48px;
}

/* ── Scrollbar ── */
QScrollBar:vertical {
    background: #0d0d0d;
    width: 8px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #333;
    border-radius: 4px;
    min-height: 32px;
}
QScrollBar::handle:vertical:hover {
    background: #555;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

/* ── Settings ── */
#settings-title {
    font-size: 24px;
    font-weight: bold;
    color: #e8e8e8;
    padding: 16px;
}
#settings-section {
    color: #a78bfa;
    font-size: 14px;
    font-weight: bold;
    margin-top: 16px;
}
#settings-value {
    color: #888;
    font-size: 13px;
    padding: 4px 0;
}

/* ── Playlist placeholder ── */
#playlist-msg {
    color: #666;
    font-size: 14px;
}

/* ── StatusBar ── */
QStatusBar {
    background: #0a0a0a;
    color: #555;
    border-top: 1px solid #181818;
    font-size: 11px;
}
"""
