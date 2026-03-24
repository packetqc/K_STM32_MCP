#!/usr/bin/env python3
"""
Check Snapshot Renderer — 3-Part Annotated Proof Images
========================================================

Composes check validation snapshots from test results and raw screenshot frames.
Each snapshot is a single image with three vertical sections:

  Part 1 — Header:   Test title, check subtitle, description
  Part 2 — Evidence: Screenshot with optional annotations (circle, arrow, border)
  Part 3 — Result:   Status LED (green/yellow/red) + conclusion text

Usage:
    # Batch: generate all check snapshots from results.json
    python3 scripts/generate_check_snapshot.py \\
        --results test-reports/results.json \\
        --frames-dir test-reports/frames/ \\
        --output test-reports/checks/ \\
        --test-title "Main Navigator — Complete Test"

    # Single: generate one check snapshot
    python3 scripts/generate_check_snapshot.py \\
        --frame frame_0001.png \\
        --title "Main Navigator — Complete Test" \\
        --subtitle "Interface Claude" \\
        --description "Verify page loads in content panel" \\
        --result PASS \\
        --conclusion "Page loaded (2,451 chars)" \\
        --output check_0001_snapshot.png

    # With annotation
    python3 scripts/generate_check_snapshot.py \\
        --frame frame_0001.png \\
        --title "Main Navigator" \\
        --subtitle "Interface Claude" \\
        --result PASS \\
        --conclusion "OK" \\
        --annotate circle --ax 500 --ay 300 --ar 80 \\
        --output snapshot.png

    # Batch GIF: animated check+proof audit (2s per frame)
    python3 scripts/generate_check_snapshot.py \\
        --batch-gif test-reports/proof-steps.json \\
        --duration 2000 \\
        --output test-reports/proof-audit.gif

Knowledge asset — part of the Check Validation methodology.
"""

import argparse
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

# ─── Constants ───────────────────────────────────────────────────────────────

HEADER_HEIGHT = 120
RESULT_HEIGHT = 60
EVIDENCE_BORDER = 3
ANNOTATION_LINE_WIDTH = 3

# Colors (RGB)
HEADER_BG = (30, 41, 59)         # dark slate
HEADER_TITLE = (255, 255, 255)   # white
HEADER_SUBTITLE = (148, 163, 184) # muted blue-gray
HEADER_DESC = (203, 213, 225)    # light muted

RESULT_BG_PASS = (5, 46, 22)     # dark green
RESULT_BG_WARN = (66, 32, 6)     # dark amber
RESULT_BG_FAIL = (69, 10, 10)    # dark red
RESULT_TEXT = (255, 255, 255)    # white

LED_PASS = (22, 163, 74)         # green
LED_WARN = (217, 119, 6)         # amber
LED_FAIL = (220, 38, 38)         # red

BORDER_PASS = (22, 163, 74)
BORDER_FAIL = (220, 38, 38)
BORDER_WARN = (217, 119, 6)

ANNOTATION_COLOR = (220, 38, 38)  # red for circles/arrows


# ─── Font Loading ────────────────────────────────────────────────────────────

def _load_font(size):
    """Load a font with fallback chain."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _load_font_regular(size):
    """Load regular weight font."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


FONT_TITLE = _load_font(22)
FONT_SUBTITLE = _load_font(16)
FONT_DESC = _load_font_regular(14)
FONT_RESULT = _load_font(18)
FONT_RESULT_TEXT = _load_font_regular(14)


# ─── Part Renderers ──────────────────────────────────────────────────────────

def render_header(width, test_title, check_subtitle, description=""):
    """Render Part 1 — Header section."""
    img = Image.new('RGB', (width, HEADER_HEIGHT), HEADER_BG)
    draw = ImageDraw.Draw(img)

    y = 12
    draw.text((20, y), test_title, fill=HEADER_TITLE, font=FONT_TITLE)
    y += 30
    draw.text((20, y), check_subtitle, fill=HEADER_SUBTITLE, font=FONT_SUBTITLE)
    y += 24
    if description:
        # Truncate if too long for one line
        max_chars = width // 8
        if len(description) > max_chars:
            description = description[:max_chars - 3] + "..."
        draw.text((20, y), description, fill=HEADER_DESC, font=FONT_DESC)

    return img


