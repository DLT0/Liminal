# Liminal

Trình phát đa phương tiện cục bộ (local media player) cho Linux. Giao diện desktop hiện đại xây dựng bằng **PyQt6** và **QML**, dùng **mpv** làm engine phát nhạc/video.

## Tính năng

- **Thư viện cục bộ** — Duyệt nhạc (album/đĩa đơn), video và playlist theo lưới trực quan
- **Phát nhạc & video** — Hỗ trợ nhiều định dạng qua mpv (MP3, FLAC, OGG, MP4, MKV…)
- **Tải từ YouTube** — Tìm kiếm hoặc dán link, xuất MP3 hoặc MP4 với tuỳ chọn chất lượng
- **Waveform seek bar** — Thanh tiến trình dạng waveform (kiểu SoundCloud), click để seek
- **Quản lý thư viện** — Tạo thư mục, sắp xếp, đổi ảnh bìa, chỉnh metadata
- **Đa chủ đề** — Nhiều bảng màu trong Settings
- **MPRIS** — Điều khiển phát nhạc qua phím media và desktop environment

## Yêu cầu hệ thống

| Thành phần | Phiên bản / ghi chú |
|---|---|
| Python | 3.10+ |
| mpv | Engine phát nhạc và video |
| ffmpeg | Chuyển đổi audio, phân tích waveform, tải media |
| PipeWire / PulseAudio | Khuyến nghị cho tích hợp desktop (MPRIS, audio) |

**Fedora:**
```bash
sudo dnf install mpv ffmpeg portaudio
```

**Ubuntu / Debian:**
```bash
sudo apt install mpv ffmpeg portaudio19-dev
```

## Cài đặt

```bash
git clone https://github.com/hmduongdl/Liminal.git
cd Liminal
pip install -r requirements.txt
```

Khuyến nghị dùng virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Chạy ứng dụng

```bash
python3 app_qt.py
```

Hoặc qua launcher script (chỉ cho phép một instance mỗi session):

```bash
./scripts/run-liminal.sh
```

### Thêm shortcut trên desktop

File `liminal.desktop.in` là template — không chứa đường dẫn cố định. Sau khi clone, chạy:

```bash
./scripts/install-desktop.sh
```

Script sẽ tạo `~/.local/share/applications/liminal.desktop` với đường dẫn đúng theo vị trí clone trên máy bạn.

## Tải media từ YouTube

Trang **Download** dùng `yt-dlp` với hai chế độ:

- **Tìm kiếm** — Nhập từ khoá, chọn kết quả để tải
- **Dán link** — Dán trực tiếp URL YouTube

Tuỳ chọn đầu ra:

- **Nhạc** — MP3
- **Video** — MP4 (480p, 720p, 1080p, 2K, 4K, Max)

File tải về lưu vào thư mục Music hoặc Videos đã cấu hình trong Settings.

Kiểm tra nhanh:
```bash
python3 -c "import yt_dlp; print(yt_dlp.version.__version__)"
ffmpeg -version
```

## Waveform seek bar

Khi bật **Show Visualizer** trong Settings, thanh tiến trình được thay bằng waveform tương tác (`SoundCloudWaveform`):

1. Khi phát một bài nhạc, `waveform_analyzer.py` dùng **ffmpeg** decode file và tính ~150 bin amplitude
2. Kết quả được cache tại `~/.config/liminal/waveforms/`
3. QML vẽ waveform với màu theo vị trí phát và hỗ trợ hover/seek

Tắt visualizer sẽ quay lại slider tiến trình thông thường.

## Cấu hình

Cấu hình lưu tại `~/.config/liminal/settings.json`.

Chọn **Media Root** trong Settings — Liminal tự tạo các thư mục con:

| Thư mục | Nội dung |
|---|---|
| `Music/` | File nhạc và album (thư mục con) |
| `Videos/` | File video và playlist (thư mục con) |
| `Playlist/` | Playlist chung |

## Định dạng hỗ trợ

**Âm thanh:** `.mp3` `.flac` `.ogg` `.wav` `.m4a` `.opus` `.aac`

**Video:** `.mp4` `.mkv` `.avi` `.mov` `.webm` `.m4v` `.ts` `.wmv`

## Cấu trúc dự án

```text
Liminal/
├── app_qt.py                 # Entry point — PyQt6 + QML
├── app.py                    # Entry point — Textual TUI (tuỳ chọn)
├── requirements.txt
├── liminal.desktop.in        # Template desktop entry
├── scripts/
│   ├── run-liminal.sh        # Launcher (single instance)
│   └── install-desktop.sh    # Cài shortcut vào ~/.local/share/applications/
└── src/
    ├── player.py             # MPV wrapper, JSON IPC
    ├── downloader.py         # Tải media từ YouTube (yt-dlp)
    ├── scanner.py            # Quét file media
    ├── waveform_analyzer.py  # Phân tích waveform offline (ffmpeg)
    ├── audio_visualizer.py   # FFT realtime từ PipeWire monitor
    ├── settings_store.py     # Cấu hình người dùng
    ├── metadata_store.py     # Metadata và ảnh bìa tuỳ chỉnh
    ├── mpris_service.py        # Tích hợp MPRIS
    ├── qml/
    │   ├── main.qml
    │   ├── components/       # PlayerBar, Download, LibraryPage, SoundCloudWaveform…
    │   └── Liminal/          # Theme singleton
    └── qt/
        ├── qml_app.py        # Khởi tạo QML engine
        ├── qml_backend.py    # AppBackend — cầu nối Python ↔ QML
        └── intro_splash.py   # Màn hình intro
```

## Giao diện TUI (tuỳ chọn)

Liminal còn có phiên bản terminal dùng Textual:

```bash
python3 app.py
```

## Giấy phép

[MIT](LICENSE) — Copyright (c) 2026 Nguyễn Phước Lộc
