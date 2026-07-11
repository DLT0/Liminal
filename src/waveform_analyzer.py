"""Offline audio waveform analyzer for Liminal.

Decodes audio files to raw PCM using ffmpeg, computes peak amplitudes for N bins,
normalizes them, and caches the results in JSON format in the user's config directory.
"""

import hashlib
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import List, Optional

import numpy as np
from src.settings_store import CONFIG_DIR

logger = logging.getLogger(__name__)

WAVEFORM_CACHE_DIR = CONFIG_DIR / "waveforms"


def _ensure_cache_dir() -> None:
    """Ensure the cache directory exists."""
    WAVEFORM_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _get_cache_path(filepath: str) -> Path:
    """Get the path to the cached JSON file for a given filepath."""
    _ensure_cache_dir()
    # Create stable hash of filepath
    hash_str = hashlib.md5(filepath.encode("utf-8")).hexdigest()
    return WAVEFORM_CACHE_DIR / f"{hash_str}.json"


def generate_waveform(filepath: str, n_bins: int = 150) -> List[float]:
    """Decodes the entire audio file via ffmpeg to PCM and calculates peak bins."""
    path = Path(filepath)
    if not path.exists():
        logger.warning("waveform_analyzer: file does not exist: %s", filepath)
        return [0.0] * n_bins

    # Use ffmpeg to downsample to 8000Hz mono 16-bit PCM
    cmd = [
        "ffmpeg",
        "-y",
        "-v", "error",
        "-i", str(path.resolve()),
        "-f", "s16le",
        "-ac", "1",
        "-ar", "8000",
        "-"
    ]

    try:
        # Run subprocess with timeout to prevent hang on corrupted files
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout_data, stderr_data = process.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        if process:
            process.kill()
            _, _ = process.communicate()
        logger.error("waveform_analyzer: ffmpeg timed out for %s", filepath)
        return [0.0] * n_bins
    except Exception as e:
        logger.error("waveform_analyzer: failed to run ffmpeg: %s", e)
        return [0.0] * n_bins

    if process.returncode != 0:
        err_msg = stderr_data.decode("utf-8", errors="ignore")
        logger.error("waveform_analyzer: ffmpeg failed (code %d): %s", process.returncode, err_msg)
        return [0.0] * n_bins

    # Parse raw bytes as 16-bit signed integers
    samples = np.frombuffer(stdout_data, dtype=np.int16)
    if len(samples) == 0:
        logger.warning("waveform_analyzer: no audio samples decoded for %s", filepath)
        return [0.0] * n_bins

    # Divide into n_bins segments
    samples_per_bin = len(samples) // n_bins
    if samples_per_bin == 0:
        # File is extremely short, fallback to duplicating whatever samples we have
        peaks = [float(abs(s)) for s in samples[:n_bins]]
        peaks += [0.0] * (n_bins - len(peaks))
    else:
        peaks = []
        for i in range(n_bins):
            start = i * samples_per_bin
            end = start + samples_per_bin
            chunk = samples[start:end]
            if len(chunk) > 0:
                # Use peak amplitude for SoundCloud visual effect
                peak = np.max(np.abs(chunk))
                peaks.append(float(peak))
            else:
                peaks.append(0.0)

    # Normalize peaks to 0.0 - 1.0 based on maximum peak
    max_peak = max(peaks) if peaks else 0
    if max_peak > 0:
        normalized = [round(p / max_peak, 4) for p in peaks]
    else:
        normalized = [0.0] * n_bins

    return normalized


def get_waveform(filepath: str, n_bins: int = 150) -> List[float]:
    """Gets normalized waveform peaks, using cache if valid, otherwise generating them."""
    if not filepath or filepath.startswith(("http://", "https://")):
        # Remote streams don't support static offline analysis easily
        return [0.0] * n_bins

    path = Path(filepath)
    if not path.exists():
        return [0.0] * n_bins

    try:
        stat = path.stat()
        mtime = stat.st_mtime
        size = stat.st_size
    except OSError:
        return [0.0] * n_bins

    cache_path = _get_cache_path(filepath)
    
    # Try reading cache
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Validate cache metadata
            if (
                data.get("filepath") == filepath
                and data.get("mtime") == mtime
                and data.get("size") == size
                and len(data.get("peaks", [])) == n_bins
            ):
                return data["peaks"]
        except Exception as e:
            logger.warning("waveform_analyzer: failed to read cache %s: %s", cache_path, e)

    # Cache miss or invalid, generate waveform
    logger.info("waveform_analyzer: cache miss, generating waveform for %s", path.name)
    peaks = generate_waveform(filepath, n_bins)

    # Save to cache
    try:
        cache_data = {
            "filepath": filepath,
            "mtime": mtime,
            "size": size,
            "peaks": peaks,
        }
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2)
    except Exception as e:
        logger.warning("waveform_analyzer: failed to write cache %s: %s", cache_path, e)

    return peaks
