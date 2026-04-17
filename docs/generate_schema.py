#!/usr/bin/env python3
"""Generate hardware connection schema for MonJardin."""

from PIL import Image, ImageDraw, ImageFont
import math

W, H = 1400, 900
BG = "#0d1117"
CARD_BG = "#1c1c1e"
CARD_BORDER = "#2c2c2e"
GREEN = "#30d158"
BLUE = "#0a84ff"
ORANGE = "#ff9f0a"
RED = "#ff453a"
PURPLE = "#bf5af2"
YELLOW = "#ffd60a"
TEXT_PRIMARY = "#f5f5f7"
TEXT_SECONDARY = "#8e8e93"
WIRE_GREEN = "#30d158"
WIRE_BLUE = "#0a84ff"
WIRE_RED = "#ff453a"
WIRE_YELLOW = "#ffd60a"
WIRE_GRAY = "#636366"

img = Image.new("RGB", (W, H), BG)
draw = ImageDraw.Draw(img)

def try_font(size, bold=False):
    for name in [
        "/System/Library/Fonts/SF-Pro-Text-Regular.otf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ]:
        try:
            return ImageFont.truetype(name, size)
        except:
            pass
    return ImageFont.load_default()

F_TITLE = try_font(22, bold=True)
F_HEAD = try_font(15, bold=True)
F_BODY = try_font(12)
F_SMALL = try_font(10)
F_BIG = try_font(18, bold=True)

def rounded_rect(draw, xy, radius, fill, outline=None, width=1):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill, outline=outline, width=width)

def card(x, y, w, h, title, icon, color, items):
    rounded_rect(draw, (x, y, x+w, y+h), 12, CARD_BG, color, 2)
    # header bar
    rounded_rect(draw, (x, y, x+w, y+34), 12, color + "33", None)
    draw.rectangle([x, y+22, x+w, y+34], fill=color + "33")
    # icon circle
    draw.ellipse([x+10, y+7, x+30, y+27], fill=color + "44", outline=color, width=1)
    draw.text((x+20, y+17), icon, font=F_HEAD, fill=color, anchor="mm")
    draw.text((x+38, y+17), title, font=F_HEAD, fill=TEXT_PRIMARY, anchor="lm")
    # items
    for i, (label, val, col) in enumerate(items):
        iy = y + 44 + i * 22
        draw.ellipse([x+12, iy+4, x+18, iy+10], fill=col)
        draw.text((x+26, iy+7), label, font=F_BODY, fill=TEXT_SECONDARY, anchor="lm")
        draw.text((x+w-10, iy+7), val, font=F_BODY, fill=col, anchor="rm")

def arrow_line(x0, y0, x1, y1, color, width=2, dashed=False):
    if dashed:
        # draw dashed
        dx, dy = x1-x0, y1-y0
        length = math.sqrt(dx*dx + dy*dy)
        steps = int(length / 10)
        for i in range(0, steps, 2):
            sx = x0 + dx * i / steps
            sy = y0 + dy * i / steps
            ex = x0 + dx * min(i+1, steps) / steps
            ey = y0 + dy * min(i+1, steps) / steps
            draw.line([sx, sy, ex, ey], fill=color, width=width)
    else:
        draw.line([x0, y0, x1, y1], fill=color, width=width)
    # arrowhead
    angle = math.atan2(y1-y0, x1-x0)
    alen = 8
    ax1 = x1 - alen * math.cos(angle - 0.4)
    ay1 = y1 - alen * math.sin(angle - 0.4)
    ax2 = x1 - alen * math.cos(angle + 0.4)
    ay2 = y1 - alen * math.sin(angle + 0.4)
    draw.polygon([(x1, y1), (ax1, ay1), (ax2, ay2)], fill=color)

