#!/usr/bin/env python3
"""Generate separate-layer transparent PNG VFX for Cino (PHVRMVCY MUGEN).

These are NOT character sprites. They are additive-friendly RGBA effects
drawn above/beside fighters. Palette: lime #39ff14, purple #b44cff, lean #c44cff.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path("/workspace/public/mugen/vfx/cino")
LIME = (57, 255, 20)
PURPLE = (180, 76, 255)
LEAN = (196, 76, 255)
CYAN = (62, 232, 255)
WHITE = (244, 244, 244)
GOLD = (255, 215, 106)
SMOKE = (48, 24, 72)

rng = random.Random(212)


def blank(w: int, h: int) -> Image.Image:
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def col(rgb, a: int):
    return (rgb[0], rgb[1], rgb[2], max(0, min(255, a)))


def composite(base: Image.Image, layer: Image.Image) -> Image.Image:
    return Image.alpha_composite(base, layer)


def glow_blob(size, cx, cy, radius, rgb, alpha=220, power=1.7):
    """Soft radial glow as its own RGBA image, then pasted conceptually via composite."""
    w, h = size
    layer = blank(w, h)
    px = layer.load()
    r = max(1.0, float(radius))
    x0 = max(0, int(cx - r - 1))
    x1 = min(w, int(cx + r + 2))
    y0 = max(0, int(cy - r - 1))
    y1 = min(h, int(cy + r + 2))
    for y in range(y0, y1):
        dy = (y - cy) / r
        for x in range(x0, x1):
            d = math.sqrt((x - cx) / r * ((x - cx) / r) + dy * dy)
            if d >= 1:
                continue
            fall = (1 - d) ** power
            a = int(alpha * fall)
            if a <= 0:
                continue
            px[x, y] = col(rgb, a)
    return layer


def add_blob(img, cx, cy, radius, rgb, alpha=220, power=1.7):
    return composite(img, glow_blob(img.size, cx, cy, radius, rgb, alpha, power))


def glow_line(img, pts, rgb, width, passes=None):
    if len(pts) < 2:
        return img
    if passes is None:
        passes = ((width * 3.2, 70), (width * 1.6, 140), (max(1, width * 0.55), 230))
    for w, a in passes:
        layer = blank(*img.size)
        d = ImageDraw.Draw(layer)
        d.line(pts, fill=col(rgb, a), width=max(1, int(w)), joint="curve")
        blur = max(0.4, w / 4)
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
        img = composite(img, layer)
    return img


def glow_ellipse(img, bbox, rgb, width, fill_a=0, outline_a=200):
    layer = blank(*img.size)
    d = ImageDraw.Draw(layer)
    if fill_a:
        d.ellipse(bbox, fill=col(rgb, fill_a))
    if width and outline_a:
        d.ellipse(bbox, outline=col(rgb, outline_a), width=max(1, int(width)))
    layer = layer.filter(ImageFilter.GaussianBlur(max(0.6, width * 0.45)))
    return composite(img, layer)


def spike_star(img, cx, cy, inner, outer, n, rgb, rot=0.0, jitter=0.18):
    pts_outer = []
    pts_inner = []
    for i in range(n):
        a = rot + i * (2 * math.pi / n)
        j = 1 + rng.uniform(-jitter, jitter)
        ox = cx + math.cos(a) * outer * j
        oy = cy + math.sin(a) * outer * j
        ia = a + math.pi / n
        ix = cx + math.cos(ia) * inner
        iy = cy + math.sin(ia) * inner
        pts_outer.append((ox, oy))
        pts_inner.append((ix, iy))
        img = glow_line(img, [(cx, cy), (ox, oy)], rgb, max(2, outer / 18))
    poly = []
    for i in range(n):
        poly.append(pts_outer[i])
        poly.append(pts_inner[i])
    layer = blank(*img.size)
    ImageDraw.Draw(layer).polygon(poly, fill=col(WHITE, 200))
    layer = layer.filter(ImageFilter.GaussianBlur(1.2))
    return composite(img, layer)


def lightning_path(x0, y0, x1, y1, gens=5, amp=28):
    pts = [(x0, y0), (x1, y1)]
    displacement = amp
    for _ in range(gens):
        nxt = [pts[0]]
        for i in range(len(pts) - 1):
            ax, ay = pts[i]
            bx, by = pts[i + 1]
            mx, my = (ax + bx) / 2, (ay + by) / 2
            dx, dy = bx - ax, by - ay
            ln = math.hypot(dx, dy) or 1
            nx, ny = -dy / ln, dx / ln
            off = rng.uniform(-displacement, displacement)
            nxt.append((mx + nx * off, my + ny * off))
            nxt.append((bx, by))
        pts = nxt
        displacement *= 0.52
    return pts


def add_lightning(img, x0, y0, x1, y1, rgb=CYAN, gens=5, amp=30, width=3.5, branches=2):
    pts = lightning_path(x0, y0, x1, y1, gens, amp)
    img = glow_line(img, pts, rgb, width)
    img = glow_line(img, pts, WHITE, max(1.2, width * 0.45), passes=((width, 90), (1.2, 255)))
    for _ in range(branches):
        if len(pts) < 4:
            break
        i = rng.randint(1, len(pts) - 2)
        sx, sy = pts[i]
        ang = rng.uniform(-2.2, 2.2)
        length = rng.uniform(18, 54)
        img = add_lightning(
            img,
            sx,
            sy,
            sx + math.cos(ang) * length,
            sy + math.sin(ang) * length,
            rgb,
            max(2, gens - 2),
            amp * 0.45,
            width * 0.7,
            0,
        )
    return img


def droplets(img, cx, cy, rgb, n=18, spread=50, life=1.0):
    for _ in range(n):
        ang = rng.uniform(-math.pi, math.pi)
        dist = rng.uniform(8, spread) * life
        r = rng.uniform(2.5, 9) * (1.15 - 0.5 * life)
        img = add_blob(img, cx + math.cos(ang) * dist, cy + math.sin(ang) * dist * 0.72, r, rgb, int(210 * (1 - 0.35 * life)), 1.3)
    return img


def save(img: Image.Image, name: str):
    path = OUT / name
    img.save(path, "PNG", optimize=True)
    return name


def frames_hitspark(kind: str):
    specs = {
        "hitsparkLight": dict(size=128, n=5, spikes=7, outer=46, rgb=WHITE, rim=LIME),
        "hitsparkMedium": dict(size=192, n=5, spikes=8, outer=72, rgb=LIME, rim=WHITE),
        "hitsparkHeavy": dict(size=256, n=6, spikes=10, outer=104, rgb=LIME, rim=CYAN),
        "hitsparkSpecial": dict(size=320, n=7, spikes=12, outer=138, rgb=LIME, rim=PURPLE),
    }[kind]
    s, n = specs["size"], specs["n"]
    out = []
    for i in range(n):
        t = i / max(1, n - 1)
        img = blank(s, s)
        c = s / 2
        scale = 0.45 + 0.7 * math.sin(math.pi * min(1, t * 1.15))
        img = add_blob(img, c, c, specs["outer"] * scale * 1.35, specs["rim"], 90, 2.2)
        img = add_blob(img, c, c, specs["outer"] * scale * 0.55, specs["rgb"], 200, 1.4)
        img = spike_star(
            img,
            c,
            c,
            8 * scale,
            specs["outer"] * scale,
            specs["spikes"],
            specs["rgb"] if i < n / 2 else specs["rim"],
            rot=t * 0.4 + rng.random() * 0.2,
            jitter=0.12 + 0.1 * t,
        )
        if kind in ("hitsparkHeavy", "hitsparkSpecial"):
            rad = specs["outer"] * (0.4 + 0.9 * t)
            img = glow_ellipse(img, (c - rad, c - rad * 0.85, c + rad, c + rad * 0.85), LIME, 6 - 3 * t, 0, 180)
        if kind == "hitsparkSpecial":
            img = add_lightning(img, c - 90, c - 40, c + 100, c + 50, CYAN, 4, 22, 2.8, 1)
        img = add_blob(img, c, c, 10 + 6 * (1 - t), WHITE, 255, 1.1)
        out.append({"file": f"/mugen/vfx/cino/{save(img, f'{kind}_{i:02d}.png')}", "ox": s // 2, "oy": s // 2, "w": s, "h": s, "dur": 2})
    return out


def frames_plasma():
    s, n = 176, 8
    out = []
    for i in range(n):
        t = i / n
        img = blank(s, s)
        c = s / 2
        wob = 1 + 0.08 * math.sin(t * 6.28)
        img = add_blob(img, c, c, 70 * wob, LIME, 70, 2.4)
        img = add_blob(img, c - 8, c - 6, 38 * wob, CYAN, 140, 1.6)
        img = add_blob(img, c + 6, c + 4, 28, PURPLE, 90, 1.8)
        img = add_blob(img, c, c, 14, WHITE, 230, 1.2)
        ang = t * 6.28
        img = add_lightning(
            img,
            c + math.cos(ang) * 12,
            c + math.sin(ang) * 12,
            c + math.cos(ang) * 68,
            c + math.sin(ang) * 68,
            LIME,
            3,
            10,
            2.2,
            1,
        )
        out.append({"file": f"/mugen/vfx/cino/{save(img, f'plasma_{i:02d}.png')}", "ox": s // 2, "oy": s // 2, "w": s, "h": s, "dur": 3})
    return out


def frames_candle():
    w, h, n = 96, 240, 6
    out = []
    for i in range(n):
        t = i / n
        img = blank(w, h)
        cx = w / 2
        body_h = 150 + 18 * math.sin(t * 6.28)
        y1 = h - 18
        y0 = y1 - body_h
        img = add_blob(img, cx, (y0 + y1) / 2, 48, LIME, 70, 2.0)
        layer = blank(w, h)
        d = ImageDraw.Draw(layer)
        d.rectangle((cx - 14, y0, cx + 14, y1), fill=col(LIME, 210))
        d.rectangle((cx - 5, y0 - 16, cx + 5, y0 + 8), fill=col(WHITE, 230))
        wick = y0 - 22 - 6 * math.sin(t * 8)
        d.line([(cx, y0), (cx, wick)], fill=col(GOLD, 240), width=3)
        layer = layer.filter(ImageFilter.GaussianBlur(1.1))
        img = composite(img, layer)
        img = add_blob(img, cx, wick, 16, WHITE, 180, 1.4)
        img = add_blob(img, cx, wick - 6, 28, LIME, 100, 1.8)
        out.append({"file": f"/mugen/vfx/cino/{save(img, f'candleTrail_{i:02d}.png')}", "ox": w // 2, "oy": h - 8, "w": w, "h": h, "dur": 3})
    return out


def frames_streak():
    w, h, n = 300, 80, 5
    out = []
    for i in range(n):
        t = i / max(1, n - 1)
        img = blank(w, h)
        y = h / 2
        length = 80 + 200 * (1 - t * 0.15)
        img = glow_line(img, [(18, y), (length, y)], LIME, 10 - 5 * t)
        img = glow_line(img, [(30, y - 14), (length * 0.85, y - 10)], CYAN, 4)
        img = glow_line(img, [(26, y + 16), (length * 0.72, y + 12)], WHITE, 3)
        for k in range(6):
            yy = y + rng.uniform(-22, 22)
            x0 = rng.uniform(20, 80)
            img = glow_line(img, [(x0, yy), (x0 + rng.uniform(40, 120) * (1 - t), yy)], LIME, 2)
        out.append({"file": f"/mugen/vfx/cino/{save(img, f'speedStreak_{i:02d}.png')}", "ox": 24, "oy": h // 2, "w": w, "h": h, "dur": 2})
    return out


def frames_lightning():
    s, n = 300, 6
    out = []
    for i in range(n):
        img = blank(s, s)
        c = s / 2
        img = add_blob(img, c, c, 40, CYAN, 60, 2.2)
        for k in range(3):
            ang = rng.uniform(0, 6.28)
            img = add_lightning(
                img,
                c,
                c,
                c + math.cos(ang) * 120,
                c + math.sin(ang) * 120,
                CYAN if k else LIME,
                5,
                26,
                3.2,
                2,
            )
        out.append({"file": f"/mugen/vfx/cino/{save(img, f'lightning_{i:02d}.png')}", "ox": s // 2, "oy": s // 2, "w": s, "h": s, "dur": 2})
    return out


def frames_lean():
    s, n = 240, 8
    out = []
    for i in range(n):
        t = i / max(1, n - 1)
        img = blank(s, s)
        c = s / 2
        img = add_blob(img, c, c + 10, 70 + 40 * t, LEAN, int(90 * (1 - 0.4 * t)), 2.0)
        img = add_blob(img, c, c, 28, WHITE, int(180 * (1 - t)), 1.3)
        img = droplets(img, c, c, LEAN, 22, 36 + 70 * t, t)
        img = droplets(img, c + 8, c - 6, PURPLE, 10, 24 + 40 * t, t)
        # splash crown
        for k in range(9):
            a = -math.pi + k * (math.pi / 8)
            img = glow_line(
                img,
                [(c, c), (c + math.cos(a) * (30 + 80 * t), c + math.sin(a) * (18 + 50 * t))],
                LEAN if k % 2 else WHITE,
                5 - 2 * t,
            )
        out.append({"file": f"/mugen/vfx/cino/{save(img, f'leanSplash_{i:02d}.png')}", "ox": s // 2, "oy": s // 2, "w": s, "h": s, "dur": 2})
    return out


def frames_aura():
    w, h, n = 300, 380, 8
    out = []
    for i in range(n):
        t = i / n
        img = blank(w, h)
        cx, cy = w / 2, h - 28
        img = add_blob(img, cx, cy - 140, 150, LIME, 50 + 18 * math.sin(t * 6.28), 2.4)
        img = add_blob(img, cx, cy - 120, 90, PURPLE, 40 + 16 * math.cos(t * 6.28), 2.2)
        img = glow_ellipse(img, (cx - 70, cy - 260, cx + 70, cy + 8), LIME, 8, 18, 140)
        img = glow_ellipse(img, (cx - 48, cy - 220, cx + 48, cy + 4), WHITE, 3, 0, 160)
        for k in range(5):
            ang = -math.pi / 2 + rng.uniform(-0.6, 0.6)
            img = add_lightning(img, cx, cy - 20, cx + math.cos(ang) * 40, cy - 180 - 30 * math.sin(t * 6.28 + k), LIME, 3, 12, 2, 0)
        out.append({"file": f"/mugen/vfx/cino/{save(img, f'chargeAura_{i:02d}.png')}", "ox": w // 2, "oy": h - 16, "w": w, "h": h, "dur": 3})
    return out


def frames_dash():
    w, h, n = 220, 110, 5
    out = []
    for i in range(n):
        t = i / max(1, n - 1)
        img = blank(w, h)
        y = h / 2
        img = add_blob(img, 40 + 20 * t, y, 34, LIME, 80, 1.8)
        img = glow_line(img, [(16, y), (180 - 40 * t, y)], LIME, 12 - 6 * t)
        img = glow_line(img, [(20, y - 18), (150, y - 8)], PURPLE, 4)
        img = droplets(img, 50, y, LIME, 8, 28, t)
        out.append({"file": f"/mugen/vfx/cino/{save(img, f'dashTrail_{i:02d}.png')}", "ox": 28, "oy": h // 2, "w": w, "h": h, "dur": 2})
    return out


def frames_shockwave():
    w, h, n = 560, 180, 6
    out = []
    for i in range(n):
        t = i / max(1, n - 1)
        img = blank(w, h)
        cx, cy = w / 2, h - 36
        rx = 40 + 240 * t
        ry = 12 + 48 * t
        img = glow_ellipse(img, (cx - rx, cy - ry, cx + rx, cy + ry), LIME, 10 - 5 * t, 20, 210)
        img = glow_ellipse(img, (cx - rx * 0.72, cy - ry * 0.7, cx + rx * 0.72, cy + ry * 0.7), WHITE, 4, 0, 180)
        img = add_blob(img, cx, cy, 30 + 10 * (1 - t), WHITE, int(160 * (1 - t)), 1.4)
        for k in range(7):
            a = math.pi + k * (math.pi / 6)
            img = glow_line(img, [(cx, cy), (cx + math.cos(a) * rx * 0.9, cy + math.sin(a) * ry)], LIME, 3)
        out.append({"file": f"/mugen/vfx/cino/{save(img, f'shockwave_{i:02d}.png')}", "ox": w // 2, "oy": h - 28, "w": w, "h": h, "dur": 3})
    return out


def frames_transform():
    s, n = 560, 10
    out = []
    for i in range(n):
        t = i / max(1, n - 1)
        img = blank(s, s)
        c = s / 2
        # smoke / energy
        for k in range(10):
            ang = k * 0.62 + t * 4
            dist = 40 + 160 * t
            img = add_blob(img, c + math.cos(ang) * dist, c + math.sin(ang) * dist * 0.85, 36 + 20 * (1 - t), SMOKE, int(140 * (1 - 0.5 * t)), 1.8)
            img = add_blob(img, c + math.cos(ang + 0.3) * dist * 0.7, c + math.sin(ang + 0.3) * dist * 0.7, 22, PURPLE, 90, 1.7)
        img = add_blob(img, c, c, 80 + 120 * t, PURPLE, int(110 * (1 - 0.4 * t)), 2.1)
        img = add_blob(img, c, c, 50 + 40 * math.sin(t * math.pi), LIME, 90, 1.8)
        img = spike_star(img, c, c, 16, 70 + 150 * t, 11, LIME, t * 0.5, 0.1)
        for k in range(4):
            ang = rng.uniform(0, 6.28)
            img = add_lightning(img, c, c, c + math.cos(ang) * (80 + 160 * t), c + math.sin(ang) * (80 + 160 * t), CYAN, 4, 24, 3, 1)
        img = add_blob(img, c, c, 22, WHITE, 230, 1.1)
        out.append({"file": f"/mugen/vfx/cino/{save(img, f'transformBurst_{i:02d}.png')}", "ox": s // 2, "oy": s // 2 + 40, "w": s, "h": s, "dur": 3})
    return out


def frames_super_burst():
    s, n = 800, 12
    out = []
    for i in range(n):
        t = i / max(1, n - 1)
        img = blank(s, s)
        c = s / 2
        img = add_blob(img, c, c, 140 + 260 * t, LIME, int(80 * (1 - 0.45 * t)), 2.3)
        img = add_blob(img, c, c, 90 + 80 * math.sin(t * math.pi), PURPLE, 70, 2.0)
        img = spike_star(img, c, c, 20, 120 + 220 * t, 14, WHITE, t * 0.35, 0.08)
        rad = 60 + 340 * t
        img = glow_ellipse(img, (c - rad, c - rad, c + rad, c + rad), LIME, 14 - 8 * t, 10, 200)
        img = glow_ellipse(img, (c - rad * 0.7, c - rad * 0.7, c + rad * 0.7, c + rad * 0.7), WHITE, 5, 0, 160)
        for k in range(6):
            ang = k * (math.pi / 3) + t
            img = add_lightning(img, c, c, c + math.cos(ang) * (180 + 200 * t), c + math.sin(ang) * (180 + 200 * t), CYAN, 5, 36, 4, 2)
        img = add_blob(img, c, c, 36, WHITE, 255, 1.05)
        out.append({"file": f"/mugen/vfx/cino/{save(img, f'superBurst_{i:02d}.png')}", "ox": s // 2, "oy": s // 2, "w": s, "h": s, "dur": 3})
    return out


def frames_super_ring():
    s, n = 720, 8
    out = []
    for i in range(n):
        t = i / max(1, n - 1)
        img = blank(s, s)
        c = s / 2
        rad = 40 + 300 * t
        img = glow_ellipse(img, (c - rad, c - rad * 0.55, c + rad, c + rad * 0.55), LIME, 16 - 8 * t, 8, 220)
        img = glow_ellipse(img, (c - rad * 0.82, c - rad * 0.42, c + rad * 0.82, c + rad * 0.42), PURPLE, 6, 0, 160)
        out.append({"file": f"/mugen/vfx/cino/{save(img, f'superRing_{i:02d}.png')}", "ox": s // 2, "oy": s // 2, "w": s, "h": s, "dur": 3})
    return out


def frames_cutin():
    w, h = 460, 250
    img = blank(w, h)
    # energy frame only — portrait is composited at runtime from Cino's HUD face
    img = glow_ellipse(img, (12, 12, w - 12, h - 12), LIME, 10, 18, 220)
    img = glow_ellipse(img, (22, 22, w - 22, h - 22), PURPLE, 4, 0, 180)
    layer = blank(w, h)
    d = ImageDraw.Draw(layer)
    d.rectangle((18, 18, w - 18, h - 18), outline=col(LIME, 230), width=3)
    d.polygon([(0, 40), (36, 18), (36, 70)], fill=col(LIME, 180))
    d.polygon([(w, h - 40), (w - 36, h - 18), (w - 36, h - 70)], fill=col(PURPLE, 180))
    img = composite(img, layer)
    img = add_lightning(img, 30, 40, w - 40, h - 36, CYAN, 4, 18, 2.4, 1)
    img = add_lightning(img, 40, h - 30, w - 28, 36, LIME, 4, 16, 2, 1)
    name = save(img, "cutinFrame_00.png")
    return [{"file": f"/mugen/vfx/cino/{name}", "ox": 0, "oy": 0, "w": w, "h": h, "dur": 48}]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    anims = {}
    print("hitsparks...")
    for k in ("hitsparkLight", "hitsparkMedium", "hitsparkHeavy", "hitsparkSpecial"):
        anims[k] = frames_hitspark(k)
    print("plasma / trails / lightning...")
    anims["plasma"] = frames_plasma()
    anims["candleTrail"] = frames_candle()
    anims["speedStreak"] = frames_streak()
    anims["lightning"] = frames_lightning()
    anims["leanSplash"] = frames_lean()
    print("aura / dash / shockwave...")
    anims["chargeAura"] = frames_aura()
    anims["dashTrail"] = frames_dash()
    anims["shockwave"] = frames_shockwave()
    print("transform / super...")
    anims["transformBurst"] = frames_transform()
    anims["superBurst"] = frames_super_burst()
    anims["superRing"] = frames_super_ring()
    anims["cutinFrame"] = frames_cutin()

    atlas = {
        "id": "cino",
        "note": "Separate-layer VFX. Do not composite onto body sheets. Human body scale stays 212px (2x atlas).",
        "palette": {"green": "#39ff14", "purple": "#b44cff", "lean": "#c44cff", "cyan": "#3ee8ff", "white": "#f4f4f4"},
        "blend": "lighter",
        "anims": anims,
        "hooks": {
            "onHit": {
                "light": "hitsparkLight",
                "heavy": "hitsparkHeavy",
                "kick": "hitsparkMedium",
                "special": "hitsparkSpecial",
                "super": "hitsparkSpecial",
            },
            "onStart": {
                "bullForm": ["transformBurst", "chargeAura", "lightning", "shockwave"],
                "overdrive": ["superBurst", "superRing", "chargeAura", "cutin"],
                "candleRush": ["candleTrail", "speedStreak"],
                "leanSplash": ["leanSplash"],
                "chartBreaker": ["shockwave", "lightning"],
                "uppercut": ["lightning", "plasma"],
                "launcher": ["lightning"],
                "standHeavy": ["plasma"],
            },
            "onActive": {
                "bullForm": {"every": 4, "kinds": ["lightning"], "untilMoveEnd": True},
                "overdrive": {"every": 3, "kinds": ["plasma", "lightning"]},
                "candleRush": {"every": 2, "kinds": ["candleTrail", "speedStreak"]},
                "leanSplash": {"every": 6, "kinds": ["leanSplash"]},
            },
            "onDash": ["dashTrail", "speedStreak"],
            "onCharge": ["chargeAura"],
        },
    }
    (OUT / "atlas.json").write_text(json.dumps(atlas, indent=2))
    n = sum(len(v) for v in anims.values())
    print(f"wrote {n} frames + atlas to {OUT}")


if __name__ == "__main__":
    main()
