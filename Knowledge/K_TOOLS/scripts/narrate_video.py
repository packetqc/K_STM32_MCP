#!/usr/bin/env python3
"""
Narrate Video — Chat-style proof narration
=============================================

Reads interaction_results.json and composites a two-sided chat panel
onto the proof.mp4 recording:

  LEFT bubbles  = Tester actions (clicks, asserts, waits)
  RIGHT bubbles = Page responses (✓ pass, ✗ fail, check results)

Check rows get a highlighted banner spanning the full panel width.

Usage:
    python3 scripts/narrate_video.py \
        --assets-dir docs/publications/test-slug/assets/

    python3 scripts/narrate_video.py \
        --results interaction_results.json \
        --video proof.mp4 \
        -o proof-narrated.mp4
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont


# ═══════════════════════════════════════════════════════════════════════
# Layout constants
# ═══════════════════════════════════════════════════════════════════════

PANEL_W = 420          # chat panel width
PANEL_BG = (245, 243, 238)  # warm light background
SEP_COLOR = (200, 190, 175)

# Bubble styles — daltonism-safe: blue vs orange (not red vs green)
BUBBLE_RADIUS = 10
LEFT_BG = (220, 232, 245)      # tester bubble (light blue)
RIGHT_BG = (215, 235, 250)    # pass result bubble (pale blue)
RIGHT_FAIL_BG = (255, 225, 175) # fail result bubble (light amber)
CHECK_BG = (190, 220, 250)    # check banner pass (blue)
CHECK_FAIL_BG = (255, 210, 150) # check banner fail (amber)
LEFT_FG = (30, 50, 80)        # tester text (dark blue)
RIGHT_FG = (15, 60, 110)      # pass result text (blue)
RIGHT_FAIL_FG = (140, 70, 0)  # fail result text (dark orange)
CHECK_FG = (0, 55, 120)       # check pass text (bold blue)
CHECK_FAIL_FG = (160, 65, 0)  # check fail text (dark orange)
TITLE_FG = (100, 95, 85)
MUTED_FG = (140, 135, 125)

# Sizes
FONT_SIZE = 13
CHECK_FONT_SIZE = 14
TITLE_FONT_SIZE = 14
BUBBLE_PAD_X = 10
BUBBLE_PAD_Y = 5
BUBBLE_GAP = 4          # vertical gap between bubbles
CHECK_GAP = 8            # extra gap around checks
MAX_BUBBLE_W = 190       # max bubble width (each side)
MARGIN_X = 8             # left/right margins
PANEL_MID = PANEL_W // 2


# ═══════════════════════════════════════════════════════════════════════
# Drawing helpers
# ═══════════════════════════════════════════════════════════════════════

def get_font(size=FONT_SIZE):
    """Get a monospace or sans font."""
    for path in [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
    ]:
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def wrap_text(text, font, max_width):
    """Word-wrap text to fit within max_width pixels."""
    words = text.split()
    lines = []
    current = ''
    for word in words:
        test = current + (' ' if current else '') + word
        bbox = font.getbbox(test)
        w = bbox[2] - bbox[0]
        if w > max_width and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    return lines or ['']


def draw_rounded_rect(draw, xy, radius, fill):
    """Draw a rounded rectangle."""
    x0, y0, x1, y1 = xy
    r = min(radius, (x1 - x0) // 2, (y1 - y0) // 2)
    draw.rounded_rectangle(xy, radius=r, fill=fill)


def render_bubble(draw, text, font, x, y, max_w, bg, fg, align='left'):
    """Render a chat bubble with wrapped text. Returns total height used."""
    lines = wrap_text(text, font, max_w - 2 * BUBBLE_PAD_X)
    line_h = font.getbbox('Ay')[3] - font.getbbox('Ay')[1] + 2

    text_h = len(lines) * line_h
    bubble_h = text_h + 2 * BUBBLE_PAD_Y

    # Calculate bubble width from longest line
    max_line_w = max(font.getbbox(l)[2] - font.getbbox(l)[0] for l in lines)
    bubble_w = min(max_line_w + 2 * BUBBLE_PAD_X, max_w)

    # Position bubble
    if align == 'right':
        bx = x + max_w - bubble_w
    else:
        bx = x

    draw_rounded_rect(draw, (bx, y, bx + bubble_w, y + bubble_h),
                       BUBBLE_RADIUS, bg)

    # Draw text lines
    ty = y + BUBBLE_PAD_Y
    for line in lines:
        draw.text((bx + BUBBLE_PAD_X, ty), line, font=font, fill=fg)
        ty += line_h

    return bubble_h


def render_check_banner(draw, text, font, y, panel_w, bg, fg):
    """Render a full-width check banner. Returns height used."""
    lines = wrap_text(text, font, panel_w - 2 * BUBBLE_PAD_X - 2 * MARGIN_X)
    line_h = font.getbbox('Ay')[3] - font.getbbox('Ay')[1] + 2
    text_h = len(lines) * line_h
    banner_h = text_h + 2 * BUBBLE_PAD_Y + 2

    draw_rounded_rect(draw,
                       (MARGIN_X, y, panel_w - MARGIN_X, y + banner_h),
                       BUBBLE_RADIUS, bg)

    ty = y + BUBBLE_PAD_Y + 1
    for line in lines:
        draw.text((MARGIN_X + BUBBLE_PAD_X, ty), line, font=font, fill=fg)
        ty += line_h

    return banner_h


# ═══════════════════════════════════════════════════════════════════════
# Chat panel compositor
# ═══════════════════════════════════════════════════════════════════════

def _render_step_bubble(draw, step, font, check_font, y):
    """Render a single step bubble. Returns height used."""
    action = step.get('action', '')
    desc = step.get('description', '')
    status = step.get('status', 'ok')
    is_check = action == 'capture'
    is_action = action in ('click_selector', 'evaluate_js', 'wait')
    ok = status == 'ok'

    if is_check:
        y += CHECK_GAP // 2
        mark = '✓' if ok else '✗'
        bg = CHECK_BG if ok else CHECK_FAIL_BG
        fg = CHECK_FG if ok else CHECK_FAIL_FG
        h = render_check_banner(draw, f'{mark}  {desc}', check_font,
                                y, PANEL_W, bg, fg)
        return h + CHECK_GAP
    elif is_action:
        h = render_bubble(draw, f'▸ {desc}', font,
                          MARGIN_X, y, MAX_BUBBLE_W,
                          LEFT_BG, LEFT_FG, align='left')
        return h + BUBBLE_GAP
    else:
        mark = '✓' if ok else '✗'
        bg = RIGHT_BG if ok else RIGHT_FAIL_BG
        fg = RIGHT_FG if ok else RIGHT_FAIL_FG
        h = render_bubble(draw, f'{mark} {desc}', font,
                          PANEL_MID, y, MAX_BUBBLE_W,
                          bg, fg, align='right')
        return h + BUBBLE_GAP


def _render_completed_check(draw, check_step, font, y):
    """Render a compact one-line summary for a completed check. Returns height."""
    desc = check_step.get('description', '')
    ok = check_step.get('status', 'ok') == 'ok'
    mark = '✓' if ok else '✗'
    fg = CHECK_FG if ok else CHECK_FAIL_FG
    # Compact: just the check result, no child steps
    text = f'{mark} {desc}'
    lines = wrap_text(text, font, PANEL_W - 2 * MARGIN_X - 2 * BUBBLE_PAD_X)
    line_h = font.getbbox('Ay')[3] - font.getbbox('Ay')[1] + 2
    for line in lines:
        draw.text((MARGIN_X + BUBBLE_PAD_X, y), line, font=font, fill=fg)
        y += line_h
    return len(lines) * line_h + 2


def build_chat_frames(steps, panel_h):
    """Build chat panel images with accumulating chat history.

    Previous check groups are shown as compact one-line summaries.
    The current group renders progressively with full bubbles.
    Chat accumulates — nothing disappears.

    Returns list of (start_ts, end_ts, PIL.Image) tuples.
    """
    font = get_font(FONT_SIZE)
    check_font = get_font(CHECK_FONT_SIZE)
    title_font = get_font(TITLE_FONT_SIZE)
    compact_font = get_font(FONT_SIZE - 1)

    # Group steps by check
    groups = []
    current = []
    for s in steps:
        current.append(s)
        if s.get('action') == 'capture':
            groups.append(current)
            current = []
    if current:
        groups.append(current)

    frames = []

    for gi, group in enumerate(groups):
        check_step = group[-1] if group[-1].get('action') == 'capture' else None
        group_end = (check_step.get('video_ts', 0) + 1.5) if check_step else (group[-1].get('video_ts', 0) + 3)

        # Render progressive frames for current group
        for step_idx in range(len(group)):
            visible_steps = group[:step_idx + 1]
            ts = visible_steps[-1].get('video_ts', 0)

            # Next step timestamp or group end
            if step_idx + 1 < len(group):
                next_ts = group[step_idx + 1].get('video_ts', ts + 0.5)
                if next_ts - ts < 0.15:
                    next_ts = ts + 0.15
            else:
                next_ts = group_end

            # Create panel image
            panel = Image.new('RGBA', (PANEL_W, panel_h), PANEL_BG + (255,))
            draw = ImageDraw.Draw(panel)

            # Title
            title = f'QA Test Log  —  CHECK {gi + 1}/{len(groups)}'
            draw.text((MARGIN_X + 4, 6), title, font=title_font, fill=TITLE_FG)

            # Separator line
            draw.line([(PANEL_W - 1, 0), (PANEL_W - 1, panel_h)], fill=SEP_COLOR, width=1)

            y = 30

            # ── Completed previous groups (compact summaries) ──
            for prev_gi in range(gi):
                prev_group = groups[prev_gi]
                prev_check = prev_group[-1] if prev_group[-1].get('action') == 'capture' else None
                if prev_check:
                    h = _render_completed_check(draw, prev_check, compact_font, y)
                    y += h

            # Small divider if we have history
            if gi > 0:
                y += 4
                draw.line([(MARGIN_X, y), (PANEL_W - MARGIN_X, y)],
                          fill=SEP_COLOR, width=1)
                y += 6

            # ── Current group (progressive bubbles) ──
            for s in visible_steps:
                h = _render_step_bubble(draw, s, font, check_font, y)
                y += h

            frames.append((ts, next_ts, panel))

    return frames


# ═══════════════════════════════════════════════════════════════════════
# Video compositor
# ═══════════════════════════════════════════════════════════════════════

def narrate_video(results_path, video_path, output_path):
    """Compose chat-style narration panel onto proof video."""

    with open(results_path) as f:
        data = json.load(f)

    steps = data.get('steps', [])
    if not steps:
        print("ERROR: No steps in results")
        return False

    # Get video dimensions
    probe = subprocess.run([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,r_frame_rate',
        '-of', 'csv=p=0', video_path
    ], capture_output=True, text=True)
    parts = probe.stdout.strip().split(',')
    vid_w, vid_h = int(parts[0]), int(parts[1])
    fps_parts = parts[2].split('/')
    fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else float(fps_parts[0])

    print(f"  Video: {vid_w}x{vid_h} @ {fps:.1f}fps")
    print(f"  Panel: {PANEL_W}px chat sidebar")

    # Build chat frames
    chat_frames = build_chat_frames(steps, vid_h)
    print(f"  Chat frames: {len(chat_frames)}")

    # Export chat frames as PNGs to temp dir
    tmp_dir = tempfile.mkdtemp(prefix='narrate_')
    frame_files = []
    for i, (start_ts, end_ts, panel) in enumerate(chat_frames):
        path = os.path.join(tmp_dir, f'chat_{i:04d}.png')
        panel.save(path)
        frame_files.append((start_ts, end_ts, path))

    # Build ffmpeg filter: pad video + overlay chat frames at their timestamps
    out_w = vid_w + PANEL_W
    pad = f"[0:v]pad={out_w}:{vid_h}:{PANEL_W}:0:color=#{PANEL_BG[0]:02x}{PANEL_BG[1]:02x}{PANEL_BG[2]:02x}[padded]"

    # Build overlay chain
    inputs = ['-i', video_path]
    for i, (_, _, path) in enumerate(frame_files):
        inputs.extend(['-i', path])

    filter_parts = [pad]
    prev = 'padded'

    for i, (start_ts, end_ts, _) in enumerate(frame_files):
        inp_idx = i + 1  # 0 is the video
        out_label = f'v{i}'
        filter_parts.append(
            f"[{prev}][{inp_idx}:v]overlay=0:0:enable='between(t,{start_ts:.3f},{end_ts:.3f})'[{out_label}]"
        )
        prev = out_label

    filter_complex = ';'.join(filter_parts)

    cmd = ['ffmpeg', '-y'] + inputs + [
        '-filter_complex', filter_complex,
        '-map', f'[{prev}]',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
        output_path
    ]

    print(f"  Compositing...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Cleanup temp files
    for _, _, path in frame_files:
        try:
            os.unlink(path)
        except OSError:
            pass
    try:
        os.rmdir(tmp_dir)
    except OSError:
        pass

    if result.returncode != 0:
        print(f"  ffmpeg error: {result.stderr[-500:]}")
        return False

    size = os.path.getsize(output_path) if os.path.isfile(output_path) else 0
    print(f"  Output: {output_path} ({size // 1024} KB)")
    return True


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Narrate Video — chat-style proof narration')
    parser.add_argument('--results', help='Path to interaction_results.json')
    parser.add_argument('--video', help='Path to input proof.mp4')
    parser.add_argument('-o', '--output', help='Output path')
    parser.add_argument('--assets-dir', help='Auto-detect from assets directory')
    args = parser.parse_args()

    if args.assets_dir:
        results_path = os.path.join(args.assets_dir, 'interaction_results.json')
        video_path = os.path.join(args.assets_dir, 'proof.mp4')
        output_path = os.path.join(args.assets_dir, 'proof-narrated.mp4')
    else:
        results_path = args.results
        video_path = args.video
        output_path = args.output

    if not results_path or not video_path:
        print("ERROR: Provide --results + --video, or --assets-dir")
        sys.exit(1)

    if not output_path:
        base, ext = os.path.splitext(video_path)
        output_path = f'{base}-narrated{ext}'

    if not os.path.isfile(results_path):
        print(f"ERROR: {results_path} not found")
        sys.exit(1)
    if not os.path.isfile(video_path):
        print(f"ERROR: {video_path} not found")
        sys.exit(1)

    ok = narrate_video(results_path, video_path, output_path)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