def label_line(x0, y0, x1, y1, text, color, width=2):
    draw.line([x0, y0, x1, y1], fill=color, width=width)
    mx, my = (x0+x1)//2, (y0+y1)//2
    tw = draw.textlength(text, font=F_SMALL)
    draw.rectangle([mx-tw//2-3, my-8, mx+tw//2+3, my+8], fill=BG)
    draw.text((mx, my), text, font=F_SMALL, fill=color, anchor="mm")

# ── Title ──────────────────────────────────────────────────────────────────────
draw.text((W//2, 30), "MonJardin — Schéma de connexion matérielle", font=F_BIG, fill=TEXT_PRIMARY, anchor="mm")
draw.text((W//2, 52), "Vullierens · Vaud · Suisse", font=F_BODY, fill=TEXT_SECONDARY, anchor="mm")
draw.line([60, 65, W-60, 65], fill=CARD_BORDER, width=1)

# ── RASPBERRY PI 5 (center-left) ──────────────────────────────────────────────
RPI_X, RPI_Y = 460, 90
RPI_W, RPI_H = 200, 230
rounded_rect(draw, (RPI_X, RPI_Y, RPI_X+RPI_W, RPI_Y+RPI_H), 14, "#1a2a1a", GREEN, 3)
draw.text((RPI_X + RPI_W//2, RPI_Y+18), "🍓 Raspberry Pi 5", font=F_HEAD, fill=GREEN, anchor="mm")
draw.line([RPI_X+10, RPI_Y+32, RPI_X+RPI_W-10, RPI_Y+32], fill=GREEN+"44", width=1)
rpi_items = [
    ("Flask :5000", GREEN),
    ("SQLite DB", BLUE),
    ("APScheduler", ORANGE),
    ("Open-Meteo", BLUE),
    ("PWA + API JSON", PURPLE),
    ("Simulation :8081", YELLOW),
]
for i, (txt, col) in enumerate(rpi_items):
    iy = RPI_Y + 44 + i * 28
    draw.ellipse([RPI_X+16, iy+4, RPI_X+24, iy+12], fill=col+"66", outline=col, width=1)
    draw.text((RPI_X+32, iy+8), txt, font=F_BODY, fill=TEXT_SECONDARY, anchor="lm")

# ── ARDUINO EDGE CONTROL (center-right) ───────────────────────────────────────
ARD_X, ARD_Y = 730, 90
ARD_W, ARD_H = 200, 230
rounded_rect(draw, (ARD_X, ARD_Y, ARD_X+ARD_W, ARD_Y+ARD_H), 14, "#1a1a2a", BLUE, 3)
draw.text((ARD_X + ARD_W//2, ARD_Y+18), "⚡ Arduino Edge Control", font=F_HEAD, fill=BLUE, anchor="mm")
draw.line([ARD_X+10, ARD_Y+32, ARD_X+ARD_W-10, ARD_Y+32], fill=BLUE+"44", width=1)
ard_items = [
    ("4× ADC SoilWatch 10", GREEN),
    ("2× DS18B20 OneWire", ORANGE),
    ("4× Relais Latching", RED),
    ("1× H-Bridge vérin", PURPLE),
    ("REST API HTTP :80", BLUE),
    ("WiFi NINA (RP2040)", YELLOW),
]
for i, (txt, col) in enumerate(ard_items):
    iy = ARD_Y + 44 + i * 28
    draw.ellipse([ARD_X+16, iy+4, ARD_X+24, iy+12], fill=col+"66", outline=col, width=1)
    draw.text((ARD_X+32, iy+8), txt, font=F_BODY, fill=TEXT_SECONDARY, anchor="lm")

# Ethernet/WiFi arrow between RPi and Arduino
MID_X = (RPI_X+RPI_W + ARD_X)//2
MID_Y = RPI_Y + RPI_H//2
draw.line([RPI_X+RPI_W, MID_Y, ARD_X, MID_Y], fill=WIRE_BLUE, width=3)
arrow_line(RPI_X+RPI_W+2, MID_Y, ARD_X-2, MID_Y, WIRE_BLUE, 3)
arrow_line(ARD_X-2, MID_Y, RPI_X+RPI_W+2, MID_Y, WIRE_BLUE, 3)
draw.rectangle([MID_X-42, MID_Y-10, MID_X+42, MID_Y+10], fill=BG)
draw.text((MID_X, MID_Y), "HTTP REST / WiFi", font=F_SMALL, fill=WIRE_BLUE, anchor="mm")

# ── SENSORS (left column) ─────────────────────────────────────────────────────
sensors = [
    (60, 100, "SoilWatch 10 — Z1 (Serre)", "Humidité sol 0–100%", GREEN, "ADC"),
    (60, 200, "SoilWatch 10 — Z2 (Soleil)", "Humidité sol 0–100%", GREEN, "ADC"),
    (60, 300, "SoilWatch 10 — Z3 (Mi-ombre)", "Humidité sol 0–100%", GREEN, "ADC"),
    (60, 400, "SoilWatch 10 — Z4 (Aromates)", "Humidité sol 0–100%", GREEN, "ADC"),
    (60, 510, "DS18B20 — Extérieur", "Temp. °C OneWire", ORANGE, "1-Wire"),
    (60, 590, "DS18B20 — Intérieur Serre", "Temp. °C OneWire", ORANGE, "1-Wire"),
]
for (sx, sy, name, desc, col, proto) in sensors:
    rounded_rect(draw, (sx, sy, sx+370, sy+70), 8, CARD_BG, col+"66", 1)
    draw.ellipse([sx+10, sy+8, sx+30, sy+28], fill=col+"33", outline=col, width=1)
    draw.text((sx+20, sy+18), "◉", font=F_BODY, fill=col, anchor="mm")
    draw.text((sx+38, sy+15), name, font=F_BODY, fill=TEXT_PRIMARY, anchor="lm")
    draw.text((sx+38, sy+35), desc, font=F_SMALL, fill=TEXT_SECONDARY, anchor="lm")
    # protocol badge
    tw = draw.textlength(proto, font=F_SMALL)
    draw.rounded_rectangle([sx+330, sy+20, sx+360, sy+36], radius=4, fill=col+"33", outline=col, width=1)
    draw.text((sx+345, sy+28), proto, font=F_SMALL, fill=col, anchor="mm")
    # arrow to Arduino
    arrow_line(sx+370, sy+35, ARD_X, ARD_Y+RPI_H//2 - 20 + sensors.index((sx,sy,name,desc,col,proto))*8, col, 1, dashed=True)

# ── ACTUATORS (right column) ──────────────────────────────────────────────────
actuators = [
    (980, 100, "Vanne 24V Latching — Z1", "Irrigation Serre", RED, "Relais"),
    (980, 185, "Vanne 24V Latching — Z2", "Irrigation Soleil", RED, "Relais"),
    (980, 270, "Vanne 24V Latching — Z3", "Irrigation Mi-ombre", RED, "Relais"),
    (980, 355, "Vanne 24V Latching — Z4", "Irrigation Aromates", RED, "Relais"),
    (980, 460, "Vérin Linéaire 24V", "Ouverture toit serre", PURPLE, "H-Bridge"),
]
for (ax, ay, name, desc, col, proto) in actuators:
    rounded_rect(draw, (ax, ay, ax+340, ay+65), 8, CARD_BG, col+"66", 1)
    draw.text((ax+16, ay+16), "▶", font=F_BODY, fill=col, anchor="lm")
    draw.text((ax+36, ay+13), name, font=F_BODY, fill=TEXT_PRIMARY, anchor="lm")
    draw.text((ax+36, ay+33), desc, font=F_SMALL, fill=TEXT_SECONDARY, anchor="lm")
    tw = draw.textlength(proto, font=F_SMALL)
    draw.rounded_rectangle([ax+300, ay+18, ax+332, ay+34], radius=4, fill=col+"33", outline=col, width=1)
    draw.text((ax+316, ay+26), proto, font=F_SMALL, fill=col, anchor="mm")
    # arrow from Arduino
    arrow_line(ARD_X+ARD_W, ARD_Y+40 + actuators.index((ax,ay,name,desc,col,proto))*35, ax, ay+32, col, 1, dashed=True)

# ── INTERNET / MÉTÉO (top center) ─────────────────────────────────────────────
WEB_X, WEB_Y = 530, 370
rounded_rect(draw, (WEB_X, WEB_Y, WEB_X+340, WEB_Y+55), 10, CARD_BG, BLUE+"88", 1)
draw.text((WEB_X+20, WEB_Y+15), "🌐  Open-Meteo API", font=F_BODY, fill=BLUE, anchor="lm")
draw.text((WEB_X+20, WEB_Y+35), "Météo Vullierens 46.778°N 6.641°E · cache 30 min", font=F_SMALL, fill=TEXT_SECONDARY, anchor="lm")
arrow_line(RPI_X+RPI_W//2, WEB_Y, RPI_X+RPI_W//2, RPI_Y+RPI_H, WIRE_BLUE, 2)

# ── USERS / BROWSER (bottom center) ──────────────────────────────────────────
USER_X, USER_Y = 460, 680
rounded_rect(draw, (USER_X, USER_Y, USER_X+480, USER_Y+80), 12, CARD_BG, GREEN+"88", 2)
draw.text((USER_X+20, USER_Y+16), "📱 iPhone / iPad / PC  —  PWA + Interface Web", font=F_HEAD, fill=GREEN, anchor="lm")
draw.text((USER_X+20, USER_Y+38), "http://monjardin.local:5000  ·  Mode sombre/clair  ·  Installable iOS", font=F_SMALL, fill=TEXT_SECONDARY, anchor="lm")
draw.text((USER_X+20, USER_Y+58), "Dashboard · Journal · Encyclopédie · Plantations · Diagnostic", font=F_SMALL, fill=TEXT_SECONDARY, anchor="lm")
arrow_line(RPI_X+RPI_W//2, USER_Y, RPI_X+RPI_W//2, RPI_Y+RPI_H+5, WIRE_GREEN, 2)
arrow_line(RPI_X+RPI_W//2, RPI_Y+RPI_H+5, RPI_X+RPI_W//2, USER_Y, WIRE_GREEN, 2)
draw.line([RPI_X+RPI_W//2, RPI_Y+RPI_H, RPI_X+RPI_W//2, USER_Y], fill=WIRE_GREEN, width=2)

# ── POWER (bottom strip) ──────────────────────────────────────────────────────
PWR_Y = 790
draw.line([60, PWR_Y, W-60, PWR_Y], fill=CARD_BORDER, width=1)
draw.text((W//2, PWR_Y+18), "Alimentation  5V USB-C → Raspberry Pi 5   ·   24V DC → Arduino Edge Control, Vannes, Vérin", font=F_SMALL, fill=TEXT_SECONDARY, anchor="mm")
draw.text((W//2, PWR_Y+36), "SQLite (garden.db) stocké sur Raspberry Pi  ·  Simulation intégrée (localhost:8081) en mode développement", font=F_SMALL, fill=TEXT_SECONDARY+"88", anchor="mm")

# ── Legend ─────────────────────────────────────────────────────────────────────
LG_X, LG_Y = 60, 670
draw.text((LG_X, LG_Y), "Légende :", font=F_SMALL, fill=TEXT_SECONDARY, anchor="lm")
legend = [
    (WIRE_BLUE, "Communication HTTP/WiFi"),
    (WIRE_GREEN, "Données capteurs / UI"),
    (RED+"aa", "Commande actionneurs"),
    (ORANGE+"aa", "Température OneWire"),
]
for i, (col, txt) in enumerate(legend):
    lx = LG_X + i * 190
    draw.line([lx, LG_Y+20, lx+30, LG_Y+20], fill=col, width=2)
    draw.text((lx+36, LG_Y+20), txt, font=F_SMALL, fill=TEXT_SECONDARY, anchor="lm")

img.save("/Users/patrick/Github/MonJardin/docs/schema_connexion.png", "PNG", optimize=True)
print("Schema saved: docs/schema_connexion.png")
