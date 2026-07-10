# Liminal

Trình phát đa phương tiện nội bộ (Local media player) dành cho người dùng Linux. Hỗ trợ cả giao diện đồ họa (PyQt6) và giao diện dòng lệnh (Textual TUI). Sử dụng `mpv` làm công cụ xử lý phát nhạc/video ở hậu cảnh.

## 📂 Cấu trúc thư mục

```text
Liminal/
├── app.py                    # File chạy chế độ TUI (Textual)
├── app_qt.py                 # File chạy chế độ GUI (PyQt6)
├── README.md                 # Tài liệu hướng dẫn
├── LICENSE                   # Thông tin giấy phép
└── src/                      # Mã nguồn chính
    ├── config.py             # Quản lý cấu hình
    ├── downloader.py         # Xử lý tải đa phương tiện
    ├── models.py             # Các model dữ liệu
    ├── player.py             # Lớp bọc MPV và điều khiển phát nhạc/video
    ├── scanner.py            # Quét file media trên máy
    ├── site_downloader.py    # Logic tải file cụ thể cho từng trang web
    ├── css/                  # Định dạng giao diện (Textual CSS)
    │   ├── main.css
    │   ├── music.css
    │   └── video.css
    ├── screens/              # Các màn hình giao diện (Textual UI)
    │   ├── main_screen.py
    │   ├── music_screen.py
    │   ├── playlist_screen.py
    │   ├── settings_screen.py
    │   └── video_screen.py
    └── qt/                   # Giao diện PyQt6
        ├── __init__.py
        ├── styles.py         # QSS dark theme
        ├── main_window.py    # Cửa sổ chính + sidebar + now-playing bar
        ├── home_widget.py    # Màn hình chào
        ├── music_widget.py   # Trình duyệt nhạc (Spotify-style)
        ├── video_widget.py   # Trình duyệt video
        ├── playlist_widget.py
        └── settings_widget.py
```

## 🚀 Hướng dẫn cách chạy

Liminal hỗ trợ hai chế độ giao diện:

### 🖥️ GUI (PyQt6) — Khuyến nghị

```bash
# Cài đặt thư viện
pip install PyQt6 qasync

# Chạy ứng dụng
python3 app_qt.py
```

Giao diện cửa sổ desktop với sidebar điều hướng, now-playing bar, slider kéo thả, và dark theme.

### ⌨️ TUI (Textual) — Terminal

```bash
# Cài đặt textual
pip install textual

# Chạy ứng dụng
python3 app.py
```

Giao diện văn bản trong terminal dành cho người dùng thích làm việc trên CLI.

### 🎮 Điều khiển
- Nhấn `q` để thoát ứng dụng.
- Sử dụng chuột hoặc bàn phím để điều hướng các thành phần trên giao diện.
