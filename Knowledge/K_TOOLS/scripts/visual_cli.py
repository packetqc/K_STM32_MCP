#!/usr/bin/env python3
"""
Visual CLI — Command-line interface for the Visual Documentation Engine
=======================================================================

Entry point for the Knowledge System's `visual` command.
Parses arguments and dispatches to visual_engine.py functions.

Usage:
  python3 scripts/visual_cli.py <video-path> [options]
  python3 scripts/visual_cli.py --repo owner/repo --file path/to/video.mp4 [options]

Modes:
  Timestamp mode:  --timestamps 10.5 30.0 60.0
  Time mode:       --times 00:01:30 00:05:00 --video-start 00:00:00
  Date mode:       --dates "2026-03-01 14:30:00" --video-start-datetime "2026-03-01 14:00:00"
  Detection mode:  --detect [--subjects keyword1 keyword2] [--sensitivity 0.35]

Output:
  --output-dir     Directory for extracted frames (default: /tmp/visual_evidence/)
  --report         Generate markdown evidence report
  --sheet          Generate contact sheet (thumbnail grid)
  --dedup          Deduplicate near-identical frames before output

Knowledge asset — part of the Visuals command category.

Related:
  - scripts/visual_engine.py — core processing engine
  - methodology/methodology-documentation-visual.md — full specification
  - Publication #22 — Visual Documentation
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Import visual_engine from same directory
from visual_engine import (
    EvidenceSession,
    VideoError,
    VideoInfo,
    analyze_image,
    deduplicate_frames,
    detect_evidence_frames,
    extract_frames_at_dates,
    extract_frames_at_times,
    extract_frames_at_timestamps,
    fetch_video_from_github,
    generate_contact_sheet,
    generate_evidence_report,
    reconstruct_clip,
    search_video,
)

# --- Logging ----------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("visual_cli")


# --- Argument Parser --------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="visual",
        description="Visual Documentation Engine — extract evidence frames from video recordings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  # Extract frames at specific timestamps (seconds)
  visual recording.mp4 --timestamps 10.5 30.0 60.0

  # Extract frames at clock times
  visual recording.mp4 --times 00:01:30 00:05:00

  # Detection mode — scan for significant frames
  visual recording.mp4 --detect

  # Detection mode with subject filtering
  visual recording.mp4 --detect --subjects "UART" "error" "timeout"

  # From GitHub repository
  visual --repo packetqc/stm32-poc --file live/dynamic/clip_0.mp4 --detect

  # Full pipeline: detect + dedup + report + contact sheet
  visual recording.mp4 --detect --dedup --report --sheet

  # Search mode — multi-criteria search directly on video
  visual recording.mp4 --search --scene-change --min-text 0.15

  # Search with time ranges
  visual recording.mp4 --search --time-range 30 60 --time-range 120 180

  # Reconstruct a clip around a specific timestamp (±10 seconds)
  visual recording.mp4 --clip 45.0 --context 10

  # Analyze a single image
  visual --image screenshot.png

  # Full evidence session with organized output
  visual recording.mp4 --search --evidence --session-name demo-2026
""",
    )

    # --- Source (mutually exclusive: local file vs GitHub repo) ---
    source = parser.add_argument_group("Video source")
    source.add_argument(
        "video_path",
        nargs="?",
        help="Path to local video file",
    )
    source.add_argument(
        "--repo",
        metavar="OWNER/REPO",
        help="GitHub repository (e.g., packetqc/stm32-poc)",
    )
    source.add_argument(
        "--file",
        metavar="PATH",
        dest="repo_file",
        help="File path within the GitHub repo",
    )
    source.add_argument(
        "--ref",
        default="main",
        help="Branch or tag for GitHub fetch (default: main)",
    )

    # --- Timestamp mode ---
    ts_group = parser.add_argument_group("Timestamp mode")
    ts_group.add_argument(
        "--timestamps", "-t",
        nargs="+",
        type=float,
        metavar="SEC",
        help="Extract frames at these timestamps (seconds from start)",
    )
    ts_group.add_argument(
        "--times",
        nargs="+",
        metavar="HH:MM:SS",
        help="Extract frames at these clock times",
    )
    ts_group.add_argument(
        "--dates",
        nargs="+",
        metavar="DATETIME",
        help="Extract frames at these date-times (YYYY-MM-DD HH:MM:SS)",
    )
    ts_group.add_argument(
        "--video-start",
        metavar="HH:MM:SS",
        help="Video recording start time (for --times offset calculation)",
    )
    ts_group.add_argument(
        "--video-start-datetime",
        metavar="DATETIME",
        help="Video recording start datetime (for --dates offset calculation)",
    )

    # --- Detection mode ---
    det_group = parser.add_argument_group("Detection mode")
    det_group.add_argument(
        "--detect", "-d",
        action="store_true",
        help="Scan video for significant frames automatically",
    )
    det_group.add_argument(
        "--subjects", "-s",
        nargs="+",
        metavar="KEYWORD",
        help="Subject keywords for content-aware detection",
    )
    det_group.add_argument(
        "--sensitivity",
        type=float,
        default=0.35,
        metavar="FLOAT",
        help="Detection sensitivity 0-1, lower=more sensitive (default: 0.35)",
    )
    det_group.add_argument(
        "--interval",
        type=float,
        default=1.0,
        metavar="SEC",
        help="Minimum interval between detections in seconds (default: 1.0)",
    )
    det_group.add_argument(
        "--max-frames",
        type=int,
        default=50,
        metavar="N",
        help="Maximum frames to extract in detection mode (default: 50)",
    )

    # --- Search mode ---
    search_group = parser.add_argument_group("Search mode (multi-criteria, multi-pass)")
    search_group.add_argument(
        "--search",
        action="store_true",
        help="Multi-criteria search mode — scan video with combined criteria",
    )
    search_group.add_argument(
        "--scene-change",
        action="store_true",
        help="Include scene change detection in search criteria",
    )
    search_group.add_argument(
        "--min-text",
        type=float,
        default=0,
        metavar="FLOAT",
        help="Minimum text density threshold for search (e.g., 0.15)",
    )
    search_group.add_argument(
        "--min-edge",
        type=float,
        default=0,
        metavar="FLOAT",
        help="Minimum edge density threshold for search (e.g., 0.12)",
    )
    search_group.add_argument(
        "--structured",
        action="store_true",
        help="Include structured content detection in search",
    )
    search_group.add_argument(
        "--time-range",
        nargs=2,
        type=float,
        action="append",
        metavar=("START", "END"),
        help="Time range to search within (seconds). Can be repeated.",
    )
    search_group.add_argument(
        "--context",
        type=float,
        default=10.0,
        metavar="SEC",
        help="Context seconds for clip reconstruction around findings (default: 10)",
    )
    search_group.add_argument(
        "--no-clips",
        action="store_true",
        help="Skip clip reconstruction (only extract evidence frames)",
    )

    # --- Clip reconstruction ---
    clip_group = parser.add_argument_group("Clip reconstruction")
    clip_group.add_argument(
        "--clip",
        type=float,
        metavar="SEC",
        help="Reconstruct a clip centered at this timestamp (seconds)",
    )

    # --- Image analysis ---
    img_group = parser.add_argument_group("Image analysis")
    img_group.add_argument(
        "--image",
        metavar="PATH",
        help="Analyze a single image for evidence matching",
    )

    # --- Evidence session ---
    ev_group = parser.add_argument_group("Evidence session")
    ev_group.add_argument(
        "--evidence",
        action="store_true",
        help="Use organized evidence directory structure",
    )
    ev_group.add_argument(
        "--session-name",
        metavar="NAME",
        help="Custom name for the evidence session directory",
    )

    # --- Output options ---
    out_group = parser.add_argument_group("Output")
    out_group.add_argument(
        "--output-dir", "-o",
        default="/tmp/visual_evidence",
        metavar="DIR",
        help="Output directory for extracted frames (default: /tmp/visual_evidence/)",
    )
    out_group.add_argument(
        "--prefix",
        default="evidence",
        help="Filename prefix for output images (default: evidence)",
    )
    out_group.add_argument(
        "--no-annotate",
        action="store_true",
        help="Skip timestamp annotation on extracted frames",
    )
    out_group.add_argument(
        "--dedup",
        action="store_true",
        help="Deduplicate near-identical frames",
    )
    out_group.add_argument(
        "--dedup-threshold",
        type=float,
        default=0.92,
        metavar="FLOAT",
        help="Deduplication similarity threshold 0-1 (default: 0.92)",
    )

    # --- Report generation ---
    report_group = parser.add_argument_group("Reports")
    report_group.add_argument(
        "--report",
        nargs="?",
        const="auto",
        metavar="PATH",
        help="Generate markdown evidence report (default: auto-named in output dir)",
    )
    report_group.add_argument(
        "--sheet",
        nargs="?",
        const="auto",
        metavar="PATH",
        help="Generate contact sheet image (default: auto-named in output dir)",
    )
    report_group.add_argument(
        "--sheet-cols",
        type=int,
        default=4,
        metavar="N",
        help="Contact sheet columns (default: 4)",
    )
    report_group.add_argument(
        "--title",
        default="Visual Evidence Report",
        help="Title for report and contact sheet",
    )
    report_group.add_argument(
        "--description",
        default="",
        help="Description/context for the evidence report",
    )

    # --- Output format ---
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON to stdout",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Show video info only (no extraction)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose logging output",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress all output except errors",
    )

    return parser


