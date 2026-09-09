#!/usr/bin/env python3
"""Extract Cino v2 from the four movement/combat/bull sheets.

The conversation six-sheet pack (PNG) is mapped onto the on-disk JPEG masters:
  Sheet 1 movement  -> cino-v2-move.jpg
  Sheet 2 combat    -> cino-v2-atk.jpg
  Sheet 3 bull      -> cino-v2-bull1.jpg + cino-v2-bull2.jpg
Sheet 4/5/6 (advanced specials / reference / green super) were not present as
separate PNG files in this workspace; specials are taken from Sheet 2 rows
and Super/transform from Sheet 3 so the in-game kit still covers every named
move. Reference labels/portraits are never exported as combat frames.

Transparency: JPEG has no alpha. Only border-connected near-black canvas is
cleared. Interiors (hoodie, dreads, bull body) stay opaque. High-chroma FX
keeps a soft glow alpha. Never global-delete black.
"""
from __future__ import annotations

import json
import shutil
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path("/workspace")
SHEETS = {
    "move": ROOT / "public/mugen/assets/cino-v2-move.jpg",
    "atk": ROOT / "public/mugen/assets/cino-v2-atk.jpg",
    "bull1": ROOT / "public/mugen/assets/cino-v2-bull1.jpg",
    "bull2": ROOT / "public/mugen/assets/cino-v2-bull2.jpg",
}
# y0, y1, expected frame count, extra pad
# Sheet1 clips (37): IDLE 11 | WALK 9 | RUN 8 | CROUCH 2 + JUMP 4 + LAND 3
ROWS = {
    "move": [
        (24, 298, 11, 36),
        (298, 558, 9, 36),
        (548, 778, 8, 36),
        (768, 998, 9, 40),
    ],
    "atk": [
        (4, 198, 8, 48),
        (186, 392, 8, 48),
        (378, 542, 8, 56),
        (520, 672, 8, 56),
        (652, 856, 8, 48),
        (838, 998, 8, 56),
    ],
    "bull1": [
        (2, 184, 9, 48),
        (172, 352, 9, 40),
        (340, 484, 9, 40),
        (470, 636, 9, 48),
        (616, 778, 8, 52),
        (762, 880, 8, 44),
        (862, 998, 8, 44),
    ],
    "bull2": [
        (2, 188, 9, 48),
        (172, 338, 9, 40),
        (322, 460, 9, 40),
        (444, 624, 9, 48),
        (608, 752, 8, 52),
        (736, 888, 8, 44),
        (872, 998, 8, 44),
    ],
}
OUT = ROOT / "public/mugen/frames/cino"
ATLAS = ROOT / "public/mugen/atlas/cino.json"
SCALE_META = ROOT / "public/mugen/atlas/cino-scale.json"
BASE_SCALE_JSON = ROOT / "public/mugen/atlas/human-cino-base-scale.json"
SPECIALIST_SCALE_JSON = (
    ROOT / "mugen-extract/cino-v2/sheet1/meta/human-cino-base-scale.json"
)
QC = Path("/tmp/cino_v2_qc")
# Roster law: Human Cino = BASE SCALE / 100% for the whole game.
# Measure BODY only on idle: feet → crown of head. Never PNG box, padding,
# hair tip, or FX frames. One character scale for ALL Human gameplay anims
# (no per-frame resize). CHARACTER SCALE ≠ EFFECT SCALE. Preserve aspect.
# Scale Align LOCKED. Median idle feet→crown = 212. Reference s1_001_IDLE.
# Never lock from s1_010_IDLE (drink pose outlier 221) or hair tip.
CINO_BASE_HEIGHT = 212
CINO_BASE_SCALE = 1  # roster 100%; future fighters normalize against this
SCALE_ALIGN_LOCK = {
    "CINO_BASE_HEIGHT": 212,
    "authority": "Scale Align",
    "referenceFrame": "s1_001_IDLE.png",
    "excludeFrame": "s1_010_IDLE",
    "excludeReason": "drink pose height outlier (221); do not use for scale lock",
    "sheet1Inventory": "37/37 qa_pass",
    "CINO_OPAQUE_WITH_HAIR": 249,
    "source": "/workspace/mugen-extract/cino-v2/sheet1/meta/human-cino-base-scale.json",
}
CINO_SPRITE_ZOOM = 2
CINO_ATLAS_BODY_HEIGHT = CINO_BASE_HEIGHT / CINO_SPRITE_ZOOM  # 106
CINO_HAIR_TO_CROWN = 249 / 212  # specialist: opaque-with-hair ≈249 vs body 212
CINO_OPAQUE_WITH_HAIR = 249  # diagnostic only — NEVER use for body scale
CINO_BULL_SCALE = 1.18  # modest bulk; still a playable fighter, not a giant
CINO_FX_SCALE = 1.75  # VFX independent of body (splash / crystals / bull head)
# Chief of Staff / MUGEN Lead — Cino v2 wiring gold criteria (roster lock).
GOLD_CRITERIA = {
    "source": "Chief of Staff / MUGEN Lead",
    "humanCinoIsRosterBaseScale": True,
    "CINO_BASE_SCALE": 1,
    "measure": "idle feet → head (character body only)",
    "oneScaleAcrossHumanAnims": True,
    "noPerAnimStretch": True,
    "noStretchSquashToFakeSize": True,
    "vfxIndependent": True,
    "bullPlayableSizedNotGiant": True,
    "futureFightersSideBySideAgainstHumanIdle": True,
}
CACHE_V = "six4"
CANVAS_MAX = 12
CANVAS_CHROMA = 8
SHEET1_DIR = ROOT / "mugen-extract/cino-v2/sheet1"
SHEET1_PNG_CANDIDATES = [
    ROOT / "mugen-facing/cino-v2/sheets/01-human-basic-movement.png",
    ROOT / "mugen-extract/cino-v2/sheet1/01-human-basic-movement.png",
    ROOT / "public/mugen/assets/01-human-basic-movement.png",
]
# Specialist atlas (1536×1024 RGBA). Windows are seeds; tight alpha bounds + pad follow.
SHEET1_SPEC = {
    "size": (1536, 1024),
    "idle": {"y0": 28, "y1": 318, "n": 11, "x0": 40, "w": 158, "pad": 18},
    "walk": {"y0": 312, "y1": 578, "n": 9, "x0": 30, "w": 188, "pad": 18},
    "run": {"y0": 572, "y1": 816, "n": 8, "x0": 24, "w": 243, "pad": 16},
    "bot": {"y0": 798, "y1": 1024, "n": 9, "x0": 40, "w": 160, "pad": 18},
}
# JPEG master is 1500×1000. Specialist atlas was 1536×1024 RGBA; rects here
# are occupancy + valley cuts on the JPEG (equivalent slicing: full-alpha
# bounds + padding, nothing cropped). Prefer these over fuzzy n_spans.
# IDLE 11 / WALK 9 / RUN 8 (overlapping windows) / BOT 9 (crouch+jump+land).
SHEET1_SPANS = [
    # row0 IDLE y 38–286
    {
        "y0": 38,
        "y1": 286,
        "pad": 36,
        "xs": [
            (50, 176),
            (188, 316),
            (323, 448),
            (456, 579),
            (583, 705),
            (719, 841),
            (847, 970),
            (976, 1096),
            (1100, 1224),
            (1224, 1345),
            (1346, 1470),
        ],
    },
    # row1 WALK y 322–545 — valley cuts, 2px gaps so neighbor shoes stay out
    {
        "y0": 322,
        "y1": 545,
        "pad": 36,
        "xs": [
            (28, 196),
            (200, 357),
            (361, 524),
            (528, 691),
            (695, 852),
            (856, 1009),
            (1013, 1161),
            (1165, 1317),
            (1321, 1474),
        ],
    },
    # row2 RUN y 574–770 — specialist ~243px windows scaled 1536→1500, overlapping
    {
        "y0": 574,
        "y1": 770,
        "pad": 36,
        "xs": [
            (22, 260),
            (198, 435),
            (374, 611),
            (549, 786),
            (725, 962),
            (900, 1137),
            (1075, 1312),
            (1251, 1488),
        ],
    },
    # row3 CROUCH 2 + JUMP 4 + LAND 3
    {
        "y0": 778,
        "y1": 998,
        "pad": 40,
        "xs": [
            (50, 194),
            (226, 350),
            (386, 510),
            (540, 664),
            (688, 824),
            (860, 990),
            (992, 1134),
            (1164, 1294),
            (1312, 1460),
        ],
    },
]
SHEET1_CLIP_FILES = [
    ("idle", 11, "IDLE"),
    ("walk", 9, "WALK"),
    ("run", 8, "RUN"),
    ("crouch", 2, "CROUCH"),
    ("jumpStart", 1, "JUMP_START"),
    ("jumpLoop", 3, "JUMP_AIR"),
    ("jumpLand", 3, "JUMP_LAND"),
]


