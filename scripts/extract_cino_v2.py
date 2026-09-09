#!/usr/bin/env python3
"""Cino v2 sprite extract.

Transparency protocol:
  1. Inspect the source PNG/JPEG alpha channel FIRST.
  2. If background pixels already have alpha==0, use that alpha directly.
     Do NOT run a black-color mask on those files.
  3. Only if the file is flattened (JPEG / opaque RGB) do we remove the
     canvas — and ONLY as connected background from the sheet BORDER
     through smooth, low-chroma canvas pixels.
  4. Never globally delete black. Cino's dreads, hoodie, outlines, shadows
     and the bull's black body are legitimate artwork.
  5. Purple FX, gold chains, horns, skin, eyes are always kept.
  6. Split merged frames with occupancy-valley cuts (long hair overlaps).
  7. Crop on occupied-pixel bounds + transparent padding.
"""
from __future__ import annotations

import json
import shutil
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

SHEETS = {
    "move": Path("/workspace/attachments/C227318F-9357-4F72-9DFB-4F9D5CD9037B.jpg"),
    "atk": Path("/workspace/attachments/3A6BCF2F-E0AB-4F73-B189-2173705317F4.jpg"),
    "bull1": Path("/workspace/attachments/B9D32065-41A2-4A62-8E5B-D8005A9EBD5C.jpg"),
    "bull2": Path("/workspace/attachments/C4EA0BF6-68BE-436C-8DD3-57FBC2A981A1.jpg"),
}
ROWS = {
    "move": [(32, 290), (305, 550), (565, 770), (775, 998)],
    "atk": [(8, 192), (192, 388), (388, 538), (528, 668), (660, 852), (848, 998)],
    "bull1": [(4, 180), (180, 348), (348, 478), (478, 632), (622, 775), (770, 875), (868, 998)],
    "bull2": [(4, 185), (180, 332), (328, 455), (448, 620), (615, 748), (742, 885), (880, 998)],
}
OUT = Path("/workspace/public/mugen/frames/cino")
ATLAS = Path("/workspace/public/mugen/atlas/cino.json")
QC = Path("/tmp/cino_v2_qc")
PAD = 40
TARGET_IDLE_H = 118
ALPHA_KEEP = 8  # source pixels with alpha > this are already artwork


def inspect_alpha(path: Path) -> dict:
    im = Image.open(path)
    arr = np.array(im.convert("RGBA"))
    a = arr[..., 3]
    tot = a.size
    z = int((a == 0).sum())
    full = int((a == 255).sum())
    corners = [tuple(int(v) for v in arr[y, x]) for (y, x) in (
        (0, 0), (0, -1), (-1, 0), (-1, -1)
    )]
    usable = z / tot >= 0.08 and np.mean([c[3] for c in corners]) < 12
    print(
        f"ALPHA {path.name}: mode={im.mode} fmt={im.format} "
        f"zero={100*z/tot:.1f}% full={100*full/tot:.1f}% "
        f"corners={corners} usable_alpha={usable}"
    )
    return {"usable": usable, "rgba": arr, "mode": im.mode, "format": im.format}


def chromatic_seed(rgb: np.ndarray) -> np.ndarray:
    """Artwork seeds: color / lights / FX. NOT 'is darker than black'."""
    r = rgb[..., 0].astype(np.int16)
    g = rgb[..., 1].astype(np.int16)
    b = rgb[..., 2].astype(np.int16)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    chroma = mx - mn
    purple = (b > 70) & (r > 30) & (g < b * 0.85) & (chroma >= 10)
    gold = (r > 100) & (g > 55) & (r > b + 18) & (chroma >= 12)
    skin = (r > 72) & (g > 32) & (b < r) & (g < r * 0.98) & (chroma >= 10)
    white = mx >= 165
    red = (r > 90) & (r > g + 25) & (r > b + 15)
    # mid-bright textured clothing (hoodie highlights, sneaker) — still not flat black
    lit = (mx >= 38) & (chroma >= 8)
    return (purple | gold | skin | white | red | lit | (chroma >= 16))


def dilate(mask: np.ndarray, n: int = 1) -> np.ndarray:
    out = mask.copy()
    h, w = mask.shape
    for _ in range(n):
        up = np.empty_like(out); up[0] = False; up[1:] = out[:-1]
        dn = np.empty_like(out); dn[-1] = False; dn[:-1] = out[1:]
        lf = np.empty_like(out); lf[:, 0] = False; lf[:, 1:] = out[:, :-1]
        rt = np.empty_like(out); rt[:, -1] = False; rt[:, :-1] = out[:, 1:]
        out = out | up | dn | lf | rt
    return out