def render_evidence(frame_path, result, annotations=None):
    """Render Part 2 — Evidence section (screenshot + annotations)."""
    frame = Image.open(frame_path).convert('RGB')
    w, h = frame.size

    # Add result-colored border
    border_color = BORDER_PASS if result == 'PASS' else (BORDER_WARN if result == 'WARN' else BORDER_FAIL)
    bordered = Image.new('RGB', (w + 2 * EVIDENCE_BORDER, h + 2 * EVIDENCE_BORDER), border_color)
    bordered.paste(frame, (EVIDENCE_BORDER, EVIDENCE_BORDER))

    # Draw annotations on top
    if annotations:
        draw = ImageDraw.Draw(bordered)
        for ann in annotations:
            atype = ann.get('type', '')
            if atype == 'circle':
                cx = ann.get('x', 0) + EVIDENCE_BORDER
                cy = ann.get('y', 0) + EVIDENCE_BORDER
                r = ann.get('r', 40)
                color = ann.get('color', ANNOTATION_COLOR)
                for offset in range(ANNOTATION_LINE_WIDTH):
                    draw.ellipse(
                        [cx - r - offset, cy - r - offset, cx + r + offset, cy + r + offset],
                        outline=color
                    )
            elif atype == 'arrow':
                x1 = ann.get('x1', 0) + EVIDENCE_BORDER
                y1 = ann.get('y1', 0) + EVIDENCE_BORDER
                x2 = ann.get('x2', 0) + EVIDENCE_BORDER
                y2 = ann.get('y2', 0) + EVIDENCE_BORDER
                color = ann.get('color', ANNOTATION_COLOR)
                draw.line([(x1, y1), (x2, y2)], fill=color, width=ANNOTATION_LINE_WIDTH)
                # Arrowhead (simple triangle)
                import math
                angle = math.atan2(y2 - y1, x2 - x1)
                arrow_len = 15
                for sign in [1, -1]:
                    ax = x2 - arrow_len * math.cos(angle + sign * 0.4)
                    ay = y2 - arrow_len * math.sin(angle + sign * 0.4)
                    draw.line([(x2, y2), (int(ax), int(ay))], fill=color, width=ANNOTATION_LINE_WIDTH)
            elif atype == 'rect':
                x1 = ann.get('x1', 0) + EVIDENCE_BORDER
                y1 = ann.get('y1', 0) + EVIDENCE_BORDER
                x2 = ann.get('x2', 0) + EVIDENCE_BORDER
                y2 = ann.get('y2', 0) + EVIDENCE_BORDER
                color = ann.get('color', ANNOTATION_COLOR)
                for offset in range(ANNOTATION_LINE_WIDTH):
                    draw.rectangle(
                        [x1 - offset, y1 - offset, x2 + offset, y2 + offset],
                        outline=color
                    )

    return bordered


def render_result(width, result, conclusion=""):
    """Render Part 3 — Result section."""
    if result == 'PASS':
        bg = RESULT_BG_PASS
        led = LED_PASS
    elif result == 'WARN':
        bg = RESULT_BG_WARN
        led = LED_WARN
    else:
        bg = RESULT_BG_FAIL
        led = LED_FAIL

    img = Image.new('RGB', (width, RESULT_HEIGHT), bg)
    draw = ImageDraw.Draw(img)

    # LED circle
    led_x, led_y = 20, RESULT_HEIGHT // 2
    led_r = 8
    draw.ellipse([led_x - led_r, led_y - led_r, led_x + led_r, led_y + led_r], fill=led)

    # Status text
    status_text = result
    draw.text((led_x + led_r + 12, led_y - 12), status_text, fill=RESULT_TEXT, font=FONT_RESULT)

    # Conclusion text
    if conclusion:
        status_width = FONT_RESULT.getlength(status_text) if hasattr(FONT_RESULT, 'getlength') else len(status_text) * 12
        conclusion_x = led_x + led_r + 12 + int(status_width) + 20
        # Truncate if too long
        max_chars = (width - conclusion_x) // 7
        if len(conclusion) > max_chars:
            conclusion = conclusion[:max(max_chars - 3, 10)] + "..."
        draw.text((conclusion_x, led_y - 9), f"— {conclusion}", fill=RESULT_TEXT, font=FONT_RESULT_TEXT)

    return img


