#!/usr/bin/env python3
"""Generate unique OG social preview images for each knowledge page.
Each image: 1200x630 PNG, dark theme, content-specific visuals."""

from PIL import Image, ImageDraw, ImageFont
import os

# Paths — scripts/ -> K_TOOLS/ -> Knowledge/ -> ROOT
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(MODULE_DIR))
OUT_DIR = os.path.join(PROJECT_ROOT, 'docs', 'assets', 'og')
os.makedirs(OUT_DIR, exist_ok=True)

# Fonts
FONT_BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
FONT_REGULAR = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FONT_MONO = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'

# Colors (matching existing dark theme)
BG_TOP = (15, 23, 42)       # #0f172a
BG_BOT = (30, 41, 59)       # #1e293b
ACCENT_BLUE = (59, 130, 246)  # #3b82f6
ACCENT_PURPLE = (139, 92, 246)  # #8b5cf6
ACCENT_CYAN = (6, 182, 212)   # #06b6d4
TEXT_WHITE = (248, 250, 252)   # #f8fafc
TEXT_MUTED = (148, 163, 184)   # #94a3b8
TEXT_DIM = (71, 85, 105)       # #475569
BORDER = (51, 65, 85)         # #334155
BOX_BG = (30, 58, 95)         # #1e3a5f

W, H = 1200, 630


def gradient_bg(draw):
    """Draw vertical gradient background."""
    for y in range(H):
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * y / H)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * y / H)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * y / H)
        draw.line([(0, y), (W, y)], fill=(r, g, b))


def accent_bars(draw):
    """Draw accent gradient bars at top and bottom."""
    for x in range(W):
        t = x / W
        if t < 0.5:
            r = int(ACCENT_BLUE[0] + (ACCENT_PURPLE[0] - ACCENT_BLUE[0]) * t * 2)
            g = int(ACCENT_BLUE[1] + (ACCENT_PURPLE[1] - ACCENT_BLUE[1]) * t * 2)
            b = int(ACCENT_BLUE[2] + (ACCENT_PURPLE[2] - ACCENT_BLUE[2]) * t * 2)
        else:
            r = int(ACCENT_PURPLE[0] + (ACCENT_CYAN[0] - ACCENT_PURPLE[0]) * (t - 0.5) * 2)
            g = int(ACCENT_PURPLE[1] + (ACCENT_CYAN[1] - ACCENT_PURPLE[1]) * (t - 0.5) * 2)
            b = int(ACCENT_PURPLE[2] + (ACCENT_CYAN[2] - ACCENT_PURPLE[2]) * (t - 0.5) * 2)
        draw.line([(x, 0), (x, 4)], fill=(r, g, b))
        draw.line([(x, H - 4), (x, H)], fill=(r, g, b))


def grid_pattern(draw, opacity=12):
    """Draw subtle grid pattern."""
    color = (148, 163, 184, opacity)
    # We'll use main image directly with low-alpha lines
    grid_color = (BG_TOP[0] + 5, BG_TOP[1] + 5, BG_TOP[2] + 8)
    for y in range(80, H, 80):
        draw.line([(0, y), (W, y)], fill=grid_color, width=1)
    for x in range(160, W, 160):
        draw.line([(x, 0), (x, H)], fill=grid_color, width=1)


def draw_box(draw, x, y, w, h, border_color=ACCENT_BLUE, radius=8):
    """Draw a rounded-ish box with border."""
    draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=BOX_BG, outline=border_color, width=2)