def erode(mask: np.ndarray, n: int = 1) -> np.ndarray:
    return ~dilate(~mask, n)


def close_mask(mask: np.ndarray, n: int = 2) -> np.ndarray:
    return erode(dilate(mask, n), n)


def fill_holes(mask: np.ndarray) -> np.ndarray:
    """Keep enclosed interior (black hoodie / bull body). Border-connected empty stays empty."""
    h, w = mask.shape
    inv = ~mask
    vis = np.zeros_like(mask)
    q: deque[tuple[int, int]] = deque()
    for x in range(w):
        if inv[0, x] and not vis[0, x]:
            vis[0, x] = True; q.append((0, x))
        if inv[h - 1, x] and not vis[h - 1, x]:
            vis[h - 1, x] = True; q.append((h - 1, x))
    for y in range(h):
        if inv[y, 0] and not vis[y, 0]:
            vis[y, 0] = True; q.append((y, 0))
        if inv[y, w - 1] and not vis[y, w - 1]:
            vis[y, w - 1] = True; q.append((y, w - 1))
    while q:
        y, x = q.popleft()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not vis[ny, nx] and inv[ny, nx]:
                vis[ny, nx] = True
                q.append((ny, nx))
    return mask | (inv & ~vis)


def border_smooth_bg(rgb: np.ndarray) -> np.ndarray:
    """Canvas only: smooth near-black, low-chroma, reachable from the sheet border."""
    r = rgb[..., 0].astype(np.int16)
    g = rgb[..., 1].astype(np.int16)
    b = rgb[..., 2].astype(np.int16)
    mx = np.maximum(np.maximum(r, g), b)
    chroma = mx - np.minimum(np.minimum(r, g), b)
    canvas = (mx <= 10) & (chroma <= 6)
    h, w = canvas.shape
    vis = np.zeros_like(canvas)
    q: deque[tuple[int, int]] = deque()
    for x in range(w):
        if canvas[0, x]:
            vis[0, x] = True; q.append((0, x))
        if canvas[h - 1, x]:
            vis[h - 1, x] = True; q.append((h - 1, x))
    for y in range(h):
        if canvas[y, 0]:
            vis[y, 0] = True; q.append((y, 0))
        if canvas[y, w - 1]:
            vis[y, w - 1] = True; q.append((y, w - 1))
    while q:
        y, x = q.popleft()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not vis[ny, nx] and canvas[ny, nx]:
                vis[ny, nx] = True
                q.append((ny, nx))
    return vis


def occupancy_mask(rgb: np.ndarray, rgba: np.ndarray | None, use_alpha: bool) -> np.ndarray:
    if use_alpha and rgba is not None:
        return rgba[..., 3] > ALPHA_KEEP
    seed = chromatic_seed(rgb)
    # hair occupancy: grow seeds a little so dreads register as occupied columns
    return dilate(seed, 2)


def valley_spans(occ, min_sep, valley_max, peak_min):
    sm = np.convolve(occ, np.ones(9) / 9, mode="same")
    n = len(sm)
    peaks = []
    for x in range(2, n - 2):
        if sm[x] >= sm[x - 1] and sm[x] >= sm[x + 1] and sm[x] >= peak_min:
            if not peaks or x - peaks[-1] >= min_sep:
                peaks.append(x)
            elif sm[x] > sm[peaks[-1]]:
                peaks[-1] = x
    if len(peaks) < 2:
        on = sm > peak_min * 0.4
        out, i = [], 0
        while i < n:
            if not on[i]:
                i += 1
                continue
            j = i
            while j < n and on[j]:
                j += 1
            if j - i >= 16:
                out.append((i, j))
            i = j
        return out
    cuts = [0]
    for i in range(len(peaks) - 1):
        a, b = peaks[i], peaks[i + 1]
        split = a + int(np.argmin(sm[a : b + 1]))
        if sm[split] <= valley_max or sm[split] < 0.5 * max(sm[a], sm[b]):
            cuts.append(split)
    cuts.append(n)
    cuts = sorted(set(int(c) for c in cuts))
    spans = []
    for i in range(len(cuts) - 1):
        a, b = cuts[i], cuts[i + 1]
        while a < b and sm[a] < peak_min * 0.22:
            a += 1
        while b > a and sm[b - 1] < peak_min * 0.22:
            b -= 1
        if b - a >= 18 and sm[a:b].max() >= peak_min:
            spans.append((a, b))
    return spans