# --- Main Logic -------------------------------------------------------------

def resolve_video_source(args) -> str:
    """Resolve video path from local file or GitHub repo."""
    if args.video_path:
        path = Path(args.video_path)
        if not path.exists():
            raise VideoError(f"Video file not found: {args.video_path}")
        return str(path.resolve())

    if args.repo and args.repo_file:
        logger.info(f"Fetching video from GitHub: {args.repo}/{args.repo_file}")
        return fetch_video_from_github(
            repo=args.repo,
            file_path=args.repo_file,
            ref=args.ref,
            output_dir=args.output_dir,
        )

    raise VideoError(
        "No video source specified. Provide a local path or --repo/--file for GitHub."
    )


def run(args) -> dict:
    """Execute the visual command and return results."""
    # --- Image analysis mode (no video needed) ---
    if args.image:
        logger.info(f"Image analysis: {args.image}")
        criteria = {}
        if args.min_text > 0:
            criteria["min_text_density"] = args.min_text
        if args.min_edge > 0:
            criteria["min_edge_density"] = args.min_edge
        if args.structured:
            criteria["structured_content"] = True

        result = analyze_image(
            args.image,
            criteria=criteria if criteria else None,
            output_dir=args.output_dir,
        )
        return {"image_analysis": result, "frames": []}

    # --- Clip-only reconstruction (no search needed) ---
    if args.clip is not None and not args.search:
        video_path = resolve_video_source(args)
        logger.info(f"Clip reconstruction at {args.clip:.1f}s ±{args.context:.0f}s")
        clip_path = reconstruct_clip(
            video_path,
            center_timestamp=args.clip,
            context_secs=args.context,
            output_dir=args.output_dir,
        )
        return {
            "video_path": video_path,
            "clip": clip_path,
            "center": args.clip,
            "context_secs": args.context,
            "frames": [],
        }

    video_path = resolve_video_source(args)
    annotate = not args.no_annotate

    # Info-only mode
    if args.info:
        info = VideoInfo(video_path)
        result = {
            "path": str(info.path),
            "width": info.width,
            "height": info.height,
            "fps": info.fps,
            "frame_count": info.frame_count,
            "duration_secs": round(info.duration_secs, 3),
            "codec": info.codec,
        }
        info.close()
        return {"video_info": result, "frames": []}

    frames = []

    # --- Search mode (multi-criteria, multi-pass) ---
    if args.search:
        criteria = {}
        if args.timestamps:
            criteria["timestamps"] = args.timestamps
        if args.time_range:
            criteria["time_ranges"] = [tuple(r) for r in args.time_range]
        if args.scene_change:
            criteria["scene_change"] = True
        if args.min_text > 0:
            criteria["min_text_density"] = args.min_text
        if args.min_edge > 0:
            criteria["min_edge_density"] = args.min_edge
        if args.structured:
            criteria["structured_content"] = True

        # Default: at least scene change + text if no criteria specified
        if not criteria:
            criteria["scene_change"] = True
            criteria["min_text_density"] = 0.15

        context = 0 if args.no_clips else args.context

        logger.info(f"Search mode: {len(criteria)} criteria, context={context}s")
        search_result = search_video(
            video_path,
            criteria=criteria,
            output_dir=args.output_dir if args.evidence else None,
            context_secs=context,
            session_name=args.session_name,
        )

        # Convert findings to frames format for report/sheet compatibility
        for f in search_result.get("findings", []):
            if "discovery_path" in f:
                f["path"] = f["discovery_path"]
            frames.append(f)

        result = {
            "video_path": video_path,
            "output_dir": search_result.get("session", args.output_dir),
            "mode": "search",
            "frames_extracted": len(frames),
            "frames": frames,
            "search": search_result,
        }

        if not args.json and not args.quiet:
            print_search_summary(search_result)

        return result

    # --- Extraction mode selection ---
    if args.timestamps:
        logger.info(f"Timestamp mode: {len(args.timestamps)} timestamps")
        frames = extract_frames_at_timestamps(
            video_path, args.timestamps, args.output_dir,
            prefix=args.prefix, annotate=annotate,
        )

    elif args.times:
        logger.info(f"Time mode: {len(args.times)} times")
        frames = extract_frames_at_times(
            video_path, args.times, args.output_dir,
            video_start_time=args.video_start,
            prefix=args.prefix, annotate=annotate,
        )

    elif args.dates:
        logger.info(f"Date mode: {len(args.dates)} date-times")
        frames = extract_frames_at_dates(
            video_path, args.dates, args.output_dir,
            video_start_datetime=args.video_start_datetime,
            prefix=args.prefix, annotate=annotate,
        )

    elif args.detect:
        logger.info(f"Detection mode: sensitivity={args.sensitivity}, interval={args.interval}s")
        frames = detect_evidence_frames(
            video_path, args.output_dir,
            subjects=args.subjects,
            sensitivity=args.sensitivity,
            interval_secs=args.interval,
            max_frames=args.max_frames,
            prefix=args.prefix, annotate=annotate,
        )

    else:
        # Default: detection mode if no explicit mode specified
        logger.info("No mode specified — defaulting to detection mode")
        frames = detect_evidence_frames(
            video_path, args.output_dir,
            prefix=args.prefix, annotate=annotate,
        )

    # --- Deduplication ---
    if args.dedup and len(frames) > 1:
        frames = deduplicate_frames(frames, threshold=args.dedup_threshold)

    # --- Report generation ---
    report_path = None
    if args.report is not None:
        if args.report == "auto":
            report_path = str(Path(args.output_dir) / "evidence_report.md")
        else:
            report_path = args.report
        generate_evidence_report(
            frames, video_path, report_path,
            title=args.title, description=args.description,
        )

    # --- Contact sheet ---
    sheet_path = None
    if args.sheet is not None:
        if args.sheet == "auto":
            sheet_path = str(Path(args.output_dir) / "contact_sheet.png")
        else:
            sheet_path = args.sheet
        if frames:
            generate_contact_sheet(
                frames, sheet_path,
                title=args.title, cols=args.sheet_cols,
            )

    # --- Build result ---
    result = {
        "video_path": video_path,
        "output_dir": args.output_dir,
        "mode": _detect_mode(args),
        "frames_extracted": len(frames),
        "frames": frames,
    }
    if report_path:
        result["report"] = report_path
    if sheet_path:
        result["contact_sheet"] = sheet_path

    return result


