# Liminal

Trình phát đa phương tiện cục bộ cho Linux. Giao diện desktop xây dựng bằng **PyQt6** và **QML** — nhạc phát qua **mpv**, video phát trong app bằng **Qt Multimedia** hoặc **mpv** tùy cấu hình.

## Tính năng

- **Thư viện cục bộ** — Duyệt nhạc (album, đĩa đơn, playlist), video và series theo lưới trực quan
- **Phát nhạc & video** — Nhạc qua mpv; video trong Focus Mode bằng Qt Multimedia hoặc cửa sổ mpv riêng
- **Focus Mode** — Xem phim toàn màn hình với điều khiển tập, phụ đề SRT và thanh tiến trình
- **Tải media** — Tìm kiếm YouTube, dán link (YouTube, Google Drive, playlist) qua `yt-dlp`
- **Chia sẻ** — Tạo mã chia sẻ playlist, đĩa đơn hoặc series; nhập mã từ bạn bè để xem/nghe
- **Series** — Tự nhận diện mùa/tập từ tên file, sắp xếp thứ tự tập, chia sẻ cả series
- **Quản lý thư viện** — Tạo thư mục, sắp xếp, đổi ảnh bìa, chỉnh metadata
- **Tuỳ chỉnh giao diện** — Màu sắc, sidebar, layout qua `settings.json` (key `liminal.*` kiểu VS Code)
- **MPRIS** — Điều khiển phát nhạc bằng phím media và tích hợp desktop (tuỳ chọn)
- **System tray** — Thu nhỏ xuống khay hệ thống, chỉ một instance mỗi phiên

> **Đang phát triển:** Podcast, Book

## Yêu cầu hệ thống

| Thành phần | Ghi chú |
|---|---|
| Python | 3.10+ |
| mpv | Engine phát nhạc; tuỳ chọn cho video |
| FFmpeg | Tải/chuyển đổi media, xử lý thumbnail |
| Qt6 Multimedia | Phát video trong QML (`qml6-module-qtmultimedia`) |
| PipeWire / PulseAudio | Khuyến nghị cho audio desktop |

## Cài đặt nhanh (Tự động)

Hỗ trợ các bản phân phối Fedora, Ubuntu/Debian/Mint, và Arch Linux. Lệnh này sẽ tự động cài các gói hệ thống cần thiết (mpv, ffmpeg, Qt6 Multimedia, MPRIS), tạo môi trường ảo Python và tạo shortcut desktop:

```bash
git clone https://github.com/hmduongdl/Liminal.git
cd Liminal
./setup.sh
```

---

## Cài đặt thủ công

Nếu bạn muốn kiểm soát từng bước cài đặt:

### 1. Gói hệ thống theo distro

<details>
<summary><b>Fedora</b></summary>

```bash
sudo dnf install mpv ffmpeg qt6-qtmultimedia
```
*(Nếu dùng RPM Fusion, hãy cài `ffmpeg` theo hướng dẫn của RPM Fusion)*
</details>

<details>
<summary><b>Arch Linux</b></summary>

```bash
sudo pacman -S mpv ffmpeg qt6-multimedia
```
</details>

<details>
<summary><b>Ubuntu / Linux Mint</b></summary>

```bash
sudo add-apt-repository universe
sudo apt update
sudo apt install mpv ffmpeg libqt6multimedia6 qml6-module-qtmultimedia
```
</details>