def merge_small_spans(spans, row_mask, frac=0.28):
    if len(spans) < 2:
        return spans
    areas = [int(row_mask[:, a:b].sum()) for a, b in spans]
    large = sorted(areas, reverse=True)[: max(3, len(areas) // 2)]
    med = float(np.median(large)) if large else 1
    out = []
    buf = None
    for (a, b), area in zip(spans, areas):
        if area < frac * med:
            if out:
                pa, pb = out[-1]
                out[-1] = (pa, max(pb, b))
            else:
                buf = (a, b)
            continue
        if buf is not None:
            a = min(a, buf[0])
            buf = None
        out.append((a, b))
    return out or spans


def finalize_cell_mask(seed_cell: np.ndarray) -> np.ndarray:
    """Per-sprite: keep FX seeds + fill enclosed black interiors. No global black cut."""
    grown = close_mask(dilate(seed_cell, 2), 3)
    filled = fill_holes(grown)
    return filled | seed_cell


def crop_cell(rgba, seed, y0, y1, x0, x1, pad=PAD):
    y0, x0 = max(0, y0), max(0, x0)
    y1, x1 = min(seed.shape[0], y1), min(seed.shape[1], x1)
    cell_seed = seed[y0:y1, x0:x1]
    if cell_seed.sum() < 80:
        return None
    fg = finalize_cell_mask(cell_seed)
    if fg.sum() < 80:
        return None
    ys, xs = np.where(fg)
    sy0, sy1 = int(ys.min()), int(ys.max()) + 1
    sx0, sx1 = int(xs.min()), int(xs.max()) + 1
    h, w = sy1 - sy0, sx1 - sx0
    canvas = np.zeros((h + 2 * pad, w + 2 * pad, 4), dtype=np.uint8)
    piece = rgba[y0 + sy0 : y0 + sy1, x0 + sx0 : x0 + sx1].copy()
    piece_m = fg[sy0:sy1, sx0:sx1]
    # Keep original RGB (including black hair/clothes/bull). Only clear true background.
    piece[~piece_m, 0] = 0
    piece[~piece_m, 1] = 0
    piece[~piece_m, 2] = 0
    piece[~piece_m, 3] = 0
    # If source already had alpha, keep the smaller of source-alpha and mask.
    src_a = piece[:, :, 3]
    piece[piece_m, 3] = np.maximum(src_a[piece_m], 255)
    piece[piece_m, 3] = 255
    canvas[pad : pad + h, pad : pad + w] = piece
    return canvas, (x0 + sx0, y0 + sy0, x0 + sx1, y0 + sy1)


def is_human_body(canvas) -> bool:
    r, g, b, a = canvas[..., 0], canvas[..., 1], canvas[..., 2], canvas[..., 3]
    vis = a > 40
    if vis.sum() < 400:
        return False
    skin = vis & (r > 70) & (g > 32) & (b < r) & (g < r * 0.95)
    bh = canvas.shape[0] - 2 * PAD
    bw = canvas.shape[1] - 2 * PAD
    if skin.sum() >= 60:
        return True
    if bh >= 90 and bh > bw * 0.85 and vis.sum() >= 1800:
        return True
    return False


def is_bull_body(canvas) -> bool:
    r, g, b, a = canvas[..., 0], canvas[..., 1], canvas[..., 2], canvas[..., 3]
    vis = a > 40
    if vis.sum() < 500:
        return False
    gold = vis & (r > 110) & (g > 70) & (b < 90) & (r > g)
    purple = vis & (b > 80) & (r > 40) & (g < b * 0.8)
    bh = canvas.shape[0] - 2 * PAD
    bw = canvas.shape[1] - 2 * PAD
    if gold.sum() >= 40:
        return True
    if bh >= 70 and vis.sum() >= 1600:
        return True
    if bw < 50 and bh < 80:
        return False
    return purple.sum() > 80 and vis.sum() > 900


def body_foot(canvas):
    a = canvas[..., 3]
    r, g, b = canvas[..., 0], canvas[..., 1], canvas[..., 2]
    chroma = np.maximum(np.maximum(r, g), b).astype(np.int16) - np.minimum(np.minimum(r, g), b)
    fx = (b > 90) & (r > 40) & (g < (b * 0.85).astype(np.uint8)) & (chroma > 28)
    body = (a > 40) & ~fx
    if body.sum() < 40:
        body = a > 40
    ys, xs = np.where(body)
    if len(ys) == 0:
        return canvas.shape[1] // 2, canvas.shape[0] - PAD
    foot_y = int(ys.max())
    band = (ys >= foot_y - 12) & (ys <= foot_y)
    ox = int(xs[band].mean()) if band.any() else int(xs.mean())
    return ox, foot_y + 1


def scale_canvas(canvas, scale, ox, oy):
    im = Image.fromarray(canvas, "RGBA")
    nw = max(8, int(round(im.width * scale)))
    nh = max(8, int(round(im.height * scale)))
    im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    return np.array(im), int(round(ox * scale)), int(round(oy * scale))


def load_sheet(path: Path):
    info = inspect_alpha(path)
    rgba = info["rgba"]
    rgb = rgba[..., :3]
    if info["usable"]:
        print(f"  -> using ORIGINAL alpha (no black mask) for {path.name}")
        seed = rgba[..., 3] > ALPHA_KEEP
        # Preserve original alpha in output
        return rgb, rgba, seed, True
    print(f"  -> flattened file, connected-canvas removal only (no global black cut) for {path.name}")
    seed = chromatic_seed(rgb)
    bg = border_smooth_bg(rgb)
    # Occupancy for splitting: chromatic seeds. Background black is NOT occupancy.
    # Character interiors get filled later per-cell so hoodie/bull body survive.
    out_rgba = np.dstack([rgb, np.where(~bg, 255, 0).astype(np.uint8)])
    return rgb, out_rgba, seed, False


def extract_sheet(key: str, kind: str, min_col_sep=80):
    path = SHEETS[key]
    rgb, rgba, seed, used_alpha = load_sheet(path)
    occ = occupancy_mask(rgb, rgba, used_alpha)
    cells = []
    for ri, (y0, y1) in enumerate(ROWS[key]):
        xocc = occ[y0:y1].mean(axis=0)
        spans = valley_spans(xocc, min_sep=min_col_sep, valley_max=0.18, peak_min=0.08)
        spans = merge_small_spans(spans, occ[y0:y1], frac=0.30)
        row_cells = []
        for x0, x1 in spans:
            got = crop_cell(rgba, seed, y0, y1, x0 - 12, x1 + 12)
            if got is None:
                continue
            canvas, box = got
            if canvas.shape[0] - 2 * PAD < 36 or canvas.shape[1] - 2 * PAD < 14:
                continue
            if kind == "human" and not is_human_body(canvas):
                continue
            if kind == "bull" and not is_bull_body(canvas):
                continue
            ox, oy = body_foot(canvas)
            row_cells.append(
                {"canvas": canvas, "ox": ox, "oy": oy, "box": box, "h": canvas.shape[0], "w": canvas.shape[1]}
            )
        if len(row_cells) >= 3:
            hs = np.array([c["h"] - 2 * PAD for c in row_cells], dtype=float)
            areas = np.array([int((c["canvas"][..., 3] > 40).sum()) for c in row_cells], dtype=float)
            med_h, med_a = float(np.median(hs)), float(np.median(areas))
            row_cells = [
                c
                for c, h, a in zip(row_cells, hs, areas)
                if h >= 0.62 * med_h and a >= 0.42 * med_a
            ]
        cells.append(row_cells)
        print(f"  {key:5s} row{ri} n={len(row_cells)} H={[c['h']-2*PAD for c in row_cells]}")
    return cells


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
    # magenta checker so leftover canvas / holes are obvious
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
    print("extracting with alpha-first protocol...")
    move = extract_sheet("move", "human", min_col_sep=115)
    atk = extract_sheet("atk", "human", min_col_sep=95)
    b1 = extract_sheet("bull1", "bull", min_col_sep=100)
    b2 = extract_sheet("bull2", "bull", min_col_sep=100)

    idle_native = [c["canvas"].shape[0] - 2 * PAD for c in (move[0] if move else [])]
    idle_h = float(np.median(idle_native)) if idle_native else 200
    scale = TARGET_IDLE_H / idle_h
    print(f"idle native h={idle_h:.1f} n={len(idle_native)} scale={scale:.3f}")

    anims = {
        "idle": take(move[0]),
        "walk": take(move[1]),
        "run": take(move[2]),
    }
    jump = take(move[3])
    if len(jump) >= 6:
        anims["jumpStart"] = jump[:2]
        anims["jumpLoop"] = jump[2:5]
        anims["jumpLand"] = jump[5:]
        anims["crouch"] = jump[-2:]
        anims["crouchWalk"] = jump[-2:]
    elif jump:
        anims["jumpStart"] = jump[:1]
        anims["jumpLoop"] = jump[1:] or jump[:1]
        anims["jumpLand"] = jump[-1:]
        anims["crouch"] = jump[-1:]
        anims["crouchWalk"] = jump[-1:]

    anims["lightJab"] = take(atk[0])
    anims["kick"] = take(atk[1]) if len(atk) > 1 else take(atk[0])
    anims["leanSplash"] = take(atk[2]) if len(atk) > 2 else take(atk[0])[:3]
    if len(atk) > 3:
        anims["candleRush"] = take(atk[3])
    if len(atk) > 4:
        anims["heavySwing"] = take(atk[4])
        anims["uppercut"] = take(atk[4])
    if len(atk) > 5:
        sl = take(atk[5])
        anims["chartBreaker"] = sl[:4] or sl
        anims["airAttack"] = sl[:3] or sl

    xform = take(b2[0]) or take(b1[0])
    anims["overdrive"] = xform
    anims["bullForm"] = xform

    def brow(sheet, i):
        return sheet[i] if sheet and len(sheet) > i else []

    anims["bullIdle"] = take(brow(b2, 1)) or take(brow(b1, 1))
    anims["bullWalk"] = take(brow(b1, 2)) or take(brow(b2, 1))
    anims["bullRun"] = take(brow(b2, 2)) or take(brow(b1, 2))
    bj = take(brow(b2, 3)) or take(brow(b1, 3))
    if bj:
        if len(bj) >= 5:
            anims["bullJumpStart"] = bj[:2]
            anims["bullJump"] = bj[2:5]
            anims["bullLand"] = bj[5:] or bj[-2:]
        else:
            anims["bullJumpStart"] = bj[:1]
            anims["bullJump"] = bj
            anims["bullLand"] = bj[-1:]
    anims["bullAttack"] = take(brow(b1, 3)) or take(brow(b2, 4))
    anims["bullSlash"] = take(brow(b2, 4)) or take(brow(b1, 3))
    anims["bullSpecial"] = take(brow(b1, 4)) or take(brow(b2, 5))
    anims["bullSuper"] = take(brow(b2, 5)) or take(brow(b1, 4))
    hurt = take(brow(b2, 6)) or take(brow(b1, 6))
    if hurt:
        anims["bullHit"] = hurt[:3] or hurt
        anims["bullKnockdown"] = hurt[3:6] or hurt[-3:]
        anims["bullGetUp"] = hurt[-3:]

    anims["block"] = anims.get("crouch") or anims["idle"][:2]
    anims["hit"] = anims["idle"][-2:] if anims["idle"] else []
    anims["knockdown"] = anims.get("jumpLand") or anims["idle"][:2]
    anims["getUp"] = (anims.get("jumpLand") or anims["idle"])[:3]
    anims["taunt"] = anims["idle"][:4]
    anims["dash"] = anims.get("run") or []
    anims["backdash"] = list(reversed(anims.get("run") or []))

    print("\nANIM COUNTS")
    for k, v in anims.items():
        print(f"  {k:16s} {len(v)}")

    if OUT.exists():
        for p in OUT.glob("*.png"):
            p.unlink()
    OUT.mkdir(parents=True, exist_ok=True)

    atlas = {"id": "cino", "anims": {}}
    scaled = {}
    for name, frames in anims.items():
        entries, qc = [], []
        for i, fr in enumerate(frames):
            canvas, ox, oy = scale_canvas(fr["canvas"], scale, fr["ox"], fr["oy"])
            fn = f"{name}_{i:02d}.png"
            save_png(canvas, OUT / fn)
            h, w = canvas.shape[:2]
            entries.append(
                {"file": f"/mugen/frames/cino/{fn}", "i": i, "ox": int(ox), "oy": int(oy), "w": int(w), "h": int(h)}
            )
            qc.append({"canvas": canvas})
        atlas["anims"][name] = entries
        scaled[name] = qc
    ATLAS.write_text(json.dumps(atlas, indent=2))
    print("wrote", ATLAS)
    if (OUT / "idle_00.png").exists():
        Image.open(OUT / "idle_00.png").save("/workspace/public/mugen/portraits/cino.png")

    contact(
        {k: scaled[k] for k in ["idle", "walk", "run", "jumpStart", "jumpLoop", "jumpLand", "lightJab", "kick", "leanSplash", "heavySwing", "candleRush"] if scaled.get(k)},
        QC / "human.png",
    )
    contact(
        {k: scaled[k] for k in ["overdrive", "bullIdle", "bullWalk", "bullRun", "bullJump", "bullLand", "bullAttack", "bullSlash", "bullSpecial", "bullSuper"] if scaled.get(k)},
        QC / "bull.png",
        cols=8,
    )

    dest = Path("/workspace/public/mugen/assets")
    dest.mkdir(parents=True, exist_ok=True)
    for k, p in SHEETS.items():
        shutil.copy(p, dest / f"cino-v2-{k}.jpg")
    print("frames", len(list(OUT.glob("*.png"))))


if __name__ == "__main__":
    main()
