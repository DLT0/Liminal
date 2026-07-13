# Liminal

Trình phát đa phương tiện cục bộ (local media player) cho Linux. Giao diện desktop hiện đại xây dựng bằng **PyQt6** và **QML**. Video phát trực tiếp trong cửa sổ ứng dụng qua **Qt Multimedia + FFmpeg**; mpv được dùng cho phần phát nhạc.

## Tính năng

- **Thư viện cục bộ** — Duyệt nhạc (album/đĩa đơn), video và playlist theo lưới trực quan
- **Phát nhạc & video** — Nhạc qua mpv; video MP4, MKV… phát ngay trong app bằng Qt Multimedia
- **Tải từ YouTube** — Tìm kiếm hoặc dán link, xuất MP3 hoặc MP4 với tuỳ chọn chất lượng
- **Waveform seek bar** — Thanh tiến trình dạng waveform (kiểu SoundCloud), click để seek
- **Quản lý thư viện** — Tạo thư mục, sắp xếp, đổi ảnh bìa, chỉnh metadata
- **Tuỳ chỉnh giao diện** — Chỉnh màu, sidebar, search, player bar qua `settings.json` (key `liminal.*` kiểu VS Code)
- **MPRIS** — Điều khiển phát nhạc qua phím media và desktop environment

## Yêu cầu hệ thống

| Thành phần | Phiên bản / ghi chú |
|---|---|
| Python | 3.10+ |
| mpv | Engine phát nhạc |
| Qt Multimedia | Bề mặt phát video trong QML |
| FFmpeg | Backend video, chuyển đổi audio, phân tích waveform, tải media |
| PipeWire / PulseAudio | Khuyến nghị cho tích hợp desktop (MPRIS, audio) |

**Fedora:**
```bash
sudo dnf install mpv portaudio qt6-qtmultimedia
```

Nếu dùng RPM Fusion để có FFmpeg đầy đủ, cài thêm gói `ffmpeg` theo hướng dẫn của RPM Fusion. Bản Fedora thông thường vẫn cần `qt6-qtmultimedia` để QML import được `QtMultimedia`.

**Arch Linux:**
```bash
sudo pacman -S mpv ffmpeg portaudio qt6-declarative qt6-multimedia qt6-multimedia-ffmpeg
```

**Ubuntu / Linux Mint:**
```bash
sudo add-apt-repository universe
sudo apt update
sudo apt install mpv ffmpeg portaudio19-dev libqt6multimedia6 qml6-module-qtmultimedia
```

Liminal dùng module Qt có cùng runtime với PyQt6. Nếu bạn cài PyQt6 bằng `pip` mà gặp `module \"QtMultimedia\" is not installed`, ưu tiên cài PyQt6 từ package manager của distro hoặc tạo lại virtual environment sau khi đã cài các gói Qt Multimedia ở trên.

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

Một file duy nhất cho **cấu hình người dùng**: `~/.config/liminal/settings.json` (giống VS Code — chỉ ghi key cần thay đổi).

Trạng thái phiên phát (bài đang nghe, vị trí seek, v.v.) lưu riêng tại `state.json` — app tự quản lý, không cần chỉnh tay.

| Nhóm key | Ví dụ |
|---|---|
| Ứng dụng | `media_root`, `volume`, `download_quality` |
| Giao diện | `liminal.sidebar.width`, `liminal.colorCustomizations.accent` |
| Layout | `liminal.layout.gridColumns`, `liminal.playerBar.alwaysVisible` |

Chọn **Media Root** trong Settings — Liminal tự tạo các thư mục con:

| Thư mục | Nội dung |
|---|---|
| `Music/` | File nhạc và album (thư mục con) |
| `Videos/` | File video và playlist (thư mục con) |

### Tuỳ chỉnh giao diện (kiểu VS Code)

Chỉ cần thêm key muốn override — phần còn lại giữ mặc định:

```json
{
  "liminal.colorCustomizations": {
    "accent": "#e91e63",
    "bgElevated": "#0f0f0f"
  },
  "liminal.sidebar.width": 260,
  "liminal.playerBar.alwaysVisible": true,
  "liminal.window.customTitleBar": false
}
```

Hoặc dùng key dạng chấm:

```json
{
  "liminal.colorCustomizations.accent": "#22c55e",
  "liminal.search.placeholder": "Tìm bài hát…"
}
```

Hoặc nhóm trong object `liminal`:

```json
{
  "liminal": {
    "sidebar": { "width": 240 },
    "colorCustomizations": { "accent": "#3b82f6" }
  }
}
```

Xem `settings.json.example` trong repo. Khởi động lại app sau khi sửa. Trong Settings, bấm **Mở thư mục** để mở nhanh `~/.config/liminal/`.

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
    ├── settings_store.py     # settings.json — app + user overrides
    ├── ui_config.py            # Resolve liminal.* UI keys for QML
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