def chromatic_seed(rgb: np.ndarray) -> np.ndarray:
    r = rgb[..., 0].astype(np.int16)
    g = rgb[..., 1].astype(np.int16)
    b = rgb[..., 2].astype(np.int16)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    chroma = mx - mn
    purple = (b > 55) & (r > 22) & (g < b * 0.92) & (chroma >= 8)
    gold = (r > 95) & (g > 50) & (r > b + 14) & (chroma >= 10)
    skin = (r > 68) & (g > 28) & (b < r) & (g < r * 0.98) & (chroma >= 8)
    white = mx >= 150
    green = (g > 90) & (g > r + 18) & (g > b + 8)
    lit = (mx >= 32) & (chroma >= 7)
    return purple | gold | skin | white | green | lit | (chroma >= 14)


def dilate(mask: np.ndarray, n: int = 1) -> np.ndarray:
    out = mask.copy()
    for _ in range(n):
        up = np.empty_like(out)
        up[0] = False
        up[1:] = out[:-1]
        dn = np.empty_like(out)
        dn[-1] = False
        dn[:-1] = out[1:]
        lf = np.empty_like(out)
        lf[:, 0] = False
        lf[:, 1:] = out[:, :-1]
        rt = np.empty_like(out)
        rt[:, -1] = False
        rt[:, :-1] = out[:, 1:]
        out = out | up | dn | lf | rt
    return out


def erode(mask: np.ndarray, n: int = 1) -> np.ndarray:
    return ~dilate(~mask, n)


def close_mask(mask: np.ndarray, n: int = 2) -> np.ndarray:
    return erode(dilate(mask, n), n)


def flood_from_border(seed: np.ndarray) -> np.ndarray:
    h, w = seed.shape
    vis = np.zeros_like(seed)
    q: deque[tuple[int, int]] = deque()
    for x in range(w):
        if seed[0, x]:
            vis[0, x] = True
            q.append((0, x))
        if seed[h - 1, x]:
            vis[h - 1, x] = True
            q.append((h - 1, x))
    for y in range(h):
        if seed[y, 0]:
            vis[y, 0] = True
            q.append((y, 0))
        if seed[y, w - 1]:
            vis[y, w - 1] = True
            q.append((y, w - 1))
    while q:
        y, x = q.popleft()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not vis[ny, nx] and seed[ny, nx]:
                vis[ny, nx] = True
                q.append((ny, nx))
    return vis


def fill_holes(mask: np.ndarray) -> np.ndarray:
    inv = ~mask
    border = flood_from_border(inv)
    return mask | (inv & ~border)


def border_canvas(rgb: np.ndarray) -> np.ndarray:
    r = rgb[..., 0].astype(np.int16)
    g = rgb[..., 1].astype(np.int16)
    b = rgb[..., 2].astype(np.int16)
    mx = np.maximum(np.maximum(r, g), b)
    chroma = mx - np.minimum(np.minimum(r, g), b)
    canvas = (mx <= CANVAS_MAX) & (chroma <= CANVAS_CHROMA)
    return flood_from_border(canvas)


