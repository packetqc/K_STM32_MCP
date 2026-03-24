#!/usr/bin/env python3
"""
Generate Test Report Webcard — 1200x630 animated OG GIF
========================================================
Creates a proper social media webcard from test report proof frames.
Scales 1920x1080 test screenshots to 1200x630 with chrome bars and
test result overlay.

Usage:
  # From proof.gif (extract frames automatically):
  python3 Knowledge/K_TOOLS/scripts/generate_test_webcard.py \\
      --proof docs/publications/test-main-navigator/assets/proof.gif \\
      --title "Main Navigator — Default Test" \\
      --results "7/14 pass" \\
      --output docs/assets/og/test-main-navigator-en-cayman.gif

  # From frame directory:
  python3 Knowledge/K_TOOLS/scripts/generate_test_webcard.py \\
      --frames /tmp/test-frames/ \\
      --title "Main Navigator — Complete Test" \\
      --results "110/110 pass" \\
      --output docs/assets/og/test-main-navigator-en-cayman.gif
"""

import argparse
import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Error: Pillow required. Install: pip3 install pillow")
    sys.exit(1)

CARD_W, CARD_H = 1200, 630
BAR_H = 40
BOT_H = 28

THEMES = {
    "cayman": {
        "bg": "#eff6ff", "accent": "#1d4ed8",
        "gradient_top": "#0d9488", "gradient_bot": "#1d4ed8",
        "pass_color": "#059669", "fail_color": "#dc2626",
        "text": "#ffffff", "muted": "#c7d2fe",
    },
    "midnight": {
        "bg": "#0f172a", "accent": "#60a5fa",
        "gradient_top": "#1e3a5f", "gradient_bot": "#0f172a",
        "pass_color": "#34d399", "fail_color": "#fb7185",
        "text": "#e2e8f0", "muted": "#94a3b8",
    },
}


def hex_rgb(h):
    return tuple(int(h.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))


def blend(c1, c2, t):
    return tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3))


def add_chrome(frame_img, title, results, theme_name, frame_num, total):
    """Add header/footer chrome bars to a test screenshot."""
    T = THEMES[theme_name]
    gt = hex_rgb(T["gradient_top"])
    gb = hex_rgb(T["gradient_bot"])
    accent = hex_rgb(T["accent"])
    text_c = hex_rgb(T["text"])
    muted_c = hex_rgb(T["muted"])

    card = Image.new("RGB", (CARD_W, CARD_H), hex_rgb(T["bg"]))
    draw = ImageDraw.Draw(card)

    # Top gradient bar
    for y in range(BAR_H):
        draw.line([(0, y), (CARD_W, y)], fill=blend(gt, gb, y / BAR_H))

    # Bottom bar
    bot_y = CARD_H - BOT_H
    draw.rectangle([(0, bot_y), (CARD_W, CARD_H)], fill=accent)

    # Fonts
    try:
        f_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
        f_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
        f_result = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
    except (IOError, OSError):
        f_title = f_small = f_result = ImageFont.load_default()

    # Top bar text
    draw.text((14, 10), f"TEST — {title}", fill=text_c, font=f_title)

    # Result badge on top bar (right side)
    if results:
        # Parse pass/total
        badge_text = f"Result: {results}"
        is_pass = "pass" in results.lower()
        badge_color = hex_rgb(T["pass_color"]) if is_pass else hex_rgb(T["fail_color"])
        # Badge background
        bbox = draw.textbbox((0, 0), badge_text, font=f_result)
        bw = bbox[2] - bbox[0] + 16
        bx = CARD_W - bw - 10
        draw.rounded_rectangle([(bx, 8), (bx + bw, 32)], radius=4, fill=badge_color)
        draw.text((bx + 8, 10), badge_text, fill=(255, 255, 255), font=f_result)

    # Bottom bar text
    draw.text((14, bot_y + 6), "packetqc/knowledge", fill=text_c, font=f_small)
    progress = f"Frame {frame_num + 1}/{total}"
    draw.text((CARD_W - 140, bot_y + 6), progress, fill=muted_c, font=f_small)

    # Paste screenshot into content area
    content_h = CARD_H - BAR_H - BOT_H
    frame_resized = frame_img.resize((CARD_W, content_h), Image.LANCZOS)
    card.paste(frame_resized, (0, BAR_H))

    return card


def extract_gif_frames(gif_path):
    """Extract all frames from an animated GIF."""
    img = Image.open(gif_path)
    frames = []
    try:
        while True:
            frames.append(img.copy().convert("RGB"))
            img.seek(img.tell() + 1)
    except EOFError:
        pass
    return frames


def main():
    parser = argparse.ArgumentParser(description="Generate test report webcard GIF")
    parser.add_argument("--proof", help="Path to proof.gif (extract frames)")
    parser.add_argument("--frames", help="Path to directory with frame PNGs")
    parser.add_argument("--title", required=True, help="Test report title")
    parser.add_argument("--results", default="", help="Result summary (e.g. '7/14 pass')")
    parser.add_argument("--theme", default="cayman", choices=list(THEMES.keys()))
    parser.add_argument("--output", required=True, help="Output GIF path")
    parser.add_argument("--duration", type=int, default=2000, help="Frame duration in ms")
    parser.add_argument("--hold", type=int, default=4000, help="Last frame hold in ms")
    args = parser.parse_args()

    # Load frames
    if args.proof:
        print(f"Extracting frames from {args.proof}...")
        source_frames = extract_gif_frames(args.proof)
    elif args.frames:
        frame_dir = Path(args.frames)
        frame_files = sorted(frame_dir.glob("frame-*.png"))
        if not frame_files:
            frame_files = sorted(frame_dir.glob("*.png"))
        source_frames = [Image.open(f).convert("RGB") for f in frame_files]
    else:
        print("Error: specify --proof or --frames")
        sys.exit(1)

    if not source_frames:
        print("Error: no frames found")
        sys.exit(1)

    print(f"Processing {len(source_frames)} frames, theme={args.theme}")

    # Generate webcard frames with chrome
    cards = []
    for i, frame in enumerate(source_frames):
        card = add_chrome(frame, args.title, args.results, args.theme, i, len(source_frames))
        cards.append(card)

    # Hold final frame
    cards.append(cards[-1])

    # Quantize and save
    optimized = [c.quantize(colors=256, method=Image.Quantize.MEDIANCUT,
                            dither=Image.Dither.FLOYDSTEINBERG) for c in cards]
    durations = [args.duration] * len(source_frames) + [args.hold]

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    optimized[0].save(args.output, save_all=True, append_images=optimized[1:],
                      duration=durations, loop=0, optimize=True)

    size_kb = os.path.getsize(args.output) / 1024
    print(f"  -> {args.output} ({size_kb:.0f} KB, {len(cards)} frames, {CARD_W}x{CARD_H})")


if __name__ == "__main__":
    main()
