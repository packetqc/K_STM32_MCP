#!/usr/bin/env python3
"""
Video Utils — Shared MP4 encoding for Knowledge test engines
=============================================================

Browser-compatible MP4 encoding using ffmpeg with H.264 (libx264).
Falls back to OpenCV mp4v if ffmpeg is unavailable (produces non-browser-playable files).

Used by:
  - web_test_engine.py — test proof videos
  - render_web_page.py — page render proof videos
  - security_test_engine.py — security audit proof videos

Pattern from: live/stream_capture.py encode_clip_mp4()

Knowledge asset — part of the Web Test command category.
"""

import os
import shutil
import subprocess
from pathlib import Path

from PIL import Image


# --- ffmpeg availability cache ------------------------------------------------

_ffmpeg_available = None


def ffmpeg_available():
    """Check if ffmpeg is in PATH. Result is cached."""
    global _ffmpeg_available
    if _ffmpeg_available is None:
        _ffmpeg_available = shutil.which("ffmpeg") is not None
    return _ffmpeg_available


# --- Size estimation ----------------------------------------------------------

def estimate_mp4_scale(frame_count, width, height, max_mb=7.0):
    """Auto-detect scale to keep MP4 under size limit.

    H.264 ultrafast CRF 23: ~25KB per 1920x1080 frame (screenshot content).
    Fallback mp4v: ~80KB per 1920x1080 frame.
    Scales down proportionally via sqrt to stay under max_mb.
    """
    if ffmpeg_available():
        bytes_per_pixel_per_frame = 25_000 / (1920 * 1080)
    else:
        bytes_per_pixel_per_frame = 80_000 / (1920 * 1080)

    estimated_bytes = frame_count * width * height * bytes_per_pixel_per_frame
    estimated_mb = estimated_bytes / (1024 * 1024)

    if estimated_mb <= max_mb:
        return 1.0

    scale = (max_mb / estimated_mb) ** 0.5
    scale = max(0.25, min(scale, 1.0))
    return round(scale, 2)


# --- MP4 encoding -------------------------------------------------------------

def encode_mp4_from_paths(frame_paths, output_path, fps=0.5, scale=0.5, crf=23):
    """Encode PNG frame files into a browser-compatible H.264 MP4.

    Args:
        frame_paths: List of PNG file paths.
        output_path: Output MP4 file path.
        fps: Frames per second (0.5 = 2s per frame for proof videos).
        scale: Resize factor (0.5 = half resolution).
        crf: H.264 quality (lower = better, 23 = default).

    Returns:
        True on success, False on failure.
    """
    valid = [p for p in frame_paths if os.path.isfile(p)]
    if not valid:
        return False

    # Read first frame to get dimensions
    first = Image.open(valid[0])
    w, h = first.size
    first.close()

    # Apply scale
    out_w = int(w * scale)
    out_h = int(h * scale)

    # H.264 requires even dimensions
    out_w = out_w if out_w % 2 == 0 else out_w + 1
    out_h = out_h if out_h % 2 == 0 else out_h + 1

    if ffmpeg_available():
        return _encode_ffmpeg(valid, output_path, fps, out_w, out_h, crf)
    else:
        print("  [warn] ffmpeg not available — MP4 will use mp4v codec (may not play in browsers)")
        return _encode_cv2_fallback(valid, output_path, fps, out_w, out_h)


def _encode_ffmpeg(frame_paths, output_path, fps, width, height, crf):
    """Encode via ffmpeg pipe — produces browser-compatible H.264 MP4."""
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", f"{width}x{height}",
        "-r", str(fps),
        "-i", "pipe:0",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-an",
        output_path
    ]

    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
    )

    for fp in frame_paths:
        img = Image.open(fp).convert("RGB")
        if img.size != (width, height):
            img = img.resize((width, height), Image.LANCZOS)
        proc.stdin.write(img.tobytes())
        img.close()

    proc.stdin.close()
    proc.wait(timeout=60)

    if proc.returncode != 0:
        err = proc.stderr.read().decode()[:200] if proc.stderr else ""
        print(f"  [ffmpeg] encode error: {err}")
        return False

    size_kb = os.path.getsize(output_path) / 1024 if os.path.exists(output_path) else 0
    print(f"  MP4 (H.264): {output_path} ({size_kb:.0f}K) [{width}x{height}]")
    return True


def _encode_cv2_fallback(frame_paths, output_path, fps, width, height):
    """Fallback encoding via OpenCV mp4v — NOT browser-compatible."""
    try:
        import cv2
    except ImportError:
        print("  [warn] Neither ffmpeg nor OpenCV available — cannot produce MP4")
        return False

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    for fp in frame_paths:
        frame = cv2.imread(fp)
        if frame is not None:
            if frame.shape[1] != width or frame.shape[0] != height:
                frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
            writer.write(frame)

    writer.release()
    size_kb = os.path.getsize(output_path) / 1024 if os.path.exists(output_path) else 0
    print(f"  MP4 (mp4v fallback): {output_path} ({size_kb:.0f}K) [{width}x{height}]")
    return True