def n_spans(xocc: np.ndarray, n: int, min_sep: int) -> list[tuple[int, int]]:
    """Split a row into n occupancy clusters using valley cuts between peaks."""
    k = 15 if len(xocc) > 200 else 9
    sm = np.convolve(xocc, np.ones(k) / k, mode="same")
    # candidate peaks
    cand = []
    for x in range(4, len(sm) - 4):
        if sm[x] >= 0.055 and sm[x] >= sm[max(0, x - 6) : x + 7].max():
            cand.append((sm[x], x))
    cand.sort(reverse=True)
    peaks = []
    for _, x in cand:
        if all(abs(x - p) >= min_sep for p in peaks):
            peaks.append(x)
        if len(peaks) >= max(n + 4, n):
            break
    peaks = sorted(peaks)
    if len(peaks) < 2:
        on = sm > 0.04
        out, i = [], 0
        while i < len(on):
            if not on[i]:
                i += 1
                continue
            j = i
            while j < len(on) and on[j]:
                j += 1
            if j - i >= 14:
                out.append((i, j))
            i = j
        return _merge_to_n(out, n)

    # too many peaks → drop weakest until n
    while len(peaks) > n:
        # drop the peak with smallest prominence vs neighbors
        worst_i, worst = 1, 1e9
        for i in range(len(peaks)):
            left = 0 if i == 0 else peaks[i - 1]
            right = len(sm) - 1 if i == len(peaks) - 1 else peaks[i + 1]
            valley = min(sm[left : peaks[i] + 1].min(), sm[peaks[i] : right + 1].min())
            prom = sm[peaks[i]] - valley
            if prom < worst:
                worst, worst_i = prom, i
        peaks.pop(worst_i)

    cuts = [0]
    for i in range(len(peaks) - 1):
        a, b = peaks[i], peaks[i + 1]
        split = a + int(np.argmin(sm[a : b + 1]))
        cuts.append(split)
    cuts.append(len(sm))
    spans = []
    for i in range(len(cuts) - 1):
        a, b = cuts[i], cuts[i + 1]
        while a < b and sm[a] < 0.03:
            a += 1
        while b > a and sm[b - 1] < 0.03:
            b -= 1
        if b - a >= 12:
            spans.append((a, b))
    return _merge_to_n(spans, n) if spans else spans


def _merge_to_n(spans: list[tuple[int, int]], n: int) -> list[tuple[int, int]]:
    if not spans:
        return spans
    spans = list(spans)
    while len(spans) > n:
        # merge the pair with smallest combined width or closest gap
        best, bi = 1e18, 0
        for i in range(len(spans) - 1):
            gap = spans[i + 1][0] - spans[i][1]
            w = (spans[i][1] - spans[i][0]) + (spans[i + 1][1] - spans[i + 1][0])
            score = gap * 3 + w * 0.02
            if score < best:
                best, bi = score, i
        a0, _ = spans[bi]
        _, b1 = spans[bi + 1]
        spans[bi : bi + 2] = [(a0, b1)]
    return spans


def largest_cc(mask: np.ndarray, prefer_center: bool = True) -> np.ndarray:
    """Keep the primary character blob; drop neighboring-frame shoes/hair."""
    h, w = mask.shape
    vis = np.zeros_like(mask, dtype=bool)
    best = None
    best_score = -1.0
    cx0, cx1 = int(w * 0.18), int(w * 0.82)
    for y in range(h):
        row = mask[y]
        for x in range(w):
            if not row[x] or vis[y, x]:
                continue
            q: deque[tuple[int, int]] = deque([(y, x)])
            vis[y, x] = True
            cells: list[tuple[int, int]] = []
            while q:
                cy, cx = q.popleft()
                cells.append((cy, cx))
                for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not vis[ny, nx]:
                        vis[ny, nx] = True
                        q.append((ny, nx))
            area = float(len(cells))
            if area < 40:
                continue
            xs = [c[1] for c in cells]
            mean_x = sum(xs) / area
            in_center = sum(1 for xx in xs if cx0 <= xx < cx1) / area
            score = area * (1.35 if (prefer_center and in_center > 0.45) else 1.0)
            # Prefer the blob sitting in this cell, not a limb peeking from the side.
            score -= abs(mean_x - w / 2) * 0.35
            if score > best_score:
                best_score = score
                best = cells
    if not best:
        return mask
    out = np.zeros_like(mask)
    for y, x in best:
        out[y, x] = True
    return out


def finalize_cell_mask(seed_cell: np.ndarray) -> np.ndarray:
    grown = close_mask(dilate(seed_cell, 2), 3)
    grown = fill_holes(grown) | seed_cell
    return largest_cc(grown)


