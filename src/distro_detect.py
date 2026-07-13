"""Detect Linux distribution and package manager for user-facing messages.

Used to provide distro-specific install instructions when system dependencies
(mpv, ffmpeg, etc.) are missing.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def _read_os_release() -> dict[str, str]:
    """Parse /etc/os-release into a dict of KEY=VALUE pairs."""
    result: dict[str, str] = {}
    paths = [Path("/etc/os-release"), Path("/usr/lib/os-release")]
    for p in paths:
        if p.exists():
            try:
                for line in p.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    result[key] = value.strip('"').strip("'")
                return result
            except OSError:
                continue
    return result


def distro_package_manager() -> str:
    """Return a human-readable install command snippet for system packages.

    Returns a string like "sudo dnf install mpv ffmpeg" that can be
    embedded in error messages shown to the user.
    """
    os_release = _read_os_release()
    distro_id = os_release.get("ID", "").lower()
    id_like = os_release.get("ID_LIKE", "").lower()

    # Prefer the distro family before PATH probing.  It avoids suggesting a
    # foreign manager on developer machines that happen to have it installed.
    if distro_id in {"linuxmint", "ubuntu", "pop", "elementary", "zorin", "debian"} or "debian" in id_like or "ubuntu" in id_like:
        return "sudo apt update && sudo apt install mpv ffmpeg"
    if distro_id in {"arch", "manjaro", "endeavouros", "cachyos", "garuda"} or "arch" in id_like:
        return "sudo pacman -S mpv ffmpeg"
    if distro_id in {"fedora", "rhel", "centos", "almalinux", "rocky", "nobara"} or "fedora" in id_like or "rhel" in id_like:
        return "sudo dnf install mpv ffmpeg"

    # Check for package managers on PATH for other distributions.
    if shutil.which("dnf"):
        return "sudo dnf install mpv ffmpeg"
    if shutil.which("apt"):
        return "sudo apt install mpv ffmpeg"
    if shutil.which("pacman"):
        return "sudo pacman -S mpv ffmpeg"
    if shutil.which("zypper"):
        return "sudo zypper install mpv ffmpeg"
    if shutil.which("apk"):
        return "sudo apk add mpv ffmpeg"

    # Fall back to distro ID recognition
    fedora_like = {"fedora", "rhel", "centos", "almalinux", "rocky", "nobara"}
    debian_like = {"debian", "ubuntu", "pop", "linuxmint", "elementary", "zorin"}
    arch_like = {"arch", "manjaro", "endeavouros", "cachyos", "garuda"}
    suse_like = {"opensuse", "suse", "opensuse-tumbleweed", "opensuse-leap"}

    if distro_id in fedora_like or "fedora" in id_like or "rhel" in id_like:
        return "sudo dnf install mpv ffmpeg"
    if distro_id in debian_like or "debian" in id_like or "ubuntu" in id_like:
        return "sudo apt install mpv ffmpeg"
    if distro_id in arch_like or "arch" in id_like:
        return "sudo pacman -S mpv ffmpeg"
    if distro_id in suse_like or "suse" in id_like:
        return "sudo zypper install mpv ffmpeg"

    return "Install mpv and ffmpeg using your distribution's package manager"


def distro_name() -> str:
    """Return a human-readable distro name for debug/logging."""
    os_release = _read_os_release()
    return os_release.get("PRETTY_NAME") or os_release.get("NAME") or "Linux"