def footer(draw, text="Martin Paquet & Claude  |  packetqc/knowledge"):
    """Draw footer text."""
    font = ImageFont.truetype(FONT_REGULAR, 14)
    draw.text((W // 2, H - 40), text, fill=TEXT_DIM, font=font, anchor="mm")


def base_image():
    """Create base image with gradient, grid, accent bars."""
    img = Image.new('RGB', (W, H))
    draw = ImageDraw.Draw(img)
    gradient_bg(draw)
    grid_pattern(draw)
    accent_bars(draw)
    return img, draw


# ============================================================
# Profile Hub
# ============================================================
def gen_profile_hub(lang='en'):
    img, draw = base_image()

    # Initials circle
    draw.ellipse([520, 60, 680, 220], fill=BOX_BG, outline=ACCENT_BLUE, width=3)
    font_init = ImageFont.truetype(FONT_BOLD, 72)
    draw.text((600, 140), "MP", fill=ACCENT_BLUE, font=font_init, anchor="mm")

    # Name
    font_name = ImageFont.truetype(FONT_BOLD, 48)
    draw.text((600, 275), "Martin Paquet", fill=TEXT_WHITE, font=font_name, anchor="mm")

    # Title
    font_sub = ImageFont.truetype(FONT_REGULAR, 22)
    if lang == 'en':
        draw.text((600, 320), "Network Security | System Security | Embedded Software", fill=TEXT_MUTED, font=font_sub, anchor="mm")
    else:
        draw.text((600, 320), u"Sécurité Réseau | Sécurité Systèmes | Logiciels Embarqués", fill=TEXT_MUTED, font=font_sub, anchor="mm")

    # Link boxes
    links = [("GitHub", "packetqc"), ("Knowledge", "packetqc/knowledge"), ("LinkedIn", "martypacket")]
    box_w = 300
    start_x = (W - len(links) * box_w - (len(links) - 1) * 20) // 2
    for i, (label, value) in enumerate(links):
        bx = start_x + i * (box_w + 20)
        colors = [ACCENT_BLUE, ACCENT_PURPLE, ACCENT_CYAN]
        draw_box(draw, bx, 380, box_w, 70, border_color=colors[i])
        font_label = ImageFont.truetype(FONT_BOLD, 14)
        font_val = ImageFont.truetype(FONT_MONO, 16)
        draw.text((bx + box_w // 2, 400), label, fill=colors[i], font=font_label, anchor="mm")
        draw.text((bx + box_w // 2, 425), value, fill=TEXT_WHITE, font=font_val, anchor="mm")

    # Language badge
    font_lang = ImageFont.truetype(FONT_BOLD, 16)
    badge_text = "English" if lang == 'en' else u"Français"
    draw.rounded_rectangle([540, 490, 660, 520], radius=12, fill=BOX_BG, outline=ACCENT_CYAN, width=1)
    draw.text((600, 505), badge_text, fill=ACCENT_CYAN, font=font_lang, anchor="mm")

    footer(draw)
    fname = f"profile-hub-{lang}.png"
    img.save(os.path.join(OUT_DIR, fname), 'PNG')
    print(f"  Generated {fname}")


# ============================================================
# Resume
# ============================================================
def gen_resume(lang='en'):
    img, draw = base_image()

    font_title = ImageFont.truetype(FONT_BOLD, 44)
    font_sub = ImageFont.truetype(FONT_REGULAR, 22)
    font_tag = ImageFont.truetype(FONT_BOLD, 15)
    font_metric = ImageFont.truetype(FONT_MONO, 18)

    # Title
    if lang == 'en':
        draw.text((600, 90), u"Martin Paquet \u2014 Resume", fill=TEXT_WHITE, font=font_title, anchor="mm")
        draw.text((600, 130), "Network Security | System Security | Embedded Software", fill=TEXT_MUTED, font=font_sub, anchor="mm")
    else:
        draw.text((600, 90), u"Martin Paquet \u2014 Résumé", fill=TEXT_WHITE, font=font_title, anchor="mm")
        draw.text((600, 130), u"Sécurité Réseau | Sécurité Systèmes | Logiciels Embarqués", fill=TEXT_MUTED, font=font_sub, anchor="mm")

    # Focus areas — 4 boxes in 2x2 grid
    if lang == 'en':
        areas = [
            ("Post-Quantum Crypto", "ML-KEM 1024 · ML-DSA", ACCENT_BLUE),
            ("High-Perf Embedded", "2,650 logs/sec · Cortex-M55", ACCENT_PURPLE),
            ("AI-Assisted Dev", "Session persistence · Live QA", ACCENT_CYAN),
            ("Hardware Security", "SAES · PKA · TEE · ECC", ACCENT_BLUE),
        ]
    else:
        areas = [
            ("Crypto post-quantique", "ML-KEM 1024 · ML-DSA", ACCENT_BLUE),
            (u"Embarqué haute perf.", u"2 650 logs/sec · Cortex-M55", ACCENT_PURPLE),
            (u"Dév. assisté par IA", u"Persistance · QA en direct", ACCENT_CYAN),
            (u"Sécurité matérielle", u"SAES · PKA · TEE · ECC", ACCENT_BLUE),
        ]

    for i, (title, desc, color) in enumerate(areas):
        col = i % 2
        row = i // 2
        bx = 120 + col * 500
        by = 190 + row * 120
        draw_box(draw, bx, by, 460, 95, border_color=color)
        draw.text((bx + 230, by + 30), title, fill=color, font=font_tag, anchor="mm")
        draw.text((bx + 230, by + 60), desc, fill=TEXT_WHITE, font=font_metric, anchor="mm")

    # Tech domains strip
    if lang == 'en':
        domains = "STM32 · C/C++ · Python · ThreadX · Cisco · Kali · Docker"
    else:
        domains = "STM32 · C/C++ · Python · ThreadX · Cisco · Kali · Docker"
    font_domains = ImageFont.truetype(FONT_REGULAR, 16)
    draw.text((600, 470), domains, fill=TEXT_DIM, font=font_domains, anchor="mm")

    # Experience badge
    if lang == 'en':
        badge = "30 years  ·  1995\u20132026  ·  Quebec, Canada"
    else:
        badge = u"30 ans  ·  1995\u20132026  ·  Québec, Canada"
    draw.text((600, 520), badge, fill=TEXT_MUTED, font=font_sub, anchor="mm")

    footer(draw)
    fname = f"resume-{lang}.png"
    img.save(os.path.join(OUT_DIR, fname), 'PNG')
    print(f"  Generated {fname}")


# ============================================================
# Full Profile
# ============================================================
def gen_full_profile(lang='en'):
    img, draw = base_image()

    font_title = ImageFont.truetype(FONT_BOLD, 40)
    font_sub = ImageFont.truetype(FONT_REGULAR, 20)
    font_year = ImageFont.truetype(FONT_MONO, 14)
    font_label = ImageFont.truetype(FONT_BOLD, 13)

    # Title
    if lang == 'en':
        draw.text((600, 70), "Martin Paquet", fill=TEXT_WHITE, font=font_title, anchor="mm")
        draw.text((600, 110), "Full Profile — 30 Years of Building", fill=TEXT_MUTED, font=font_sub, anchor="mm")
    else:
        draw.text((600, 70), "Martin Paquet", fill=TEXT_WHITE, font=font_title, anchor="mm")
        draw.text((600, 110), u"Profil complet — 30 ans de construction", fill=TEXT_MUTED, font=font_sub, anchor="mm")

    # Timeline visualization: dots from 1995 to 2026
    timeline_y = 200
    start_x = 100
    end_x = 1100
    years = [1995, 1997, 2004, 2007, 2010, 2016, 2017, 2018, 2020, 2023, 2025, 2026]
    labels_en = ["RTOS\nKernel", "HTTP\nServer", "Web\nApps", "Net\nSniffer", "CyberSec\nLab", "vCloud", "VR\nAndroid", "Cisco\nAutom.", "IoT\nArduino", "STM32\nSecurity", "PQC\nML-KEM", "SQLite\nPipeline"]
    labels_fr = ["Noyau\nRTOS", "Serveur\nHTTP", "Apps\nWeb", "Sniffer\nRéseau", "Labo\nCyber", "vCloud", "VR\nAndroid", "Autom.\nCisco", "IoT\nArduino", u"Sécu.\nSTM32", "PQC\nML-KEM", "Pipeline\nSQLite"]
    labels = labels_en if lang == 'en' else labels_fr

    # Timeline line
    draw.line([(start_x, timeline_y), (end_x, timeline_y)], fill=BORDER, width=2)

    for i, (year, label) in enumerate(zip(years, labels)):
        t = (year - 1995) / (2026 - 1995)
        x = int(start_x + t * (end_x - start_x))
        # Dot
        color = ACCENT_BLUE if i % 3 == 0 else (ACCENT_PURPLE if i % 3 == 1 else ACCENT_CYAN)
        draw.ellipse([x - 6, timeline_y - 6, x + 6, timeline_y + 6], fill=color)
        # Year
        draw.text((x, timeline_y + 20), str(year), fill=TEXT_DIM, font=font_year, anchor="mm")
        # Label
        draw.text((x, timeline_y + 50), label, fill=TEXT_MUTED, font=font_label, anchor="mm")

    # Domain boxes at bottom
    if lang == 'en':
        domains = [
            ("Embedded", "STM32 · ThreadX · PQC", ACCENT_BLUE),
            ("Network Security", "Cisco · Firewall · SIEM", ACCENT_PURPLE),
            ("Cybersecurity", "Kali · Metasploit · RF", ACCENT_CYAN),
            ("Programming", "C · C++ · Python · C#", ACCENT_BLUE),
        ]
    else:
        domains = [
            (u"Embarqué", "STM32 · ThreadX · PQC", ACCENT_BLUE),
            (u"Sécurité réseau", "Cisco · Pare-feu · SIEM", ACCENT_PURPLE),
            (u"Cybersécurité", u"Kali · Metasploit · RF", ACCENT_CYAN),
            ("Programmation", "C · C++ · Python · C#", ACCENT_BLUE),
        ]

    box_w = 250
    total_w = len(domains) * box_w + (len(domains) - 1) * 15
    sx = (W - total_w) // 2
    for i, (title, desc, color) in enumerate(domains):
        bx = sx + i * (box_w + 15)
        draw_box(draw, bx, 380, box_w, 80, border_color=color)
        draw.text((bx + box_w // 2, 405), title, fill=color, font=font_label, anchor="mm")
        font_desc = ImageFont.truetype(FONT_REGULAR, 14)
        draw.text((bx + box_w // 2, 435), desc, fill=TEXT_WHITE, font=font_desc, anchor="mm")

    # Publications count
    if lang == 'en':
        draw.text((600, 520), "3 publications  ·  12+ projects  ·  1995\u20132026", fill=TEXT_MUTED, font=font_sub, anchor="mm")
    else:
        draw.text((600, 520), u"3 publications  ·  12+ projets  ·  1995\u20132026", fill=TEXT_MUTED, font=font_sub, anchor="mm")

    footer(draw)
    fname = f"full-profile-{lang}.png"
    img.save(os.path.join(OUT_DIR, fname), 'PNG')
    print(f"  Generated {fname}")


# ============================================================
# Publication #1: MPLIB Storage Pipeline
# ============================================================
def gen_mplib_pipeline(lang='en'):
    img, draw = base_image()

    font_title = ImageFont.truetype(FONT_BOLD, 36)
    font_sub = ImageFont.truetype(FONT_REGULAR, 20)
    font_metric_big = ImageFont.truetype(FONT_BOLD, 56)
    font_metric_label = ImageFont.truetype(FONT_REGULAR, 16)
    font_stage = ImageFont.truetype(FONT_MONO, 14)

    # Title
    draw.text((600, 70), "MPLIB Storage Pipeline", fill=TEXT_WHITE, font=font_title, anchor="mm")
    if lang == 'en':
        draw.text((600, 110), "High-Throughput SQLite on Cortex-M55", fill=TEXT_MUTED, font=font_sub, anchor="mm")
    else:
        draw.text((600, 110), "SQLite haute performance sur Cortex-M55", fill=TEXT_MUTED, font=font_sub, anchor="mm")

    # Big metric
    draw.text((600, 210), "2,650", fill=ACCENT_BLUE, font=font_metric_big, anchor="mm")
    draw.text((600, 250), "logs/sec sustained", fill=TEXT_MUTED, font=font_metric_label, anchor="mm")

    # 5-stage pipeline visualization
    stages = ["Generate", "DualBuffer", "Ingest", "WAL", "SD Card"]
    colors = [ACCENT_BLUE, ACCENT_PURPLE, ACCENT_CYAN, ACCENT_BLUE, ACCENT_PURPLE]
    box_w = 160
    gap = 20
    total = len(stages) * box_w + (len(stages) - 1) * gap
    sx = (W - total) // 2

    for i, (stage, color) in enumerate(zip(stages, colors)):
        bx = sx + i * (box_w + gap)
        draw_box(draw, bx, 310, box_w, 50, border_color=color)
        draw.text((bx + box_w // 2, 335), stage, fill=color, font=font_stage, anchor="mm")
        # Arrow
        if i < len(stages) - 1:
            ax = bx + box_w + 2
            draw.text((ax + gap // 2, 335), u"\u25B6", fill=TEXT_DIM, font=font_stage, anchor="mm")

    # Metrics row
    if lang == 'en':
        metrics = [
            ("400K+", "rows tested"),
            ("7.2 MB", "PSRAM buffers"),
            ("4 MB", "page cache"),
            ("800 MHz", "Cortex-M55"),
        ]
    else:
        metrics = [
            ("400K+", u"lignes testées"),
            ("7,2 Mo", "tampons PSRAM"),
            ("4 Mo", "cache pages"),
            ("800 MHz", "Cortex-M55"),
        ]

    font_mv = ImageFont.truetype(FONT_BOLD, 28)
    font_ml = ImageFont.truetype(FONT_REGULAR, 13)
    mx_start = 100
    mx_gap = (W - 200) // len(metrics)
    for i, (val, label) in enumerate(metrics):
        mx = mx_start + i * mx_gap + mx_gap // 2
        draw.text((mx, 430), val, fill=TEXT_WHITE, font=font_mv, anchor="mm")
        draw.text((mx, 460), label, fill=TEXT_DIM, font=font_ml, anchor="mm")

    # Tech stack
    draw.text((600, 520), "ThreadX RTOS  ·  TouchGFX  ·  SQLite WAL  ·  STM32N6570-DK", fill=TEXT_DIM, font=font_metric_label, anchor="mm")

    footer(draw)
    fname = f"mplib-pipeline-{lang}.png"
    img.save(os.path.join(OUT_DIR, fname), 'PNG')
    print(f"  Generated {fname}")


# ============================================================
# Publication #2: Live Session Analysis
# ============================================================
def gen_live_session(lang='en'):
    img, draw = base_image()

    font_title = ImageFont.truetype(FONT_BOLD, 36)
    font_sub = ImageFont.truetype(FONT_REGULAR, 20)
    font_metric_big = ImageFont.truetype(FONT_BOLD, 56)
    font_label = ImageFont.truetype(FONT_REGULAR, 16)
    font_mode = ImageFont.truetype(FONT_MONO, 15)
    font_mode_desc = ImageFont.truetype(FONT_REGULAR, 12)

    # Title
    if lang == 'en':
        draw.text((600, 70), "Live Session Analysis", fill=TEXT_WHITE, font=font_title, anchor="mm")
        draw.text((600, 110), "AI-Assisted Real-Time Debugging", fill=TEXT_MUTED, font=font_sub, anchor="mm")
    else:
        draw.text((600, 70), "Analyse de session en direct", fill=TEXT_WHITE, font=font_title, anchor="mm")
        draw.text((600, 110), u"Débogage temps réel assisté par IA", fill=TEXT_MUTED, font=font_sub, anchor="mm")

    # Pipeline flow
    font_flow = ImageFont.truetype(FONT_MONO, 16)
    if lang == 'en':
        flow_text = u"Board \u2192 OBS/RTSP \u2192 H.264 \u2192 Git \u2192 Claude \u2192 Analysis"
    else:
        flow_text = u"Carte \u2192 OBS/RTSP \u2192 H.264 \u2192 Git \u2192 Claude \u2192 Analyse"
    draw.text((600, 170), flow_text, fill=ACCENT_CYAN, font=font_flow, anchor="mm")

    # Big metric
    draw.text((600, 260), "~6 sec", fill=ACCENT_BLUE, font=font_metric_big, anchor="mm")
    if lang == 'en':
        draw.text((600, 300), "end-to-end latency", fill=TEXT_MUTED, font=font_label, anchor="mm")
    else:
        draw.text((600, 300), u"latence bout en bout", fill=TEXT_MUTED, font=font_label, anchor="mm")

    # 4 analysis modes
    if lang == 'en':
        modes = [
            ("I'm live", "Pull & report", ACCENT_BLUE),
            ("analyze", "Static timeline", ACCENT_PURPLE),
            ("multi-live", "Cross-source", ACCENT_CYAN),
            ("deep", "Frame forensics", ACCENT_BLUE),
        ]
    else:
        modes = [
            ("I'm live", "Pull & rapport", ACCENT_BLUE),
            ("analyze", "Chronologie", ACCENT_PURPLE),
            ("multi-live", u"Multi-source", ACCENT_CYAN),
            ("deep", u"Forensique", ACCENT_BLUE),
        ]

    box_w = 230
    total = len(modes) * box_w + (len(modes) - 1) * 20
    sx = (W - total) // 2
    for i, (cmd, desc, color) in enumerate(modes):
        bx = sx + i * (box_w + 20)
        draw_box(draw, bx, 360, box_w, 75, border_color=color)
        draw.text((bx + box_w // 2, 385), cmd, fill=color, font=font_mode, anchor="mm")
        draw.text((bx + box_w // 2, 415), desc, fill=TEXT_WHITE, font=font_mode_desc, anchor="mm")

    # Results
    if lang == 'en':
        draw.text((600, 510), "2 timing bugs found  ·  3x dev speed  ·  Race conditions detected", fill=TEXT_DIM, font=font_label, anchor="mm")
    else:
        draw.text((600, 510), u"2 bugs timing trouvés  ·  Vitesse 3x  ·  Conditions de course détectées", fill=TEXT_DIM, font=font_label, anchor="mm")

    footer(draw)
    fname = f"live-session-{lang}.png"
    img.save(os.path.join(OUT_DIR, fname), 'PNG')
    print(f"  Generated {fname}")


# ============================================================
# Publication #3: AI Session Persistence
# ============================================================
def gen_ai_persistence(lang='en'):
    img, draw = base_image()

    font_title = ImageFont.truetype(FONT_BOLD, 36)
    font_sub = ImageFont.truetype(FONT_REGULAR, 20)
    font_metric_big = ImageFont.truetype(FONT_BOLD, 48)
    font_label = ImageFont.truetype(FONT_REGULAR, 16)
    font_cmd = ImageFont.truetype(FONT_MONO, 18)
    font_comp = ImageFont.truetype(FONT_BOLD, 14)

    # Title
    if lang == 'en':
        draw.text((600, 65), "AI Session Persistence", fill=TEXT_WHITE, font=font_title, anchor="mm")
        draw.text((600, 105), "Cross-Session Knowledge Continuity", fill=TEXT_MUTED, font=font_sub, anchor="mm")
    else:
        draw.text((600, 65), u"Persistance de session IA", fill=TEXT_WHITE, font=font_title, anchor="mm")
        draw.text((600, 105), u"Continuité des connaissances inter-sessions", fill=TEXT_MUTED, font=font_sub, anchor="mm")

    # Sunglasses icon (simplified)
    cx, cy = 600, 185
    # Left lens
    draw.rounded_rectangle([cx - 80, cy - 20, cx - 10, cy + 20], radius=8, fill=None, outline=ACCENT_BLUE, width=2)
    # Right lens
    draw.rounded_rectangle([cx + 10, cy - 20, cx + 80, cy + 20], radius=8, fill=None, outline=ACCENT_PURPLE, width=2)
    # Bridge
    draw.arc([cx - 15, cy - 25, cx + 15, cy - 5], start=180, end=0, fill=TEXT_DIM, width=2)
    # Arms
    draw.line([(cx - 80, cy - 10), (cx - 110, cy - 20)], fill=TEXT_DIM, width=2)
    draw.line([(cx + 80, cy - 10), (cx + 110, cy - 20)], fill=TEXT_DIM, width=2)

    # Lifecycle flow: wakeup → work → save (with loop)
    cmds = [("wakeup", ACCENT_BLUE), ("work", ACCENT_PURPLE), ("save", ACCENT_CYAN)]
    box_w = 140
    gap = 30
    total = len(cmds) * box_w + (len(cmds) - 1) * gap
    sx = (W - total) // 2

    for i, (cmd, color) in enumerate(cmds):
        bx = sx + i * (box_w + gap)
        draw_box(draw, bx, 250, box_w, 50, border_color=color)
        draw.text((bx + box_w // 2, 275), cmd, fill=color, font=font_cmd, anchor="mm")
        if i < len(cmds) - 1:
            ax = bx + box_w + 5
            draw.text((ax + gap // 2, 275), u"\u25B6", fill=TEXT_DIM, font=font_cmd, anchor="mm")

    # Loop arrow (simplified)
    loop_y = 240
    draw.arc([sx - 20, loop_y - 30, sx + total + 20, loop_y + 10], start=180, end=360, fill=BORDER, width=2)

    # Components
    if lang == 'en':
        comps = [
            ("CLAUDE.md", "Project identity", ACCENT_BLUE),
            ("notes/", "Session memory", ACCENT_PURPLE),
            ("Lifecycle", "init → work → save", ACCENT_CYAN),
        ]
    else:
        comps = [
            ("CLAUDE.md", u"Identité projet", ACCENT_BLUE),
            ("notes/", u"Mémoire de session", ACCENT_PURPLE),
            ("Cycle de vie", u"init → travail → save", ACCENT_CYAN),
        ]

    box_w2 = 300
    total2 = len(comps) * box_w2 + (len(comps) - 1) * 25
    sx2 = (W - total2) // 2
    for i, (name, desc, color) in enumerate(comps):
        bx = sx2 + i * (box_w2 + 25)
        draw_box(draw, bx, 350, box_w2, 70, border_color=color)
        draw.text((bx + box_w2 // 2, 375), name, fill=color, font=font_comp, anchor="mm")
        draw.text((bx + box_w2 // 2, 397), desc, fill=TEXT_WHITE, font=font_label, anchor="mm")

    # Metric
    if lang == 'en':
        draw.text((600, 490), "~30 seconds", fill=ACCENT_BLUE, font=font_metric_big, anchor="mm")
        draw.text((600, 530), "context recovery  vs  15 min manual re-explain", fill=TEXT_MUTED, font=font_label, anchor="mm")
    else:
        draw.text((600, 490), "~30 secondes", fill=ACCENT_BLUE, font=font_metric_big, anchor="mm")
        draw.text((600, 530), u"récupération de contexte  vs  15 min ré-explication", fill=TEXT_MUTED, font=font_label, anchor="mm")

    footer(draw)
    fname = f"ai-persistence-{lang}.png"
    img.save(os.path.join(OUT_DIR, fname), 'PNG')
    print(f"  Generated {fname}")


# ============================================================
# Publications Index
# ============================================================
def gen_publications_index(lang='en'):
    img, draw = base_image()

    font_title = ImageFont.truetype(FONT_BOLD, 44)
    font_sub = ImageFont.truetype(FONT_REGULAR, 20)
    font_num = ImageFont.truetype(FONT_BOLD, 36)
    font_pub_title = ImageFont.truetype(FONT_BOLD, 16)
    font_pub_desc = ImageFont.truetype(FONT_REGULAR, 13)

    # Title
    if lang == 'en':
        draw.text((600, 80), "Technical Publications", fill=TEXT_WHITE, font=font_title, anchor="mm")
        draw.text((600, 125), "Embedded Systems · AI Workflows · Methodology", fill=TEXT_MUTED, font=font_sub, anchor="mm")
    else:
        draw.text((600, 80), "Publications techniques", fill=TEXT_WHITE, font=font_title, anchor="mm")
        draw.text((600, 125), u"Systèmes embarqués · Flux IA · Méthodologie", fill=TEXT_MUTED, font=font_sub, anchor="mm")

    # 3 publication cards
    if lang == 'en':
        pubs = [
            ("#1", "MPLIB Storage Pipeline", "2,650 logs/sec on Cortex-M55", ACCENT_BLUE),
            ("#2", "Live Session Analysis", "~6 sec AI debugging feedback", ACCENT_PURPLE),
            ("#3", "AI Session Persistence", "30-sec context recovery", ACCENT_CYAN),
        ]
    else:
        pubs = [
            ("#1", "MPLIB Storage Pipeline", u"2 650 logs/sec sur Cortex-M55", ACCENT_BLUE),
            ("#2", "Analyse de session en direct", u"~6 sec retour IA", ACCENT_PURPLE),
            ("#3", u"Persistance de session IA", u"Récup. contexte 30 sec", ACCENT_CYAN),
        ]

    box_w = 320
    total = len(pubs) * box_w + (len(pubs) - 1) * 25
    sx = (W - total) // 2
    for i, (num, title, desc, color) in enumerate(pubs):
        bx = sx + i * (box_w + 25)
        draw_box(draw, bx, 190, box_w, 180, border_color=color)
        draw.text((bx + box_w // 2, 225), num, fill=color, font=font_num, anchor="mm")
        draw.text((bx + box_w // 2, 275), title, fill=TEXT_WHITE, font=font_pub_title, anchor="mm")
        # Word-wrap desc
        draw.text((bx + box_w // 2, 310), desc, fill=TEXT_MUTED, font=font_pub_desc, anchor="mm")

    # Author
    if lang == 'en':
        draw.text((600, 450), "By Martin Paquet & Claude (Anthropic, Opus 4.6)", fill=TEXT_MUTED, font=font_sub, anchor="mm")
    else:
        draw.text((600, 450), "Par Martin Paquet & Claude (Anthropic, Opus 4.6)", fill=TEXT_MUTED, font=font_sub, anchor="mm")

    # Badge
    draw.text((600, 510), "packetqc/knowledge", fill=TEXT_DIM, font=font_sub, anchor="mm")

    footer(draw)
    fname = f"publications-index-{lang}.png"
    img.save(os.path.join(OUT_DIR, fname), 'PNG')
    print(f"  Generated {fname}")


# ============================================================
# Generate all
# ============================================================
if __name__ == '__main__':
    print("Generating OG social images...")
    for lang in ['en', 'fr']:
        gen_profile_hub(lang)
        gen_resume(lang)
        gen_full_profile(lang)
        gen_mplib_pipeline(lang)
        gen_live_session(lang)
        gen_ai_persistence(lang)
        gen_publications_index(lang)
    print(f"\nDone! {14} images generated in {OUT_DIR}")