### 2. Thiết lập môi trường ảo và dependencies

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt
./scripts/install-desktop.sh
```

*(Sử dụng `--system-site-packages` để ứng dụng nhận diện và sử dụng gói `dbus`/`gobject` hệ thống cho tính năng phím Media/MPRIS).*

## Chạy ứng dụng

```bash
python3 app_qt.py
```

Hoặc qua launcher (một instance mỗi phiên):

```bash
./scripts/run-liminal.sh
```

### Shortcut trên desktop

```bash
./scripts/install-desktop.sh
```

Script tạo `~/.local/share/applications/liminal.desktop` với đường dẫn đúng theo vị trí clone trên máy bạn.

## Tải media

Trang **Download** hỗ trợ hai chế độ:

| Chế độ | Mô tả |
|---|---|
| **Tìm kiếm** | Nhập từ khoá, chọn kết quả để tải |
| **Dán link** | Dán URL YouTube, Google Drive hoặc playlist |

Đầu ra:

- **Nhạc** — MP3
- **Video** — MP4 (480p, 720p, 1080p, 2K, 4K, Max)

File tải về lưu vào thư mục Music hoặc Videos trong Settings. YouTube có thể dùng cookie trình duyệt hoặc OAuth — cấu hình trong `settings.json` (`youtube_auth_mode`, `youtube_browser`, …).

Kiểm tra nhanh:

```bash
python3 -c "import yt_dlp; print(yt_dlp.version.__version__)"
ffmpeg -version
```

Trong Settings, bấm **Cập nhật yt-dlp** khi tải xuống gặp lỗi do YouTube thay đổi.

## Chia sẻ media

Liminal hỗ trợ chia sẻ playlist nhạc, đĩa đơn và series phim qua **mã ngắn**:

1. Chọn nội dung trong thư viện → **Chia sẻ** → nhận mã
2. Bạn bè vào **Videos** hoặc **Music** → **Nhập mã** → xem/nghe
3. Series chia sẻ sẽ tự tải 3 tập đầu; các tập còn lại tải khi phát

Chỉ hỗ trợ link **YouTube** và **Google Drive**. File tải qua trang Download sẽ lưu `source_url` để chia sẻ sau này.

## Focus Mode & phụ đề

Khi mở video, Liminal chuyển sang **Focus Mode** — giao diện xem phim toàn màn hình với:

- Danh sách tập (series)
- Phụ đề SRT/VTT đặt cạnh file video (`.srt`, `.vtt`)
- Điều khiển âm lượng video độc lập với nhạc

Trong **Settings → Trình phát video**, chọn:

- **Trong ứng dụng (Qt Multimedia)** — mặc định
- **mpv (cửa sổ riêng)** — hữu ích khi codec Qt Multimedia không phát được

## Cấu hình

Cấu hình người dùng: `~/.config/liminal/settings.json` — chỉ ghi key cần thay đổi, giống VS Code.

Trạng thái phiên phát (bài đang nghe, vị trí seek, …) lưu riêng tại `state.json`.

| Nhóm key | Ví dụ |
|---|---|
| Ứng dụng | `media_root`, `volume`, `download_quality`, `video_playback_backend` |
| YouTube | `youtube_auth_mode`, `youtube_browser`, `youtube_cookies_file` |
| Giao diện | `liminal.sidebar.width`, `liminal.colorCustomizations.accent` |
| Layout | `liminal.layout.gridColumns`, `liminal.playerBar.alwaysVisible` |

Chọn **Media Root** trong Settings — Liminal tự tạo:

| Thư mục | Nội dung |
|---|---|
| `Music/` | Nhạc, album, playlist |
| `Videos/` | Video, series, playlist |
| `Books/` | Dành cho tính năng sách (sắp ra mắt) |

### Tuỳ chỉnh giao diện

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

Key dạng chấm cũng được hỗ trợ:

```json
{
  "liminal.colorCustomizations.accent": "#22c55e",
  "liminal.search.placeholder": "Tìm bài hát…"
}
```

Xem `settings.json.example` để biết đầy đủ các key. Khởi động lại app sau khi sửa.

## Định dạng hỗ trợ

**Âm thanh:** `.mp3` `.flac` `.ogg` `.wav` `.m4a` `.opus` `.aac`

**Video:** `.mp4` `.mkv` `.avi` `.mov` `.webm` `.m4v` `.ts` `.wmv`

**Phụ đề:** `.srt` `.vtt`

**Sách (sắp ra mắt):** `.pdf` `.epub` `.mobi` `.azw3` `.fb2` `.djvu` `.cbr` `.cbz`

## Cấu trúc dự án

```text
Liminal/
├── app_qt.py                    # Entry point — PyQt6 + QML
├── app.py                       # Entry point — Textual TUI (tuỳ chọn)
├── requirements.txt             # Cài đặt đầy đủ (có MPRIS)
├── requirements-minimal.txt     # Cài đặt không MPRIS
├── settings.json.example
├── liminal.desktop.in
├── scripts/
│   ├── run-liminal.sh           # Launcher (single instance)
│   └── install-desktop.sh       # Cài desktop shortcut
└── src/
    ├── player.py                # MPV wrapper, JSON IPC
    ├── downloader.py            # Tải media (yt-dlp, Google Drive)
    ├── google_drive.py          # Tải file/folder Google Drive
    ├── scanner.py               # Quét file media
    ├── share_manager.py         # API chia sẻ & cache
    ├── series_layout.py         # Nhận diện mùa/tập series
    ├── playlist_layout.py       # Sắp xếp playlist nhạc
    ├── metadata_store.py        # Metadata & ảnh bìa
    ├── settings_store.py        # settings.json
    ├── state_store.py           # state.json — phiên phát
    ├── ui_config.py             # Resolve key liminal.* cho QML
    ├── mpris_service.py         # Tích hợp MPRIS (tuỳ chọn)
    ├── config.py                # Extension, browser cookies, mpv
    ├── qml/
    │   ├── main.qml
    │   ├── components/          # PlayerBar, Download, FocusModeScreen…
    │   └── Liminal/             # Theme singleton
    └── qt/
        ├── qml_app.py           # Khởi tạo QML engine
        ├── qml_backend.py       # AppBackend — Python ↔ QML
        ├── share_bridge.py      # Bridge chia sẻ cho QML
        ├── mpv_video_bridge.py  # Video mpv trong QML
        └── intro_splash.py      # Màn hình intro
```

## Giao diện TUI (tuỳ chọn)

Phiên bản terminal dùng Textual (đã có trong `requirements.txt`):

```bash
python3 app.py
```

## Giấy phép

[MIT](LICENSE) — Copyright (c) 2026