def crop_cell(rgba, seed, y0, y1, x0, x1, pad=40):
    y0, x0 = max(0, y0), max(0, x0)
    y1, x1 = min(seed.shape[0], y1), min(seed.shape[1], x1)
    cell_seed = seed[y0:y1, x0:x1]
    if cell_seed.sum() < 60:
        return None
    fg = finalize_cell_mask(cell_seed)
    if fg.sum() < 60:
        return None
    ys, xs = np.where(fg)
    sy0, sy1 = int(ys.min()), int(ys.max()) + 1
    sx0, sx1 = int(xs.min()), int(xs.max()) + 1
    h, w = sy1 - sy0, sx1 - sx0
    canvas = np.zeros((h + 2 * pad, w + 2 * pad, 4), dtype=np.uint8)
    piece = rgba[y0 + sy0 : y0 + sy1, x0 + sx0 : x0 + sx1].copy()
    piece_m = fg[sy0:sy1, sx0:sx1]
    r, g, b = piece[..., 0], piece[..., 1], piece[..., 2]
    mx = np.maximum(np.maximum(r, g), b)
    chroma = mx.astype(np.int16) - np.minimum(np.minimum(r, g), b)
    fx = piece_m & (chroma > 22) & (mx > 40)
    body = piece_m & ~fx
    out = np.zeros_like(piece)
    out[body, :3] = piece[body, :3]
    out[body, 3] = 255
    # soft glow: scale alpha by chroma so purple FX bleeds without a black box
    if fx.any():
        out[fx, :3] = piece[fx, :3]
        glow = np.clip(chroma[fx].astype(np.int16) * 3 + mx[fx].astype(np.int16) // 2, 90, 255)
        out[fx, 3] = glow.astype(np.uint8)
    canvas[pad : pad + h, pad : pad + w] = out
    return canvas, (x0 + sx0, y0 + sy0, x0 + sx1, y0 + sy1)


def feet_to_crown(canvas, ox, oy):
    """Idle body height: feet (oy) → crown of head, skipping hair tip.

    Skin at the temples/forehead is the crown lock. Drink-pose outliers
    (head tipped back) should be excluded by the caller. Fallback uses the
    specialist hair/body ratio 249/212 on opaque-from-feet height.
    """
    a = canvas[..., 3]
    r, g, b = canvas[..., 0], canvas[..., 1], canvas[..., 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    chroma = mx.astype(np.int16) - mn
    skin = (
        (a > 80)
        & (r > 68)
        & (g > 28)
        & (b < r)
        & (g < (r * 0.98).astype(np.uint8))
        & (chroma >= 8)
    )
    if skin.sum() >= 24:
        ys, xs = np.where(skin)
        # prefer skin near the torso column so a stray cup highlight is ignored
        near = np.abs(xs.astype(np.int32) - int(ox)) < max(28, canvas.shape[1] // 3)
        if near.any():
            crown = int(ys[near].min())
        else:
            crown = int(ys.min())
        h = int(oy) - crown
        if 40 <= h <= 400:
            return h
    ys, xs = np.where(a > 80)
    if len(ys) == 0:
        return None
    opaque = int(oy) - int(ys.min())
    return int(round(opaque / CINO_HAIR_TO_CROWN))


def body_foot(canvas):
    a = canvas[..., 3]
    r, g, b = canvas[..., 0], canvas[..., 1], canvas[..., 2]
    chroma = np.maximum(np.maximum(r, g), b).astype(np.int16) - np.minimum(np.minimum(r, g), b)
    fx = (b > 90) & (r > 40) & (g < (b * 0.85).astype(np.uint8)) & (chroma > 28)
    green = (g > 100) & (g > r + 20)
    body = (a > 80) & ~fx & ~green
    if body.sum() < 40:
        body = a > 80
    ys, xs = np.where(body)
    if len(ys) == 0:
        return canvas.shape[1] // 2, canvas.shape[0] - 8
    foot_y = int(ys.max())
    band = (ys >= foot_y - 14) & (ys <= foot_y)
    ox = int(xs[band].mean()) if band.any() else int(xs.mean())
    return ox, foot_y + 1


def scale_canvas(canvas, scale, ox, oy):
    im = Image.fromarray(canvas, "RGBA")
    nw = max(8, int(round(im.width * scale)))
    nh = max(8, int(round(im.height * scale)))
    im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    return np.array(im), int(round(ox * scale)), int(round(oy * scale))


def pack_cell(rgba, seed, y0, y1, x0, x1, pad):
    got = crop_cell(rgba, seed, y0, y1, x0, x1, pad=pad)
    if got is None:
        return None
    canvas, box = got
    bh, bw = canvas.shape[0] - 2 * pad, canvas.shape[1] - 2 * pad
    if bh < 88 or bw < 18:
        return None
    ox, oy = body_foot(canvas)
    return {
        "canvas": canvas,
        "ox": ox,
        "oy": oy,
        "box": box,
        "h": canvas.shape[0],
        "w": canvas.shape[1],
        "pad": pad,
    }


def strip_origin_dots(rgba: np.ndarray) -> np.ndarray:
    """Contact-preview yellow feet dots are not gameplay pixels."""
    out = rgba.copy()
    r, g, b, a = out[..., 0], out[..., 1], out[..., 2], out[..., 3]
    yellow = (r > 180) & (g > 150) & (b < 90) & (a > 40)
    if yellow.any() and yellow.mean() < 0.02:
        out[yellow, 3] = 0
    return out


def jpeg_to_rgba1536(path: Path) -> np.ndarray:
    rgb = np.array(Image.open(path).convert("RGB").resize((1536, 1024), Image.Resampling.LANCZOS))
    bg = border_canvas(rgb)
    seed = chromatic_seed(rgb) | (~bg & (rgb.max(axis=2) > 18))
    a = np.where(seed | ~bg, 255, 0).astype(np.uint8)
    return np.dstack([rgb, a])


def load_sheet1_rgba() -> tuple[np.ndarray, str]:
    """Prefer the 1536×1024 RGBA master; otherwise scale the JPEG master."""
    for p in SHEET1_PNG_CANDIDATES:
        if not p.exists():
            continue
        im = Image.open(p).convert("RGBA")
        if im.size != (1536, 1024):
            im = im.resize((1536, 1024), Image.Resampling.LANCZOS)
        arr = strip_origin_dots(np.array(im))
        a0 = float((arr[..., 3] == 0).mean())
        print(f"sheet1 PNG {p} alpha0={a0:.3f}")
        dest = ROOT / "mugen-facing/cino-v2/sheets/01-human-basic-movement.png"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if p.resolve() != dest.resolve():
            Image.fromarray(arr, "RGBA").save(dest)
        return arr, str(p)
    jpg = SHEETS["move"]
    print(f"sheet1 PNG missing — building 1536 RGBA from {jpg.name}")
    arr = strip_origin_dots(jpeg_to_rgba1536(jpg))
    dest = ROOT / "mugen-facing/cino-v2/sheets/01-human-basic-movement.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr, "RGBA").save(dest)
    public = ROOT / "public/mugen/assets/01-human-basic-movement.png"
    Image.fromarray(arr, "RGBA").save(public)
    return arr, f"jpeg→1536:{jpg}"


def row_windows(spec: dict, width: int) -> list[tuple[int, int]]:
    n, x0, w = spec["n"], spec["x0"], spec["w"]
    if n <= 1:
        return [(x0, min(width, x0 + w))]
    span = max(w, width - x0)
    step = (span - w) / max(1, n - 1)
    out = []
    for i in range(n):
        a = int(round(x0 + i * step))
        b = min(width, a + w)
        out.append((max(0, a), b))
    return out


def extract_sheet1():
    """Slice Human movement from 1536×1024 Sheet1 (RGBA or JPEG-upscaled)."""
    rgba, src = load_sheet1_rgba()
    print("  sheet1 source", src, "size", rgba.shape[1], "x", rgba.shape[0])
    seed = rgba[..., 3] > 12
    cells = []
    order = ["idle", "walk", "run", "bot"]
    for name in order:
        spec = SHEET1_SPEC[name]
        y0, y1, pad = spec["y0"], spec["y1"], spec["pad"]
        xs = row_windows(spec, rgba.shape[1])
        xocc = seed[y0:y1].mean(axis=0)
        spans = n_spans(xocc, spec["n"], min_sep=max(40, spec["w"] // 3))
        if name != "run" and len(spans) == spec["n"]:
            xs = [(max(0, a - 4), min(rgba.shape[1], b + 4)) for a, b in spans]
        row_cells = []
        for x0, x1 in xs:
            packed = pack_cell(rgba, seed, y0, y1, x0, x1, pad)
            if packed:
                row_cells.append(packed)
        cells.append(row_cells)
        print(
            f"  move  {name:5s} n={len(row_cells)} expect={spec['n']} "
            f"H={[c['h']-2*c['pad'] for c in row_cells]}"
        )
    return cells


def extract_sheet(key: str, min_col_sep=70):
    path = SHEETS[key]
    rgb = np.array(Image.open(path).convert("RGB"))
    bg = border_canvas(rgb)
    seed = chromatic_seed(rgb) | (~bg & (rgb.max(axis=2) > 18))
    rgba = np.dstack([rgb, np.where(~bg, 255, 0).astype(np.uint8)])
    occ = dilate(seed, 1)
    cells = []
    for ri, (y0, y1, expect, pad) in enumerate(ROWS[key]):
        xocc = occ[y0:y1].mean(axis=0)
        spans = n_spans(xocc, expect, min_sep=min_col_sep)
        row_cells = []
        for x0, x1 in spans:
            packed = pack_cell(rgba, seed, y0, y1, x0 - 8, x1 + 8, pad)
            if packed:
                row_cells.append(packed)
        cells.append(row_cells)
        print(f"  {key:5s} row{ri} n={len(row_cells)} expect={expect} H={[c['h']-2*c['pad'] for c in row_cells]}")
    return cells


def write_sheet1_aliases(atlas, extract_scale):
    """s1_001–037 aliases + anim_map for the specialist box contract."""
    frames_dir = SHEET1_DIR / "frames"
    if frames_dir.exists():
        for p in frames_dir.glob("s1_*.png"):
            p.unlink()
    frames_dir.mkdir(parents=True, exist_ok=True)
    n = 1
    clips = {}
    compact = {"CINO_BASE_HEIGHT": CINO_BASE_HEIGHT, "clips": {}}
    atlas_s1 = {
        "id": "cino-sheet1",
        "CINO_BASE_HEIGHT": CINO_BASE_HEIGHT,
        "anims": {},
    }
    engine_ms = {
        "idle": 100,
        "walk": 80,
        "run": 60,
        "crouch": 50,
        "jumpStart": 50,
        "jumpLoop": 70,
        "jumpLand": 55,
    }
    engine_loop = {
        "idle": True,
        "walk": True,
        "run": True,
        "crouch": False,
        "jumpStart": False,
        "jumpLoop": True,
        "jumpLand": False,
    }
    for anim, count, clip in SHEET1_CLIP_FILES:
        entries = (atlas.get("anims") or {}).get(anim) or []
        ids = []
        s1_frames = []
        for i in range(min(count, len(entries))):
            src = ROOT / "public" / entries[i]["file"].split("?")[0].lstrip("/")
            sid = f"s1_{n:03d}"
            name = f"{sid}_{clip}.png"
            if src.exists():
                shutil.copy(src, frames_dir / name)
            ids.append(sid)
            s1_frames.append(
                {
                    "id": sid,
                    "file": f"frames/{name}",
                    "clip": clip,
                    "engineAnim": anim,
                    "i": i,
                    "ox": entries[i]["ox"],
                    "oy": entries[i]["oy"],
                    "w": entries[i]["w"],
                    "h": entries[i]["h"],
                    "gameplay": entries[i]["file"].split("?")[0],
                }
            )
            n += 1
        clips[clip] = {
            "engineAnim": anim,
            "count": len(ids),
            "loop": engine_loop[anim],
            "holdLast": clip == "CROUCH",
            "ms": engine_ms[anim],
            "ids": ids,
            "frames": s1_frames,
        }
        compact["clips"][clip] = {
            "engineAnim": anim,
            "count": len(ids),
            "loop": engine_loop[anim],
            "holdLast": clip == "CROUCH",
            "ms": engine_ms[anim],
            "ids": ids,
        }
        atlas_s1["anims"][anim] = s1_frames
    anim_map = {
        "CINO_BASE_HEIGHT": CINO_BASE_HEIGHT,
        "source": "public/mugen/assets/cino-sheet1-movement.jpg",
        "scaleLock": SCALE_ALIGN_LOCK,
        "extractScale": extract_scale,
        "clips": clips,
    }
    (SHEET1_DIR / "anim_map.json").write_text(json.dumps(anim_map, indent=2))
    (SHEET1_DIR / "anim_map_compact.json").write_text(json.dumps(compact, indent=2))
    (SHEET1_DIR / "atlas.json").write_text(json.dumps(atlas_s1, indent=2))
    print("sheet1 aliases", n - 1, "→", frames_dir)


def save_png(arr, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr, "RGBA").save(dest, format="PNG")


def contact(named, dest: Path, cols=10):
    thumbs, labels = [], []
    for name, frames in named.items():
        for i, fr in enumerate(frames):
            thumbs.append(fr)
            labels.append(f"{name}_{i:02d}")
    if not thumbs:
        return
    tw, th = 120, 140
    cols = min(cols, max(1, len(thumbs)))
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * tw, rows * (th + 16)), (0, 0, 0, 0))
    bg = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    px = bg.load()
    for y in range(0, sheet.size[1], 8):
        for x in range(0, sheet.size[0], 8):
            c = (210, 40, 180, 255) if ((x // 8) + (y // 8)) % 2 == 0 else (40, 10, 40, 255)
            for yy in range(y, min(y + 8, sheet.size[1])):
                for xx in range(x, min(x + 8, sheet.size[0])):
                    px[xx, yy] = c
    sheet = bg
    dr = ImageDraw.Draw(sheet)
    for i, (fr, lab) in enumerate(zip(thumbs, labels)):
        im = Image.fromarray(fr["canvas"], "RGBA")
        im.thumbnail((tw - 6, th - 8))
        r, c = divmod(i, cols)
        x = c * tw + (tw - im.width) // 2
        y = r * (th + 16)
        sheet.paste(im, (x, y), im)
        dr.text((c * tw + 2, y + im.height), lab[:18], fill=(160, 255, 120, 255))
    dest.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dest)
    print("qc", dest)


def take(row, n=None):
    row = list(row or [])
    return row[:n] if n else row


def main():
    QC.mkdir(parents=True, exist_ok=True)
    print("extracting Cino v2 six-sheet mapping from JPEG masters...")
    move = extract_sheet1()
    atk = extract_sheet("atk", min_col_sep=72)
    b1 = extract_sheet("bull1", min_col_sep=78)
    b2 = extract_sheet("bull2", min_col_sep=78)

    idle_row = list(move[0] if move else [])
    # Scale Align: lock on s1_001–005 (indices 0–4). NEVER s1_010 drink pose (index 9, 221).
    lock_src = [c for i, c in enumerate(idle_row) if i < 5] or idle_row[:1]
    body_heights = []
    opaque_heights = []
    for c in lock_src:
        a = c["canvas"][..., 3]
        ys = np.where(a > 80)[0]
        if len(ys):
            opaque_heights.append(int(c["oy"]) - int(ys.min()))
        bh = feet_to_crown(c["canvas"], c["ox"], c["oy"])
        if bh:
            body_heights.append(bh)
    idle_body = float(np.median(body_heights)) if body_heights else 200.0
    idle_opaque = float(np.median(opaque_heights)) if opaque_heights else idle_body * CINO_HAIR_TO_CROWN
    scale = CINO_ATLAS_BODY_HEIGHT / idle_body
    print(
        f"CINO_BASE_HEIGHT={CINO_BASE_HEIGHT} atlas_body={CINO_ATLAS_BODY_HEIGHT:.1f} "
        f"native_body={idle_body:.1f} native_opaque(hair)={idle_opaque:.1f} scale={scale:.4f}"
    )

    def brow(sheet, i):
        return sheet[i] if sheet and len(sheet) > i else []

    idle = take(move[0])
    walk = take(move[1])
    run = take(move[2])
    jump = take(move[3])

    anims = {
        "idle": idle,
        "walk": walk,
        "run": run,
        "dash": run,
        "backdash": list(reversed(run)),
    }
    # Sheet1 anim map: CROUCH 2 hold-last | JUMP_START 1 | JUMP_AIR 3 | JUMP_LAND 3
    if len(jump) >= 9:
        anims["crouch"] = jump[:2]
        anims["crouchWalk"] = jump[:2]
        anims["jumpStart"] = jump[2:3]
        anims["jumpLoop"] = jump[3:6]
        anims["jumpLand"] = jump[6:9]
    elif len(jump) >= 8:
        anims["crouch"] = jump[:2]
        anims["crouchWalk"] = jump[:2]
        anims["jumpStart"] = jump[2:3]
        anims["jumpLoop"] = jump[3:6]
        anims["jumpLand"] = jump[5:]
    elif jump:
        anims["crouch"] = jump[:2] or jump
        anims["crouchWalk"] = jump[:2] or jump
        anims["jumpStart"] = jump[:1] or jump
        anims["jumpLoop"] = jump[1:4] or jump
        anims["jumpLand"] = jump[-3:] or jump

    punch = take(brow(atk, 0))
    kick = take(brow(atk, 1))
    splash = take(brow(atk, 2))
    beam = take(brow(atk, 3))
    aura = take(brow(atk, 4))
    dashatk = take(brow(atk, 5))

    anims["lightJab"] = punch[:5] or punch or idle[:3]
    anims["heavySwing"] = punch or idle[:4]
    anims["kick"] = kick[:6] or kick or punch
    anims["airAttack"] = kick[2:6] or kick or punch
    anims["leanSplash"] = splash[:4] or splash or punch
    anims["fxSplash"] = splash[3:] or splash
    anims["uppercut"] = (kick[:3] + beam[:5]) if beam else kick
    anims["fxBeam"] = beam[3:] or beam
    anims["candleRush"] = dashatk[:5] or dashatk or run
    anims["chartBreaker"] = (aura[:2] + beam[-3:] + splash[-2:]) if beam else aura
    anims["fxCrystal"] = aura[4:] or aura
    anims["bullCharge"] = dashatk[3:] or dashatk
    anims["fxBullHead"] = dashatk[4:] or dashatk
    anims["pillStorm"] = splash or beam
    anims["shadowClones"] = punch[:4] + punch[:4] if punch else idle[:4]
    anims["taunt"] = aura[:4] or idle[:4]
    anims["overdrive"] = (aura + dashatk[-3:]) if aura else punch
    anims["fxSuper"] = aura[3:] or aura

    xform = take(brow(b2, 0)) or take(brow(b1, 0))
    anims["bullForm"] = xform
    if not anims["overdrive"]:
        anims["overdrive"] = xform

    anims["bullIdle"] = take(brow(b2, 1)) or take(brow(b1, 1))
    anims["bullWalk"] = take(brow(b1, 2)) or take(brow(b2, 2))
    anims["bullRun"] = take(brow(b2, 2)) or take(brow(b1, 2))
    bj = take(brow(b1, 2)) or take(brow(b2, 2))
    # row2 is movement: walk + run-charge + jump mixed; prefer bull2 row 3 for jump
    bjump = take(brow(b2, 3)) or take(brow(b1, 3))
    if bjump:
        if len(bjump) >= 6:
            anims["bullJumpStart"] = bjump[:2]
            anims["bullJump"] = bjump[2:5]
            anims["bullLand"] = bjump[5:] or bjump[-2:]
        else:
            anims["bullJumpStart"] = bjump[:1]
            anims["bullJump"] = bjump
            anims["bullLand"] = bjump[-1:]
    anims["bullAttack"] = take(brow(b1, 3)) or take(brow(b2, 3))
    anims["bullSlash"] = take(brow(b2, 4)) or take(brow(b1, 4))
    anims["bullSpecial"] = take(brow(b1, 4)) or take(brow(b2, 5))
    anims["bullSuper"] = take(brow(b2, 5)) or take(brow(b1, 4))
    hurt = take(brow(b1, 5)) or take(brow(b2, 5))
    rec = take(brow(b1, 6)) or take(brow(b2, 6))
    if hurt:
        anims["bullHit"] = hurt[:3] or hurt
        anims["bullKnockdown"] = hurt[3:6] or hurt[-3:] or hurt
    else:
        anims["bullHit"] = anims.get("bullIdle", idle)[:2]
        anims["bullKnockdown"] = anims.get("bullIdle", idle)[:2]
    anims["bullGetUp"] = rec[:4] or rec or anims.get("bullIdle", idle)[:3]
    anims["bullWin"] = rec[-4:] or rec or anims.get("bullIdle", idle)[:3]
    anims["block"] = anims.get("crouch") or idle[:2]
    anims["hit"] = idle[-2:] if idle else []
    anims["knockdown"] = anims.get("jumpLand") or idle[:2]
    anims["getUp"] = (anims.get("jumpLand") or idle)[:3]
    anims["win"] = aura[-3:] or idle[:3]

    # drop empty
    anims = {k: v for k, v in anims.items() if v}

    print("\nANIM COUNTS")
    for k, v in anims.items():
        print(f"  {k:16s} {len(v)}")

    if OUT.exists():
        for p in OUT.glob("*.png"):
            p.unlink()
    OUT.mkdir(parents=True, exist_ok=True)

    atlas = {
        "id": "cino",
        "anims": {},
        "version": CACHE_V,
        "scale": {
            "CINO_BASE_HEIGHT": CINO_BASE_HEIGHT,
            "CINO_BASE_SCALE": CINO_BASE_SCALE,
            "CINO_SPRITE_ZOOM": CINO_SPRITE_ZOOM,
            "CINO_ATLAS_BODY_HEIGHT": CINO_ATLAS_BODY_HEIGHT,
            "CINO_BULL_SCALE": CINO_BULL_SCALE,
            "CINO_FX_SCALE": CINO_FX_SCALE,
            "goldCriteria": GOLD_CRITERIA,
            "scaleAlign": SCALE_ALIGN_LOCK,
            "nativeJpegLockBodyPx": idle_body,
            "extractScale": scale,
        },
    }
    CHAR_ANIMS = {
        "idle",
        "walk",
        "run",
        "dash",
        "backdash",
        "crouch",
        "crouchWalk",
        "jumpStart",
        "jumpLoop",
        "jumpLand",
        "lightJab",
        "heavySwing",
        "kick",
        "airAttack",
        "block",
        "hit",
        "knockdown",
        "getUp",
        "taunt",
        "win",
        "leanSplash",
        "uppercut",
        "candleRush",
        "chartBreaker",
        "bullCharge",
        "pillStorm",
        "shadowClones",
        "overdrive",
    }
    BULL_ANIMS = {
        "bullForm",
        "bullIdle",
        "bullWalk",
        "bullRun",
        "bullJumpStart",
        "bullJump",
        "bullLand",
        "bullAttack",
        "bullSlash",
        "bullSpecial",
        "bullSuper",
        "bullHit",
        "bullKnockdown",
        "bullGetUp",
        "bullWin",
    }
    scaled = {}
    for name, frames in anims.items():
        if name in BULL_ANIMS:
            use = scale * CINO_BULL_SCALE
        elif name.startswith("fx"):
            use = scale * CINO_FX_SCALE
        else:
            use = scale
        entries, qc = [], []
        for i, fr in enumerate(frames):
            canvas, ox, oy = scale_canvas(fr["canvas"], use, fr["ox"], fr["oy"])
            fn = f"{name}_{i:02d}.png"
            save_png(canvas, OUT / fn)
            h, w = canvas.shape[:2]
            entries.append(
                {
                    "file": f"/mugen/frames/cino/{fn}?v={CACHE_V}",
                    "i": i,
                    "ox": int(ox),
                    "oy": int(oy),
                    "w": int(w),
                    "h": int(h),
                }
            )
            qc.append({"canvas": canvas})
        atlas["anims"][name] = entries
        scaled[name] = qc
    ATLAS.write_text(json.dumps(atlas, indent=2))
    SCALE_META.write_text(
        json.dumps(
            {
                "CINO_BASE_HEIGHT": CINO_BASE_HEIGHT,
                "CINO_BASE_SCALE": CINO_BASE_SCALE,
                "meaning": "Human Cino idle feet/ground → crown of head (NOT hair tip). Roster BASE SCALE 100%. Future fighters normalize idle body height against this.",
                "CINO_SPRITE_ZOOM": CINO_SPRITE_ZOOM,
                "CINO_ATLAS_BODY_HEIGHT": CINO_ATLAS_BODY_HEIGHT,
                "CINO_BULL_SCALE": CINO_BULL_SCALE,
                "CINO_FX_SCALE": CINO_FX_SCALE,
                "goldCriteria": GOLD_CRITERIA,
                "scaleAlign": SCALE_ALIGN_LOCK,
                "nativeJpegLockBodyPx": idle_body,
                "nativeOpaqueWithHairPx": idle_opaque,
                "extractScale": scale,
                "clips": {
                    "IDLE": {"frames": "idle_00–10", "count": 11, "loop": True, "ms": 100},
                    "WALK": {"frames": "walk_00–08", "count": 9, "loop": True, "ms": 80},
                    "RUN": {"frames": "run_00–07", "count": 8, "loop": True, "ms": 60},
                    "CROUCH": {"frames": "crouch_00–01", "count": 2, "holdLast": True, "ms": 50},
                    "JUMP_START": {"frames": "jumpStart_00", "count": 1, "ms": 50},
                    "JUMP_AIR": {"frames": "jumpLoop_00–02", "count": 3, "loop": True, "ms": 70},
                    "JUMP_LAND": {"frames": "jumpLand_00–02", "count": 3, "ms": 55},
                },
                "note": "Engine drawFighter uses 2× zoom; atlas body height is CINO_BASE_HEIGHT/2 so on-canvas feet→crown = 212. nativeJpegLockBodyPx is this VM's JPEG idle 0–4 median — not the s1_010 drink-pose 221.",
            },
            indent=2,
        )
    )
    lock_doc = {
        "CINO_BASE_HEIGHT": CINO_BASE_HEIGHT,
        "CINO_BASE_SCALE": CINO_BASE_SCALE,
        "locked": True,
        **SCALE_ALIGN_LOCK,
        "meaning": "Human Cino idle feet/ground → head crown (NOT hair tip). Roster BASE SCALE 100% for all future side-by-sides.",
        "oneScaleAcrossHumanAnims": True,
        "preserveAspect": True,
        "neverStretch": True,
        "vfxScaleIndependent": True,
        "bullPlayableSizedNotGiant": True,
        "inRepoCopy": "/mugen/atlas/human-cino-base-scale.json",
        "note": "Specialist extract dir may be absent. Constant is Scale Align 212. Engine paints atlas at 2× so atlas body = 106 → 212 on canvas.",
    }
    BASE_SCALE_JSON.parent.mkdir(parents=True, exist_ok=True)
    BASE_SCALE_JSON.write_text(json.dumps(lock_doc, indent=2))
    SPECIALIST_SCALE_JSON.parent.mkdir(parents=True, exist_ok=True)
    SPECIALIST_SCALE_JSON.write_text(json.dumps(lock_doc, indent=2))
    print("wrote", ATLAS, "and", SCALE_META, "and", BASE_SCALE_JSON)
    run_frames = atlas["anims"].get("run") or []
    if run_frames:
        ratios = [fr["ox"] / max(1, fr["w"]) for fr in run_frames]
        med = float(np.median(ratios))
        for i, fr in enumerate(run_frames):
            ratio = fr["ox"] / max(1, fr["w"])
            if ratio > 0.72 or ratio < 0.28:
                fr["ox"] = int(round(med * fr["w"]))
                print(f"  adjusted run_{i:02d} origin_x → {fr['ox']} (was {ratio:.2f}, median {med:.2f})")
        ATLAS.write_text(json.dumps(atlas, indent=2))
    if (OUT / "idle_00.png").exists():
        Image.open(OUT / "idle_00.png").save(ROOT / "public/mugen/portraits/cino.png")

    contact(
        {
            k: scaled[k]
            for k in [
                "idle",
                "walk",
                "run",
                "crouch",
                "jumpStart",
                "jumpLoop",
                "jumpLand",
                "lightJab",
                "kick",
                "leanSplash",
                "heavySwing",
                "candleRush",
                "bullCharge",
                "uppercut",
                "pillStorm",
            ]
            if scaled.get(k)
        },
        QC / "human.png",
    )
    contact(
        {
            k: scaled[k]
            for k in [
                "bullForm",
                "bullIdle",
                "bullWalk",
                "bullRun",
                "bullJump",
                "bullLand",
                "bullAttack",
                "bullSlash",
                "bullSpecial",
                "bullSuper",
                "bullHit",
                "bullGetUp",
            ]
            if scaled.get(k)
        },
        QC / "bull.png",
        cols=8,
    )
    dest = ROOT / "public/mugen/assets"
    dest.mkdir(parents=True, exist_ok=True)
    named = {
        "move": "cino-sheet1-movement.jpg",
        "atk": "cino-sheet2-combat.jpg",
        "bull1": "cino-sheet3-bull-a.jpg",
        "bull2": "cino-sheet3-bull-b.jpg",
    }
    for k, name in named.items():
        shutil.copy(SHEETS[k], dest / name)
    facing = ROOT / "mugen-facing/cino-v2"
    facing.mkdir(parents=True, exist_ok=True)
    shutil.copy(SHEETS["move"], facing / "01-human-basic-movement.jpg")
    write_sheet1_aliases(atlas, scale)
    print("frames", len(list(OUT.glob("*.png"))))


MOVEMENT_ANIMS = (
    "idle",
    "walk",
    "run",
    "dash",
    "backdash",
    "crouch",
    "crouchWalk",
    "jumpStart",
    "jumpLoop",
    "jumpLand",
    "block",
    "hit",
    "knockdown",
    "getUp",
)


def import_sheet1_only():
    """Replace Human movement frames only. Combat / Bull files stay as-is."""
    print("Sheet1 movement-only import (combat/Bull held)")
    move = extract_sheet1()
    idle = take(move[0])
    walk = take(move[1])
    run = take(move[2])
    jump = take(move[3])
    anims = {
        "idle": idle,
        "walk": walk,
        "run": run,
        "dash": run,
        "backdash": list(reversed(run)),
    }
    if len(jump) >= 9:
        anims["crouch"] = jump[:2]
        anims["crouchWalk"] = jump[:2]
        anims["jumpStart"] = jump[2:3]
        anims["jumpLoop"] = jump[3:6]
        anims["jumpLand"] = jump[6:9]
    else:
        anims["crouch"] = jump[:2] or jump
        anims["crouchWalk"] = jump[:2] or jump
        anims["jumpStart"] = jump[:1] or jump
        anims["jumpLoop"] = jump[1:4] or jump
        anims["jumpLand"] = jump[-3:] or jump
    anims["block"] = anims.get("crouch") or idle[:2]
    anims["hit"] = idle[-2:] if idle else []
    anims["knockdown"] = anims.get("jumpLand") or idle[:2]
    anims["getUp"] = (anims.get("jumpLand") or idle)[:3]

    lock_src = [c for i, c in enumerate(idle) if i < 5] or idle[:1]
    body_heights = []
    for c in lock_src:
        bh = feet_to_crown(c["canvas"], c["ox"], c["oy"])
        if bh:
            body_heights.append(bh)
    idle_body = float(np.median(body_heights)) if body_heights else 200.0
    scale = CINO_ATLAS_BODY_HEIGHT / idle_body
    print(
        f"CINO_BASE_HEIGHT={CINO_BASE_HEIGHT} native_body={idle_body:.1f} scale={scale:.4f}"
    )

    atlas = json.loads(ATLAS.read_text()) if ATLAS.exists() else {"id": "cino", "anims": {}}
    atlas["version"] = CACHE_V
    atlas.setdefault("scale", {})
    atlas["scale"].update(
        {
            "CINO_BASE_HEIGHT": CINO_BASE_HEIGHT,
            "CINO_BASE_SCALE": CINO_BASE_SCALE,
            "CINO_SPRITE_ZOOM": CINO_SPRITE_ZOOM,
            "CINO_ATLAS_BODY_HEIGHT": CINO_ATLAS_BODY_HEIGHT,
            "extractScale": scale,
            "nativeJpegLockBodyPx": idle_body,
            "sheet1Source": "1536x1024",
        }
    )
    scaled = {}
    for name in MOVEMENT_ANIMS:
        frames = anims.get(name) or []
        if not frames:
            continue
        entries, qc = [], []
        for i, fr in enumerate(frames):
            canvas, ox, oy = scale_canvas(fr["canvas"], scale, fr["ox"], fr["oy"])
            fn = f"{name}_{i:02d}.png"
            save_png(canvas, OUT / fn)
            h, w = canvas.shape[:2]
            entries.append(
                {
                    "file": f"/mugen/frames/cino/{fn}?v={CACHE_V}",
                    "i": i,
                    "ox": int(ox),
                    "oy": int(oy),
                    "w": int(w),
                    "h": int(h),
                }
            )
            qc.append({"canvas": canvas})
        atlas["anims"][name] = entries
        scaled[name] = qc
        print(f"  wrote {name} {len(entries)}")
    run_frames = atlas["anims"].get("run") or []
    if run_frames:
        for i, fr in enumerate(run_frames):
            ratio = fr["ox"] / max(1, fr["w"])
            if ratio > 0.72 or ratio < 0.32:
                fr["ox"] = int(round(0.45 * fr["w"]))
                print(f"  adjusted run_{i:02d} origin_x → {fr['ox']} (was {ratio:.2f})")
    # Bump cache on leftover combat/bull files so HMR doesn't mix six3/six4.
    for name, frames in atlas["anims"].items():
        if name in MOVEMENT_ANIMS:
            continue
        for fr in frames:
            fr["file"] = fr["file"].split("?")[0] + f"?v={CACHE_V}"
    ATLAS.write_text(json.dumps(atlas, indent=2))
    write_sheet1_aliases(atlas, scale)
    contact(
        {k: scaled[k] for k in ["idle", "walk", "run", "crouch", "jumpStart", "jumpLoop", "jumpLand"] if scaled.get(k)},
        SHEET1_DIR / "preview-contact.png",
        cols=11,
    )
    for clip, key in (("IDLE", "idle"), ("WALK", "walk"), ("RUN", "run")):
        if scaled.get(key):
            contact({key: scaled[key]}, SHEET1_DIR / f"preview-row-{clip}.png", cols=len(scaled[key]))
    if (OUT / "idle_00.png").exists():
        Image.open(OUT / "idle_00.png").save(ROOT / "public/mugen/portraits/cino.png")
    print("sheet1 movement import done")


if __name__ == "__main__":
    import sys

    if "--sheet1-only" in sys.argv:
        import_sheet1_only()
    else:
        main()
