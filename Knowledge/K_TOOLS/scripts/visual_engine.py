#!/usr/bin/env python3
"""
Visual Engine — Automated Documentation from Video Recordings
=============================================================

Core video processing engine for the Knowledge System's `visual` command.
Extracts evidence frames from video recordings for documentation creation,
update, and review.

Three operating paradigms:
  1. Timestamp mode — extract frames at specific dates/times
  2. Detection mode — scan for content-relevant frames automatically
  3. Search mode — multi-criteria search directly on video (multi-pass, no bulk extraction)

Additional capabilities:
  - Evidence structure — organized output with discoveries/ and clips/
  - Clip reconstruction — extract video segments around evidence (±N seconds context)
  - Image analysis — single image input for evidence matching

Technology stack (standard/recognized libraries only):
  - OpenCV 4.x (cv2) — video decoding, frame extraction, image processing, video writing
  - Pillow (PIL) — image annotation, format conversion, thumbnails
  - NumPy — array operations (OpenCV dependency)
  - Python stdlib — pathlib, datetime, json, urllib, tempfile, hashlib

Knowledge asset — part of the Visuals command category.

Related:
  - scripts/visual_cli.py — CLI entry point
  - methodology/methodology-documentation-visual.md — full specification
  - Publication #22 — Visual Documentation (Automated from Recordings)
"""

import cv2
import hashlib
import json
import logging
import os
import re
import tempfile
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# --- Logging ----------------------------------------------------------------

logger = logging.getLogger("visual_engine")


# --- Constants --------------------------------------------------------------

# Frame similarity threshold (0-1, higher = more similar required to skip)
SIMILARITY_THRESHOLD = 0.92

# Minimum scene change threshold for detection mode (0-1, lower = more sensitive)
SCENE_CHANGE_THRESHOLD = 0.35

# Maximum frames to extract per video in detection mode
MAX_DETECTION_FRAMES = 50

# Default output image format
DEFAULT_IMAGE_FORMAT = "png"

# Annotation colors (BGR for OpenCV, RGB for Pillow)
ANNOTATION_COLOR_CV = (0, 200, 100)  # green
ANNOTATION_COLOR_PIL = (100, 200, 0)  # green

# Evidence frame border width
BORDER_WIDTH = 4

# Thumbnail dimensions for contact sheet
THUMBNAIL_SIZE = (320, 180)

# Maximum video duration to process (seconds) — safety limit
MAX_VIDEO_DURATION = 7200  # 2 hours


# --- Video Info Extraction --------------------------------------------------

