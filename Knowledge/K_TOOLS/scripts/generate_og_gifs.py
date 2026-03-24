#!/usr/bin/env python3
"""Generate animated OG social preview GIFs for each knowledge page.
Each GIF: 1200x630, dual-theme (Cayman light + Midnight dark), content-specific frame animations.

Animations per card type:
  - Corporate (profile-hub, resume, full-profile): Photo with pulsing border ring
  - MPLIB Pipeline: Left-to-right node activation flow
  - Live Session: Data pulse flowing through pipeline stages
  - AI Persistence: Single Vicky NPC→AWARE transformation
  - Publications Index: Cards appearing sequentially with glow
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import argparse
import os
import math
import re
import sys

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# scripts/ -> K_TOOLS/ -> Knowledge/ -> ROOT
MODULE_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(MODULE_DIR))
OUT_DIR = os.path.join(PROJECT_ROOT, 'docs', 'assets', 'og')
REF_DIR = os.path.join(PROJECT_ROOT, 'references', 'Martin')
os.makedirs(OUT_DIR, exist_ok=True)

PHOTO_PATH = os.path.join(REF_DIR, 'me3.JPG')
VICKY_PATH = os.path.join(REF_DIR, 'vicky.png')
VICKY_SUNGLASSES_PATH = os.path.join(REF_DIR, 'vicky-sunglasses.png')

# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------
FONT_BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
FONT_REGULAR = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FONT_MONO = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'
FONT_SERIF = '/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf'

# ---------------------------------------------------------------------------
# Theme palettes — Cayman (light) + Midnight (dark)
# ---------------------------------------------------------------------------
THEMES = {
    'daltonism-light': {
        'BG_TOP':        (250, 246, 241),      # #faf6f1  warm cream
        'BG_BOT':        (240, 232, 220),      # #f0e8dc  warm beige
        'ACCENT_BLUE':   (0, 85, 179),         # #0055b3  high-contrast blue
        'ACCENT_PURPLE': (107, 33, 168),       # #6b21a8  purple
        'ACCENT_CYAN':   (14, 116, 144),       # #0e7490  teal
        'ACCENT_GREEN':  (21, 128, 61),        # #15803d  green
        'TEXT_WHITE':    (26, 26, 46),          # #1a1a2e  dark text on light bg
        'TEXT_MUTED':    (92, 92, 120),         # #5c5c78
        'TEXT_DIM':      (120, 120, 140),       # #78788c
        'BORDER':        (0, 85, 179),           # #0055b3  accent blue
        'BOX_BG':        (250, 246, 241),       # #faf6f1  warm cream box fill
        'CODE_BG':       (240, 232, 220),       # #f0e8dc  warm beige
    },
    'daltonism-dark': {
        'BG_TOP':        (26, 26, 46),          # #1a1a2e  purple-navy
        'BG_BOT':        (20, 20, 40),          # #141428  deeper purple-navy
        'ACCENT_BLUE':   (91, 155, 213),        # #5b9bd5  muted blue
        'ACCENT_PURPLE': (176, 136, 208),       # #b088d0  soft purple
        'ACCENT_CYAN':   (80, 184, 208),        # #50b8d0  soft teal
        'ACCENT_GREEN':  (96, 192, 128),        # #60c080  soft green
        'TEXT_WHITE':    (232, 224, 212),        # #e8e0d4  warm light text
        'TEXT_MUTED':    (136, 136, 160),        # #8888a0
        'TEXT_DIM':      (108, 108, 132),        # #6c6c84
        'BORDER':        (42, 74, 122),          # #2a4a7a
        'BOX_BG':        (35, 35, 55),           # #232337  dark box fill
        'CODE_BG':       (42, 42, 62),           # #2a2a3e
    },
}

# Active theme state — set by set_theme()
CURRENT_THEME = 'daltonism-light'
BG_TOP = THEMES['daltonism-light']['BG_TOP']
BG_BOT = THEMES['daltonism-light']['BG_BOT']
ACCENT_BLUE = THEMES['daltonism-light']['ACCENT_BLUE']
ACCENT_PURPLE = THEMES['daltonism-light']['ACCENT_PURPLE']
ACCENT_CYAN = THEMES['daltonism-light']['ACCENT_CYAN']
ACCENT_GREEN = THEMES['daltonism-light']['ACCENT_GREEN']
TEXT_WHITE = THEMES['daltonism-light']['TEXT_WHITE']
TEXT_MUTED = THEMES['daltonism-light']['TEXT_MUTED']
TEXT_DIM = THEMES['daltonism-light']['TEXT_DIM']
BORDER = THEMES['daltonism-light']['BORDER']
BOX_BG = THEMES['daltonism-light']['BOX_BG']
CODE_BG = THEMES['daltonism-light']['CODE_BG']


def set_theme(theme_name):
    """Switch active theme — sets all color globals and clears caches."""
    global CURRENT_THEME, BG_TOP, BG_BOT, ACCENT_BLUE, ACCENT_PURPLE
    global ACCENT_CYAN, ACCENT_GREEN, TEXT_WHITE, TEXT_MUTED, TEXT_DIM
    global BORDER, BOX_BG, CODE_BG, _base_cache
    t = THEMES[theme_name]
    CURRENT_THEME = theme_name
    BG_TOP = t['BG_TOP']
    BG_BOT = t['BG_BOT']
    ACCENT_BLUE = t['ACCENT_BLUE']
    ACCENT_PURPLE = t['ACCENT_PURPLE']
    ACCENT_CYAN = t['ACCENT_CYAN']
    ACCENT_GREEN = t['ACCENT_GREEN']
    TEXT_WHITE = t['TEXT_WHITE']
    TEXT_MUTED = t['TEXT_MUTED']
    TEXT_DIM = t['TEXT_DIM']
    BORDER = t['BORDER']
    BOX_BG = t['BOX_BG']
    CODE_BG = t['CODE_BG']
    _base_cache = None  # clear cached base image


W, H = 1200, 630

# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def lerp(a, b, t):
    """Linear interpolation between scalars."""
    return a + (b - a) * max(0.0, min(1.0, t))


def lerp_color(c1, c2, t):
    """Linear interpolation between RGB tuples."""
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def brighten(color, factor=1.3):
    return tuple(min(255, int(c * factor)) for c in color[:3])


def dim(color, factor=0.5):
    return tuple(int(c * factor) for c in color[:3])


def ease_in_out(t):
    """Smooth ease-in-out curve (0→1→0 if used with sin)."""
    return 0.5 - 0.5 * math.cos(math.pi * t)


# ---------------------------------------------------------------------------
# Cached base image (gradient + grid + accent bars — same for every frame)
# ---------------------------------------------------------------------------
_base_cache = None


def _build_base():
    img = Image.new('RGB', (W, H))
    draw = ImageDraw.Draw(img)
    # Vertical gradient
    for y in range(H):
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * y / H)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * y / H)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * y / H)
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    # Grid — slightly offset from background (lighter on dark, darker on light)
    offset = 12 if BG_TOP[0] > 128 else -12  # dark theme → subtract = lighter
    gc = tuple(max(0, min(255, c - offset)) for c in BG_TOP)
    for y in range(80, H, 80):
        draw.line([(0, y), (W, y)], fill=gc, width=1)
    for x in range(160, W, 160):
        draw.line([(x, 0), (x, H)], fill=gc, width=1)
    # Accent bars
    for x in range(W):
        t = x / W
        if t < 0.5:
            c = lerp_color(ACCENT_BLUE, ACCENT_PURPLE, t * 2)
        else:
            c = lerp_color(ACCENT_PURPLE, ACCENT_CYAN, (t - 0.5) * 2)
        draw.line([(x, 0), (x, 4)], fill=c)
        draw.line([(x, H - 4), (x, H)], fill=c)
    return img


def base_image():
    """Return a fresh copy of the cached base image + draw context."""
    global _base_cache
    if _base_cache is None:
        _base_cache = _build_base()
    img = _base_cache.copy()
    return img, ImageDraw.Draw(img)


def draw_box(draw, x, y, w, h, border_color=ACCENT_BLUE, radius=8,
             fill_color=BOX_BG, width=2):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=radius,
                           fill=fill_color, outline=border_color, width=width)


def footer(draw, text="Martin Paquet & Claude  |  packetqc/knowledge"):
    font = ImageFont.truetype(FONT_REGULAR, 14)
    draw.text((W // 2, H - 40), text, fill=TEXT_DIM, font=font, anchor="mm")


# ---------------------------------------------------------------------------
# Asset loaders
# ---------------------------------------------------------------------------

def load_photo_circular(size=160):
    """Load me3.JPG → square crop from top → circular mask."""
    try:
        photo = Image.open(PHOTO_PATH).convert('RGBA')
        pw, ph = photo.size
        s = min(pw, ph)
        left = (pw - s) // 2
        photo = photo.crop((left, 0, left + s, s))
        photo = photo.resize((size, size), Image.LANCZOS)
        # Circular mask
        mask = Image.new('L', (size, size), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
        result = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        result.paste(photo, (0, 0))
        result.putalpha(mask)
        return result
    except FileNotFoundError:
        return None


def load_vicky(size=200, sunglasses=False):
    """Load vicky.png (or vicky-sunglasses.png), resize, and apply circular mask."""
    path = VICKY_SUNGLASSES_PATH if sunglasses else VICKY_PATH
    try:
        v = Image.open(path).convert('RGBA')
        v = v.resize((size, size), Image.LANCZOS)
        # Circular mask
        mask = Image.new('L', (size, size), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
        result = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        result.paste(v, (0, 0))
        result.putalpha(mask)
        return result
    except FileNotFoundError:
        return None


# ---------------------------------------------------------------------------
# GIF saver
# ---------------------------------------------------------------------------

def save_gif(frames, fname, duration=650):
    """Save list of RGB PIL images as animated GIF.
    Injects CURRENT_THEME into filename: foo-en.gif → foo-en-midnight.gif"""
    # Inject theme into filename: base-lang.gif → base-lang-theme.gif
    base, ext = os.path.splitext(fname)
    themed_fname = f"{base}-{CURRENT_THEME}{ext}"

    gif_frames = []
    for f in frames:
        rgb = f.convert('RGB')
        q = rgb.quantize(colors=256, method=Image.Quantize.MEDIANCUT,
                         dither=Image.Dither.FLOYDSTEINBERG)
        gif_frames.append(q)

    path = os.path.join(OUT_DIR, themed_fname)
    gif_frames[0].save(
        path, format='GIF', save_all=True,
        append_images=gif_frames[1:],
        duration=duration, loop=0, optimize=True
    )
    size_kb = os.path.getsize(path) / 1024
    print(f"  Generated {themed_fname}  ({len(frames)} frames, {size_kb:.0f} KB)")


# ---------------------------------------------------------------------------
# Dashboard data parser — reads real satellite data from README harvest table
# ---------------------------------------------------------------------------

_dashboard_data_cache = None


def parse_dashboard_data():
    """Parse satellite network status + master stats from the dashboard README.

    Returns dict with:
      'master': {'version': 'v10', 'entries': '10', 'publications': '5',
                 'patterns': '4', 'pitfalls': '12'}
      'satellites': [{'name': ..., 'version': ..., 'drift': ...,
                      'bootstrap': ..., 'sessions': ..., 'assets': ...,
                      'live': ..., 'publications': ..., 'health': ...,
                      'last_harvest': ...}, ...]
    """
    global _dashboard_data_cache
    if _dashboard_data_cache is not None:
        return _dashboard_data_cache

    readme_path = os.path.join(SCRIPT_DIR, '..', 'publications',
                               'distributed-knowledge-dashboard', 'v1',
                               'README.md')
    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        _dashboard_data_cache = None
        return None

    data = {'master': {}, 'satellites': []}

    # Parse master mind status table
    m = re.search(r'Current version\s*\|\s*\*\*(\w+)\*\*', content)
    data['master']['version'] = m.group(1) if m else 'v10'
    m = re.search(r'Total evolution entries\s*\|\s*(\d+)', content)
    data['master']['entries'] = m.group(1) if m else '10'
    m = re.search(r'Publications\s*\|\s*(\d+)', content)
    data['master']['publications'] = m.group(1) if m else '5'
    m = re.search(r'Proven patterns\s*\|\s*(\d+)', content)
    data['master']['patterns'] = m.group(1) if m else '4'
    m = re.search(r'Lessons documented\s*\|\s*(\d+)', content)
    data['master']['pitfalls'] = m.group(1) if m else '12'

    # Helper: strip severity emoji icons from cell values
    def strip_emoji(val):
        """Remove leading severity emoji (🟢🟡🟠🔴⚪) from table cell."""
        return re.sub(r'^[\U0001f7e2\U0001f7e1\U0001f7e0\U0001f534\u26aa]\s*', '', val)

    # Parse satellite network status table (between header and HARVEST-TABLE)
    table_match = re.search(
        r'\| Satellite\s*\|.*?\n\|[-| ]+\n(.*?)(?=\n<!-- HARVEST-TABLE)',
        content, re.DOTALL)
    if table_match:
        rows = table_match.group(1).strip().split('\n')
        for row in rows:
            cells = [c.strip() for c in row.split('|')[1:-1]]
            if len(cells) >= 8:
                # Extract name from markdown link [name](url) or plain text
                name_cell = cells[0]
                name_m = re.match(r'\[([^\]]+)\]', name_cell)
                name = name_m.group(1) if name_m else name_cell.strip('* ')
                is_self = '(self)' in name_cell
                # Parse columns — handle 10-col (with Assets+Live), 9-col, or 8-col
                sat_data = {
                    'name': name,
                    'version': strip_emoji(cells[1]).strip('* '),
                    'drift': strip_emoji(cells[2]).strip(),
                    'bootstrap': strip_emoji(cells[3]).strip('* '),
                    'sessions': strip_emoji(cells[4]).strip(),
                    'assets': strip_emoji(cells[5]).strip(),
                    'is_self': is_self,
                }
                if len(cells) >= 10:
                    # 10-column format: Assets at index 5, Live at index 6
                    sat_data['live'] = strip_emoji(cells[6]).strip()
                    sat_data['publications'] = strip_emoji(cells[7]).strip()
                    sat_data['health'] = strip_emoji(cells[8]).strip()
                    sat_data['last_harvest'] = cells[9].strip()
                elif len(cells) >= 9:
                    sat_data['live'] = '0'
                    sat_data['publications'] = strip_emoji(cells[6]).strip()
                    sat_data['health'] = strip_emoji(cells[7]).strip()
                    sat_data['last_harvest'] = cells[8].strip()
                else:
                    sat_data['live'] = '0'
                    sat_data['publications'] = strip_emoji(cells[6]).strip()
                    sat_data['health'] = 'pending'
                    sat_data['last_harvest'] = cells[7].strip()
                data['satellites'].append(sat_data)

    # Parse promotion candidates per satellite from Harvested Insights table
    candidates = {}
    cand_match = re.search(
        r'### Promotion Candidates.*?\n\|.*?\n\|[-| ]+\n(.*?)(?=\n###|\n---|\Z)',
        content, re.DOTALL)
    if cand_match:
        for row in cand_match.group(1).strip().split('\n'):
            cells = [c.strip() for c in row.split('|')[1:-1]]
            if len(cells) >= 3:
                source = cells[2].strip()
                candidates[source] = candidates.get(source, 0) + 1
    for sat in data['satellites']:
        sat['candidates'] = str(candidates.get(sat['name'], 0))

    _dashboard_data_cache = data
    return data


# ---------------------------------------------------------------------------
# Draw photo with animated border ring
# ---------------------------------------------------------------------------

def draw_photo_ring(img, draw, cx, cy, photo, frame_idx, n_frames,
                    photo_size=160):
    """Draw circular photo with animated pulsing border ring."""
    t = frame_idx / n_frames
    # Radius oscillates 4→12→4 via sine
    border_w = 4 + 8 * (0.5 + 0.5 * math.sin(2 * math.pi * t))
    # Color cycles blue→cyan→purple→blue
    if t < 0.33:
        bc = lerp_color(ACCENT_BLUE, ACCENT_CYAN, t * 3)
    elif t < 0.66:
        bc = lerp_color(ACCENT_CYAN, ACCENT_PURPLE, (t - 0.33) * 3)
    else:
        bc = lerp_color(ACCENT_PURPLE, ACCENT_BLUE, (t - 0.66) * 3)
    # Brighten proportional to border width
    brightness = 1.0 + 0.4 * (border_w - 4) / 8
    bc = brighten(bc, brightness)

    total_r = photo_size // 2 + int(border_w)
    # Outer glow rings
    for off in range(4, 0, -1):
        glow_c = lerp_color(BG_TOP, bc, 0.15 * (5 - off) / 4)
        draw.ellipse([cx - total_r - off, cy - total_r - off,
                      cx + total_r + off, cy + total_r + off],
                     outline=glow_c, width=1)
    # Main border circle
    draw.ellipse([cx - total_r, cy - total_r,
                  cx + total_r, cy + total_r],
                 fill=BOX_BG, outline=bc, width=max(2, int(border_w / 2)))
    # Paste photo
    if photo:
        px = cx - photo_size // 2
        py = cy - photo_size // 2
        img.paste(photo, (px, py), photo)
    else:
        font_init = ImageFont.truetype(FONT_BOLD, 72)
        draw.text((cx, cy), "MP", fill=ACCENT_BLUE, font=font_init,
                  anchor="mm")


# ===================================================================
# PROFILE HUB — photo + pulsing ring + link boxes
# ===================================================================

def gen_profile_hub(lang='en'):
    photo = load_photo_circular(160)
    n = 8
    frames = []
    for fi in range(n):
        img, draw = base_image()
        draw_photo_ring(img, draw, 600, 140, photo, fi, n, 160)

        font_name = ImageFont.truetype(FONT_BOLD, 48)
        draw.text((600, 275), "Martin Paquet", fill=TEXT_WHITE,
                  font=font_name, anchor="mm")

        font_sub = ImageFont.truetype(FONT_REGULAR, 22)
        subtitle = ("Network Security | System Security | Embedded Software"
                     if lang == 'en' else
                     u"Sécurité Réseau | Sécurité Systèmes | Logiciels Embarqués")
        draw.text((600, 320), subtitle, fill=TEXT_MUTED,
                  font=font_sub, anchor="mm")

        links = [("GitHub", "packetqc"), ("Knowledge", "packetqc/knowledge"),
                 ("LinkedIn", "martypacket")]
        box_w = 300
        sx = (W - len(links) * box_w - (len(links) - 1) * 20) // 2
        colors = [ACCENT_BLUE, ACCENT_PURPLE, ACCENT_CYAN]
        for i, (label, value) in enumerate(links):
            bx = sx + i * (box_w + 20)
            draw_box(draw, bx, 380, box_w, 70, border_color=colors[i])
            fl = ImageFont.truetype(FONT_BOLD, 18)
            fv = ImageFont.truetype(FONT_MONO, 20)
            draw.text((bx + box_w // 2, 398), label, fill=colors[i],
                      font=fl, anchor="mm")
            draw.text((bx + box_w // 2, 428), value, fill=TEXT_WHITE,
                      font=fv, anchor="mm")

        font_lang = ImageFont.truetype(FONT_BOLD, 18)
        badge = "English" if lang == 'en' else u"Français"
        draw.rounded_rectangle([540, 490, 660, 520], radius=12,
                               fill=BOX_BG, outline=ACCENT_CYAN, width=1)
        draw.text((600, 505), badge, fill=ACCENT_CYAN,
                  font=font_lang, anchor="mm")

        footer(draw)
        frames.append(img)

    save_gif(frames, f"profile-hub-{lang}.gif", duration=650)


# ===================================================================
# RESUME — big photo bottom-right, business card style
# ===================================================================

def gen_resume(lang='en'):
    photo = load_photo_circular(400)
    n = 8
    frames = []

    for fi in range(n):
        img, draw = base_image()

        # BOTTOM RIGHT — big photo
        draw_photo_ring(img, draw, 1000, 430, photo, fi, n, 400)

        # FULL WIDTH — huge name
        font_name = ImageFont.truetype(FONT_BOLD, 80)
        draw.text((50, 70), "Martin Paquet", fill=TEXT_WHITE,
                  font=font_name, anchor="lm")

        font_label = ImageFont.truetype(FONT_BOLD, 38)
        if lang == 'en':
            draw.text((50, 145), "Resume", fill=ACCENT_CYAN,
                      font=font_label, anchor="lm")
        else:
            draw.text((50, 145), u"Résumé", fill=ACCENT_CYAN,
                      font=font_label, anchor="lm")

        # 5 specialties — colored bullets
        font_focus = ImageFont.truetype(FONT_BOLD, 32)
        areas = [
            ("STM32 / Cortex-M", ACCENT_BLUE),
            ("TouchGFX / LTDC", ACCENT_PURPLE),
            ("IoT / ThreadX RTOS", ACCENT_CYAN),
            ("Network Security", ACCENT_BLUE),
            ("C/C++ / Python", ACCENT_PURPLE),
        ]

        active = fi % len(areas)
        for i, (title, color) in enumerate(areas):
            y = 220 + i * 48
            c = brighten(color, 1.4) if i == active else color
            draw.ellipse([50, y - 6, 74, y + 18], fill=c)
            draw.text((88, y), title, fill=c, font=font_focus, anchor="lm")

        # Catch phrase — code block style (big for resume card)
        font_catch = ImageFont.truetype(FONT_MONO, 26)
        catch_text = "Read packetqc/knowledge"
        bbox = font_catch.getbbox(catch_text)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        code_x = 50
        code_y = 480
        pad_x, pad_y = 18, 12
        draw.rounded_rectangle(
            [code_x, code_y, code_x + tw + pad_x * 2, code_y + th + pad_y * 2],
            radius=8, fill=CODE_BG, outline=BORDER, width=1)
        draw.text((code_x + pad_x, code_y + pad_y), catch_text,
                  fill=TEXT_WHITE, font=font_catch)

        font_tagline = ImageFont.truetype(FONT_SERIF, 17)
        if lang == 'en':
            tagline = "From your git repo to acquire and maintain knowledge..."
        else:
            tagline = u"Depuis votre dépôt git pour acquérir et maintenir la connaissance..."
        draw.text((code_x + 5, code_y + th + pad_y * 2 + 10), tagline,
                  fill=TEXT_MUTED, font=font_tagline, anchor="lm")

        footer(draw)
        frames.append(img)

    save_gif(frames, f"resume-{lang}.gif", duration=900)


# ===================================================================
# FULL PROFILE — big photo bottom-right, business card style
# ===================================================================

def gen_full_profile(lang='en'):
    photo = load_photo_circular(400)
    n = 8
    frames = []

    for fi in range(n):
        img, draw = base_image()

        # BOTTOM RIGHT — big photo
        draw_photo_ring(img, draw, 1000, 430, photo, fi, n, 400)

        # FULL WIDTH — huge name
        font_name = ImageFont.truetype(FONT_BOLD, 80)
        draw.text((50, 70), "Martin Paquet", fill=TEXT_WHITE,
                  font=font_name, anchor="lm")

        font_label = ImageFont.truetype(FONT_BOLD, 38)
        if lang == 'en':
            draw.text((50, 145), "Full Profile", fill=ACCENT_CYAN,
                      font=font_label, anchor="lm")
        else:
            draw.text((50, 145), "Profil complet", fill=ACCENT_CYAN,
                      font=font_label, anchor="lm")

        # Occupation — full width, big
        font_role = ImageFont.truetype(FONT_BOLD, 38)
        if lang == 'en':
            draw.text((50, 240),
                      "Embedded & Network Security Analyst Programmer",
                      fill=ACCENT_BLUE, font=font_role, anchor="lm")
            draw.text((50, 295), "AI-Assisted Development",
                      fill=ACCENT_CYAN, font=font_role, anchor="lm")
        else:
            draw.text((50, 240),
                      u"Analyste programmeur — Embarqué & sécu. réseau",
                      fill=ACCENT_BLUE, font=font_role, anchor="lm")
            draw.text((50, 295), u"Développement assisté par IA",
                      fill=ACCENT_CYAN, font=font_role, anchor="lm")

        font_info = ImageFont.truetype(FONT_REGULAR, 30)
        if lang == 'en':
            draw.text((50, 370), "30 years · Quebec, Canada",
                      fill=TEXT_MUTED, font=font_info, anchor="lm")
        else:
            draw.text((50, 370), u"30 ans · Québec, Canada",
                      fill=TEXT_MUTED, font=font_info, anchor="lm")

        # Catch phrase — code block style (for full profile)
        font_catch = ImageFont.truetype(FONT_MONO, 20)
        catch_text = "Read packetqc/knowledge"
        bbox = font_catch.getbbox(catch_text)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        code_x = 50
        code_y = 440
        pad_x, pad_y = 14, 10
        draw.rounded_rectangle(
            [code_x, code_y, code_x + tw + pad_x * 2, code_y + th + pad_y * 2],
            radius=7, fill=CODE_BG, outline=BORDER, width=1)
        draw.text((code_x + pad_x, code_y + pad_y), catch_text,
                  fill=TEXT_WHITE, font=font_catch)

        font_tagline = ImageFont.truetype(FONT_SERIF, 15)
        if lang == 'en':
            tagline = "From your git repo to acquire and maintain knowledge..."
        else:
            tagline = u"Depuis votre dépôt git pour acquérir et maintenir la connaissance..."
        draw.text((code_x + 5, code_y + th + pad_y * 2 + 8), tagline,
                  fill=TEXT_MUTED, font=font_tagline, anchor="lm")

        footer(draw)
        frames.append(img)

    save_gif(frames, f"full-profile-{lang}.gif", duration=900)


# ===================================================================
# MPLIB PIPELINE — left-to-right node activation
# ===================================================================

def gen_mplib_pipeline(lang='en'):
    stages = ["Generate", "DualBuffer", "Ingest", "WAL", "SD Card"]
    stage_colors = [ACCENT_BLUE, ACCENT_PURPLE, ACCENT_CYAN,
                    ACCENT_BLUE, ACCENT_PURPLE]
    n_stages = len(stages)
    # 7 frames: all-dim, then each stage active, then all-bright
    n = n_stages + 2
    frames = []

    font_title = ImageFont.truetype(FONT_BOLD, 38)
    font_sub = ImageFont.truetype(FONT_REGULAR, 22)
    font_big = ImageFont.truetype(FONT_BOLD, 60)
    font_ml = ImageFont.truetype(FONT_REGULAR, 17)
    font_stage = ImageFont.truetype(FONT_MONO, 17)
    font_mv = ImageFont.truetype(FONT_BOLD, 32)
    font_small = ImageFont.truetype(FONT_REGULAR, 15)

    if lang == 'en':
        metrics = [("400K+", "rows tested"), ("7.2 MB", "PSRAM buffers"),
                   ("4 MB", "page cache"), ("800 MHz", "Cortex-M55")]
    else:
        metrics = [("400K+", u"lignes testées"), ("7,2 Mo", "tampons PSRAM"),
                   ("4 Mo", "cache pages"), ("800 MHz", "Cortex-M55")]

    box_w = 160
    gap = 20
    total = n_stages * box_w + (n_stages - 1) * gap
    sx = (W - total) // 2

    for fi in range(n):
        img, draw = base_image()

        draw.text((600, 70), "MPLIB Storage Pipeline", fill=TEXT_WHITE,
                  font=font_title, anchor="mm")
        subtitle = ("High-Throughput SQLite on Cortex-M55" if lang == 'en'
                    else "SQLite haute performance sur Cortex-M55")
        draw.text((600, 110), subtitle, fill=TEXT_MUTED, font=font_sub,
                  anchor="mm")

        # Big metric
        draw.text((600, 210), "2,650", fill=ACCENT_BLUE, font=font_big,
                  anchor="mm")
        draw.text((600, 250), "logs/sec sustained", fill=TEXT_MUTED,
                  font=font_ml, anchor="mm")

        # Pipeline stages
        active_idx = fi - 1  # -1 = none active, 0-4 = stage active, 5 = all
        for i, (stage, sc) in enumerate(zip(stages, stage_colors)):
            bx = sx + i * (box_w + gap)

            if fi == n - 1:
                # Last frame: all bright
                bc = brighten(sc, 1.4)
                bw = 3
                ff = lerp_color(BOX_BG, sc, 0.2)
                tc = brighten(sc, 1.4)
                extra_h = 4
            elif i == active_idx:
                # Active stage: bigger, brighter
                bc = brighten(sc, 1.5)
                bw = 3
                ff = lerp_color(BOX_BG, sc, 0.25)
                tc = brighten(sc, 1.5)
                extra_h = 6
            elif i < active_idx:
                # Already passed: slightly lit
                bc = brighten(sc, 1.1)
                bw = 2
                ff = lerp_color(BOX_BG, sc, 0.08)
                tc = brighten(sc, 1.1)
                extra_h = 0
            else:
                # Not yet reached: dim
                bc = dim(sc, 0.5)
                bw = 2
                ff = BOX_BG
                tc = dim(sc, 0.6)
                extra_h = 0

            # Draw box (slightly taller when active)
            by = 310 - extra_h
            bh = 50 + extra_h * 2
            draw_box(draw, bx, by, box_w, bh, border_color=bc,
                     fill_color=ff, width=bw)
            draw.text((bx + box_w // 2, by + bh // 2), stage, fill=tc,
                      font=font_stage, anchor="mm")

            # Arrow between stages
            if i < n_stages - 1:
                ax = bx + box_w + 2
                arrow_c = (brighten(TEXT_DIM, 1.5) if i <= active_idx
                           else TEXT_DIM)
                draw.text((ax + gap // 2, 335), u"\u25B6", fill=arrow_c,
                          font=font_stage, anchor="mm")

        # Metrics row
        mx_start = 100
        mx_gap = (W - 200) // len(metrics)
        for i, (val, label) in enumerate(metrics):
            mx = mx_start + i * mx_gap + mx_gap // 2
            draw.text((mx, 430), val, fill=TEXT_WHITE, font=font_mv,
                      anchor="mm")
            draw.text((mx, 460), label, fill=TEXT_DIM, font=font_small,
                      anchor="mm")

        # Tech stack
        draw.text((600, 520),
                  u"ThreadX RTOS  ·  TouchGFX  ·  SQLite WAL  ·  STM32N6570-DK",
                  fill=TEXT_DIM, font=font_ml, anchor="mm")

        footer(draw)
        frames.append(img)

    save_gif(frames, f"mplib-pipeline-{lang}.gif", duration=800)


# ===================================================================
# LIVE SESSION — data pulse flowing through pipeline
# ===================================================================

def gen_live_session(lang='en'):
    if lang == 'en':
        flow_stages = ["Board", "OBS/RTSP", "H.264", "Git", "Claude",
                       "Analysis"]
    else:
        flow_stages = ["Carte", "OBS/RTSP", "H.264", "Git", "Claude",
                       "Analyse"]

    n_flow = len(flow_stages)
    n = n_flow + 2  # 8 frames
    frames = []

    font_title = ImageFont.truetype(FONT_BOLD, 38)
    font_sub = ImageFont.truetype(FONT_REGULAR, 22)
    font_big = ImageFont.truetype(FONT_BOLD, 60)
    font_label = ImageFont.truetype(FONT_REGULAR, 17)
    font_flow = ImageFont.truetype(FONT_MONO, 17)
    font_mode = ImageFont.truetype(FONT_MONO, 19)
    font_desc = ImageFont.truetype(FONT_REGULAR, 15)

    if lang == 'en':
        modes = [("I'm live", "Pull & report", ACCENT_BLUE),
                 ("analyze", "Static timeline", ACCENT_PURPLE),
                 ("multi-live", "Cross-source", ACCENT_CYAN),
                 ("deep", "Frame forensics", ACCENT_BLUE)]
    else:
        modes = [("I'm live", "Pull & rapport", ACCENT_BLUE),
                 ("analyze", "Chronologie", ACCENT_PURPLE),
                 ("multi-live", "Multi-source", ACCENT_CYAN),
                 ("deep", u"Forensique", ACCENT_BLUE)]

    for fi in range(n):
        img, draw = base_image()

        if lang == 'en':
            draw.text((600, 70), "Live Session Analysis", fill=TEXT_WHITE,
                      font=font_title, anchor="mm")
            draw.text((600, 110), "AI-Assisted Real-Time Debugging",
                      fill=TEXT_MUTED, font=font_sub, anchor="mm")
        else:
            draw.text((600, 70), "Analyse de session en direct",
                      fill=TEXT_WHITE, font=font_title, anchor="mm")
            draw.text((600, 110),
                      u"Débogage temps réel assisté par IA",
                      fill=TEXT_MUTED, font=font_sub, anchor="mm")

        # Flow pipeline with animated pulse
        active_flow = fi - 1  # -1 = none, 0-5 = stage, 6 = all
        flow_box_w = 140
        flow_gap = 18
        flow_total = n_flow * flow_box_w + (n_flow - 1) * flow_gap
        flow_sx = (W - flow_total) // 2

        for i, stage in enumerate(flow_stages):
            fbx = flow_sx + i * (flow_box_w + flow_gap)

            if fi == n - 1:
                bc = ACCENT_CYAN
                fc = lerp_color(BOX_BG, ACCENT_CYAN, 0.15)
                tc = ACCENT_CYAN
                bw = 2
            elif i == active_flow:
                bc = brighten(ACCENT_CYAN, 1.5)
                fc = lerp_color(BOX_BG, ACCENT_CYAN, 0.25)
                tc = brighten(ACCENT_CYAN, 1.5)
                bw = 3
            elif i < active_flow:
                bc = brighten(ACCENT_CYAN, 1.1)
                fc = lerp_color(BOX_BG, ACCENT_CYAN, 0.08)
                tc = brighten(ACCENT_CYAN, 1.1)
                bw = 2
            else:
                bc = dim(ACCENT_CYAN, 0.4)
                fc = BOX_BG
                tc = dim(ACCENT_CYAN, 0.5)
                bw = 2

            draw_box(draw, fbx, 160, flow_box_w, 40, border_color=bc,
                     fill_color=fc, width=bw)
            draw.text((fbx + flow_box_w // 2, 180), stage, fill=tc,
                      font=font_flow, anchor="mm")

            if i < n_flow - 1:
                ax = fbx + flow_box_w + 2
                ac = brighten(TEXT_DIM, 1.3) if i < active_flow else TEXT_DIM
                draw.text((ax + flow_gap // 2, 180), u"\u25B6", fill=ac,
                          font=font_flow, anchor="mm")

        # Big metric
        draw.text((600, 275), "~6 sec", fill=ACCENT_BLUE, font=font_big,
                  anchor="mm")
        metric_label = ("end-to-end latency" if lang == 'en'
                        else u"latence bout en bout")
        draw.text((600, 315), metric_label, fill=TEXT_MUTED,
                  font=font_label, anchor="mm")

        # 4 mode boxes — highlight one per pair of frames
        active_mode = (fi // 2) % 4
        box_w = 230
        mode_total = len(modes) * box_w + (len(modes) - 1) * 20
        mode_sx = (W - mode_total) // 2
        for i, (cmd, desc, mc) in enumerate(modes):
            mbx = mode_sx + i * (box_w + 20)
            if i == active_mode:
                mbc = brighten(mc, 1.4)
                mfc = lerp_color(BOX_BG, mc, 0.15)
                mbw = 3
            else:
                mbc = mc
                mfc = BOX_BG
                mbw = 2
            draw_box(draw, mbx, 370, box_w, 75, border_color=mbc,
                     fill_color=mfc, width=mbw)
            draw.text((mbx + box_w // 2, 395), cmd,
                      fill=mbc if i == active_mode else mc,
                      font=font_mode, anchor="mm")
            draw.text((mbx + box_w // 2, 420), desc, fill=TEXT_WHITE,
                      font=font_desc, anchor="mm")

        # Results
        if lang == 'en':
            draw.text((600, 510),
                      u"2 timing bugs found  ·  3x dev speed  ·  Race conditions detected",
                      fill=TEXT_DIM, font=font_label, anchor="mm")
        else:
            draw.text((600, 510),
                      u"2 bugs timing trouvés  ·  Vitesse 3x  ·  Conditions de course détectées",
                      fill=TEXT_DIM, font=font_label, anchor="mm")

        footer(draw)
        frames.append(img)

    save_gif(frames, f"live-session-{lang}.gif", duration=750)


# ===================================================================
# AI PERSISTENCE — Single Vicky NPC → AWARE transformation
# ===================================================================

def draw_sunglasses(draw, cx, cy, scale=1.0, alpha=1.0):
    """Draw cyan sunglasses at position. alpha controls visibility (0-1)."""
    if alpha < 0.05:
        return
    # Sunglasses color fades in
    glass_color = lerp_color(BG_TOP, ACCENT_CYAN, alpha)
    frame_color = lerp_color(TEXT_DIM, TEXT_WHITE, alpha)
    lens_fill = lerp_color(BG_TOP, (30, 80, 110), alpha)

    lw = max(2, int(3 * scale))
    lens_w = int(55 * scale)
    lens_h = int(30 * scale)
    bridge = int(12 * scale)

    # Left lens
    draw.rounded_rectangle(
        [cx - bridge - lens_w, cy - lens_h // 2,
         cx - bridge, cy + lens_h // 2],
        radius=int(6 * scale), fill=lens_fill, outline=frame_color, width=lw)
    # Right lens
    draw.rounded_rectangle(
        [cx + bridge, cy - lens_h // 2,
         cx + bridge + lens_w, cy + lens_h // 2],
        radius=int(6 * scale), fill=lens_fill, outline=frame_color, width=lw)
    # Bridge
    draw.arc([cx - bridge, cy - int(15 * scale),
              cx + bridge, cy + int(5 * scale)],
             start=180, end=0, fill=frame_color, width=lw)
    # Arms
    draw.line([(cx - bridge - lens_w, cy - int(5 * scale)),
               (cx - bridge - lens_w - int(25 * scale),
                cy - int(15 * scale))],
              fill=frame_color, width=lw)
    draw.line([(cx + bridge + lens_w, cy - int(5 * scale)),
               (cx + bridge + lens_w + int(25 * scale),
                cy - int(15 * scale))],
              fill=frame_color, width=lw)

    # Cyan glow in lenses (when nearly visible)
    if alpha > 0.6:
        glow_a = (alpha - 0.6) / 0.4
        glow_c = lerp_color(lens_fill, ACCENT_CYAN, glow_a * 0.5)
        # Left lens inner glow
        draw.rounded_rectangle(
            [cx - bridge - lens_w + 4, cy - lens_h // 2 + 4,
             cx - bridge - 4, cy + lens_h // 2 - 4],
            radius=int(4 * scale), fill=glow_c)
        # Right lens inner glow
        draw.rounded_rectangle(
            [cx + bridge + 4, cy - lens_h // 2 + 4,
             cx + bridge + lens_w - 4, cy + lens_h // 2 - 4],
            radius=int(4 * scale), fill=glow_c)


def draw_glow_rings(draw, cx, cy, radius, color, count=3):
    """Draw concentric glow rings expanding outward."""
    for i in range(count):
        r = radius + i * 12
        alpha = 1.0 - i / count
        rc = lerp_color(BG_TOP, color, alpha * 0.4)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                     outline=rc, width=2)


def gen_ai_persistence(lang='en'):
    """Single Vicky character in circular frame, NPC to AWARE transformation.

    10 frames:
      0-1: NPC — greyed, no glasses, dim
      2-3: Transition — color returning, glasses outline appearing
      4-5: Glasses on — full color, glasses solidifying
      6-7: AWARE — vibrant, cyan glow in lenses
      8-9: Glow rings + knowledge keywords
    """
    vicky_orig = load_vicky(340)
    vicky_aware_orig = load_vicky(340, sunglasses=True)
    n = 10
    frames = []

    font_title = ImageFont.truetype(FONT_BOLD, 52)
    font_sub = ImageFont.truetype(FONT_REGULAR, 28)
    font_state = ImageFont.truetype(FONT_BOLD, 38)
    font_kw = ImageFont.truetype(FONT_MONO, 17)

    # Vicky center — middle of card
    vx, vy = 600, 340

    # Make Vicky circular (like photo)
    vicky_circular = None
    vicky_npc_circular = None
    if vicky_orig:
        size = vicky_orig.width
        mask = Image.new('L', (size, size), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
        from PIL import ImageChops

        # AWARE version — use vicky-sunglasses.png (production picture)
        aware_src = vicky_aware_orig if vicky_aware_orig else vicky_orig
        vicky_circ = aware_src.copy()
        vicky_circ.putalpha(ImageChops.multiply(
            aware_src.split()[3], mask))
        vicky_circular = vicky_circ

        # NPC version — grey + dark (from original vicky.png without sunglasses)
        grey_rgb = vicky_orig.convert('LA').convert('RGBA')
        enhancer = ImageEnhance.Brightness(grey_rgb)
        vicky_npc = enhancer.enhance(0.75)
        vicky_npc.putalpha(ImageChops.multiply(
            vicky_orig.split()[3], mask))
        vicky_npc_circular = vicky_npc

    for fi in range(n):
        img, draw = base_image()

        # Title at top
        if lang == 'en':
            draw.text((600, 55), "AI Session Persistence", fill=TEXT_WHITE,
                      font=font_title, anchor="mm")
            draw.text((600, 95), "Cross-Session Knowledge Continuity",
                      fill=TEXT_MUTED, font=font_sub, anchor="mm")
        else:
            draw.text((600, 55), u"Persistance de session IA",
                      fill=TEXT_WHITE, font=font_title, anchor="mm")
            draw.text((600, 95),
                      u"Continuité des connaissances inter-sessions",
                      fill=TEXT_MUTED, font=font_sub, anchor="mm")

        # --- Vicky transformation ---
        progress = fi / (n - 1)

        # Draw circular border ring (like corporate photo ring)
        t = progress
        border_w = 3 + 3 * (0.5 + 0.5 * math.sin(2 * math.pi * t))
        if t < 0.33:
            bc = lerp_color(ACCENT_BLUE, ACCENT_CYAN, t * 3)
        elif t < 0.66:
            bc = lerp_color(ACCENT_CYAN, ACCENT_PURPLE, (t - 0.33) * 3)
        else:
            bc = lerp_color(ACCENT_PURPLE, ACCENT_BLUE, (t - 0.66) * 3)
        brightness = 1.0 + 0.2 * (border_w - 3) / 3
        bc = brighten(bc, brightness)

        photo_r = 170
        total_r = photo_r + int(border_w)

        # Outer glow rings
        for off in range(4, 0, -1):
            glow_c = lerp_color(BG_TOP, bc, 0.15 * (5 - off) / 4)
            draw.ellipse([vx - total_r - off, vy - total_r - off,
                          vx + total_r + off, vy + total_r + off],
                         outline=glow_c, width=1)
        # Main border circle
        draw.ellipse([vx - total_r, vy - total_r,
                      vx + total_r, vy + total_r],
                     fill=BOX_BG, outline=bc,
                     width=max(2, int(border_w / 2)))

        # Blend and paste Vicky
        if vicky_circular and vicky_npc_circular:
            if progress < 0.2:
                vicky_frame = vicky_npc_circular.copy()
            elif progress < 0.6:
                blend_t = (progress - 0.2) / 0.4
                vicky_frame = Image.blend(
                    vicky_npc_circular.convert('RGBA'),
                    vicky_circular.convert('RGBA'),
                    blend_t)
            else:
                vicky_frame = vicky_circular.copy()
                if progress > 0.7:
                    bright_t = 1.0 + 0.2 * (progress - 0.7) / 0.3
                    enh = ImageEnhance.Brightness(vicky_frame)
                    vicky_frame = enh.enhance(bright_t)
                    vicky_frame.putalpha(vicky_circular.split()[3])

            px = vx - vicky_frame.width // 2
            py = vy - vicky_frame.height // 2
            img.paste(vicky_frame, (px, py), vicky_frame)
        else:
            font_init = ImageFont.truetype(FONT_BOLD, 72)
            draw.text((vx, vy), "V", fill=ACCENT_CYAN, font=font_init,
                      anchor="mm")

        # Sunglasses are now part of vicky-sunglasses.png — no PIL drawing needed
        # The blend from NPC (vicky.png) to AWARE (vicky-sunglasses.png) handles the transition

        # Additional glow rings (AWARE state, frames 6-9)
        if progress >= 0.6:
            glow_progress = (progress - 0.6) / 0.4
            ring_r = int(190 + 30 * glow_progress)
            n_rings = int(1 + 2 * glow_progress)
            draw_glow_rings(draw, vx, vy, ring_r, ACCENT_CYAN,
                            count=n_rings)

        # State label below circle — high contrast colors
        if progress < 0.3:
            state_text = "NPC"
            state_color = TEXT_WHITE
        elif progress < 0.6:
            state_text = "Awakening..." if lang == 'en' else u"Éveil..."
            state_color = ACCENT_PURPLE
        elif progress < 0.8:
            state_text = "AWARE"
            state_color = ACCENT_BLUE
        else:
            state_text = "AWARE"
            state_color = ACCENT_BLUE

        draw.text((vx, vy + 195), state_text, fill=state_color,
                  font=font_state, anchor="mm")

        # Knowledge keywords (appear in later frames)
        if progress >= 0.7:
            kw_alpha = (progress - 0.7) / 0.3
            kw_color = lerp_color(TEXT_MUTED, ACCENT_PURPLE, kw_alpha)
            keywords = ["CLAUDE.md", "notes/", "wakeup", "save",
                        "lifecycle", "persist"]
            for ki, kw in enumerate(keywords):
                angle = (math.pi * 0.15 +
                         ki * math.pi * 0.7 / (len(keywords) - 1))
                kr = 220 + 20 * kw_alpha
                kx = vx + int(kr * math.cos(angle - math.pi / 2))
                ky = vy + int(kr * math.sin(angle - math.pi / 2))
                if ki <= int(kw_alpha * len(keywords)):
                    draw.text((kx, ky), kw, fill=kw_color, font=font_kw,
                              anchor="mm")

        footer(draw)
        frames.append(img)

    save_gif(frames, f"ai-persistence-{lang}.gif", duration=900)


# ===================================================================
# DISTRIBUTED MINDS — split-panel bidirectional flow diagram
# Left: title + version + layers.  Right: flow diagram with animation.
# ===================================================================

def gen_distributed_minds(lang='en'):
    """Distributed Minds webcard — bidirectional flow with split-panel layout.

    Left panel (left-aligned): Title, subtitle, knowledge layers.
    Right panel (right-aligned): Master→Satellites flow diagram with animated
    push/harvest arrows and pulsing satellite nodes.
    Middle: breathing room.

    8 frames, 250ms per frame.
    """
    n = 8
    frames = []

    font_title = ImageFont.truetype(FONT_BOLD, 40)
    font_sub = ImageFont.truetype(FONT_REGULAR, 19)
    font_label = ImageFont.truetype(FONT_BOLD, 16)
    font_layer = ImageFont.truetype(FONT_MONO, 15)
    font_node = ImageFont.truetype(FONT_BOLD, 15)
    font_node_sub = ImageFont.truetype(FONT_REGULAR, 12)
    font_arrow = ImageFont.truetype(FONT_BOLD, 14)
    font_ver = ImageFont.truetype(FONT_MONO, 22)
    font_stat = ImageFont.truetype(FONT_BOLD, 18)

    # Layout: left panel [50..520], gap [520..680], right panel [680..1150]
    LEFT_X = 50
    RIGHT_X = 680
    RIGHT_END = 1150

    if lang == 'en':
        title = "Distributed Minds"
        subtitle = "Bidirectional Knowledge Flow"
        layers = [("Core", "CLAUDE.md", ACCENT_BLUE),
                  ("Proven", "patterns/ lessons/", ACCENT_PURPLE),
                  ("Harvested", "minds/", ACCENT_CYAN),
                  ("Session", "notes/", TEXT_DIM)]
        stats = [("15", "repos"), ("9", "candidates"), ("v10", "version")]
        lbl_push = "push"
        lbl_harvest = "harvest"
    else:
        title = u"Connaissances distribuées"
        subtitle = u"Flux bidirectionnel de connaissances"
        layers = [("Core", "CLAUDE.md", ACCENT_BLUE),
                  (u"Prouvé", "patterns/ lessons/", ACCENT_PURPLE),
                  (u"Récolté", "minds/", ACCENT_CYAN),
                  ("Session", "notes/", TEXT_DIM)]
        stats = [("15", u"dépôts"), ("9", "candidats"), ("v10", "version")]
        lbl_push = "push"
        lbl_harvest = "harvest"

    # Right panel: master node and 3 satellite nodes
    master_cx = (RIGHT_X + RIGHT_END) // 2
    master_cy = 120
    master_w, master_h = 200, 56

    sat_names = ["STM32", "MPLIB", "PQC"]
    sat_colors = [ACCENT_BLUE, ACCENT_PURPLE, ACCENT_CYAN]
    sat_cx = [RIGHT_X + 55, master_cx, RIGHT_END - 55]
    sat_cy = 420
    sat_w, sat_h = 120, 44

    for fi in range(n):
        img, draw = base_image()
        t = fi / n  # 0..0.875

        # === LEFT PANEL (left-aligned) ===

        # Title
        draw.text((LEFT_X, 55), title, fill=TEXT_WHITE,
                  font=font_title, anchor="lm")

        # Subtitle
        draw.text((LEFT_X, 100), subtitle, fill=TEXT_MUTED,
                  font=font_sub, anchor="lm")

        # Version badge
        ver_color = lerp_color(ACCENT_CYAN, ACCENT_BLUE,
                               0.5 + 0.5 * math.sin(2 * math.pi * t))
        draw.rounded_rectangle([LEFT_X, 125, LEFT_X + 80, 155],
                               radius=6, fill=BOX_BG, outline=ver_color,
                               width=2)
        draw.text((LEFT_X + 40, 140), "v10", fill=ver_color,
                  font=font_arrow, anchor="mm")

        # Knowledge layers — stacked boxes
        layer_y_start = 190
        layer_h = 52
        layer_w = 430
        for li, (name, path, color) in enumerate(layers):
            ly = layer_y_start + li * (layer_h + 8)
            # Animate: highlight one layer per 2 frames
            active_layer = (fi // 2) % len(layers)
            if li == active_layer:
                bc = brighten(color, 1.4)
                fc = lerp_color(BOX_BG, color, 0.15)
                bw = 3
            else:
                bc = color
                fc = BOX_BG
                bw = 2
            draw_box(draw, LEFT_X, ly, layer_w, layer_h,
                     border_color=bc, fill_color=fc, width=bw)
            draw.text((LEFT_X + 15, ly + 16), name, fill=bc,
                      font=font_label, anchor="lm")
            draw.text((LEFT_X + 15, ly + 36), path, fill=TEXT_DIM,
                      font=font_layer, anchor="lm")

        # Stats row at bottom
        stat_y = 450
        for si, (val, label) in enumerate(stats):
            sx = LEFT_X + si * 160
            draw.text((sx + 30, stat_y), val, fill=ACCENT_BLUE,
                      font=font_stat, anchor="mm")
            draw.text((sx + 30, stat_y + 25), label, fill=TEXT_DIM,
                      font=font_node_sub, anchor="mm")

        # Catch phrase
        font_catch = ImageFont.truetype(FONT_MONO, 14)
        catch_text = "Read packetqc/knowledge"
        bbox = font_catch.getbbox(catch_text)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        code_x = LEFT_X
        code_y = 520
        pad_x, pad_y = 10, 6
        draw.rounded_rectangle(
            [code_x, code_y, code_x + tw + pad_x * 2,
             code_y + th + pad_y * 2],
            radius=5, fill=CODE_BG, outline=BORDER, width=1)
        draw.text((code_x + pad_x, code_y + pad_y), catch_text,
                  fill=TEXT_WHITE, font=font_catch)

        # === RIGHT PANEL (right-aligned) — flow diagram ===

        # Master node (top center of right panel)
        draw_box(draw, master_cx - master_w // 2, master_cy - master_h // 2,
                 master_w, master_h, border_color=ACCENT_BLUE,
                 fill_color=lerp_color(BOX_BG, ACCENT_BLUE, 0.08), width=2)
        draw.text((master_cx, master_cy - 8), "knowledge",
                  fill=ACCENT_BLUE, font=font_node, anchor="mm")
        draw.text((master_cx, master_cy + 12), "(master mind)",
                  fill=TEXT_DIM, font=font_node_sub, anchor="mm")

        # Animated arrows — push down (left), harvest up (right)
        # Arrow pulse: a bright dot travels along the arrow path
        arrow_top = master_cy + master_h // 2 + 10
        arrow_bot = sat_cy - sat_h // 2 - 10
        arrow_mid = (arrow_top + arrow_bot) // 2

        # Push arrow (left side of center) — dot moves down
        push_x = master_cx - 40
        push_progress = (t * 2) % 1.0  # cycles 0→1 twice per loop
        push_dot_y = int(lerp(arrow_top, arrow_bot, push_progress))
        # Arrow line
        draw.line([(push_x, arrow_top), (push_x, arrow_bot)],
                  fill=TEXT_DIM, width=2)
        # Arrowhead down
        draw.polygon([(push_x - 6, arrow_bot - 8), (push_x + 6, arrow_bot - 8),
                      (push_x, arrow_bot)], fill=ACCENT_BLUE)
        # Traveling dot
        dot_color = brighten(ACCENT_BLUE, 1.3)
        draw.ellipse([push_x - 5, push_dot_y - 5,
                      push_x + 5, push_dot_y + 5], fill=dot_color)
        # Label
        draw.text((push_x - 12, arrow_mid), lbl_push, fill=ACCENT_BLUE,
                  font=font_arrow, anchor="rm")

        # Harvest arrow (right side of center) — dot moves up
        harv_x = master_cx + 40
        harv_progress = ((t * 2) + 0.5) % 1.0  # offset from push
        harv_dot_y = int(lerp(arrow_bot, arrow_top, harv_progress))
        # Arrow line
        draw.line([(harv_x, arrow_bot), (harv_x, arrow_top)],
                  fill=TEXT_DIM, width=2)
        # Arrowhead up
        draw.polygon([(harv_x - 6, arrow_top + 8), (harv_x + 6, arrow_top + 8),
                      (harv_x, arrow_top)], fill=ACCENT_CYAN)
        # Traveling dot
        dot_color_h = brighten(ACCENT_CYAN, 1.3)
        draw.ellipse([harv_x - 5, harv_dot_y - 5,
                      harv_x + 5, harv_dot_y + 5], fill=dot_color_h)
        # Label
        draw.text((harv_x + 12, arrow_mid), lbl_harvest, fill=ACCENT_CYAN,
                  font=font_arrow, anchor="lm")

        # Fan-out lines from arrows to each satellite
        for si in range(3):
            # Line from push arrow bottom to satellite top
            draw.line([(push_x, arrow_bot),
                       (sat_cx[si], sat_cy - sat_h // 2)],
                      fill=dim(TEXT_DIM, 0.6), width=1)
            # Line from satellite top to harvest arrow bottom
            draw.line([(sat_cx[si], sat_cy - sat_h // 2),
                       (harv_x, arrow_bot)],
                      fill=dim(TEXT_DIM, 0.6), width=1)

        # Satellite nodes (bottom of right panel)
        for si, (name, sc) in enumerate(zip(sat_names, sat_colors)):
            # Pulse: each satellite lights up in sequence
            active_sat = fi % 3
            if si == active_sat:
                sbc = brighten(sc, 1.4)
                sfc = lerp_color(BOX_BG, sc, 0.2)
                sbw = 3
            else:
                sbc = sc
                sfc = BOX_BG
                sbw = 2

            sx_left = sat_cx[si] - sat_w // 2
            draw_box(draw, sx_left, sat_cy - sat_h // 2, sat_w, sat_h,
                     border_color=sbc, fill_color=sfc, width=sbw)
            draw.text((sat_cx[si], sat_cy), name, fill=sbc,
                      font=font_node, anchor="mm")

            # Version drift indicator (small red dot for v0)
            drift_x = sx_left + sat_w - 8
            drift_y = sat_cy - sat_h // 2 + 8
            draw.ellipse([drift_x - 4, drift_y - 4, drift_x + 4, drift_y + 4],
                         fill=(220, 50, 50))

        # Right panel: "100% drift" stat
        drift_label = "100% drift" if lang == 'en' else u"100% dérive"
        draw.text(((RIGHT_X + RIGHT_END) // 2, sat_cy + 50), drift_label,
                  fill=(220, 50, 50), font=font_arrow, anchor="mm")

        footer(draw)
        frames.append(img)

    save_gif(frames, f"distributed-minds-{lang}.gif", duration=800)


# ===================================================================
# KNOWLEDGE DASHBOARD — split-panel network status
# Left: master status metrics.  Right: satellite network grid.
# ===================================================================

def gen_knowledge_dashboard(lang='en'):
    """Knowledge Dashboard webcard — 90/10 top/bottom layout.

    Top 90%: title + full-width inventory table (up to 15 satellites).
    Bottom 10%: compact metrics summary row.

    Data is read from publications/distributed-knowledge-dashboard/v1/README.md
    so the webcard always reflects the latest harvest results.

    10 columns: Satellite, Ver, Drift, Boot, Sess, Assets, Live, Pubs, Cand., Health.
    Font size 14px for table data (scaled up from 12px to use available width).
    Sort: core first, then drift desc + version asc (most critical at top).
    8 frames, 200ms per frame.
    """
    n = 8
    frames = []

    font_title = ImageFont.truetype(FONT_BOLD, 32)
    font_metric_val = ImageFont.truetype(FONT_BOLD, 22)
    font_metric_lbl = ImageFont.truetype(FONT_REGULAR, 11)
    font_ver = ImageFont.truetype(FONT_BOLD, 15)
    font_badge = ImageFont.truetype(FONT_BOLD, 15)

    MARGIN = 30

    # --- Load real data from harvest table ---
    dash_data = parse_dashboard_data()

    if dash_data:
        m = dash_data['master']
        sats = dash_data['satellites']
    else:
        m = {'version': 'v10', 'entries': '10', 'publications': '5',
             'patterns': '4', 'pitfalls': '12'}
        sats = []

    if lang == 'en':
        title = "Knowledge Dashboard"
        col_headers = ["Satellite", "Ver", "Drift", "Boot", "Sess",
                       "Assets", "Live", "Pubs", "Cand.", "Health"]
        lbl_harvested = "harvested"
        lbl_drift = "drift"
    else:
        title = "Tableau de bord"
        col_headers = ["Satellite", "Ver", u"Dér.", "Boot", "Sess",
                       "Assets", "Live", "Pubs", "Cand.", u"Santé"]
        lbl_harvested = u"récoltés"
        lbl_drift = u"dérive"

    # Sort: core first, then version desc + drift desc (matches page tables).
    # Cap at 15.
    def _ver_num(v):
        m = re.match(r'v(\d+)', v)
        return int(m.group(1)) if m else 0

    sats_sorted = sorted(sats, key=lambda s: (
        0 if s.get('is_self') else 1,
        -_ver_num(s['version']),
        -(int(s['drift']) if s['drift'].isdigit() else 0),
    ))[:15]

    # Compute summary stats
    harv_count = len([s for s in sats if not s.get('is_self')])
    total_drift = sum(int(s['drift']) for s in sats
                      if s['drift'].isdigit())

    # === LAYOUT: 90% top / 10% bottom ===
    # Card: 630px total. Top accent: 4px, bottom accent: 4px.
    # Usable: 622px. 90% = 560px top, 10% = 62px bottom.
    BOTTOM_Y = 560                  # separator line
    FOOTER_Y = H - 20              # footer text

    # === TOP SECTION: title + inventory table — fills full content area ===
    TABLE_TOTAL = 1140              # margin-to-margin
    table_x = MARGIN                # left-aligned to margin

    title_y = 24
    header_y = 54
    hdr_h = 32
    row_gap = 2
    row_start_y = header_y + hdr_h + 2

    # Dynamic row height — fill available vertical space
    n_rows = max(len(sats_sorted), 1)
    avail_h = BOTTOM_Y - row_start_y - 4
    row_h = min(90, max(32, (avail_h - n_rows * row_gap) // n_rows))

    # Dynamic font sizing — values scale with row height, names stay fixed
    # Values: row_h 32→min 15px, row_h 90→max 28px (linear interpolation)
    td_val_size = min(28, max(15, int(15 + (row_h - 32) * 13 / 58)))
    th_size = 18  # headers fixed
    name_size = 17  # satellite names fixed
    font_th = ImageFont.truetype(FONT_BOLD, th_size)
    font_td = ImageFont.truetype(FONT_MONO, td_val_size)
    font_td_name = ImageFont.truetype(FONT_BOLD, name_size)

    # Adaptive column 1 width — fit the longest actual repo name + padding
    max_name_w = 0
    for sat in sats_sorted:
        nm = sat['name']
        if sat.get('is_self'):
            nm += '  (core)'
        w = font_td_name.getlength(nm)
        max_name_w = max(max_name_w, w)
    col1_w = int(max_name_w + 24)  # 8px left pad + 16px right breathing
    col1_w = max(280, min(440, col1_w))  # clamp between 280-440px

    # Distribute remaining width across 9 value columns proportionally
    val_total = TABLE_TOTAL - col1_w
    # Base proportions for 9 value columns
    base_props = [80, 80, 96, 74, 88, 74, 74, 82, 112]
    base_total = sum(base_props)
    val_cols = [int(p * val_total / base_total) for p in base_props]
    # Fix rounding: add/subtract remainder to last column
    val_cols[-1] += val_total - sum(val_cols)
    col_widths = [col1_w] + val_cols
    table_w = sum(col_widths)

    for fi in range(n):
        img, draw = base_image()
        t = fi / n

        # === TOP — Title + pulsing version badge ===
        draw.text((MARGIN, title_y), title, fill=TEXT_WHITE,
                  font=font_title, anchor="lm")

        vc = lerp_color(ACCENT_BLUE, ACCENT_CYAN,
                        0.5 + 0.5 * math.sin(2 * math.pi * t))
        ver_x = MARGIN + font_title.getlength(title) + 14
        draw.rounded_rectangle([ver_x, title_y - 14, ver_x + 58,
                                title_y + 12],
                               radius=5, fill=BOX_BG, outline=vc, width=2)
        draw.text((ver_x + 29, title_y - 1), m['version'], fill=vc,
                  font=font_ver, anchor="mm")

        # === TOP — Inventory table header ===
        hx = table_x
        draw.rounded_rectangle(
            [table_x - 5, header_y - 2, table_x + table_w + 5,
             header_y + hdr_h - 1],
            radius=4, fill=lerp_color(BOX_BG, ACCENT_BLUE, 0.08),
            outline=BORDER, width=1)
        for ci, (hdr, cw) in enumerate(zip(col_headers, col_widths)):
            draw.text((hx + cw // 2, header_y + hdr_h // 2 - 1), hdr,
                      fill=ACCENT_BLUE, font=font_th, anchor="mm")
            hx += cw

        # === TOP — Data rows (core first, scan animation) ===
        scan_idx = fi % max(len(sats_sorted), 1)
        for si, sat in enumerate(sats_sorted):
            ry = row_start_y + si * (row_h + row_gap)
            if ry + row_h > BOTTOM_Y - 4:
                break

            is_self = sat.get('is_self', False)
            is_scanned = si == scan_idx

            if is_scanned:
                row_fill = lerp_color(BOX_BG, ACCENT_CYAN, 0.15)
                row_border = brighten(ACCENT_CYAN, 1.3)
                row_bw = 2
            elif is_self:
                row_fill = lerp_color(BOX_BG, ACCENT_GREEN, 0.06)
                row_border = ACCENT_GREEN
                row_bw = 1
            else:
                row_fill = BOX_BG
                row_border = BORDER
                row_bw = 1

            draw.rounded_rectangle(
                [table_x - 5, ry - 1, table_x + table_w + 5,
                 ry + row_h - 1],
                radius=4, fill=row_fill, outline=row_border, width=row_bw)

            # Cell values — truncate name to fit column at current font size
            name = sat['name']
            max_name_px = col_widths[0] - 16  # 8px padding each side
            if is_self:
                suffix = '  (core)'
            else:
                suffix = ''
            # Pixel-based truncation
            while (font_td_name.getlength(name + suffix) > max_name_px
                   and len(name) > 4):
                name = name[:-1]
            if name != sat['name']:
                name = name.rstrip() + '..'
            name += suffix

            boot = sat.get('bootstrap', 'missing')
            boot_short = (u"\u2713" if boot in ('core', '**core**', 'active')
                          else u"\u2713" if 'knowledge' in boot.lower()
                          else u"\u2717")
            sess = sat.get('sessions', '0')
            assets = sat.get('assets', 'missing')
            assets_short = (u"\u2713" if assets in ('core', 'deployed',
                            '**core**', 'active')
                            or 'deploy' in assets.lower()
                            else u"\u2717")
            live = sat.get('live', '0')
            live_m = re.match(r'(\d+)', live)
            live_num = live_m.group(1) if live_m else '0'
            pubs = sat.get('publications', '0')
            pubs_m = re.match(r'(\d+)', pubs)
            pubs_num = pubs_m.group(1) if pubs_m else '0'

            cells = [name, sat['version'], sat['drift'],
                     boot_short, sess, assets_short, live_num,
                     pubs_num, sat.get('candidates', '0'),
                     sat.get('health', 'pending')]
            cx = table_x
            for ci, (cell, cw) in enumerate(zip(cells, col_widths)):
                text_y = ry + row_h // 2 - 1
                if ci == 0:
                    # Satellite name
                    color = ACCENT_GREEN if is_self else TEXT_WHITE
                    if is_scanned:
                        color = brighten(ACCENT_CYAN, 1.2)
                    draw.text((cx + 8, text_y), cell,
                              fill=color, font=font_td_name, anchor="lm")
                elif ci == 1:
                    # Version
                    color = ((220, 50, 50) if cell == 'v0'
                             else ACCENT_GREEN if cell == m['version']
                             else TEXT_MUTED)
                    draw.text((cx + cw // 2, text_y), cell,
                              fill=color, font=font_td, anchor="mm")
                elif ci == 2:
                    # Drift
                    color = ((220, 50, 50)
                             if cell.isdigit() and int(cell) > 0
                             else ACCENT_GREEN if cell == '0'
                             else TEXT_DIM)
                    draw.text((cx + cw // 2, text_y), cell,
                              fill=color, font=font_td, anchor="mm")
                elif ci == 3:
                    # Bootstrap (checkmark or X)
                    color = (ACCENT_GREEN if u"\u2713" in cell
                             else (220, 50, 50))
                    draw.text((cx + cw // 2, text_y), cell,
                              fill=color, font=font_td, anchor="mm")
                elif ci == 4:
                    # Sessions
                    color = (ACCENT_GREEN
                             if cell.isdigit() and int(cell) > 0
                             else TEXT_DIM)
                    draw.text((cx + cw // 2, text_y), cell,
                              fill=color, font=font_td, anchor="mm")
                elif ci == 5:
                    # Assets (deployed/missing)
                    color = (ACCENT_GREEN if u"\u2713" in cell
                             else (220, 50, 50))
                    draw.text((cx + cw // 2, text_y), cell,
                              fill=color, font=font_td, anchor="mm")
                elif ci == 6:
                    # Live (active instances on network)
                    color = (ACCENT_CYAN
                             if cell.isdigit() and int(cell) > 0
                             else TEXT_DIM)
                    draw.text((cx + cw // 2, text_y), cell,
                              fill=color, font=font_td, anchor="mm")
                elif ci == 7:
                    # Publications
                    color = (ACCENT_PURPLE
                             if cell.isdigit() and int(cell) > 0
                             else TEXT_DIM)
                    draw.text((cx + cw // 2, text_y), cell,
                              fill=color, font=font_td, anchor="mm")
                elif ci == 8:
                    # Candidates
                    color = (ACCENT_PURPLE
                             if cell.isdigit() and int(cell) > 0
                             else TEXT_DIM)
                    draw.text((cx + cw // 2, text_y), cell,
                              fill=color, font=font_td, anchor="mm")
                elif ci == 9:
                    # Health (with dot indicator)
                    if cell == 'healthy':
                        dot_c = ACCENT_GREEN
                        lbl = u"\u2713"
                    elif cell == 'unreachable':
                        dot_c = (220, 50, 50)
                        lbl = u"\u2717"
                    elif cell == 'stale':
                        dot_c = (220, 160, 50)
                        lbl = "!"
                    else:
                        dot_c = TEXT_DIM
                        lbl = "?"
                    dot_cx = cx + cw // 2 - 6
                    draw.ellipse([dot_cx - 4, text_y - 4,
                                  dot_cx + 4, text_y + 4], fill=dot_c)
                    draw.text((dot_cx + 10, text_y), lbl,
                              fill=dot_c, font=font_td, anchor="lm")
                cx += cw

        # === BOTTOM 10% — separator + compact metrics + footer ===
        draw.line([(MARGIN, BOTTOM_Y), (W - MARGIN, BOTTOM_Y)],
                  fill=BORDER, width=1)

        # Metrics row: version | entries | pubs | patterns | pitfalls
        #              + harvested badge + drift badge
        metric_y = BOTTOM_Y + 22
        metrics = [
            (m['version'], "ver", vc),
            (m['entries'], "evo", TEXT_WHITE),
            (m['publications'], "pubs", TEXT_WHITE),
            (m['patterns'], "pat", TEXT_WHITE),
            (m['pitfalls'], "pit", TEXT_WHITE),
        ]
        n_met = len(metrics)
        met_spacing = 100
        met_start = MARGIN + 20
        for mi, (val, lbl, color) in enumerate(metrics):
            mx = met_start + mi * met_spacing
            draw.text((mx, metric_y - 6), val, fill=color,
                      font=font_metric_val, anchor="mm")
            draw.text((mx, metric_y + 12), lbl, fill=TEXT_DIM,
                      font=font_metric_lbl, anchor="mm")

        # Badges: harvested + drift (right side)
        badge_x = met_start + n_met * met_spacing + 20
        draw_box(draw, badge_x, metric_y - 14, 120, 26,
                 border_color=ACCENT_CYAN, width=2, radius=5)
        draw.text((badge_x + 60, metric_y - 1),
                  f"{harv_count} {lbl_harvested}", fill=ACCENT_CYAN,
                  font=font_badge, anchor="mm")

        if total_drift > 0:
            badge_x2 = badge_x + 132
            draw_box(draw, badge_x2, metric_y - 14, 110, 26,
                     border_color=(220, 50, 50), width=2, radius=5)
            draw.text((badge_x2 + 55, metric_y - 1),
                      f"{total_drift} {lbl_drift}", fill=(220, 50, 50),
                      font=font_badge, anchor="mm")

        # Footer below metrics
        font_foot = ImageFont.truetype(FONT_REGULAR, 11)
        draw.text((W // 2, H - 18),
                  "harvest --healthcheck  |  packetqc/knowledge",
                  fill=TEXT_DIM, font=font_foot, anchor="mm")
        frames.append(img)

    save_gif(frames, f"knowledge-dashboard-{lang}.gif", duration=750)


# ===================================================================
# PUBLICATIONS INDEX — cards appear one by one with glow
# ===================================================================

def gen_knowledge_system(lang='en'):
    """Knowledge System — hub-and-spoke: #0 center + 5 children radiating."""
    if lang == 'en':
        title_text = "Knowledge"
        subtitle_text = "Self-Evolving AI Engineering Intelligence"
        hub_label = "Knowledge"
        children = [
            ("#3", "AI Persistence", "Foundation", ACCENT_CYAN),
            ("#1", "MPLIB Pipeline", "First satellite", ACCENT_BLUE),
            ("#2", "Live Session", "Tooling", ACCENT_PURPLE),
            ("#4", "Distributed Minds", "Architecture", ACCENT_GREEN),
            ("#4a", "Dashboard", "Self-awareness", ACCENT_BLUE),
        ]
    else:
        title_text = "Knowledge"
        subtitle_text = u"Intelligence d\u2019ing\u00e9nierie IA auto-\u00e9volutive"
        hub_label = "Knowledge"
        children = [
            ("#3", u"Persistance IA", "Fondation", ACCENT_CYAN),
            ("#1", "MPLIB Pipeline", u"1er satellite", ACCENT_BLUE),
            ("#2", "Session en direct", "Outillage", ACCENT_PURPLE),
            ("#4", u"Connaissances distribu\u00e9es", "Architecture", ACCENT_GREEN),
            ("#4a", "Tableau de bord", u"Conscience de soi", ACCENT_BLUE),
        ]

    n = 8
    frames = []

    font_title = ImageFont.truetype(FONT_BOLD, 40)
    font_sub = ImageFont.truetype(FONT_REGULAR, 20)
    font_hub_num = ImageFont.truetype(FONT_BOLD, 48)
    font_hub_label = ImageFont.truetype(FONT_BOLD, 18)
    font_child_num = ImageFont.truetype(FONT_BOLD, 28)
    font_child_name = ImageFont.truetype(FONT_BOLD, 14)
    font_child_role = ImageFont.truetype(FONT_REGULAR, 12)

    # Layout — hub center, children in arc below
    hub_cx, hub_cy = 600, 260
    hub_w, hub_h = 220, 100

    # Child positions — spread evenly below the hub
    child_w, child_h = 180, 80
    child_positions = []
    nc = len(children)
    total_cw = nc * child_w + (nc - 1) * 20
    cx_start = (W - total_cw) // 2
    child_y = 440
    for i in range(nc):
        cx = cx_start + i * (child_w + 20) + child_w // 2
        child_positions.append((cx, child_y))

    for fi in range(n):
        img, draw = base_image()

        # Title
        draw.text((600, 65), title_text, fill=TEXT_WHITE,
                  font=font_title, anchor="mm")
        draw.text((600, 105), subtitle_text, fill=TEXT_MUTED,
                  font=font_sub, anchor="mm")

        # Hub — appears on frame 1+
        if fi >= 1:
            hub_age = fi - 1
            if hub_age == 0:
                hbc = dim(ACCENT_BLUE, 0.5)
                hfc = lerp_color(BG_BOT, BOX_BG, 0.5)
                htc = dim(TEXT_WHITE, 0.6)
                hbw = 2
            elif fi >= 7:
                hbc = brighten(ACCENT_BLUE, 1.4)
                hfc = lerp_color(BOX_BG, ACCENT_BLUE, 0.15)
                htc = TEXT_WHITE
                hbw = 3
            else:
                hbc = ACCENT_BLUE
                hfc = BOX_BG
                htc = TEXT_WHITE
                hbw = 2

            draw_box(draw, hub_cx - hub_w // 2, hub_cy - hub_h // 2,
                     hub_w, hub_h, border_color=hbc, fill_color=hfc, width=hbw)
            draw.text((hub_cx, hub_cy - 20), "#0", fill=hbc,
                      font=font_hub_num, anchor="mm")
            draw.text((hub_cx, hub_cy + 25), hub_label, fill=htc,
                      font=font_hub_label, anchor="mm")

        # Children — appear one per frame starting at frame 2
        for ci, (num, name, role, color) in enumerate(children):
            child_appear = ci + 2  # frame 2,3,4,5,6
            if fi < child_appear:
                continue

            ccx, ccy = child_positions[ci]
            cage = fi - child_appear

            if cage == 0:
                cbc = dim(color, 0.5)
                cfc = lerp_color(BG_BOT, BOX_BG, 0.5)
                cnc = dim(color, 0.6)
                ctc = lerp_color(BG_BOT, TEXT_WHITE, 0.5)
                crc = lerp_color(BG_BOT, TEXT_MUTED, 0.5)
                cbw = 2
                line_color = dim(color, 0.3)
            elif fi >= 7:
                cbc = brighten(color, 1.3)
                cfc = lerp_color(BOX_BG, color, 0.12)
                cnc = brighten(color, 1.3)
                ctc = TEXT_WHITE
                crc = TEXT_MUTED
                cbw = 3
                line_color = brighten(color, 1.2)
            else:
                cbc = color
                cfc = BOX_BG
                cnc = color
                ctc = TEXT_WHITE
                crc = TEXT_MUTED
                cbw = 2
                line_color = color

            # Connection line from hub bottom to child top
            if fi >= 1:
                draw.line([(hub_cx, hub_cy + hub_h // 2),
                           (ccx, ccy - child_h // 2)],
                          fill=line_color, width=2)

            # Child box
            draw_box(draw, ccx - child_w // 2, ccy - child_h // 2,
                     child_w, child_h, border_color=cbc, fill_color=cfc,
                     width=cbw)
            draw.text((ccx, ccy - 18), num, fill=cnc,
                      font=font_child_num, anchor="mm")
            draw.text((ccx, ccy + 8), name, fill=ctc,
                      font=font_child_name, anchor="mm")
            draw.text((ccx, ccy + 26), role, fill=crc,
                      font=font_child_role, anchor="mm")

        footer(draw)
        frames.append(img)

    save_gif(frames, f"knowledge-system-{lang}.gif", duration=800)


def gen_knowledge_2(lang='en'):
    """Knowledge 2.0 — Interactive Intelligence Framework.
    Diagram type: hub (Knowledge 2.0) + 6 feature nodes radiating below."""
    if lang == 'en':
        title_text = "Knowledge 2.0"
        subtitle_text = "Interactive Intelligence Framework"
        hub_label = "K 2.0"
        children = [
            ("Q", "Questionnaire", "Session grid", ACCENT_CYAN),
            ("R", "Router", "routes.json", ACCENT_BLUE),
            ("S", "Skills", "Registry", ACCENT_PURPLE),
            ("M", "Methodology", "Family resolve", ACCENT_GREEN),
            ("D", "Dedup", "0 re-reads", ACCENT_CYAN),
            ("I", "Interactive", "3 modes", ACCENT_BLUE),
        ]
    else:
        title_text = "Knowledge 2.0"
        subtitle_text = u"Cadre d\u2019intelligence interactif"
        hub_label = "K 2.0"
        children = [
            ("Q", "Questionnaire", u"Grille session", ACCENT_CYAN),
            ("R", "Routeur", "routes.json", ACCENT_BLUE),
            ("S", "Skills", u"Registre", ACCENT_PURPLE),
            ("M", u"M\u00e9thodologie", u"R\u00e9solution", ACCENT_GREEN),
            ("D", u"D\u00e9dup", u"0 relectures", ACCENT_CYAN),
            ("I", "Interactif", "3 modes", ACCENT_BLUE),
        ]

    n = 8
    frames = []

    font_title = ImageFont.truetype(FONT_BOLD, 40)
    font_sub = ImageFont.truetype(FONT_REGULAR, 20)
    font_hub_num = ImageFont.truetype(FONT_BOLD, 44)
    font_hub_label = ImageFont.truetype(FONT_BOLD, 16)
    font_child_num = ImageFont.truetype(FONT_BOLD, 32)
    font_child_name = ImageFont.truetype(FONT_BOLD, 14)
    font_child_role = ImageFont.truetype(FONT_REGULAR, 12)

    # Layout — hub center, children in arc below
    hub_cx, hub_cy = 600, 250
    hub_w, hub_h = 200, 90

    # Child positions — 6 nodes spread evenly below
    child_w, child_h = 160, 75
    nc = len(children)
    total_cw = nc * child_w + (nc - 1) * 16
    cx_start = (W - total_cw) // 2
    child_y = 440
    child_positions = []
    for i in range(nc):
        cx = cx_start + i * (child_w + 16) + child_w // 2
        child_positions.append((cx, child_y))

    for fi in range(n):
        img, draw = base_image()

        # Title
        draw.text((600, 60), title_text, fill=TEXT_WHITE,
                  font=font_title, anchor="mm")
        draw.text((600, 100), subtitle_text, fill=TEXT_MUTED,
                  font=font_sub, anchor="mm")

        # Hub — appears on frame 1+
        if fi >= 1:
            hub_age = fi - 1
            if hub_age == 0:
                hbc = dim(ACCENT_GREEN, 0.5)
                hfc = lerp_color(BG_BOT, BOX_BG, 0.5)
                htc = dim(TEXT_WHITE, 0.6)
                hbw = 2
            elif fi >= 7:
                hbc = brighten(ACCENT_GREEN, 1.4)
                hfc = lerp_color(BOX_BG, ACCENT_GREEN, 0.15)
                htc = TEXT_WHITE
                hbw = 3
            else:
                hbc = ACCENT_GREEN
                hfc = BOX_BG
                htc = TEXT_WHITE
                hbw = 2

            draw_box(draw, hub_cx - hub_w // 2, hub_cy - hub_h // 2,
                     hub_w, hub_h, border_color=hbc, fill_color=hfc, width=hbw)
            draw.text((hub_cx, hub_cy - 16), hub_label, fill=hbc,
                      font=font_hub_num, anchor="mm")
            # Version badge
            draw.text((hub_cx, hub_cy + 22), "v2 — March 2026", fill=htc,
                      font=font_hub_label, anchor="mm")

        # Children — appear one per frame starting at frame 2
        for ci, (num, name, role, color) in enumerate(children):
            child_appear = ci + 2  # frame 2,3,4,5,6,7
            if fi < child_appear:
                continue

            ccx, ccy = child_positions[ci]
            cage = fi - child_appear

            if cage == 0:
                cbc = dim(color, 0.5)
                cfc = lerp_color(BG_BOT, BOX_BG, 0.5)
                cnc = dim(color, 0.6)
                ctc = lerp_color(BG_BOT, TEXT_WHITE, 0.5)
                crc = lerp_color(BG_BOT, TEXT_MUTED, 0.5)
                cbw = 2
                line_color = dim(color, 0.3)
            elif fi >= 7:
                cbc = brighten(color, 1.3)
                cfc = lerp_color(BOX_BG, color, 0.12)
                cnc = brighten(color, 1.3)
                ctc = TEXT_WHITE
                crc = TEXT_MUTED
                cbw = 3
                line_color = brighten(color, 1.2)
            else:
                cbc = color
                cfc = BOX_BG
                cnc = color
                ctc = TEXT_WHITE
                crc = TEXT_MUTED
                cbw = 2
                line_color = color

            # Connection line from hub bottom to child top
            if fi >= 1:
                draw.line([(hub_cx, hub_cy + hub_h // 2),
                           (ccx, ccy - child_h // 2)],
                          fill=line_color, width=2)

            # Child box
            draw_box(draw, ccx - child_w // 2, ccy - child_h // 2,
                     child_w, child_h, border_color=cbc, fill_color=cfc,
                     width=cbw)
            draw.text((ccx, ccy - 16), num, fill=cnc,
                      font=font_child_num, anchor="mm")
            draw.text((ccx, ccy + 8), name, fill=ctc,
                      font=font_child_name, anchor="mm")
            draw.text((ccx, ccy + 24), role, fill=crc,
                      font=font_child_role, anchor="mm")

        footer(draw, "Martin Paquet & Claude  |  packetqc/knowledge")
        frames.append(img)

    save_gif(frames, f"knowledge-2-{lang}.gif", duration=800)


def gen_publications_index(lang='en'):
    if lang == 'en':
        pubs = [
            ("#1", "MPLIB Storage Pipeline",
             "2,650 logs/sec on Cortex-M55", ACCENT_BLUE),
            ("#2", "Live Session Analysis",
             "~6 sec AI debugging feedback", ACCENT_PURPLE),
            ("#3", "AI Session Persistence",
             "30-sec context recovery", ACCENT_CYAN),
        ]
    else:
        pubs = [
            ("#1", "MPLIB Storage Pipeline",
             u"2 650 logs/sec sur Cortex-M55", ACCENT_BLUE),
            ("#2", "Analyse de session en direct",
             u"~6 sec retour IA", ACCENT_PURPLE),
            ("#3", u"Persistance de session IA",
             u"Récup. contexte 30 sec", ACCENT_CYAN),
        ]

    # 8 frames: 0=empty, 1=card1 fade, 2=card1 solid, 3=card2 fade,
    #           4=card2 solid, 5=card3 fade, 6=all solid, 7=all glow
    n = 8
    frames = []

    font_title = ImageFont.truetype(FONT_BOLD, 46)
    font_sub = ImageFont.truetype(FONT_REGULAR, 22)
    font_num = ImageFont.truetype(FONT_BOLD, 42)
    font_pub = ImageFont.truetype(FONT_BOLD, 19)
    font_desc = ImageFont.truetype(FONT_REGULAR, 16)

    box_w = 320
    total_bw = len(pubs) * box_w + (len(pubs) - 1) * 25
    sx = (W - total_bw) // 2

    for fi in range(n):
        img, draw = base_image()

        if lang == 'en':
            draw.text((600, 80), "Technical Publications", fill=TEXT_WHITE,
                      font=font_title, anchor="mm")
            draw.text((600, 125),
                      u"Embedded Systems · AI Workflows · Methodology",
                      fill=TEXT_MUTED, font=font_sub, anchor="mm")
        else:
            draw.text((600, 80), "Publications techniques", fill=TEXT_WHITE,
                      font=font_title, anchor="mm")
            draw.text((600, 125),
                      u"Systèmes embarqués · Flux IA · Méthodologie",
                      fill=TEXT_MUTED, font=font_sub, anchor="mm")

        # Determine card visibility
        # fi: 0=none, 1=c1 fading, 2=c1+c2 fading, 3=c1+c2 solid,
        #     4=c1+c2+c3 fading, 5=all solid, 6=all glow1, 7=all glow2
        for ci, (num, title, desc, color) in enumerate(pubs):
            bx = sx + ci * (box_w + 25)

            # Determine this card's state
            card_appear_frame = ci * 2  # 0, 2, 4
            if fi < card_appear_frame:
                continue  # not visible yet

            age = fi - card_appear_frame
            if age == 0:
                # Fading in: dim border, muted content
                bc = dim(color, 0.5)
                fc = lerp_color(BG_BOT, BOX_BG, 0.5)
                nc = dim(color, 0.6)
                tc = lerp_color(BG_BOT, TEXT_WHITE, 0.5)
                dc = lerp_color(BG_BOT, TEXT_MUTED, 0.5)
                bw = 2
            elif fi >= 6:
                # Glow state
                glow_t = (fi - 6) / 1.0
                bc = brighten(color, 1.3 + 0.2 * glow_t)
                fc = lerp_color(BOX_BG, color, 0.1 + 0.05 * glow_t)
                nc = brighten(color, 1.3 + 0.2 * glow_t)
                tc = TEXT_WHITE
                dc = TEXT_MUTED
                bw = 3
            else:
                # Solid
                bc = color
                fc = BOX_BG
                nc = color
                tc = TEXT_WHITE
                dc = TEXT_MUTED
                bw = 2

            draw_box(draw, bx, 190, box_w, 180, border_color=bc,
                     fill_color=fc, width=bw)
            draw.text((bx + box_w // 2, 225), num, fill=nc,
                      font=font_num, anchor="mm")
            draw.text((bx + box_w // 2, 275), title, fill=tc,
                      font=font_pub, anchor="mm")
            draw.text((bx + box_w // 2, 310), desc, fill=dc,
                      font=font_desc, anchor="mm")

        # Author
        if lang == 'en':
            draw.text((600, 450),
                      "By Martin Paquet & Claude (Anthropic, Opus 4.6)",
                      fill=TEXT_MUTED, font=font_sub, anchor="mm")
        else:
            draw.text((600, 450),
                      "Par Martin Paquet & Claude (Anthropic, Opus 4.6)",
                      fill=TEXT_MUTED, font=font_sub, anchor="mm")

        draw.text((600, 510), "packetqc/knowledge", fill=TEXT_DIM,
                  font=font_sub, anchor="mm")

        footer(draw)
        frames.append(img)

    save_gif(frames, f"publications-index-{lang}.gif", duration=800)


# ===================================================================
# Generic animated text-card generator — reused by pubs #5-#10
# ===================================================================

def gen_text_card(lang, card_name, title_en, title_fr, subtitle_en, subtitle_fr,
                  keywords_en, keywords_fr, pub_num):
    """Generic animated card: title + subtitle + keywords appearing one by one."""
    title = title_en if lang == 'en' else title_fr
    subtitle = subtitle_en if lang == 'en' else subtitle_fr
    keywords = keywords_en if lang == 'en' else keywords_fr

    n = 8
    frames = []

    font_title = ImageFont.truetype(FONT_BOLD, 38)
    font_sub = ImageFont.truetype(FONT_REGULAR, 20)
    font_num = ImageFont.truetype(FONT_BOLD, 56)
    font_kw = ImageFont.truetype(FONT_BOLD, 18)
    font_footer_text = ImageFont.truetype(FONT_REGULAR, 14)

    # Keyword box layout
    kw_colors = [ACCENT_BLUE, ACCENT_PURPLE, ACCENT_CYAN, ACCENT_GREEN,
                 ACCENT_BLUE, ACCENT_PURPLE, ACCENT_CYAN, ACCENT_GREEN]

    for fi in range(n):
        img, draw = base_image()

        # Publication number — always visible, pulses on last frames
        if fi >= 6:
            nc = brighten(ACCENT_BLUE, 1.4)
        else:
            nc = ACCENT_BLUE
        draw.text((600, 100), pub_num, fill=nc, font=font_num, anchor="mm")

        # Title
        draw.text((600, 170), title, fill=TEXT_WHITE, font=font_title, anchor="mm")

        # Subtitle
        draw.text((600, 210), subtitle, fill=TEXT_MUTED, font=font_sub, anchor="mm")

        # Keywords — appear one by one starting frame 1
        nk = len(keywords)
        kw_w = 200
        kw_h = 50
        kw_gap = 15
        cols = min(nk, 4)
        rows = (nk + cols - 1) // cols
        total_w = cols * kw_w + (cols - 1) * kw_gap
        sx = (W - total_w) // 2
        sy = 270

        for ki, kw in enumerate(keywords):
            kw_appear = ki + 1
            if fi < kw_appear:
                continue

            row = ki // cols
            col = ki % cols
            kx = sx + col * (kw_w + kw_gap)
            ky = sy + row * (kw_h + kw_gap)
            kc = kw_colors[ki % len(kw_colors)]

            age = fi - kw_appear
            if age == 0:
                bc = dim(kc, 0.5)
                fc = lerp_color(BG_BOT, BOX_BG, 0.5)
                tc = dim(TEXT_WHITE, 0.5)
                bw = 2
            elif fi >= 6:
                bc = brighten(kc, 1.3)
                fc = lerp_color(BOX_BG, kc, 0.12)
                tc = TEXT_WHITE
                bw = 3
            else:
                bc = kc
                fc = BOX_BG
                tc = TEXT_WHITE
                bw = 2

            draw_box(draw, kx, ky, kw_w, kw_h, border_color=bc,
                     fill_color=fc, width=bw)
            draw.text((kx + kw_w // 2, ky + kw_h // 2), kw, fill=tc,
                      font=font_kw, anchor="mm")

        footer(draw)
        frames.append(img)

    save_gif(frames, f"{card_name}-{lang}.gif", duration=750)


def gen_webcards_social_sharing(lang='en'):
    """#5 — Webcards & Social Sharing."""
    gen_text_card(lang, 'webcards-social-sharing',
        "Webcards & Social Sharing",
        u"Webcards et partage social",
        "Animated OG Social Preview System",
        u"Syst\u00e8me d\u2019aper\u00e7u social anim\u00e9",
        ["Animated GIF", "Dual Theme", "OG Tags", "Bilingual",
         "1200\u00d7630", "Social Preview"],
        [u"GIF anim\u00e9", u"Double th\u00e8me", "OG Tags", "Bilingue",
         "1200\u00d7630", u"Aper\u00e7u social"],
        "#5")


def gen_normalize(lang='en'):
    """#6 — Normalize & Structure Concordance."""
    gen_text_card(lang, 'normalize',
        "Normalize & Concordance",
        "Normalize et concordance",
        "Self-Healing Knowledge Architecture",
        u"Architecture de connaissances auto-r\u00e9paratrice",
        ["Structure", "Layout", "Webcards", "Links",
         "Assets", "Mindset", "Bilingual"],
        ["Structure", "Mise en page", "Webcards", "Liens",
         "Assets", u"Mentalit\u00e9", "Bilingue"],
        "#6")


def gen_harvest_protocol(lang='en'):
    """#7 — Harvest Protocol."""
    gen_text_card(lang, 'harvest-protocol',
        "Harvest Protocol",
        u"Protocole de r\u00e9colte",
        "Distributed Knowledge Collection",
        u"Collecte de connaissances distribu\u00e9es",
        ["Crawl", "Extract", "Review", "Stage",
         "Promote", "Healthcheck"],
        ["Explorer", "Extraire", u"R\u00e9viser", u"Pr\u00e9parer",
         "Promouvoir", u"Bilan de sant\u00e9"],
        "#7")


def gen_session_management(lang='en'):
    """#8 — Session Management."""
    gen_text_card(lang, 'session-management',
        "Session Management",
        "Gestion de session",
        "Wakeup \u2192 Work \u2192 Save \u2192 Resume",
        u"Wakeup \u2192 Travail \u2192 Save \u2192 Reprise",
        ["Wakeup", "Save", "Resume", "Recall",
         "Checkpoint", "Refresh"],
        ["Wakeup", "Save", "Reprise", u"R\u00e9cup\u00e9rer",
         u"Point de contr\u00f4le", u"Rafra\u00eechir"],
        "#8")


def gen_security_by_design(lang='en'):
    """#9 — Security by Design."""
    gen_text_card(lang, 'security-by-design',
        "Security by Design",
        u"S\u00e9curit\u00e9 par conception",
        "Zero Credentials, Full Protection",
        u"Z\u00e9ro identifiants, protection compl\u00e8te",
        ["Ephemeral", "PQC Envelope", "Proxy-Scoped",
         "Owner-Only", "Fork-Safe", "Compliance"],
        [u"\u00c9ph\u00e9m\u00e8re", "PQC Envelope", u"Port\u00e9e proxy",
         u"Propri\u00e9taire", u"Fork s\u00fbr", u"Conformit\u00e9"],
        "#9")


def gen_live_knowledge_network(lang='en'):
    """#10 — Live Knowledge Network."""
    gen_text_card(lang, 'live-knowledge-network',
        "Live Knowledge Network",
        u"R\u00e9seau de connaissances en direct",
        "PQC-Secured Inter-Instance Discovery",
        u"D\u00e9couverte inter-instances s\u00e9curis\u00e9e PQC",
        ["Beacon", "Scanner", "ML-KEM-1024", "Discovery",
         "Port 21337", "Encrypted"],
        ["Balise", "Scanner", "ML-KEM-1024", u"D\u00e9couverte",
         "Port 21337", u"Chiffr\u00e9"],
        "#10")


def gen_project_management(lang='en'):
    """#12 — Project Management."""
    gen_text_card(lang, 'project-management',
        "Project Management",
        u"Gestion de projet",
        "First-Class Entities & Hierarchical Indexing",
        u"Entit\u00e9s de premier ordre et indexation hi\u00e9rarchique",
        ["P#/S#/D#", "Bootstrap", "Dual-Origin",
         "Satellite", "Tagged Input", "Web Scaffold"],
        ["P#/S#/D#", "Bootstrap", "Double origine",
         "Satellite", u"Entr\u00e9e cibl\u00e9e", u"Pr\u00e9sence web"],
        "#12")


def gen_behavioral_intelligence(lang='en'):
    """#25 — Behavioral Intelligence."""
    gen_text_card(lang, 'behavioral-intelligence',
        "Behavioral Intelligence",
        "Intelligence comportementale",
        "Operant Conditioning for AI Agents",
        "Conditionnement op\u00e9rant pour agents IA",
        ["Soar", "CMC", "Routing", "Scaffolding",
         "Approval", "Self-Evolving"],
        ["Soar", "CMC", "Routage", "Scaffolding",
         "Approbation", u"Auto-\u00e9volution"],
        "#25")


# ===================================================================
# Generic text-card from front matter — for new publications
# ===================================================================

def gen_from_frontmatter(pub_path, lang='en'):
    """Generate a text-card webcard from a publication's front matter.

    Usage: python3 generate_og_gifs.py --from-frontmatter docs/publications/<slug>/index.md
    """
    import yaml  # noqa: delayed import

    with open(pub_path, 'r') as f:
        content = f.read()

    # Extract YAML front matter
    if not content.startswith('---'):
        print(f"  ERROR: No front matter in {pub_path}")
        return
    parts = content.split('---', 2)
    fm = yaml.safe_load(parts[1])

    # Derive slug from path
    slug = os.path.basename(os.path.dirname(pub_path))
    pub_id = fm.get('pub_id', '')
    # Extract number from "Publication #25" or "Publication #25 — Full"
    num_match = re.match(r'Publication (#\d+\w?)', pub_id)
    pub_num = num_match.group(1) if num_match else ''

    title = fm.get('title', slug).split(' — ')[0]  # Take first part before em dash
    description = fm.get('description', '')
    # Use first sentence of description as subtitle
    subtitle = description.split('.')[0] if '.' in description else description[:60]

    # Extract keywords from front matter
    kw_str = fm.get('keywords', '')
    keywords = [k.strip().title() for k in kw_str.split(',')][:6]

    gen_text_card(lang, slug, title, title, subtitle, subtitle,
                  keywords, keywords, pub_num)


# ===================================================================
# IMPORT — wrap any animated GIF into the standard webcard frame
# ===================================================================

def gen_import_card(lang, card_name, title_en, title_fr, subtitle_en, subtitle_fr,
                    gif_path, pub_num=None):
    """Import an external animated GIF into the standard webcard frame.

    Resizes/crops the source GIF into the content zone (140-530),
    preserving all source frames. Adds title zone, footer, and accent bars.
    Works with any animated GIF — test results, demos, screen captures, etc.
    """
    title = title_en if lang == 'en' else title_fr
    subtitle = subtitle_en if lang == 'en' else subtitle_fr

    font_title = ImageFont.truetype(FONT_BOLD, 32)
    font_sub = ImageFont.truetype(FONT_REGULAR, 18)
    font_num = ImageFont.truetype(FONT_BOLD, 16)

    # Load source GIF frames
    try:
        src = Image.open(gif_path)
    except FileNotFoundError:
        print(f"    [SKIP] Source GIF not found: {gif_path}")
        return

    src_frames = []
    src_duration = src.info.get('duration', 500)
    try:
        while True:
            src_frames.append(src.copy().convert('RGB'))
            src.seek(src.tell() + 1)
    except EOFError:
        pass

    if not src_frames:
        print(f"    [SKIP] No frames in source GIF: {gif_path}")
        return

    # Content zone: y=130 to y=560 (430px tall), full width with padding
    content_y = 130
    content_h = 430
    content_x = 20
    content_w = W - 2 * content_x  # 1160px

    # Resize source frames to fit content zone (maintain aspect ratio)
    src_w, src_h = src_frames[0].size
    scale = min(content_w / src_w, content_h / src_h)
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)
    paste_x = content_x + (content_w - new_w) // 2
    paste_y = content_y + (content_h - new_h) // 2

    frames = []
    for sf in src_frames:
        img, draw = base_image()

        # Title zone
        ty = 25
        if pub_num:
            draw.text((600, ty), pub_num, fill=ACCENT_BLUE, font=font_num, anchor="mm")
            ty += 22

        # Wrap title if too long
        bbox = draw.textbbox((0, 0), title, font=font_title)
        tw = bbox[2] - bbox[0]
        if tw > W - 80:
            # Use smaller font for long titles
            font_title_sm = ImageFont.truetype(FONT_BOLD, 26)
            draw.text((600, ty + 15), title, fill=TEXT_WHITE, font=font_title_sm, anchor="mm")
        else:
            draw.text((600, ty + 15), title, fill=TEXT_WHITE, font=font_title, anchor="mm")

        # Subtitle
        draw.text((600, ty + 48), subtitle, fill=TEXT_MUTED, font=font_sub, anchor="mm")

        # Content border (rounded rect around the imported GIF area)
        draw.rounded_rectangle(
            [paste_x - 4, paste_y - 4, paste_x + new_w + 4, paste_y + new_h + 4],
            radius=6, outline=BORDER, width=1)

        # Paste resized source frame
        resized = sf.resize((new_w, new_h), Image.LANCZOS)
        img.paste(resized, (paste_x, paste_y))

        footer(draw)
        frames.append(img)

    save_gif(frames, f"{card_name}-{lang}.gif", duration=src_duration)


def gen_story_28(lang='en'):
    """Story #28 — From Mindmap to Test Board."""
    proof_gif = os.path.join(PROJECT_ROOT, 'docs', 'publications',
                             'test-main-navigator', 'assets', 'proof.gif')
    gen_import_card(lang, 'story-28',
        "From Mindmap to Test Board",
        u"Du Mindmap au tableau de tests",
        "The Session That Built Its Own QA",
        u"La session qui a construit son propre QA",
        proof_gif,
        pub_num="Story #28")


def gen_tests(lang='en'):
    """Interface I7 — Tests dashboard."""
    proof_gif = os.path.join(PROJECT_ROOT, 'docs', 'publications',
                             'test-main-navigator', 'assets', 'proof.gif')
    gen_import_card(lang, 'tests',
        "Tests Dashboard",
        u"Tableau de bord des tests",
        "LED Matrix — Pass/Fail History",
        u"Matrice LED — Historique pass/fail",
        proof_gif,
        pub_num="Interface I7")


# ===================================================================
# INTERFACES HUB — interactive tools showcase
# ===================================================================

def gen_interfaces_hub(lang='en'):
    """Interfaces hub — interactive tools directory."""
    n = 8
    frames = []

    font_title = ImageFont.truetype(FONT_BOLD, 44)
    font_sub = ImageFont.truetype(FONT_REGULAR, 20)
    font_id = ImageFont.truetype(FONT_BOLD, 28)
    font_name = ImageFont.truetype(FONT_BOLD, 22)
    font_desc = ImageFont.truetype(FONT_REGULAR, 16)
    font_badge = ImageFont.truetype(FONT_MONO, 14)

    interfaces = [
        {
            'id': 'I1',
            'name_en': 'Session Review',
            'name_fr': u'R\u00e9vision de sessions',
            'desc_en': 'Metrics, time compilation, deliveries',
            'desc_fr': u'M\u00e9triques, compilation temporelle, livraisons',
            'color': ACCENT_BLUE,
            'icon_items': [u'\u2630', u'\U0001f4ca', u'\u23f1'],  # list, chart, stopwatch
        },
        {
            'id': 'I2',
            'name_en': 'Main Navigator',
            'name_fr': 'Navigateur principal',
            'desc_en': 'Three-panel knowledge browser',
            'desc_fr': u'Navigateur de connaissances \u00e0 trois panneaux',
            'color': ACCENT_PURPLE,
            'icon_items': [u'\u2630', u'\U0001f4c4', u'\U0001f50d'],  # list, page, search
        },
    ]

    for fi in range(n):
        img, draw = base_image()

        # Title
        title = "Interfaces" if lang == 'en' else "Interfaces"
        draw.text((600, 80), title, fill=TEXT_WHITE,
                  font=font_title, anchor="mm")

        subtitle = ("Interactive Web Applications" if lang == 'en'
                     else "Applications web interactives")
        draw.text((600, 125), subtitle, fill=TEXT_MUTED,
                  font=font_sub, anchor="mm")

        # Type badge
        badge = "page_type: interface" if lang == 'en' else "page_type: interface"
        bbox = font_badge.getbbox(badge)
        bw = bbox[2] - bbox[0] + 24
        draw.rounded_rectangle([600 - bw // 2, 155, 600 + bw // 2, 180],
                               radius=10, fill=CODE_BG, outline=BORDER, width=1)
        draw.text((600, 167), badge, fill=ACCENT_CYAN, font=font_badge,
                  anchor="mm")

        # Interface cards — appear sequentially
        card_w = 460
        card_h = 140
        card_gap = 40
        total_h = len(interfaces) * card_h + (len(interfaces) - 1) * card_gap
        sy = 210

        for idx, iface in enumerate(interfaces):
            appear_frame = idx * 2 + 1  # I1 at frame 1, I2 at frame 3
            if fi < appear_frame:
                continue

            cx = W // 2
            cy = sy + idx * (card_h + card_gap)
            age = fi - appear_frame

            # Animation state
            if age == 0:
                bc = dim(iface['color'], 0.5)
                fc = lerp_color(BG_BOT, BOX_BG, 0.5)
                tc = dim(TEXT_WHITE, 0.5)
                bw_line = 2
            elif fi >= 6:
                bc = brighten(iface['color'], 1.3)
                fc = lerp_color(BOX_BG, iface['color'], 0.1)
                tc = TEXT_WHITE
                bw_line = 3
            else:
                bc = iface['color']
                fc = BOX_BG
                tc = TEXT_WHITE
                bw_line = 2

            # Draw card
            x0 = cx - card_w // 2
            draw_box(draw, x0, cy, card_w, card_h, border_color=bc,
                     fill_color=fc, width=bw_line)

            # ID badge (left side)
            id_x = x0 + 50
            id_y = cy + card_h // 2
            draw.rounded_rectangle([id_x - 30, id_y - 22, id_x + 30, id_y + 22],
                                   radius=8, fill=lerp_color(fc, bc, 0.2),
                                   outline=bc, width=1)
            draw.text((id_x, id_y), iface['id'], fill=bc,
                      font=font_id, anchor="mm")

            # Name + description (right of badge)
            name = iface['name_en'] if lang == 'en' else iface['name_fr']
            desc = iface['desc_en'] if lang == 'en' else iface['desc_fr']
            text_x = id_x + 60
            draw.text((text_x, cy + 35), name, fill=tc, font=font_name,
                      anchor="lm")
            draw.text((text_x, cy + 65), desc, fill=TEXT_MUTED, font=font_desc,
                      anchor="lm")

            # Animated icons (right side) — cycle through on active frames
            icons = iface['icon_items']
            active_icon = fi % len(icons)
            for ii, icon in enumerate(icons):
                ix = x0 + card_w - 80 + ii * 30
                iy = cy + card_h // 2
                ic = brighten(bc, 1.4) if ii == active_icon and fi >= 4 else bc
                draw.text((ix, iy), icon, fill=ic,
                          font=ImageFont.truetype(FONT_REGULAR, 22),
                          anchor="mm")

        # Bottom tagline
        font_tag = ImageFont.truetype(FONT_SERIF, 16)
        tag = ("Dynamic JavaScript \u00b7 PDF/DOCX Export \u00b7 State Persistence"
               if lang == 'en' else
               u"JavaScript dynamique \u00b7 Export PDF/DOCX \u00b7 Persistance d'\u00e9tat")
        draw.text((600, 555), tag, fill=TEXT_DIM, font=font_tag, anchor="mm")

        footer(draw)
        frames.append(img)

    save_gif(frames, f"interfaces-hub-{lang}.gif", duration=750)


# ===================================================================
# SESSION REVIEW (I1) — data visualization dashboard card
# ===================================================================

def gen_session_review(lang='en'):
    """I1 — Session Review interface webcard."""
    n = 8
    frames = []

    font_title = ImageFont.truetype(FONT_BOLD, 38)
    font_sub = ImageFont.truetype(FONT_REGULAR, 20)
    font_id = ImageFont.truetype(FONT_BOLD, 56)
    font_label = ImageFont.truetype(FONT_BOLD, 16)
    font_val = ImageFont.truetype(FONT_BOLD, 32)
    font_unit = ImageFont.truetype(FONT_REGULAR, 14)
    font_section = ImageFont.truetype(FONT_MONO, 15)
    font_tag = ImageFont.truetype(FONT_SERIF, 16)

    # Simulated session metrics
    if lang == 'en':
        metrics = [
            ("Files", "12", ACCENT_BLUE),
            ("Lines", "847", ACCENT_PURPLE),
            ("PRs", "3", ACCENT_CYAN),
            ("Commits", "8", ACCENT_GREEN),
        ]
        sections = ["Summary", "Metrics", "Time", "Deliveries",
                     "Lessons", "Velocity"]
    else:
        metrics = [
            ("Fichiers", "12", ACCENT_BLUE),
            ("Lignes", "847", ACCENT_PURPLE),
            ("PRs", "3", ACCENT_CYAN),
            ("Commits", "8", ACCENT_GREEN),
        ]
        sections = [u"R\u00e9sum\u00e9", u"M\u00e9triques", "Temps",
                     "Livraisons", u"Le\u00e7ons", u"V\u00e9locit\u00e9"]

    for fi in range(n):
        img, draw = base_image()

        # Interface ID
        draw.text((600, 75), "I1", fill=ACCENT_BLUE, font=font_id,
                  anchor="mm")

        # Title
        title = "Session Review" if lang == 'en' else u"R\u00e9vision de sessions"
        draw.text((600, 135), title, fill=TEXT_WHITE, font=font_title,
                  anchor="mm")

        subtitle = ("Interactive Session Data Viewer" if lang == 'en'
                     else "Visualiseur interactif de sessions")
        draw.text((600, 170), subtitle, fill=TEXT_MUTED, font=font_sub,
                  anchor="mm")

        # Metrics row — animated counters
        mx_gap = 250
        mx_start = (W - (len(metrics) - 1) * mx_gap) // 2
        for mi, (label, val, color) in enumerate(metrics):
            mx = mx_start + mi * mx_gap
            my = 240

            # Counter animation — values appear progressively
            appear = mi + 1
            if fi < appear:
                continue

            age = fi - appear
            if age == 0:
                vc = dim(color, 0.5)
                display_val = "..."
            elif fi >= 6:
                vc = brighten(color, 1.3)
                display_val = val
            else:
                vc = color
                display_val = val

            draw.text((mx, my), display_val, fill=vc, font=font_val,
                      anchor="mm")
            draw.text((mx, my + 28), label, fill=TEXT_MUTED, font=font_label,
                      anchor="mm")

        # Pie chart simulation (simplified)
        pie_cx, pie_cy, pie_r = 250, 420, 80
        segments = [
            (0.45, ACCENT_BLUE),     # Active time
            (0.30, ACCENT_PURPLE),   # Calendar
            (0.25, ACCENT_CYAN),     # Enterprise
        ]
        start_angle = -90
        for si, (pct, color) in enumerate(segments):
            if fi < 3:
                # Before chart appears
                continue
            sweep = pct * 360
            end_angle = start_angle + sweep
            sc = brighten(color, 1.2) if fi >= 6 else color
            draw.pieslice([pie_cx - pie_r, pie_cy - pie_r,
                           pie_cx + pie_r, pie_cy + pie_r],
                          start=start_angle, end=end_angle,
                          fill=sc, outline=BOX_BG, width=2)
            start_angle = end_angle

        if fi >= 3:
            pie_label = ("Time Compilation" if lang == 'en'
                         else "Compilation temporelle")
            draw.text((pie_cx, pie_cy + pie_r + 25), pie_label,
                      fill=TEXT_MUTED, font=font_label, anchor="mm")

        # Section tabs — appear right side
        tab_x = 520
        tab_y = 340
        tab_w = 180
        tab_h = 36
        tab_gap = 8
        for si, sec in enumerate(sections):
            appear = 2 + si // 2
            if fi < appear:
                continue

            sy = tab_y + si * (tab_h + tab_gap)
            active = (fi + si) % len(sections) == 0 and fi >= 5

            if active:
                bc = brighten(ACCENT_BLUE, 1.3)
                fc = lerp_color(BOX_BG, ACCENT_BLUE, 0.15)
            else:
                bc = BORDER
                fc = BOX_BG

            draw_box(draw, tab_x, sy, tab_w, tab_h, border_color=bc,
                     fill_color=fc, width=2 if active else 1)
            tc = brighten(ACCENT_BLUE, 1.3) if active else TEXT_MUTED
            draw.text((tab_x + tab_w // 2, sy + tab_h // 2), sec,
                      fill=tc, font=font_section, anchor="mm")

        # Badge row
        if fi >= 4:
            badges = [
                (u"\U0001f7e2 feature", ACCENT_GREEN),
                (u"\U0001f7e3 delivery", ACCENT_PURPLE),
            ]
            bx = 730
            for bi, (btxt, bcol) in enumerate(badges):
                by = 370 + bi * 38
                draw.rounded_rectangle([bx, by, bx + 140, by + 30],
                                       radius=6, fill=lerp_color(BOX_BG, bcol, 0.1),
                                       outline=bcol, width=1)
                draw.text((bx + 70, by + 15), btxt, fill=bcol,
                          font=font_unit, anchor="mm")

        # Bottom tagline
        tag = ("Chart.js \u00b7 Engineering Taxonomy \u00b7 PDF Export"
               if lang == 'en' else
               u"Chart.js \u00b7 Taxonomie d'ing\u00e9nierie \u00b7 Export PDF")
        draw.text((600, 555), tag, fill=TEXT_DIM, font=font_tag, anchor="mm")

        footer(draw)
        frames.append(img)

    save_gif(frames, f"session-review-{lang}.gif", duration=750)


# ===================================================================
# MAIN NAVIGATOR (I2) — three-panel browser card
# ===================================================================

def gen_main_navigator(lang='en'):
    """I2 — Main Navigator interface webcard."""
    n = 8
    frames = []

    font_title = ImageFont.truetype(FONT_BOLD, 38)
    font_sub = ImageFont.truetype(FONT_REGULAR, 20)
    font_id = ImageFont.truetype(FONT_BOLD, 56)
    font_panel = ImageFont.truetype(FONT_BOLD, 14)
    font_item = ImageFont.truetype(FONT_REGULAR, 13)
    font_divider = ImageFont.truetype(FONT_BOLD, 18)
    font_tag = ImageFont.truetype(FONT_SERIF, 16)

    for fi in range(n):
        img, draw = base_image()

        # Interface ID
        draw.text((600, 65), "I2", fill=ACCENT_PURPLE, font=font_id,
                  anchor="mm")

        # Title
        title = "Main Navigator" if lang == 'en' else "Navigateur principal"
        draw.text((600, 120), title, fill=TEXT_WHITE, font=font_title,
                  anchor="mm")

        subtitle = ("Three-Panel Knowledge Browser" if lang == 'en'
                     else u"Navigateur de connaissances \u00e0 trois panneaux")
        draw.text((600, 155), subtitle, fill=TEXT_MUTED, font=font_sub,
                  anchor="mm")

        # Three-panel mockup
        panel_y = 195
        panel_h = 340
        panel_bottom = panel_y + panel_h

        # Left panel (directory)
        left_w = 220
        left_x = 60

        # Center panel
        center_x = left_x + left_w + 35
        center_w = 420

        # Right panel
        right_x = center_x + center_w + 35
        right_w = 280

        # Panel appearance animation
        panels_visible = min(fi + 1, 3)  # 1 panel per frame, max 3

        # LEFT PANEL — widget directory
        if panels_visible >= 1:
            lc = brighten(ACCENT_BLUE, 1.2) if fi >= 6 else ACCENT_BLUE
            draw_box(draw, left_x, panel_y, left_w, panel_h,
                     border_color=lc, fill_color=BOX_BG, width=2)

            # Panel label
            plabel = "Directory" if lang == 'en' else u"R\u00e9pertoire"
            draw.text((left_x + left_w // 2, panel_y + 18), plabel,
                      fill=lc, font=font_panel, anchor="mm")

            # Simulated menu items
            if lang == 'en':
                items = ["Publications", "Commands", "Interfaces",
                         "Hubs", "Profile", "Essentials"]
            else:
                items = ["Publications", "Commandes", "Interfaces",
                         "Hubs", "Profil", "Essentiels"]

            for ii, item in enumerate(items):
                iy = panel_y + 42 + ii * 28
                appear = 1 + ii // 2
                if fi < appear:
                    continue

                # Highlight one item per frame
                active = (fi + ii) % len(items) == 0 and fi >= 3
                ic = brighten(ACCENT_BLUE, 1.3) if active else TEXT_MUTED
                prefix = u"\u25b6 " if active else "  "
                draw.text((left_x + 15, iy), prefix + item,
                          fill=ic, font=font_item)

            # Simulated expand state
            if fi >= 4:
                sub_items = ["#0", "#1", "#2", "#3", "#4"]
                for si, sub in enumerate(sub_items):
                    sy = panel_y + 42 + len(items) * 28 + si * 22
                    if sy + 22 > panel_bottom - 15:
                        break
                    sc = dim(ACCENT_CYAN, 0.7) if si != fi % len(sub_items) else ACCENT_CYAN
                    draw.text((left_x + 35, sy), u"\u2514 " + sub,
                              fill=sc, font=font_item)

        # Divider LEFT
        if panels_visible >= 2:
            div_x = left_x + left_w + 10
            dc = ACCENT_BLUE if fi >= 4 else BORDER
            draw.line([(div_x, panel_y + 20), (div_x, panel_bottom - 20)],
                      fill=dc, width=2)
            draw.text((div_x, panel_y + panel_h // 2), u"\u25c0",
                      fill=dc, font=font_divider, anchor="mm")

        # CENTER PANEL — content viewer
        if panels_visible >= 2:
            cc = brighten(ACCENT_CYAN, 1.2) if fi >= 6 else ACCENT_CYAN
            draw_box(draw, center_x, panel_y, center_w, panel_h,
                     border_color=cc, fill_color=BOX_BG, width=2)

            clabel = "Content Viewer" if lang == 'en' else "Visualiseur de contenu"
            draw.text((center_x + center_w // 2, panel_y + 18), clabel,
                      fill=cc, font=font_panel, anchor="mm")

            # Simulated content lines
            content_y = panel_y + 42
            for li in range(12):
                ly = content_y + li * 22
                if ly + 18 > panel_bottom - 15:
                    break
                line_w = 120 + (li * 37 + fi * 23) % 260
                line_c = lerp_color(BOX_BG, BORDER, 0.6)
                draw.rounded_rectangle(
                    [center_x + 15, ly, center_x + 15 + line_w, ly + 10],
                    radius=3, fill=line_c)

            # iframe indicator
            if fi >= 3:
                iframe_badge = "iframe"
                draw.rounded_rectangle(
                    [center_x + center_w - 75, panel_bottom - 30,
                     center_x + center_w - 10, panel_bottom - 10],
                    radius=5, fill=CODE_BG, outline=cc, width=1)
                draw.text((center_x + center_w - 42, panel_bottom - 20),
                          iframe_badge, fill=cc,
                          font=ImageFont.truetype(FONT_MONO, 11), anchor="mm")

        # Divider RIGHT
        if panels_visible >= 3:
            div_x2 = center_x + center_w + 10
            dc2 = ACCENT_PURPLE if fi >= 4 else BORDER
            draw.line([(div_x2, panel_y + 20), (div_x2, panel_bottom - 20)],
                      fill=dc2, width=2)
            # Bidirectional arrows
            draw.text((div_x2, panel_y + panel_h // 2 - 12), u"\u25b6",
                      fill=dc2, font=font_divider, anchor="mm")
            draw.text((div_x2, panel_y + panel_h // 2 + 12), u"\u25c0",
                      fill=dc2, font=font_divider, anchor="mm")

        # RIGHT PANEL — extensible viewer
        if panels_visible >= 3:
            rc = brighten(ACCENT_PURPLE, 1.2) if fi >= 6 else ACCENT_PURPLE
            draw_box(draw, right_x, panel_y, right_w, panel_h,
                     border_color=rc, fill_color=BOX_BG, width=2)

            rlabel = "Viewer" if lang == 'en' else "Visualiseur"
            draw.text((right_x + right_w // 2, panel_y + 18), rlabel,
                      fill=rc, font=font_panel, anchor="mm")

            # State badges (collapsed/mid/full)
            states = ["0px", "50vw", "1fr"]
            active_state = fi % 3
            for si, st in enumerate(states):
                sx = right_x + 15 + si * 85
                sy = panel_y + 45
                sc = brighten(rc, 1.3) if si == active_state else dim(rc, 0.5)
                draw.rounded_rectangle([sx, sy, sx + 75, sy + 24],
                                       radius=5, fill=lerp_color(BOX_BG, rc, 0.1 if si == active_state else 0.0),
                                       outline=sc, width=1)
                draw.text((sx + 37, sy + 12), st, fill=sc,
                          font=ImageFont.truetype(FONT_MONO, 11), anchor="mm")

            # Simulated page preview
            if fi >= 4:
                prev_y = panel_y + 85
                for li in range(8):
                    ly = prev_y + li * 20
                    if ly + 10 > panel_bottom - 15:
                        break
                    lw = 60 + (li * 29 + fi * 17) % 180
                    lw = min(lw, right_w - 30)
                    lc = lerp_color(BOX_BG, BORDER, 0.5)
                    draw.rounded_rectangle(
                        [right_x + 15, ly, right_x + 15 + lw, ly + 8],
                        radius=2, fill=lc)

        # Bottom tagline
        tag = ("localStorage \u00b7 9 State Keys \u00b7 Widget Directory"
               if lang == 'en' else
               u"localStorage \u00b7 9 cl\u00e9s d'\u00e9tat \u00b7 R\u00e9pertoire de widgets")
        draw.text((600, 555), tag, fill=TEXT_DIM, font=font_tag, anchor="mm")

        footer(draw)
        frames.append(img)

    save_gif(frames, f"main-navigator-{lang}.gif", duration=750)


# ===================================================================
# Main — generate all GIFs
# ===================================================================

# ---------------------------------------------------------------------------
# Card registry — maps short names to generator functions
# ---------------------------------------------------------------------------
CARD_REGISTRY = {
    # Profile cards
    'profile-hub':    gen_profile_hub,
    'resume':         gen_resume,
    'full-profile':   gen_full_profile,
    # Publication cards
    'mplib-pipeline': gen_mplib_pipeline,
    'live-session':   gen_live_session,
    'ai-persistence': gen_ai_persistence,
    'distributed-minds': gen_distributed_minds,
    'knowledge-dashboard': gen_knowledge_dashboard,
    'knowledge-system': gen_knowledge_system,
    'publications-index': gen_publications_index,
    'webcards-social-sharing': gen_webcards_social_sharing,
    'normalize': gen_normalize,
    'harvest-protocol': gen_harvest_protocol,
    'session-management': gen_session_management,
    'security-by-design': gen_security_by_design,
    'live-knowledge-network': gen_live_knowledge_network,
    'project-management': gen_project_management,
    'knowledge-2': gen_knowledge_2,
    # Interface cards
    'interfaces-hub': gen_interfaces_hub,
    'session-review': gen_session_review,
    'main-navigator': gen_main_navigator,
    # Behavioral / Research cards
    'behavioral-intelligence': gen_behavioral_intelligence,
    # Import cards (wrapping external animated GIFs)
    'story-28': gen_story_28,
    'tests': gen_tests,
}

# Groups — logical subsets
CARD_GROUPS = {
    'profile':      ['profile-hub', 'resume', 'full-profile'],
    'publications': ['mplib-pipeline', 'live-session', 'ai-persistence',
                     'distributed-minds', 'knowledge-dashboard',
                     'knowledge-system', 'publications-index',
                     'webcards-social-sharing', 'normalize',
                     'harvest-protocol', 'session-management',
                     'security-by-design', 'live-knowledge-network',
                     'project-management', 'knowledge-2',
                     'behavioral-intelligence'],
    'interfaces':   ['interfaces-hub', 'session-review', 'main-navigator', 'tests'],
    'stories':      ['story-28'],
}

# Publication number aliases
PUB_ALIASES = {
    '0':  'knowledge-system',
    '1':  'mplib-pipeline',
    '2':  'live-session',
    '3':  'ai-persistence',
    '4':  'distributed-minds',
    '4a': 'knowledge-dashboard',
    '5':  'webcards-social-sharing',
    '6':  'normalize',
    '7':  'harvest-protocol',
    '8':  'session-management',
    '9':  'security-by-design',
    '10': 'live-knowledge-network',
    '12': 'project-management',
    '0v2': 'knowledge-2',
    '11':  'story-28',
    '25':  'behavioral-intelligence',
}

# Interface aliases
IFACE_ALIASES = {
    'i1': 'session-review',
    'i2': 'main-navigator',
    'hub': 'interfaces-hub',
    'i7':  'tests',
}


def resolve_targets(args):
    """Resolve CLI arguments to a list of card names."""
    if not args or 'all' in args:
        return list(CARD_REGISTRY.keys())

    targets = []
    for arg in args:
        a = arg.lower().strip('#')
        if a in CARD_REGISTRY:
            targets.append(a)
        elif a in CARD_GROUPS:
            targets.extend(CARD_GROUPS[a])
        elif a in PUB_ALIASES:
            targets.append(PUB_ALIASES[a])
        elif a in IFACE_ALIASES:
            targets.append(IFACE_ALIASES[a])
        else:
            print(f"  Unknown target: '{arg}'")
            print(f"  Cards:  {', '.join(sorted(CARD_REGISTRY.keys()))}")
            print(f"  Groups: {', '.join(sorted(CARD_GROUPS.keys()))}")
            print(f"  Pubs:   {', '.join(f'#{k}' for k in sorted(PUB_ALIASES.keys(), key=lambda x: (len(x), x)))}")
            print(f"  Ifaces: {', '.join(sorted(IFACE_ALIASES.keys()))}")
            sys.exit(1)
    # deduplicate while preserving order
    seen = set()
    return [t for t in targets if not (t in seen or seen.add(t))]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Generate animated OG social preview GIFs.',
        epilog=f"cards:  {', '.join(sorted(CARD_REGISTRY.keys()))}\n"
               f"groups: {', '.join(sorted(CARD_GROUPS.keys()))}\n"
               f"themes: {', '.join(sorted(THEMES.keys()))}\n"
               f"pubs:   {', '.join(f'#{k}' for k in sorted(PUB_ALIASES.keys(), key=lambda x: (len(x), x)))}",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('targets', nargs='*', default=[],
                        help='Card names, group names, or publication numbers (default: all)')
    parser.add_argument('--lang', choices=['en', 'fr', 'both'], default='both',
                        help='Language to generate (default: both)')
    parser.add_argument('--theme', choices=list(THEMES.keys()) + ['all'], default='all',
                        help='Theme to generate (default: all)')
    parser.add_argument('--list', action='store_true',
                        help='List available cards and exit')
    parser.add_argument('--from-frontmatter', metavar='PATH',
                        help='Generate text-card from publication front matter (YAML)')
    opts = parser.parse_args()

    if opts.list:
        print("Available cards:")
        for name in CARD_REGISTRY:
            # find which group(s) this card belongs to
            groups = [g for g, members in CARD_GROUPS.items() if name in members]
            # find pub alias
            alias = next((f'#{k}' for k, v in PUB_ALIASES.items() if v == name), '')
            print(f"  {name:<24s} {alias:<6s} [{', '.join(groups)}]")
        print(f"\nAvailable themes: {', '.join(sorted(THEMES.keys()))}")
        sys.exit(0)

    if opts.from_frontmatter:
        langs = ['en', 'fr'] if opts.lang == 'both' else [opts.lang]
        themes = list(THEMES.keys()) if opts.theme == 'all' else [opts.theme]
        count = 0
        for theme in themes:
            set_theme(theme)
            for lang in langs:
                gen_from_frontmatter(opts.from_frontmatter, lang)
                count += 1
        print(f"Done! {count} GIF(s) from front matter.")
        sys.exit(0)

    targets = resolve_targets(opts.targets)
    langs = ['en', 'fr'] if opts.lang == 'both' else [opts.lang]
    themes = list(THEMES.keys()) if opts.theme == 'all' else [opts.theme]

    count = 0
    print("Generating animated OG social preview GIFs...")
    print()
    for theme in themes:
        set_theme(theme)
        print(f"  === Theme: {theme} ===")
        for lang in langs:
            print(f"  [{lang.upper()}]")
            for name in targets:
                CARD_REGISTRY[name](lang)
                count += 1
            print()
    print(f"Done! {count} animated GIF(s) generated in {os.path.abspath(OUT_DIR)}")