def _detect_mode(args) -> str:
    """Determine which extraction mode was used."""
    if args.search:
        return "search"
    if args.timestamps:
        return "timestamps"
    if args.times:
        return "times"
    if args.dates:
        return "dates"
    return "detection"


def print_search_summary(search_result: dict) -> None:
    """Print human-readable summary of search results."""
    findings = search_result.get("findings", [])
    clips = search_result.get("clips", [])
    session_dir = search_result.get("session", "")

    print(f"\n{'=' * 60}")
    print(f"  Search Results — {len(findings)} findings, {len(clips)} clips")
    print(f"{'=' * 60}")
    print(f"  Session:    {session_dir}")

    if findings:
        print(f"\n  {'#':<4} {'Timestamp':<14} {'Reasons':<35} {'File'}")
        print(f"  {'─' * 4} {'─' * 14} {'─' * 35} {'─' * 25}")
        for f in findings:
            idx = f.get("finding_id", "?")
            ts = f"{f.get('timestamp', 0):.3f}s"
            reason = f.get("reason", "")
            if len(reason) > 35:
                reason = reason[:32] + "..."
            fname = Path(f.get("discovery_path", "")).name
            print(f"  {idx:<4} {ts:<14} {reason:<35} {fname}")

    if clips:
        print(f"\n  Clips:")
        for c in clips:
            ctx = c.get("context", {})
            center = ctx.get("center_timestamp", 0)
            secs = ctx.get("context_secs", 0)
            cpath = Path(c.get("clip_path", "")).name
            print(f"    ±{secs:.0f}s around {center:.1f}s → {cpath}")

    print(f"\n{'=' * 60}\n")