class VideoInfo:
    """Metadata extracted from a video file."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.cap = cv2.VideoCapture(str(self.path))

        if not self.cap.isOpened():
            raise VideoError(f"Cannot open video: {path}")

        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.duration_secs = self.frame_count / self.fps if self.fps > 0 else 0
        self.codec = _decode_fourcc(int(self.cap.get(cv2.CAP_PROP_FOURCC)))

    def close(self):
        if self.cap and self.cap.isOpened():
            self.cap.release()

    def __repr__(self):
        return (
            f"VideoInfo({self.path.name}: {self.width}x{self.height}, "
            f"{self.fps:.1f}fps, {self.frame_count} frames, "
            f"{self.duration_secs:.1f}s, codec={self.codec})"
        )


class VideoError(Exception):
    """Raised when video processing fails."""
    pass


# --- Frame Extraction -------------------------------------------------------

def extract_frames_at_timestamps(
    video_path: str,
    timestamps: list[float],
    output_dir: str,
    prefix: str = "evidence",
    annotate: bool = True,
) -> list[dict]:
    """
    Extract frames at specific timestamps (in seconds from video start).

    Args:
        video_path: Path to the video file.
        timestamps: List of float timestamps in seconds.
        output_dir: Directory to write extracted frames.
        prefix: Filename prefix for output images.
        annotate: Whether to add timestamp annotation on frames.

    Returns:
        List of dicts with frame metadata:
        [{"timestamp": float, "frame_number": int, "path": str, "hash": str}]
    """
    info = VideoInfo(video_path)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    results = []
    sorted_ts = sorted(set(timestamps))

    for ts in sorted_ts:
        if ts < 0 or ts > info.duration_secs:
            logger.warning(f"Timestamp {ts:.2f}s out of range (0-{info.duration_secs:.2f}s), skipping")
            continue

        frame_num = int(ts * info.fps)
        info.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = info.cap.read()

        if not ret or frame is None:
            logger.warning(f"Failed to read frame at {ts:.2f}s (frame {frame_num})")
            continue

        # Annotate frame with timestamp
        if annotate:
            frame = _annotate_frame_cv(frame, ts, info)

        # Save frame
        fname = f"{prefix}_{frame_num:06d}_{ts:.2f}s.{DEFAULT_IMAGE_FORMAT}"
        fpath = output_path / fname
        cv2.imwrite(str(fpath), frame)

        frame_hash = _hash_frame(frame)
        results.append({
            "timestamp": round(ts, 3),
            "frame_number": frame_num,
            "path": str(fpath),
            "hash": frame_hash,
            "width": frame.shape[1],
            "height": frame.shape[0],
        })
        logger.info(f"Extracted frame at {ts:.2f}s → {fpath.name}")

    info.close()
    return results


def extract_frames_at_times(
    video_path: str,
    times: list[str],
    output_dir: str,
    video_start_time: Optional[str] = None,
    prefix: str = "evidence",
    annotate: bool = True,
) -> list[dict]:
    """
    Extract frames at specific clock times (HH:MM:SS or HH:MM:SS.mmm).

    If video_start_time is provided, times are interpreted as absolute clock times
    and converted to offsets from the video start. Otherwise, times are treated
    as offsets from 00:00:00.

    Args:
        video_path: Path to the video file.
        times: List of time strings ("HH:MM:SS" or "HH:MM:SS.mmm").
        output_dir: Directory to write extracted frames.
        video_start_time: Optional start time of the video ("HH:MM:SS").
        prefix: Filename prefix.
        annotate: Whether to add timestamp annotation.

    Returns:
        List of frame metadata dicts.
    """
    base_offset = _parse_time_to_seconds(video_start_time) if video_start_time else 0.0
    timestamps = []

    for t in times:
        secs = _parse_time_to_seconds(t)
        offset = secs - base_offset if video_start_time else secs
        if offset >= 0:
            timestamps.append(offset)
        else:
            logger.warning(f"Time {t} is before video start {video_start_time}, skipping")

    return extract_frames_at_timestamps(video_path, timestamps, output_dir, prefix, annotate)


def extract_frames_at_dates(
    video_path: str,
    date_times: list[str],
    output_dir: str,
    video_start_datetime: Optional[str] = None,
    prefix: str = "evidence",
    annotate: bool = True,
) -> list[dict]:
    """
    Extract frames at specific date-times (YYYY-MM-DD HH:MM:SS).

    If video_start_datetime is provided, date-times are converted to offsets.
    Otherwise, only the time portion is used.

    Args:
        video_path: Path to the video file.
        date_times: List of datetime strings ("YYYY-MM-DD HH:MM:SS").
        output_dir: Directory for output.
        video_start_datetime: When the video recording started.
        prefix: Filename prefix.
        annotate: Whether to annotate frames.

    Returns:
        List of frame metadata dicts.
    """
    timestamps = []

    if video_start_datetime:
        base_dt = _parse_datetime(video_start_datetime)
        for dt_str in date_times:
            dt = _parse_datetime(dt_str)
            offset = (dt - base_dt).total_seconds()
            if offset >= 0:
                timestamps.append(offset)
            else:
                logger.warning(f"DateTime {dt_str} is before video start, skipping")
    else:
        # Use time portion only
        for dt_str in date_times:
            dt = _parse_datetime(dt_str)
            timestamps.append(dt.hour * 3600 + dt.minute * 60 + dt.second + dt.microsecond / 1e6)

    return extract_frames_at_timestamps(video_path, timestamps, output_dir, prefix, annotate)


# --- Detection Mode ---------------------------------------------------------

def detect_evidence_frames(
    video_path: str,
    output_dir: str,
    subjects: Optional[list[str]] = None,
    sensitivity: float = 0.35,
    interval_secs: float = 1.0,
    max_frames: int = MAX_DETECTION_FRAMES,
    prefix: str = "detected",
    annotate: bool = True,
) -> list[dict]:
    """
    Scan video for significant frames using scene change detection and
    optional content analysis.

    Detects:
      - Scene changes (significant visual transitions)
      - Text-heavy frames (documentation-relevant content)
      - UI state changes (button highlights, modal dialogs)
      - High information density frames (tables, diagrams, code)

    Args:
        video_path: Path to the video file.
        output_dir: Directory for output.
        subjects: Optional list of subject keywords for content filtering.
        sensitivity: Scene change sensitivity (0-1, lower = more sensitive).
        interval_secs: Minimum interval between detections (seconds).
        max_frames: Maximum number of frames to extract.
        prefix: Filename prefix.
        annotate: Whether to annotate frames.

    Returns:
        List of frame metadata dicts with detection reason.
    """
    info = VideoInfo(video_path)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if info.duration_secs > MAX_VIDEO_DURATION:
        raise VideoError(
            f"Video duration {info.duration_secs:.0f}s exceeds maximum "
            f"{MAX_VIDEO_DURATION}s. Use timestamp mode for long videos."
        )

    results = []
    prev_gray = None
    prev_hist = None
    last_extract_time = -interval_secs  # Allow first frame
    frame_idx = 0
    step = max(1, int(info.fps * 0.5))  # Sample every 0.5s by default

    logger.info(
        f"Detection scan: {info.path.name} ({info.duration_secs:.1f}s, "
        f"{info.frame_count} frames, step={step})"
    )

    while len(results) < max_frames:
        info.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = info.cap.read()

        if not ret or frame is None:
            break

        timestamp = frame_idx / info.fps
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        cv2.normalize(hist, hist)

        reason = None

        # --- Scene change detection ---
        if prev_hist is not None:
            correlation = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL)
            if correlation < (1.0 - sensitivity):
                reason = f"scene_change (corr={correlation:.3f})"

        # --- Text density detection ---
        if reason is None and prev_gray is not None:
            text_score = _estimate_text_density(gray)
            if text_score > 0.15:  # High text density threshold
                # Check if significantly different from previous frame
                diff = cv2.absdiff(prev_gray, gray)
                change_ratio = np.count_nonzero(diff > 30) / diff.size
                if change_ratio > 0.05:
                    reason = f"text_content (density={text_score:.3f}, change={change_ratio:.3f})"

        # --- Information density detection (edges, structure) ---
        if reason is None:
            edge_score = _estimate_edge_density(gray)
            if edge_score > 0.12:
                if prev_gray is not None:
                    diff = cv2.absdiff(prev_gray, gray)
                    change_ratio = np.count_nonzero(diff > 30) / diff.size
                    if change_ratio > 0.05:
                        reason = f"high_info_density (edges={edge_score:.3f})"

        # --- Subject keyword matching (OCR-free heuristic) ---
        if reason is None and subjects:
            # Use template matching as a lightweight proxy for content detection
            # This is a structural heuristic — not OCR
            structure_score = _estimate_structured_content(gray)
            if structure_score > 0.08:
                reason = f"structured_content (score={structure_score:.3f})"

        # Apply minimum interval between extractions
        if reason and (timestamp - last_extract_time) >= interval_secs:
            if annotate:
                frame = _annotate_frame_cv(frame, timestamp, info, reason=reason)

            fname = f"{prefix}_{frame_idx:06d}_{timestamp:.2f}s.{DEFAULT_IMAGE_FORMAT}"
            fpath = output_path / fname
            cv2.imwrite(str(fpath), frame)

            frame_hash = _hash_frame(frame)
            results.append({
                "timestamp": round(timestamp, 3),
                "frame_number": frame_idx,
                "path": str(fpath),
                "hash": frame_hash,
                "width": frame.shape[1],
                "height": frame.shape[0],
                "reason": reason,
            })
            last_extract_time = timestamp
            logger.info(f"Detected at {timestamp:.2f}s: {reason} → {fpath.name}")

        prev_gray = gray.copy()
        prev_hist = hist.copy()
        frame_idx += step

    # Always capture first and last frame if not already captured
    results = _ensure_bookend_frames(info, results, output_path, prefix, annotate)

    info.close()
    logger.info(f"Detection complete: {len(results)} frames extracted")
    return results


# --- Contact Sheet Generation -----------------------------------------------

def generate_contact_sheet(
    frames: list[dict],
    output_path: str,
    title: str = "Evidence Contact Sheet",
    cols: int = 4,
    thumb_size: tuple = THUMBNAIL_SIZE,
) -> str:
    """
    Generate a contact sheet (grid of thumbnails) from extracted frames.

    Args:
        frames: List of frame metadata dicts (from extract/detect functions).
        output_path: Path for the output image.
        title: Title text for the sheet header.
        cols: Number of columns in the grid.
        thumb_size: Thumbnail dimensions (width, height).

    Returns:
        Path to the generated contact sheet image.
    """
    if not frames:
        raise VideoError("No frames provided for contact sheet")

    tw, th = thumb_size
    rows = (len(frames) + cols - 1) // cols
    padding = 10
    header_height = 60
    label_height = 24

    sheet_w = cols * (tw + padding) + padding
    sheet_h = header_height + rows * (th + label_height + padding) + padding

    sheet = Image.new("RGB", (sheet_w, sheet_h), color=(245, 245, 245))
    draw = ImageDraw.Draw(sheet)

    # Header
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        font_label = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    except (OSError, IOError):
        font_title = ImageFont.load_default()
        font_label = ImageFont.load_default()

    draw.text((padding, 15), title, fill=(30, 30, 30), font=font_title)
    draw.text(
        (padding, 40),
        f"{len(frames)} frames · {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        fill=(100, 100, 100),
        font=font_label,
    )

    # Thumbnails
    for i, frame_meta in enumerate(frames):
        row = i // cols
        col = i % cols
        x = padding + col * (tw + padding)
        y = header_height + row * (th + label_height + padding)

        try:
            img = Image.open(frame_meta["path"])
            img.thumbnail(thumb_size, Image.LANCZOS)

            # Center in cell
            offset_x = x + (tw - img.width) // 2
            offset_y = y + (th - img.height) // 2
            sheet.paste(img, (offset_x, offset_y))

            # Border
            draw.rectangle(
                [x - 1, y - 1, x + tw, y + th],
                outline=(180, 180, 180),
                width=1,
            )

            # Label
            ts = frame_meta.get("timestamp", 0)
            reason = frame_meta.get("reason", "")
            label = f"{_format_timestamp(ts)}"
            if reason:
                label += f" · {reason.split('(')[0].strip()}"
            draw.text(
                (x, y + th + 2),
                label[:45],
                fill=(60, 60, 60),
                font=font_label,
            )
        except Exception as e:
            logger.warning(f"Failed to add frame {i} to contact sheet: {e}")
            draw.rectangle([x, y, x + tw, y + th], fill=(220, 220, 220))
            draw.text((x + 5, y + th // 2), "Error", fill=(180, 0, 0), font=font_label)

    sheet.save(output_path)
    logger.info(f"Contact sheet: {output_path} ({sheet_w}x{sheet_h})")
    return output_path


# --- Evidence Report Generation ---------------------------------------------

def generate_evidence_report(
    frames: list[dict],
    video_path: str,
    output_path: str,
    title: str = "Visual Evidence Report",
    description: str = "",
) -> str:
    """
    Generate a markdown evidence report from extracted frames.

    Args:
        frames: List of frame metadata dicts.
        video_path: Source video path (for reference).
        output_path: Path for the output markdown file.
        title: Report title.
        description: Optional description/context.

    Returns:
        Path to the generated report.
    """
    info = VideoInfo(video_path)
    report_path = Path(output_path)

    lines = [
        f"# {title}",
        "",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Source**: `{Path(video_path).name}`",
        f"**Video**: {info.width}x{info.height}, {info.fps:.1f} fps, "
        f"{_format_timestamp(info.duration_secs)} duration",
        f"**Frames extracted**: {len(frames)}",
        "",
    ]

    if description:
        lines.extend(["## Context", "", description, ""])

    lines.extend(["## Evidence Frames", ""])

    # Summary table
    lines.append("| # | Timestamp | Frame | Reason | Hash |")
    lines.append("|---|-----------|-------|--------|------|")

    for i, f in enumerate(frames, 1):
        ts = _format_timestamp(f.get("timestamp", 0))
        fname = Path(f["path"]).name
        reason = f.get("reason", "manual")
        fhash = f.get("hash", "")[:8]
        lines.append(f"| {i} | {ts} | `{fname}` | {reason} | `{fhash}` |")

    lines.extend(["", "## Frame Details", ""])

    for i, f in enumerate(frames, 1):
        ts = _format_timestamp(f.get("timestamp", 0))
        fname = Path(f["path"]).name
        reason = f.get("reason", "manual")
        lines.extend([
            f"### Frame {i} — {ts}",
            "",
            f"- **File**: `{fname}`",
            f"- **Frame number**: {f.get('frame_number', 'N/A')}",
            f"- **Resolution**: {f.get('width', '?')}x{f.get('height', '?')}",
            f"- **Detection**: {reason}",
            f"- **Hash**: `{f.get('hash', 'N/A')}`",
            "",
            f"![{fname}]({fname})",
            "",
        ])

    lines.extend([
        "---",
        "",
        f"*Report generated by Visual Engine — Knowledge System*",
        f"*Technology: OpenCV {cv2.__version__}, Pillow, NumPy*",
    ])

    info.close()
    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Evidence report: {report_path}")
    return str(report_path)


# --- GitHub Video Fetching --------------------------------------------------

def fetch_video_from_github(
    repo: str,
    file_path: str,
    ref: str = "main",
    output_dir: Optional[str] = None,
) -> str:
    """
    Fetch a video file from a GitHub repository.

    Uses git clone (sparse checkout) for large files, or raw download for
    files under the GitHub raw content size limit.

    Args:
        repo: Repository in "owner/repo" format.
        file_path: Path to the video file within the repo.
        ref: Branch or tag to fetch from.
        output_dir: Directory to save the file. Defaults to /tmp.

    Returns:
        Local path to the downloaded video file.
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="visual_")

    output_path = Path(output_dir) / Path(file_path).name

    # Try raw download first (works for files < 100MB on public repos)
    raw_url = f"https://raw.githubusercontent.com/{repo}/{ref}/{file_path}"
    logger.info(f"Fetching video: {raw_url}")

    try:
        req = urllib.request.Request(raw_url)
        token = os.environ.get("GH_TOKEN")
        if token:
            req.add_header("Authorization", f"token {token}")

        with urllib.request.urlopen(req, timeout=120) as response:
            with open(output_path, "wb") as f:
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)

        logger.info(f"Downloaded: {output_path} ({output_path.stat().st_size} bytes)")
        return str(output_path)

    except urllib.error.HTTPError as e:
        if e.code == 404:
            # Try alternate branch name
            alt_ref = "master" if ref == "main" else "main"
            alt_url = f"https://raw.githubusercontent.com/{repo}/{alt_ref}/{file_path}"
            try:
                req = urllib.request.Request(alt_url)
                if token:
                    req.add_header("Authorization", f"token {token}")
                with urllib.request.urlopen(req, timeout=120) as response:
                    with open(output_path, "wb") as f:
                        while True:
                            chunk = response.read(65536)
                            if not chunk:
                                break
                            f.write(chunk)
                logger.info(f"Downloaded (alt branch): {output_path}")
                return str(output_path)
            except Exception:
                pass
        raise VideoError(f"Failed to fetch video from GitHub: {e}")

    except Exception as e:
        raise VideoError(f"Failed to fetch video: {e}")


