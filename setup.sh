#!/usr/bin/env bash
# Unified setup script for Liminal (Fedora, Debian/Ubuntu, Arch Linux)
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0;0m'

echo -e "${GREEN}=== Liminal Auto Setup ===${NC}"

# 1. Detect OS distribution
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    OS_LIKE=${ID_LIKE:-""}
else
    echo -e "${RED}Lỗi: Không thể xác định hệ điều hành.${NC}" >&2
    exit 1
fi

# 2. Map OS to package lists
SYS_PACKAGES=""
PKG_MANAGER=""
INSTALL_CMD=""

case "$OS" in
    fedora|nobara)
        PKG_MANAGER="dnf"
        INSTALL_CMD="sudo dnf install -y"
        SYS_PACKAGES="mpv ffmpeg qt6-qtmultimedia python3-dbus python3-gobject"
        ;;
    ubuntu|debian|pop|linuxmint)
        PKG_MANAGER="apt"
        INSTALL_CMD="sudo apt update && sudo apt install -y"
        SYS_PACKAGES="mpv ffmpeg libqt6multimedia6 qml6-module-qtmultimedia python3-dbus python3-gi"
        ;;
    arch|manjaro|endeavouros)
        PKG_MANAGER="pacman"
        INSTALL_CMD="sudo pacman -S --noconfirm"
        SYS_PACKAGES="mpv ffmpeg qt6-multimedia python-dbus python-gobject"
        ;;
    *)
        # Fallback detection using ID_LIKE
        if [[ "$OS_LIKE" =~ "debian" || "$OS_LIKE" =~ "ubuntu" ]]; then
            PKG_MANAGER="apt"
            INSTALL_CMD="sudo apt update && sudo apt install -y"
            SYS_PACKAGES="mpv ffmpeg libqt6multimedia6 qml6-module-qtmultimedia python3-dbus python3-gi"
        elif [[ "$OS_LIKE" =~ "fedora" || "$OS_LIKE" =~ "rhel" ]]; then
            PKG_MANAGER="dnf"
            INSTALL_CMD="sudo dnf install -y"
            SYS_PACKAGES="mpv ffmpeg qt6-qtmultimedia python3-dbus python3-gobject"
        elif [[ "$OS_LIKE" =~ "arch" ]]; then
            PKG_MANAGER="pacman"
            INSTALL_CMD="sudo pacman -S --noconfirm"
            SYS_PACKAGES="mpv ffmpeg qt6-multimedia python-dbus python-gobject"
        fi
        ;;
esac

# 3. Install system packages
if [ -n "$PKG_MANAGER" ]; then
    echo -e "${YELLOW}Đang cài đặt các gói phụ thuộc hệ thống bằng $PKG_MANAGER...${NC}"
    eval "$INSTALL_CMD $SYS_PACKAGES"
else
    echo -e "${YELLOW}Hệ điều hành chưa hỗ trợ cài đặt tự động. Vui lòng cài đặt thủ công các gói: mpv, ffmpeg, qt6 multimedia, python-dbus, python-gobject.${NC}"
fi

# 4. Set up python virtual environment
echo -e "${YELLOW}Đang tạo môi trường ảo Python (.venv)...${NC}"
python3 -m venv --system-site-packages .venv

# 5. Install Python dependencies
echo -e "${YELLOW}Đang cài đặt các thư viện Python...${NC}"
.venv/bin/pip install --upgrade pip

.venv/bin/pip install -r requirements.txt

# 6. Generate desktop entry shortcut
if [ -f scripts/install-desktop.sh ]; then
    echo -e "${YELLOW}Đang tạo shortcut Desktop...${NC}"
    chmod +x scripts/install-desktop.sh scripts/run-liminal.sh
    ./scripts/install-desktop.sh
fi

echo -e "${GREEN}=== Cài đặt hoàn tất! ===${NC}"
echo -e "Để chạy Liminal, hãy dùng lệnh:"
echo -e "  ${GREEN}./scripts/run-liminal.sh${NC}"