def print_summary(result: dict) -> None:
    """Print human-readable summary of results."""
    print(f"\n{'=' * 60}")
    print(f"  Visual Evidence — {result['frames_extracted']} frames extracted")
    print(f"{'=' * 60}")
    print(f"  Source:     {Path(result['video_path']).name}")
    print(f"  Mode:       {result['mode']}")
    print(f"  Output:     {result['output_dir']}")

    if result.get("report"):
        print(f"  Report:     {result['report']}")
    if result.get("contact_sheet"):
        print(f"  Sheet:      {result['contact_sheet']}")

    print()
    if result["frames"]:
        print(f"  {'#':<4} {'Timestamp':<14} {'Reason':<24} {'File'}")
        print(f"  {'─' * 4} {'─' * 14} {'─' * 24} {'─' * 30}")
        for i, f in enumerate(result["frames"], 1):
            ts = f"{f['timestamp']:.3f}s"
            reason = f.get("reason", "manual")
            if "(" in reason:
                reason = reason.split("(")[0].strip()
            fname = Path(f["path"]).name
            print(f"  {i:<4} {ts:<14} {reason:<24} {fname}")

    print(f"\n{'=' * 60}\n")


# --- Entry Point ------------------------------------------------------------

def main():
    parser = build_parser()
    args = parser.parse_args()

    # Logging level
    if args.quiet:
        logging.getLogger().setLevel(logging.ERROR)
    elif args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        result = run(args)

        if args.json:
            print(json.dumps(result, indent=2, default=str))
        elif not args.quiet:
            if result.get("image_analysis"):
                analysis = result["image_analysis"]
                print(f"\n{'=' * 60}")
                print(f"  Image Analysis — {Path(analysis['path']).name}")
                print(f"{'=' * 60}")
                print(f"  Resolution: {analysis['width']}x{analysis['height']}")
                print(f"  Hash:       {analysis['hash']}")
                print(f"\n  Scores:")
                for k, v in analysis["scores"].items():
                    print(f"    {k:<25} {v:.4f}")
                print(f"\n  Evidence: {'YES' if analysis['is_evidence'] else 'NO'}")
                if analysis["matches"]:
                    for m in analysis["matches"]:
                        print(f"    ✓ {m}")
                if analysis.get("annotated_path"):
                    print(f"\n  Annotated: {analysis['annotated_path']}")
                print(f"\n{'=' * 60}\n")
            elif result.get("clip"):
                print(f"\n{'=' * 60}")
                print(f"  Clip Reconstructed")
                print(f"{'=' * 60}")
                print(f"  Center:  {result['center']:.1f}s")
                print(f"  Context: ±{result['context_secs']:.0f}s")
                print(f"  Output:  {result['clip']}")
                print(f"\n{'=' * 60}\n")
            elif result.get("video_info"):
                info = result["video_info"]
                print(f"\nVideo: {Path(info['path']).name}")
                print(f"  Resolution: {info['width']}x{info['height']}")
                print(f"  FPS:        {info['fps']:.1f}")
                print(f"  Frames:     {info['frame_count']}")
                print(f"  Duration:   {info['duration_secs']:.1f}s")
                print(f"  Codec:      {info['codec']}")
            else:
                print_summary(result)

    except VideoError as e:
        logger.error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Interrupted")
        sys.exit(130)


if __name__ == "__main__":
    main()