# ─── Progressive Description Lookup ──────────────────────────────────────────

_DESC_REGISTRY = None

def _load_description_registry():
    """Load check_descriptions.json once (lazy)."""
    global _DESC_REGISTRY
    if _DESC_REGISTRY is not None:
        return _DESC_REGISTRY
    registry_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'check_descriptions.json')
    if os.path.isfile(registry_path):
        with open(registry_path) as f:
            _DESC_REGISTRY = json.load(f)
    else:
        _DESC_REGISTRY = {}
    return _DESC_REGISTRY


def resolve_description(check):
    """Resolve check description using progressive fallback chain:

    1. Explicit description on the check (if not generic template)
    2. Exact doc path match in registry
    3. Phase-based template in registry (with {target}/{panel} interpolation)
    4. Generic template fallback
    """
    desc = check.get('description', '')
    doc = check.get('doc', '')
    phase = check.get('phase', '')
    target = check.get('target', '?')
    panel = check.get('panel', 'panel')

    # 1. If check already has a non-generic description, use it
    generic_prefix = f"Verify {target} loads in {panel} panel"
    if desc and desc != generic_prefix:
        return desc

    reg = _load_description_registry()

    # 2. Exact doc path match
    by_doc = reg.get('by_doc', {})
    if doc in by_doc:
        return by_doc[doc]

    # 3. Phase-based template with interpolation
    by_phase = reg.get('by_phase', {})
    if phase in by_phase:
        return by_phase[phase].format(target=target, panel=panel)

    # 4. Generic fallback
    return desc or f"Verify {target} loads in {panel} panel"


# ─── Compositor ──────────────────────────────────────────────────────────────

