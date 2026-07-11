# Liminal

Trình phát đa phương tiện nội bộ (Local media player) dành cho người dùng Linux. Ứng dụng cung cấp giao diện đồ họa hiện đại được xây dựng bằng **PyQt6** và **QML**, và giao diện dòng lệnh (Textual TUI) cơ bản. Sử dụng `mpv` làm công cụ xử lý phát nhạc/video ở hậu cảnh.

## 📂 Cấu trúc thư mục

```text
Liminal/
├── app.py                    # File chạy chế độ TUI (Textual)
├── app_qt.py                 # File chạy chế độ GUI (PyQt6 + QML)
├── requirements.txt          # Các thư viện phụ thuộc
├── README.md                 # Tài liệu hướng dẫn
├── LICENSE                   # Thông tin giấy phép
└── src/                      # Mã nguồn chính
    ├── config.py             # Quản lý cấu hình
    ├── models.py             # Các model dữ liệu
    ├── player.py             # Lớp bọc MPV và điều khiển phát nhạc/video
    ├── scanner.py            # Quét file media trên máy
    ├── settings_store.py     # Quản lý lưu trữ cài đặt
    ├── qml/                  # Giao diện người dùng đồ họa (QML)
    │   ├── main.qml          # Layout chính
    │   └── components/       # Các thành phần giao diện (MediaPage, SettingsPage, PlayerBar...)
    ├── qt/                   # Backend kết nối giao diện QML và logic Python
    │   ├── qml_app.py        # Khởi tạo QML Engine
    │   └── qml_backend.py    # Lớp cầu nối (AppBackend) phơi bày dữ liệu cho QML
    ├── screens/              # Các màn hình cho giao diện TUI (Textual UI)
    └── css/                  # Định dạng cho giao diện TUI
```

## 🚀 Hướng dẫn cách chạy

Liminal hỗ trợ hai chế độ giao diện:

### 1. Cài đặt thư viện phụ thuộc

Trước tiên, hãy đảm bảo bạn đã cài đặt các thư viện phụ thuộc của Python và các công cụ hệ thống cần thiết.

**1. Công cụ hệ thống (System Dependencies):**
- **`mpv`**: Bắt buộc để phát nhạc và video.
- **`ffmpeg`**: Bắt buộc cho mô-đun tải (yt-dlp) để có thể trích xuất và chuyển đổi âm thanh sang mp3.
*(Ví dụ trên Arch Linux: `sudo pacman -S mpv ffmpeg` hoặc Ubuntu: `sudo apt install mpv ffmpeg`)*

**2. Thư viện Python:**
```bash
pip install -r requirements.txt
```

*(Yêu cầu `PyQt6` cho GUI, `yt-dlp` cho tính năng tải, và `textual` cho TUI. Nếu hệ thống của bạn yêu cầu, hãy tạo môi trường ảo `python3 -m venv .venv` và kích hoạt nó trước).*

#### Tìm kiếm và tải từ YouTube

Trang **Tải xuống** dùng trực tiếp Python API của `yt-dlp` trong worker thread,
do đó không cần cài binary `yt-dlp` riêng. Cài phiên bản được khai báo trong
`requirements.txt` bằng lệnh trên. Có thể kiểm tra nhanh bằng:

```bash
python3 -c "import yt_dlp; print(yt_dlp.version.__version__)"
ffmpeg -version
```

Nếu thiếu `yt-dlp`, ứng dụng vẫn khởi động và sẽ hiển thị hướng dẫn cài đặt khi
tìm kiếm/tải. `ffmpeg` chỉ bắt buộc khi tải nhạc vì yt-dlp cần nó để chuyển đổi
nguồn âm thanh sang MP3. File nhạc và video được lưu vào các thư mục tương ứng
đã cấu hình trong Settings. Nhạc tải từ YouTube dùng tiêu đề làm tên file, được
ghi metadata và nhúng thumbnail. Scanner dùng `mutagen` để đọc title/artist và
trích cover nhúng vào cache `~/.cache/liminal/thumbnails` cho QML hiển thị.
Video tải mới giữ thumbnail JPG cạnh file video. Với video cũ không có ảnh đi
kèm, scanner dùng `ffmpeg` trích một frame đại diện và lưu vào cùng cache trên.
Ngoài tìm kiếm, chế độ **Dán link** nhận URL YouTube trực tiếp và tải bằng cùng
pipeline yt-dlp; người dùng có thể chọn đầu ra Nhạc (MP3) hoặc Video (MP4).

### 2. Chạy ứng dụng

#### 🖥️ GUI (PyQt6 + QML) — Khuyến nghị

```bash
python3 app_qt.py
```

Giao diện cửa sổ desktop với sidebar điều hướng, thanh trình phát hiện đại, hỗ trợ duyệt danh sách nhạc/video có sẵn trong thư mục máy tính của bạn và tuỳ chỉnh dễ dàng trong tab Settings.

#### ⌨️ TUI (Textual) — Terminal

```bash
python3 app.py
```

Giao diện văn bản trong terminal dành cho người dùng thích làm việc qua CLI.

### 🎮 Điều khiển

#### GUI (PyQt6 + QML)

Ngoài chuột, ứng dụng hỗ trợ các phím tắt sau:

| Phím | Hành động |
|------|-----------|
| `Tab` | Chuyển sang tab tiếp theo (Playlist → Music → Videos → Settings) |
| `Shift+Tab` | Chuyển sang tab trước |
| `←` / `→` | Chuyển tab sidebar |
| `Space` | Pause / phát tiếp |
| `Z` | Lùi 10 giây |
| `C` | Tiến 10 giây |
| `Esc` | Thoát ô tìm kiếm; hoặc lùi thư mục playlist; hoặc về tab Playlist |
| `Meta+Q` / `Super+Q` | Thoát ứng dụng |

`Space`, `Z` và `C` không kích hoạt khi đang gõ trong ô tìm kiếm.

#### TUI (Textual)

| Phím | Hành động |
|------|-----------|
| `↑` / `↓` | Chọn bài / video |
| `Enter` | Phát mục đang chọn |
| `Space` | Pause / phát tiếp |
| `←` / `→` | Seek ±5s (nhạc) / ±10s (video) |
| `+` / `=` / `−` | Tăng / giảm âm lượng ±5 |
| `Esc` | Thoát ô tìm kiếm; hoặc quay lại màn hình trước |
| `q` | Thoát ứng dụng |
