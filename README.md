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
- **GUI**: Sử dụng chuột để điều hướng qua các tab Nhạc, Video, Playlist và Settings.
- **TUI**: Sử dụng phím mũi tên để chọn, và nhấn `q` để thoát ứng dụng.