# --- Deduplication ----------------------------------------------------------

def deduplicate_frames(
    frames: list[dict],
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[dict]:
    """
    Remove near-duplicate frames based on perceptual hashing.

    Args:
        frames: List of frame metadata dicts with "path" keys.
        threshold: Similarity threshold (0-1). Higher = more aggressive dedup.

    Returns:
        Deduplicated list of frame metadata dicts.
    """
    if len(frames) <= 1:
        return frames

    unique = [frames[0]]
    prev_phash = _perceptual_hash(frames[0]["path"])

    for frame in frames[1:]:
        curr_phash = _perceptual_hash(frame["path"])
        similarity = _hamming_similarity(prev_phash, curr_phash)

        if similarity < threshold:
            unique.append(frame)
            prev_phash = curr_phash
        else:
            logger.debug(
                f"Dedup: skipping frame at {frame.get('timestamp', '?')}s "
                f"(similarity={similarity:.3f})"
            )

    logger.info(f"Deduplication: {len(frames)} → {len(unique)} frames")
    return unique


# --- Evidence Structure Management ------------------------------------------

class EvidenceSession:
    """
    Manages an organized evidence directory for a video analysis session.

    Structure:
      evidence/<session-name>/
        metadata.json        — source info, criteria, timestamps
        discoveries/         — extracted evidence frames
        clips/               — reconstructed video segments
        index.md             — inventory of findings
    """

    def __init__(self, source_path: str, session_name: Optional[str] = None):
        self.source_path = Path(source_path)

        if session_name is None:
            stem = self.source_path.stem
            date_str = datetime.now().strftime("%Y-%m-%d")
            session_name = f"{date_str}-{stem}"

        self.name = session_name
        self.base_dir = Path("evidence") / session_name
        self.discoveries_dir = self.base_dir / "discoveries"
        self.clips_dir = self.base_dir / "clips"
        self.metadata_path = self.base_dir / "metadata.json"
        self.index_path = self.base_dir / "index.md"
        self.metadata = {}
        self.findings = []

    def initialize(self) -> "EvidenceSession":
        """Create the directory structure and initialize metadata."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.discoveries_dir.mkdir(exist_ok=True)
        self.clips_dir.mkdir(exist_ok=True)

        is_image = self.source_path.suffix.lower() in (
            ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp",
        )

        self.metadata = {
            "source": str(self.source_path),
            "source_type": "image" if is_image else "video",
            "session_name": self.name,
            "created": datetime.now().isoformat(),
            "criteria": [],
            "findings_count": 0,
            "clips_count": 0,
        }

        if not is_image and self.source_path.exists():
            try:
                info = VideoInfo(str(self.source_path))
                self.metadata.update({
                    "width": info.width,
                    "height": info.height,
                    "fps": info.fps,
                    "frame_count": info.frame_count,
                    "duration_secs": round(info.duration_secs, 3),
                    "codec": info.codec,
                })
                info.close()
            except VideoError:
                pass

        self._save_metadata()
        return self

    def add_finding(self, frame_data: dict, frame: Optional[np.ndarray] = None) -> dict:
        """
        Record a finding (discovered evidence frame).

        Args:
            frame_data: Metadata dict from extraction functions.
            frame: Optional raw frame array to save (if not already saved).

        Returns:
            Updated frame_data with discovery path.
        """
        idx = len(self.findings) + 1
        ts = frame_data.get("timestamp", 0)
        reason = frame_data.get("reason", "manual")

        fname = f"finding_{idx:04d}_{ts:.2f}s.{DEFAULT_IMAGE_FORMAT}"
        dest = self.discoveries_dir / fname

        # Copy or save the frame
        if frame is not None:
            cv2.imwrite(str(dest), frame)
        elif "path" in frame_data and Path(frame_data["path"]).exists():
            import shutil
            shutil.copy2(frame_data["path"], dest)

        finding = {
            **frame_data,
            "finding_id": idx,
            "discovery_path": str(dest),
            "reason": reason,
        }
        self.findings.append(finding)
        self.metadata["findings_count"] = len(self.findings)
        self._save_metadata()
        return finding

    def add_clip(self, clip_path: str, context: dict) -> dict:
        """Record a reconstructed clip."""
        clip_info = {
            "clip_path": clip_path,
            "context": context,
        }
        self.metadata["clips_count"] = self.metadata.get("clips_count", 0) + 1
        self._save_metadata()
        return clip_info

    def generate_index(self) -> str:
        """Generate a markdown index of all findings."""
        lines = [
            f"# Evidence Index — {self.name}",
            "",
            f"**Source**: `{self.source_path.name}`",
            f"**Created**: {self.metadata.get('created', 'N/A')}",
            f"**Findings**: {len(self.findings)}",
            f"**Clips**: {self.metadata.get('clips_count', 0)}",
            "",
            "## Findings",
            "",
            "| # | Timestamp | Reason | File |",
            "|---|-----------|--------|------|",
        ]

        for f in self.findings:
            ts = _format_timestamp(f.get("timestamp", 0))
            reason = f.get("reason", "manual")
            if "(" in reason:
                reason = reason.split("(")[0].strip()
            fname = Path(f.get("discovery_path", "")).name
            lines.append(f"| {f['finding_id']} | {ts} | {reason} | `{fname}` |")

        lines.extend(["", "---", f"*Generated by Visual Engine*"])
        content = "\n".join(lines)
        self.index_path.write_text(content, encoding="utf-8")
        return str(self.index_path)

    def _save_metadata(self):
        """Persist metadata to JSON."""
        self.metadata_path.write_text(
            json.dumps(self.metadata, indent=2, default=str),
            encoding="utf-8",
        )


# --- Search Mode (Multi-Criteria, Multi-Pass) ------------------------------

def search_video(
    video_path: str,
    criteria: dict,
    output_dir: Optional[str] = None,
    context_secs: float = 10.0,
    session_name: Optional[str] = None,
) -> dict:
    """
    Multi-criteria search directly on the video file (no bulk frame extraction).

    Performs intelligent multi-pass scanning:
      Pass 1 — coarse scan at intervals (every 1-2 seconds)
      Pass 2 — fine-grained scan around hits (frame by frame)

    Args:
        video_path: Path to the video file.
        criteria: Search criteria dict with optional keys:
            - timestamps: list[float] — specific timestamps to check
            - time_ranges: list[tuple[float, float]] — time ranges (start, end) in seconds
            - text_patterns: list[str] — text/patterns to search for visually
            - scene_change: bool — detect scene changes
            - min_text_density: float — minimum text density threshold
            - min_edge_density: float — minimum edge density threshold
        output_dir: Base output directory. Defaults to evidence/<session-name>.
        context_secs: Seconds of context around each hit for clip reconstruction.
        session_name: Optional session name for evidence structure.

    Returns:
        Dict with search results, evidence session info, and generated clips.
    """
    info = VideoInfo(video_path)

    if info.duration_secs > MAX_VIDEO_DURATION:
        raise VideoError(
            f"Video duration {info.duration_secs:.0f}s exceeds maximum "
            f"{MAX_VIDEO_DURATION}s."
        )

    # Initialize evidence session
    session = EvidenceSession(video_path, session_name)
    if output_dir:
        session.base_dir = Path(output_dir)
        session.discoveries_dir = session.base_dir / "discoveries"
        session.clips_dir = session.base_dir / "clips"
        session.metadata_path = session.base_dir / "metadata.json"
        session.index_path = session.base_dir / "index.md"
    session.initialize()
    session.metadata["criteria"] = criteria

    hits = []

    # --- Pass 1: Coarse scan ---
    coarse_step = max(1, int(info.fps))  # ~1 frame per second
    logger.info(f"Search pass 1 (coarse): scanning every {coarse_step} frames")

    frame_idx = 0
    while frame_idx < info.frame_count:
        info.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = info.cap.read()
        if not ret or frame is None:
            break

        timestamp = frame_idx / info.fps
        match = _evaluate_criteria(frame, timestamp, criteria, info)

        if match:
            hits.append({
                "frame_idx": frame_idx,
                "timestamp": round(timestamp, 3),
                "match_reasons": match,
                "pass": "coarse",
            })

        frame_idx += coarse_step

    logger.info(f"Pass 1 complete: {len(hits)} coarse hits")

    # --- Pass 2: Fine scan around hits ---
    refined_hits = []
    visited = set()

    for hit in hits:
        center = hit["frame_idx"]
        # Scan ±0.5 seconds around each hit, frame by frame
        scan_radius = int(info.fps * 0.5)
        start_frame = max(0, center - scan_radius)
        end_frame = min(info.frame_count - 1, center + scan_radius)

        best_score = 0
        best_frame_idx = center
        best_frame = None
        best_reasons = hit["match_reasons"]

        for fidx in range(start_frame, end_frame + 1):
            if fidx in visited:
                continue
            visited.add(fidx)

            info.cap.set(cv2.CAP_PROP_POS_FRAMES, fidx)
            ret, frame = info.cap.read()
            if not ret or frame is None:
                continue

            ts = fidx / info.fps
            match = _evaluate_criteria(frame, ts, criteria, info)
            if match:
                score = len(match)
                if score > best_score:
                    best_score = score
                    best_frame_idx = fidx
                    best_frame = frame.copy()
                    best_reasons = match

        if best_frame is not None:
            ts = best_frame_idx / info.fps
            annotated = _annotate_frame_cv(
                best_frame, ts, info,
                reason="; ".join(best_reasons),
            )

            finding_data = {
                "timestamp": round(ts, 3),
                "frame_number": best_frame_idx,
                "reason": "; ".join(best_reasons),
                "width": best_frame.shape[1],
                "height": best_frame.shape[0],
                "hash": _hash_frame(best_frame),
            }

            finding = session.add_finding(finding_data, annotated)
            refined_hits.append(finding)

    logger.info(f"Pass 2 complete: {len(refined_hits)} refined findings")

    # --- Generate clips for each finding ---
    clips = []
    if context_secs > 0 and refined_hits:
        for finding in refined_hits:
            clip_path = reconstruct_clip(
                video_path,
                finding["timestamp"],
                context_secs=context_secs,
                output_dir=str(session.clips_dir),
            )
            if clip_path:
                clip_info = session.add_clip(clip_path, {
                    "center_timestamp": finding["timestamp"],
                    "context_secs": context_secs,
                    "finding_id": finding.get("finding_id"),
                })
                clips.append(clip_info)

    # Generate index
    session.generate_index()

    info.close()

    return {
        "session": str(session.base_dir),
        "findings": refined_hits,
        "clips": clips,
        "metadata": session.metadata,
        "index": str(session.index_path),
    }


def _evaluate_criteria(
    frame: np.ndarray,
    timestamp: float,
    criteria: dict,
    info: VideoInfo,
) -> list[str]:
    """
    Evaluate a frame against multi-criteria search parameters.

    Returns list of matched reasons (empty = no match).
    """
    matches = []
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Timestamp match
    timestamps = criteria.get("timestamps", [])
    for ts in timestamps:
        if abs(timestamp - ts) < (1.0 / info.fps):
            matches.append(f"timestamp_match ({ts:.2f}s)")

    # Time range match
    for start, end in criteria.get("time_ranges", []):
        if start <= timestamp <= end:
            matches.append(f"in_range ({start:.1f}-{end:.1f}s)")

    # Scene change detection
    if criteria.get("scene_change", False):
        # Store previous histogram in criteria dict for stateful comparison
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        cv2.normalize(hist, hist)
        prev_hist = criteria.get("_prev_hist")
        if prev_hist is not None:
            corr = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL)
            if corr < 0.65:
                matches.append(f"scene_change (corr={corr:.3f})")
        criteria["_prev_hist"] = hist

    # Text density
    min_text = criteria.get("min_text_density", 0)
    if min_text > 0:
        text_score = _estimate_text_density(gray)
        if text_score >= min_text:
            matches.append(f"text_density ({text_score:.3f})")

    # Edge density
    min_edge = criteria.get("min_edge_density", 0)
    if min_edge > 0:
        edge_score = _estimate_edge_density(gray)
        if edge_score >= min_edge:
            matches.append(f"edge_density ({edge_score:.3f})")

    # Structured content
    if criteria.get("structured_content", False):
        struct_score = _estimate_structured_content(gray)
        if struct_score > 0.08:
            matches.append(f"structured ({struct_score:.3f})")

    return matches


# --- Clip Reconstruction ---------------------------------------------------

def reconstruct_clip(
    video_path: str,
    center_timestamp: float,
    context_secs: float = 10.0,
    output_dir: Optional[str] = None,
    output_filename: Optional[str] = None,
) -> Optional[str]:
    """
    Reconstruct a video clip centered around a timestamp.

    Extracts [center - context_secs, center + context_secs] from the video.

    Args:
        video_path: Path to the source video.
        center_timestamp: Center point in seconds.
        context_secs: Seconds of context before and after (default: 10).
        output_dir: Output directory (default: /tmp/visual_clips/).
        output_filename: Custom filename (default: auto-generated).

    Returns:
        Path to the reconstructed clip, or None on failure.
    """
    info = VideoInfo(video_path)

    start_time = max(0, center_timestamp - context_secs)
    end_time = min(info.duration_secs, center_timestamp + context_secs)

    if start_time >= end_time:
        logger.warning(f"Invalid clip range: {start_time:.2f}-{end_time:.2f}s")
        info.close()
        return None

    start_frame = int(start_time * info.fps)
    end_frame = int(end_time * info.fps)

    if output_dir is None:
        output_dir = "/tmp/visual_clips"
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    if output_filename is None:
        output_filename = (
            f"clip_{center_timestamp:.1f}s_ctx{context_secs:.0f}s.mp4"
        )
    clip_path = out_path / output_filename

    # Write the clip using OpenCV VideoWriter
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(
        str(clip_path), fourcc, info.fps,
        (info.width, info.height),
    )

    if not writer.isOpened():
        logger.error(f"Failed to create video writer for {clip_path}")
        info.close()
        return None

    info.cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    frames_written = 0

    for fidx in range(start_frame, end_frame + 1):
        ret, frame = info.cap.read()
        if not ret or frame is None:
            break
        writer.write(frame)
        frames_written += 1

    writer.release()
    info.close()

    if frames_written == 0:
        logger.warning("No frames written to clip")
        clip_path.unlink(missing_ok=True)
        return None

    duration = frames_written / info.fps
    logger.info(
        f"Clip reconstructed: {clip_path.name} "
        f"({duration:.1f}s, {frames_written} frames, "
        f"{start_time:.1f}s-{end_time:.1f}s)"
    )
    return str(clip_path)


# --- Image Analysis --------------------------------------------------------

def analyze_image(
    image_path: str,
    criteria: Optional[dict] = None,
    output_dir: Optional[str] = None,
) -> dict:
    """
    Analyze a single image for evidence matching.

    Supports the same visual heuristics as video detection (text density,
    edge density, structured content) applied to a single frame.

    Args:
        image_path: Path to the image file.
        criteria: Optional search criteria (same format as search_video).
            If None, runs all heuristics and reports scores.
        output_dir: Optional output directory for annotated copy.

    Returns:
        Dict with analysis results: scores, matches, and annotated path.
    """
    img_path = Path(image_path)
    if not img_path.exists():
        raise VideoError(f"Image not found: {image_path}")

    frame = cv2.imread(str(img_path))
    if frame is None:
        raise VideoError(f"Cannot read image: {image_path}")

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = frame.shape[:2]

    # Compute all scores
    text_score = _estimate_text_density(gray)
    edge_score = _estimate_edge_density(gray)
    struct_score = _estimate_structured_content(gray)
    frame_hash = _hash_frame(frame)

    result = {
        "path": str(img_path.resolve()),
        "width": w,
        "height": h,
        "hash": frame_hash,
        "scores": {
            "text_density": round(text_score, 4),
            "edge_density": round(edge_score, 4),
            "structured_content": round(struct_score, 4),
        },
        "matches": [],
    }

    # Evaluate against criteria if provided
    if criteria:
        if criteria.get("min_text_density", 0) > 0 and text_score >= criteria["min_text_density"]:
            result["matches"].append(f"text_density ({text_score:.3f})")
        if criteria.get("min_edge_density", 0) > 0 and edge_score >= criteria["min_edge_density"]:
            result["matches"].append(f"edge_density ({edge_score:.3f})")
        if criteria.get("structured_content", False) and struct_score > 0.08:
            result["matches"].append(f"structured ({struct_score:.3f})")
    else:
        # Report which heuristics fire at default thresholds
        if text_score > 0.15:
            result["matches"].append(f"text_density ({text_score:.3f})")
        if edge_score > 0.12:
            result["matches"].append(f"edge_density ({edge_score:.3f})")
        if struct_score > 0.08:
            result["matches"].append(f"structured ({struct_score:.3f})")

    result["is_evidence"] = len(result["matches"]) > 0

    # Save annotated copy if output dir specified
    if output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        # Create a lightweight annotation for images
        annotated = frame.copy()
        overlay = annotated.copy()
        bar_height = 40
        cv2.rectangle(overlay, (0, h - bar_height), (w, h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, annotated, 0.4, 0, annotated)

        info_text = f"{img_path.name} | {w}x{h}"
        cv2.putText(
            annotated, info_text,
            (10, h - 12),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6,
            (255, 255, 255), 1, cv2.LINE_AA,
        )

        scores_text = f"txt={text_score:.3f} edge={edge_score:.3f} struct={struct_score:.3f}"
        cv2.putText(
            annotated, scores_text,
            (w - 450, h - 12),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45,
            (180, 180, 180), 1, cv2.LINE_AA,
        )

        if result["is_evidence"]:
            mark_len = 20
            cv2.line(annotated, (2, 2), (mark_len, 2), ANNOTATION_COLOR_CV, 2)
            cv2.line(annotated, (2, 2), (2, mark_len), ANNOTATION_COLOR_CV, 2)
            cv2.line(annotated, (w - 2, 2), (w - mark_len, 2), ANNOTATION_COLOR_CV, 2)
            cv2.line(annotated, (w - 2, 2), (w - 2, mark_len), ANNOTATION_COLOR_CV, 2)
            cv2.line(annotated, (2, h - 2), (mark_len, h - 2), ANNOTATION_COLOR_CV, 2)
            cv2.line(annotated, (2, h - 2), (2, h - mark_len), ANNOTATION_COLOR_CV, 2)
            cv2.line(annotated, (w - 2, h - 2), (w - mark_len, h - 2), ANNOTATION_COLOR_CV, 2)
            cv2.line(annotated, (w - 2, h - 2), (w - 2, h - mark_len), ANNOTATION_COLOR_CV, 2)

            badge_text = "EVIDENCE"
            badge_w = len(badge_text) * 9 + 16
            cv2.rectangle(annotated, (10, 8), (10 + badge_w, 32), ANNOTATION_COLOR_CV, -1)
            cv2.putText(
                annotated, badge_text,
                (18, 26),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                (255, 255, 255), 1, cv2.LINE_AA,
            )

        annotated_path = out_path / f"analyzed_{img_path.name}"
        cv2.imwrite(str(annotated_path), annotated)
        result["annotated_path"] = str(annotated_path)

    return result


# --- Internal Helpers -------------------------------------------------------

def _decode_fourcc(fourcc: int) -> str:
    """Decode OpenCV fourcc integer to codec string."""
    return "".join(chr((fourcc >> (8 * i)) & 0xFF) for i in range(4))


def _parse_time_to_seconds(time_str: str) -> float:
    """Parse HH:MM:SS or HH:MM:SS.mmm to seconds."""
    if not time_str:
        return 0.0

    parts = time_str.strip().split(":")
    if len(parts) == 3:
        h, m = int(parts[0]), int(parts[1])
        s = float(parts[2])
        return h * 3600 + m * 60 + s
    elif len(parts) == 2:
        m = int(parts[0])
        s = float(parts[1])
        return m * 60 + s
    else:
        return float(parts[0])


def _parse_datetime(dt_str: str) -> datetime:
    """Parse datetime string in common formats."""
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(dt_str.strip(), fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse datetime: {dt_str}")


def _format_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS.mmm."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:06.3f}"
    return f"{m:02d}:{s:06.3f}"


def _hash_frame(frame: np.ndarray) -> str:
    """Compute SHA-256 hash of a frame's raw bytes."""
    return hashlib.sha256(frame.tobytes()).hexdigest()[:16]


def _perceptual_hash(image_path: str, hash_size: int = 16) -> np.ndarray:
    """
    Compute a perceptual hash (pHash) of an image.
    Uses DCT-based approach for robust similarity detection.
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return np.zeros((hash_size, hash_size), dtype=np.float32)

    # Resize to slightly larger than hash size for DCT
    resized = cv2.resize(img, (hash_size * 4, hash_size * 4), interpolation=cv2.INTER_AREA)

    # Apply DCT
    dct = cv2.dct(np.float32(resized))

    # Keep top-left low-frequency components
    dct_low = dct[:hash_size, :hash_size]

    # Threshold at median
    median = np.median(dct_low)
    return (dct_low > median).astype(np.uint8)


def _hamming_similarity(hash1: np.ndarray, hash2: np.ndarray) -> float:
    """Compute similarity between two perceptual hashes (0=different, 1=identical)."""
    if hash1.shape != hash2.shape:
        return 0.0
    total = hash1.size
    matching = np.count_nonzero(hash1 == hash2)
    return matching / total


def _annotate_frame_cv(
    frame: np.ndarray,
    timestamp: float,
    info: VideoInfo,
    reason: Optional[str] = None,
) -> np.ndarray:
    """Add timestamp and metadata annotation to a frame using OpenCV."""
    annotated = frame.copy()
    h, w = annotated.shape[:2]

    # Semi-transparent overlay bar at bottom
    overlay = annotated.copy()
    bar_height = 40
    cv2.rectangle(overlay, (0, h - bar_height), (w, h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, annotated, 0.4, 0, annotated)

    # Timestamp text
    ts_text = _format_timestamp(timestamp)
    cv2.putText(
        annotated, ts_text,
        (10, h - 12),
        cv2.FONT_HERSHEY_SIMPLEX, 0.6,
        (255, 255, 255), 1, cv2.LINE_AA,
    )

    # Source info
    src_text = f"{info.path.name} | {info.width}x{info.height}"
    cv2.putText(
        annotated, src_text,
        (w - 350, h - 12),
        cv2.FONT_HERSHEY_SIMPLEX, 0.45,
        (180, 180, 180), 1, cv2.LINE_AA,
    )

    # Reason badge (if detection mode)
    if reason:
        reason_short = reason.split("(")[0].strip()
        badge_w = len(reason_short) * 9 + 16
        cv2.rectangle(annotated, (10, 8), (10 + badge_w, 32), ANNOTATION_COLOR_CV, -1)
        cv2.putText(
            annotated, reason_short,
            (18, 26),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45,
            (255, 255, 255), 1, cv2.LINE_AA,
        )

    # Green corner marks (evidence indicator)
    mark_len = 20
    cv2.line(annotated, (2, 2), (mark_len, 2), ANNOTATION_COLOR_CV, 2)
    cv2.line(annotated, (2, 2), (2, mark_len), ANNOTATION_COLOR_CV, 2)
    cv2.line(annotated, (w - 2, 2), (w - mark_len, 2), ANNOTATION_COLOR_CV, 2)
    cv2.line(annotated, (w - 2, 2), (w - 2, mark_len), ANNOTATION_COLOR_CV, 2)
    cv2.line(annotated, (2, h - 2), (mark_len, h - 2), ANNOTATION_COLOR_CV, 2)
    cv2.line(annotated, (2, h - 2), (2, h - mark_len), ANNOTATION_COLOR_CV, 2)
    cv2.line(annotated, (w - 2, h - 2), (w - mark_len, h - 2), ANNOTATION_COLOR_CV, 2)
    cv2.line(annotated, (w - 2, h - 2), (w - 2, h - mark_len), ANNOTATION_COLOR_CV, 2)

    return annotated


def _estimate_text_density(gray: np.ndarray) -> float:
    """
    Estimate text density in a grayscale frame.
    Uses edge detection + morphological analysis as a proxy for text regions.
    """
    # Adaptive threshold to find text-like regions
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 15, 10,
    )

    # Morphological close to connect text characters
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 2))
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    # Count text-like pixels as fraction of total
    text_pixels = np.count_nonzero(closed)
    total_pixels = closed.size

    return text_pixels / total_pixels


def _estimate_edge_density(gray: np.ndarray) -> float:
    """
    Estimate edge/structure density in a grayscale frame.
    High edge density suggests diagrams, tables, code, or UI elements.
    """
    edges = cv2.Canny(gray, 50, 150)
    return np.count_nonzero(edges) / edges.size


def _estimate_structured_content(gray: np.ndarray) -> float:
    """
    Estimate structured content (tables, grids, forms) using line detection.
    """
    edges = cv2.Canny(gray, 50, 150)

    # Detect horizontal and vertical lines
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))

    h_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, h_kernel)
    v_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, v_kernel)

    combined = cv2.bitwise_or(h_lines, v_lines)
    return np.count_nonzero(combined) / combined.size


def _ensure_bookend_frames(
    info: VideoInfo,
    results: list[dict],
    output_path: Path,
    prefix: str,
    annotate: bool,
) -> list[dict]:
    """Ensure first and last frames are captured if not already present."""
    timestamps_present = {r["timestamp"] for r in results}

    bookends = []
    # First frame
    if 0.0 not in timestamps_present and not any(t < 1.0 for t in timestamps_present):
        info.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ret, frame = info.cap.read()
        if ret and frame is not None:
            if annotate:
                frame = _annotate_frame_cv(frame, 0.0, info, reason="first_frame")
            fname = f"{prefix}_000000_0.00s.{DEFAULT_IMAGE_FORMAT}"
            fpath = output_path / fname
            cv2.imwrite(str(fpath), frame)
            bookends.insert(0, {
                "timestamp": 0.0,
                "frame_number": 0,
                "path": str(fpath),
                "hash": _hash_frame(frame),
                "width": frame.shape[1],
                "height": frame.shape[0],
                "reason": "first_frame",
            })

    # Last frame
    last_ts = info.duration_secs - 0.1
    if last_ts > 0 and not any(t > (info.duration_secs - 2.0) for t in timestamps_present):
        last_frame_num = max(0, info.frame_count - 2)
        info.cap.set(cv2.CAP_PROP_POS_FRAMES, last_frame_num)
        ret, frame = info.cap.read()
        if ret and frame is not None:
            if annotate:
                frame = _annotate_frame_cv(frame, last_ts, info, reason="last_frame")
            fname = f"{prefix}_{last_frame_num:06d}_{last_ts:.2f}s.{DEFAULT_IMAGE_FORMAT}"
            fpath = output_path / fname
            cv2.imwrite(str(fpath), frame)
            bookends.append({
                "timestamp": round(last_ts, 3),
                "frame_number": last_frame_num,
                "path": str(fpath),
                "hash": _hash_frame(frame),
                "width": frame.shape[1],
                "height": frame.shape[0],
                "reason": "last_frame",
            })

    # Merge and sort
    all_frames = bookends[:1] + results + bookends[1:]
    all_frames.sort(key=lambda x: x["timestamp"])
    return all_frames


# --- Module API Summary -----------------------------------------------------

__all__ = [
    "VideoInfo",
    "VideoError",
    "EvidenceSession",
    "extract_frames_at_timestamps",
    "extract_frames_at_times",
    "extract_frames_at_dates",
    "detect_evidence_frames",
    "generate_contact_sheet",
    "generate_evidence_report",
    "fetch_video_from_github",
    "deduplicate_frames",
    "search_video",
    "reconstruct_clip",
    "analyze_image",
]