def render_before_after_evidence(before_path, after_path, annotations_before=None, annotations_after=None):
    """Render Part 2 — Before/After split evidence (two screenshots side by side).

    Layout: [BEFORE label + screenshot] | [AFTER label + screenshot]
    Before gets a FAIL border (red), After gets a PASS border (green).
    """
    LABEL_HEIGHT = 28
    GAP = 6  # gap between left and right panels

    before_img = render_evidence(before_path, 'FAIL', annotations_before)
    after_img = render_evidence(after_path, 'PASS', annotations_after)

    # Scale both to same height
    bw, bh = before_img.size
    aw, ah = after_img.size
    target_h = max(bh, ah)

    if bh != target_h:
        scale = target_h / bh
        before_img = before_img.resize((int(bw * scale), target_h), Image.LANCZOS)
    if ah != target_h:
        scale = target_h / ah
        after_img = after_img.resize((int(aw * scale), target_h), Image.LANCZOS)

    bw, bh = before_img.size
    aw, ah = after_img.size

    total_w = bw + GAP + aw
    total_h = LABEL_HEIGHT + target_h

    composite = Image.new('RGB', (total_w, total_h), HEADER_BG)
    draw = ImageDraw.Draw(composite)

    # Labels
    label_font = _load_font(14)
    # BEFORE label — red
    draw.text((bw // 2 - 30, 6), "BEFORE", fill=(248, 113, 113), font=label_font)
    # AFTER label — green
    draw.text((bw + GAP + aw // 2 - 24, 6), "AFTER", fill=(134, 239, 172), font=label_font)

    # Paste screenshots
    composite.paste(before_img, (0, LABEL_HEIGHT))
    composite.paste(after_img, (bw + GAP, LABEL_HEIGHT))

    return composite


def compose_check_snapshot(frame_path, test_title, check_subtitle,
                           description, result, conclusion,
                           annotations=None, output_path=None):
    """Compose a complete 3-part check snapshot image.

    Returns the PIL Image (also saves to output_path if provided).
    """
    # Render evidence first to get dimensions
    evidence = render_evidence(frame_path, result, annotations)
    width = evidence.size[0]

    header = render_header(width, test_title, check_subtitle, description)
    result_bar = render_result(width, result, conclusion)

    # Compose vertically
    total_height = HEADER_HEIGHT + evidence.size[1] + RESULT_HEIGHT
    snapshot = Image.new('RGB', (width, total_height), (0, 0, 0))
    snapshot.paste(header, (0, 0))
    snapshot.paste(evidence, (0, HEADER_HEIGHT))
    snapshot.paste(result_bar, (0, HEADER_HEIGHT + evidence.size[1]))

    if output_path:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        snapshot.save(output_path, quality=95)
        print(f"  check: {output_path} ({snapshot.size[0]}x{snapshot.size[1]})")

    return snapshot


def compose_proof_of_completion(before_path, after_path, test_title,
                                 check_subtitle, description, conclusion,
                                 annotations_before=None, annotations_after=None,
                                 output_path=None):
    """Compose a proof-of-completion image: Header → Before/After evidence → Result.

    Three vertical parts:
      Part 1 — Header:   Test title, check subtitle, description
      Part 2 — Evidence: BEFORE (red border) | AFTER (green border) side by side
      Part 3 — Result:   PASS LED + conclusion text

    Returns the PIL Image (also saves to output_path if provided).
    """
    evidence = render_before_after_evidence(
        before_path, after_path,
        annotations_before=annotations_before,
        annotations_after=annotations_after,
    )
    width = evidence.size[0]

    header = render_header(width, test_title, check_subtitle, description)
    result_bar = render_result(width, 'PASS', conclusion)

    total_height = HEADER_HEIGHT + evidence.size[1] + RESULT_HEIGHT
    snapshot = Image.new('RGB', (width, total_height), (0, 0, 0))
    snapshot.paste(header, (0, 0))
    snapshot.paste(evidence, (0, HEADER_HEIGHT))
    snapshot.paste(result_bar, (0, HEADER_HEIGHT + evidence.size[1]))

    if output_path:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        snapshot.save(output_path, quality=95)
        print(f"  proof: {output_path} ({snapshot.size[0]}x{snapshot.size[1]})")

    return snapshot


# ─── Check+Proof Composite (Animated GIF Frames) ────────────────────────────

def render_check_proof_evidence(check_path, proof_path, result,
                                 annotations_check=None, annotations_proof=None):
    """Render Part 2 — CHECK | PROOF split evidence (two screenshots side by side).

    Layout: [CHECK label + screenshot] | [PROOF label + screenshot]
    Both panels get a border colored by result (green=PASS, amber=WARN, red=FAIL).
    """
    LABEL_HEIGHT = 28
    GAP = 6

    check_img = render_evidence(check_path, result, annotations_check)
    proof_img = render_evidence(proof_path, result, annotations_proof)

    # Scale both to same height
    cw, ch = check_img.size
    pw, ph = proof_img.size
    target_h = max(ch, ph)

    if ch != target_h:
        scale = target_h / ch
        check_img = check_img.resize((int(cw * scale), target_h), Image.LANCZOS)
    if ph != target_h:
        scale = target_h / ph
        proof_img = proof_img.resize((int(pw * scale), target_h), Image.LANCZOS)

    cw, ch = check_img.size
    pw, ph = proof_img.size

    total_w = cw + GAP + pw
    total_h = LABEL_HEIGHT + target_h

    composite = Image.new('RGB', (total_w, total_h), HEADER_BG)
    draw = ImageDraw.Draw(composite)

    # Labels — color matches result
    label_font = _load_font(14)
    label_color = LED_PASS if result == 'PASS' else (LED_WARN if result == 'WARN' else LED_FAIL)
    draw.text((cw // 2 - 24, 6), "CHECK", fill=label_color, font=label_font)
    draw.text((cw + GAP + pw // 2 - 24, 6), "PROOF", fill=label_color, font=label_font)

    # Paste screenshots
    composite.paste(check_img, (0, LABEL_HEIGHT))
    composite.paste(proof_img, (cw + GAP, LABEL_HEIGHT))

    return composite


def compose_check_proof_frame(check_path, proof_path, test_title,
                               check_subtitle, description, result, conclusion,
                               annotations_check=None, annotations_proof=None,
                               output_path=None):
    """Compose a complete check+proof frame — one step of the animated audit.

    Three vertical parts:
      Part 1 — Header:   Step title, check subtitle, description
      Part 2 — Evidence: CHECK (left) | PROOF (right) side by side
      Part 3 — Result:   Status LED + conclusion text

    Returns the PIL Image (also saves to output_path if provided).
    """
    evidence = render_check_proof_evidence(
        check_path, proof_path, result,
        annotations_check=annotations_check,
        annotations_proof=annotations_proof,
    )
    width = evidence.size[0]

    header = render_header(width, test_title, check_subtitle, description)
    result_bar = render_result(width, result, conclusion)

    total_height = HEADER_HEIGHT + evidence.size[1] + RESULT_HEIGHT
    frame = Image.new('RGB', (width, total_height), (0, 0, 0))
    frame.paste(header, (0, 0))
    frame.paste(evidence, (0, HEADER_HEIGHT))
    frame.paste(result_bar, (0, HEADER_HEIGHT + evidence.size[1]))

    if output_path:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        frame.save(output_path, quality=95)
        print(f"  frame: {output_path} ({frame.size[0]}x{frame.size[1]})")

    return frame


def batch_proof_gif(proof_json_path, output_path, duration_ms=2000):
    """Generate animated GIF from check+proof steps.

    Each frame is a complete composite (header + CHECK|PROOF evidence + result).
    Frames pause for duration_ms (default 2 seconds) between steps.

    Input JSON:
    {
      "test_title": "Test Suite Title",
      "steps": [
        {
          "check": "path/to/check_screenshot.png",
          "proof": "path/to/proof_screenshot.png",
          "label": "Step 1 — Area name",
          "description": "What is being verified",
          "result": "PASS",
          "conclusion": "Verified — explanation",
          "annotations_check": [...],
          "annotations_proof": [...]
        }
      ]
    }
    """
    with open(proof_json_path) as f:
        data = json.load(f)

    test_title = data.get('test_title', 'Test')
    steps = data.get('steps', [])

    if not steps:
        print("  ERROR: no steps found in proof JSON")
        return None

    frames = []
    # Track max dimensions for uniform frame size
    max_w, max_h = 0, 0

    for i, step in enumerate(steps, 1):
        check_path = step.get('check', '')
        proof_path = step.get('proof', '')

        if not os.path.isfile(check_path):
            print(f"  SKIP step {i}: check not found ({check_path})")
            continue
        if not os.path.isfile(proof_path):
            print(f"  SKIP step {i}: proof not found ({proof_path})")
            continue

        frame = compose_check_proof_frame(
            check_path=check_path,
            proof_path=proof_path,
            test_title=test_title,
            check_subtitle=step.get('label', f'Step {i}'),
            description=step.get('description', ''),
            result=step.get('result', 'PASS'),
            conclusion=step.get('conclusion', ''),
            annotations_check=step.get('annotations_check'),
            annotations_proof=step.get('annotations_proof'),
        )
        frames.append(frame)
        w, h = frame.size
        max_w = max(max_w, w)
        max_h = max(max_h, h)

    if not frames:
        print("  ERROR: no frames generated")
        return None

    # Normalize all frames to same size (pad smaller frames with dark bg)
    normalized = []
    for frame in frames:
        if frame.size == (max_w, max_h):
            normalized.append(frame)
        else:
            padded = Image.new('RGB', (max_w, max_h), (0, 0, 0))
            padded.paste(frame, (0, 0))
            normalized.append(padded)

    # Assemble animated GIF
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    normalized[0].save(
        output_path,
        save_all=True,
        append_images=normalized[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
    )
    size_kb = os.path.getsize(output_path) / 1024
    print(f"  GIF: {output_path} ({len(normalized)} frames, {max_w}x{max_h}, {size_kb:.0f}K, {duration_ms}ms/frame)")

    return output_path


# ─── Batch Mode ──────────────────────────────────────────────────────────────

def batch_generate(results_path, frames_dir, output_dir, test_title):
    """Generate check snapshots for all checks in results.json.

    Dual CHECK/PROOF format is the mandatory default. When both check_path
    and proof_path exist, produces side-by-side CHECK|PROOF evidence.
    Falls back to single-screenshot only for discovery mode (no check_path).
    """
    with open(results_path) as f:
        data = json.load(f)

    checks = data.get('checks', [])
    if not checks:
        # Fall back: build checks from default[] results (discovery / legacy)
        checks = []
        for r in data.get('default', []):
            idx = r['num'] - 1
            error = r.get('error', '')
            conclusion = error if error else f"Page loaded ({r.get('target', '?')})"
            checks.append({
                'check_id': r['num'],
                'test_title': test_title,
                'label': f"{r.get('phase', '?')} — {r.get('target', '?')}",
                'description': '',  # let resolve_description() handle it
                'phase': r.get('phase', ''),
                'target': r.get('target', '?'),
                'panel': r.get('panel', 'panel'),
                'doc': r.get('doc', ''),
                'result': r.get('result', 'FAIL'),
                'conclusion': conclusion,
                'check_path': f"check_{idx:04d}.png",
                'proof_path': f"proof_{idx:04d}.png",
                'frame_path': f"frame_{idx:04d}.png",
                'annotations': [{'type': 'border'}],
            })

    os.makedirs(output_dir, exist_ok=True)
    generated = []

    for check in checks:
        check_id = check.get('check_id', 0)
        output_path = os.path.join(output_dir, f"check_{check_id:04d}_snapshot.png")

        # Progressive description resolution
        description = resolve_description(check)

        # Dual CHECK/PROOF mode (mandatory default for test execution)
        check_file = check.get('check_path')
        proof_file = check.get('proof_path', check.get('frame_path'))
        if check_file and proof_file:
            check_full = os.path.join(frames_dir, check_file)
            proof_full = os.path.join(frames_dir, proof_file)
            if os.path.isfile(check_full) and os.path.isfile(proof_full):
                compose_check_proof_frame(
                    check_path=check_full,
                    proof_path=proof_full,
                    test_title=check.get('test_title', test_title),
                    check_subtitle=check.get('label', f'Check {check_id}'),
                    description=description,
                    result=check.get('result', 'FAIL'),
                    conclusion=check.get('conclusion', ''),
                    annotations_check=check.get('annotations'),
                    annotations_proof=check.get('annotations'),
                    output_path=output_path,
                )
                generated.append(output_path)
                continue

        # Single-screenshot fallback (discovery mode / legacy results only)
        frame_file = check.get('frame_path', f'frame_{check_id - 1:04d}.png')
        frame_full = os.path.join(frames_dir, frame_file)

        if not os.path.isfile(frame_full):
            print(f"  SKIP check {check_id}: frame not found ({frame_file})")
            continue

        compose_check_snapshot(
            frame_path=frame_full,
            test_title=check.get('test_title', test_title),
            check_subtitle=check.get('label', f'Check {check_id}'),
            description=description,
            result=check.get('result', 'FAIL'),
            conclusion=check.get('conclusion', ''),
            annotations=check.get('annotations'),
            output_path=output_path,
        )
        generated.append(output_path)

    print(f"\n  Generated {len(generated)} check snapshots in {output_dir}")
    return generated


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Check Snapshot Renderer — 3-part annotated proof images')

    # Batch mode
    parser.add_argument('--results', help='Path to results.json (batch mode)')
    parser.add_argument('--frames-dir', help='Directory containing raw frame PNGs')
    parser.add_argument('--test-title', help='Test title for batch header')

    # Proof-of-completion mode (before/after)
    parser.add_argument('--before', help='BEFORE screenshot path (proof-of-completion mode)')
    parser.add_argument('--after', help='AFTER screenshot path (proof-of-completion mode)')
    parser.add_argument('--proof-json', help='JSON file with proof-of-completion data (batch mode)')

    # Batch GIF mode (animated check+proof audit)
    parser.add_argument('--batch-gif', help='JSON file with check+proof steps (animated GIF mode)')
    parser.add_argument('--duration', type=int, default=2000, help='Frame duration in ms (default 2000)')

    # Single mode
    parser.add_argument('--frame', help='Single frame PNG path')
    parser.add_argument('--title', help='Test title (single mode)')
    parser.add_argument('--subtitle', help='Check subtitle (single mode)')
    parser.add_argument('--description', default='', help='Check description')
    parser.add_argument('--result', choices=['PASS', 'WARN', 'FAIL'], help='Check result')
    parser.add_argument('--conclusion', default='', help='Conclusion text')

    # Annotations (single mode)
    parser.add_argument('--annotate', choices=['circle', 'arrow', 'rect'], help='Annotation type')
    parser.add_argument('--ax', type=int, help='Annotation X (or X1 for arrow/rect)')
    parser.add_argument('--ay', type=int, help='Annotation Y (or Y1 for arrow/rect)')
    parser.add_argument('--ar', type=int, default=40, help='Annotation radius (circle)')
    parser.add_argument('--ax2', type=int, help='X2 for arrow/rect')
    parser.add_argument('--ay2', type=int, help='Y2 for arrow/rect')

    # Output
    parser.add_argument('--output', '-o', required=True, help='Output path (file or directory)')

    args = parser.parse_args()

    # Batch mode
    if args.results:
        if not args.frames_dir:
            print("ERROR: --frames-dir required for batch mode")
            sys.exit(1)
        batch_generate(
            results_path=args.results,
            frames_dir=args.frames_dir,
            output_dir=args.output,
            test_title=args.test_title or 'Test',
        )
        return

    # Batch GIF mode (animated check+proof audit)
    if args.batch_gif:
        batch_proof_gif(
            proof_json_path=args.batch_gif,
            output_path=args.output,
            duration_ms=args.duration,
        )
        return

    # Proof-of-completion mode (before/after)
    if args.before and args.after:
        compose_proof_of_completion(
            before_path=args.before,
            after_path=args.after,
            test_title=args.title or 'Test',
            check_subtitle=args.subtitle or 'Check',
            description=args.description,
            conclusion=args.conclusion or 'Fix verified — before/after comparison',
            output_path=args.output,
        )
        return

    # Proof from JSON (batch proof-of-completion from structured data)
    if args.proof_json:
        with open(args.proof_json) as f:
            proof_data = json.load(f)
        for check in proof_data.get('checks', []):
            compose_proof_of_completion(
                before_path=check['before'],
                after_path=check['after'],
                test_title=check.get('test_title', proof_data.get('test_title', 'Test')),
                check_subtitle=check.get('label', 'Check'),
                description=check.get('description', ''),
                conclusion=check.get('conclusion', 'Fix verified'),
                output_path=check.get('output', args.output),
            )
        return

    # Single mode
    if args.frame:
        if not args.result:
            print("ERROR: --result required for single mode")
            sys.exit(1)

        annotations = []
        if args.annotate == 'circle' and args.ax is not None and args.ay is not None:
            annotations.append({'type': 'circle', 'x': args.ax, 'y': args.ay, 'r': args.ar})
        elif args.annotate == 'arrow' and all(v is not None for v in [args.ax, args.ay, args.ax2, args.ay2]):
            annotations.append({'type': 'arrow', 'x1': args.ax, 'y1': args.ay, 'x2': args.ax2, 'y2': args.ay2})
        elif args.annotate == 'rect' and all(v is not None for v in [args.ax, args.ay, args.ax2, args.ay2]):
            annotations.append({'type': 'rect', 'x1': args.ax, 'y1': args.ay, 'x2': args.ax2, 'y2': args.ay2})

        compose_check_snapshot(
            frame_path=args.frame,
            test_title=args.title or 'Test',
            check_subtitle=args.subtitle or 'Check',
            description=args.description,
            result=args.result,
            conclusion=args.conclusion,
            annotations=annotations or None,
            output_path=args.output,
        )
        return

    parser.print_help()


if __name__ == '__main__':
    main()
