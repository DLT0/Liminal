# Liminal

Trình phát đa phương tiện nội bộ (Local media player) dành cho Linux. Giao diện đồ họa hiện đại xây dựng bằng **PyQt6** và **QML**, sử dụng `mpv` làm engine phát nhạc/video.

## Yêu cầu hệ thống

- **Python** 3.10+
- **mpv** — engine phát nhạc và video
- **ffmpeg** — cần thiết cho tính năng tải nhạc (chuyển đổi sang MP3)

Cài đặt trên Fedora:
```bash
sudo dnf install mpv ffmpeg
```

Cài đặt trên Ubuntu/Debian:
```bash
sudo apt install mpv ffmpeg
```

## Cài đặt

```bash
git clone https://github.com/hmduongdl/Liminal.git
cd Liminal
pip install -r requirements.txt
```

Nếu cần, tạo môi trường ảo trước:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Chạy ứng dụng

```bash
python3 app_qt.py
```

Giao diện desktop với sidebar điều hướng, thanh trình phát, hỗ trợ duyệt nhạc/video trong thư mục máy và tải từ YouTube.

### Tìm kiếm và tải từ YouTube

Trang **Download** dùng `yt-dlp` để tìm kiếm và tải media từ YouTube. Có hai chế độ:

- **Tìm kiếm** — nhập từ khóa, chọn kết quả để tải
- **Dán link** — dán trực tiếp URL YouTube cần tải

Người dùng chọn đầu ra **Nhạc** (MP3) hoặc **Video** (MP4). Với video, có thể chọn chất lượng (480p, 720p, 1080p, 2K, 4K, Max) trước khi tải.

File tải về được lưu vào thư mục Music hoặc Videos đã cấu hình trong Settings.

Kiểm tra nhanh yt-dlp và ffmpeg:
```bash
python3 -c "import yt_dlp; print(yt_dlp.version.__version__)"
ffmpeg -version
```

## Cấu trúc thư mục

```text
Liminal/
├── app_qt.py                 # File chạy chính (PyQt6 + QML)
├── requirements.txt          # Thư viện phụ thuộc Python
├── README.md
└── src/
    ├── config.py             # Cấu hình định dạng file hỗ trợ
    ├── downloader.py         # Tải media từ YouTube (yt-dlp)
    ├── models.py             # Model dữ liệu MediaInfo, PlaybackStatus
    ├── player.py             # Lớp bọc MPV, giao tiếp JSON IPC
    ├── scanner.py            # Quét file media trong thư mục
    ├── settings_store.py     # Lưu/cài đặt cấu hình
    ├── metadata_store.py     # Metadata và ảnh bìa tuỳ chỉnh
    ├── mpris_service.py      # Tích hợp MPRIS (Linux desktop)
    ├── folder_order.py       # Thứ tự hiển thị trong thư mục
    ├── qml/                  # Giao diện QML
    │   ├── main.qml          # Layout chính
    │   ├── components/       # Các thành phần giao diện
    │   └── Liminal/          # Theme
    └── qt/                   # Backend Python ↔ QML
        ├── qml_app.py        # Khởi tạo QML engine
        ├── qml_backend.py    # AppBackend — cầu nối dữ liệu
        └── intro_splash.py   # Màn hình giới thiệu
```

## Tính năng chính

- **Duyệt thư viện** — Music (album/đĩa đơn), Videos, Playlist với giao diện lưới trực quan
- **Phát nhạc/video** — Sử dụng mpv, hỗ trợ nhiều định dạng (MP3, FLAC, OGG, MP4, MKV...)
- **Tải từ YouTube** — Tìm kiếm và tải nhạc/video trực tiếp trong ứng dụng
- **Quản lý thư viện** — Tạo thư mục, sắp xếp, đổi ảnh bìa, chỉnh sửa metadata
- **Đa chủ đề** — Nhiều bảng màu để lựa chọn trong Settings
- **Tích hợp MPRIS** — Điều khiển phát nhạc qua phím media và desktop environment

## Định dạng hỗ trợ

**Âm thanh:** `.mp3`, `.flac`, `.ogg`, `.wav`, `.m4a`, `.opus`, `.aac`
**Video:** `.mp4`, `.mkv`, `.avi`, `.mov`, `.webm`, `.m4v`, `.ts`, `.wmv`

## Cấu hình

Cấu hình lưu tại `~/.config/liminal/settings.json`. Chọn thư mục gốc trong Settings, Liminal sẽ tự tạo các thư mục con `Music/`, `Videos/`, `Playlist/`.

- **Music** — chứa file nhạc và album (thư mục con)
- **Videos** — chứa file video và playlist (thư mục con)
- **Playlist** — thư mục playlist chung
