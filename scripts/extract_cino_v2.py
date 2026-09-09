#!/usr/bin/env python3
"""Extract NEW Cino. Fixed row bands, X valleys, merge stray FX, drop cup-only cells."""
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
PAD = 32
TARGET_IDLE_H = 118


def fg_mask(rgb: np.ndarray) -> np.ndarray:
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    chroma = mx - mn
    seed = (mx >= 28) | (chroma >= 14)
    growable = (mx >= 7) | (chroma >= 10)
    h, w = seed.shape
    vis = np.zeros((h, w), dtype=bool)
    q = deque()
    ys, xs = np.where(seed)
    for y, x in zip(ys.tolist(), xs.tolist()):
        vis[y, x] = True
        q.append((y, x))
    while q:
        y, x = q.popleft()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not vis[ny, nx] and growable[ny, nx]:
                vis[ny, nx] = True
                q.append((ny, nx))
    return vis


def valley_spans(occ, min_sep, valley_max, peak_min):
    sm = np.convolve(occ, np.ones(9) / 9, mode="same")
    n = len(sm)
    peaks = []
    for x in range(2, n - 2):
        if sm[x] >= sm[x - 1] and sm[x] >= sm[x + 1] and sm[x] >= peak_min:
            if not peaks or x - peaks[-1] >= min_sep * 0.5:
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
    buf_area = 0
    for (a, b), area in zip(spans, areas):
        if area < frac * med:
            if out:
                # merge into previous
                pa, pb = out[-1]
                out[-1] = (pa, max(pb, b))
            else:
                buf = (a, b)
                buf_area = area
            continue
        if buf is not None:
            a = min(a, buf[0])
            buf = None
        out.append((a, b))
    return out or spans


def crop_cell(rgba, mask, y0, y1, x0, x1, pad=PAD):
    y0, x0 = max(0, y0), max(0, x0)
    y1, x1 = min(mask.shape[0], y1), min(mask.shape[1], x1)
    sub = mask[y0:y1, x0:x1]
    if sub.sum() < 80:
        return None
    ys, xs = np.where(sub)
    sy0, sy1 = y0 + int(ys.min()), y0 + int(ys.max()) + 1
    sx0, sx1 = x0 + int(xs.min()), x0 + int(xs.max()) + 1
    h, w = sy1 - sy0, sx1 - sx0
    canvas = np.zeros((h + 2 * pad, w + 2 * pad, 4), dtype=np.uint8)
    piece = rgba[sy0:sy1, sx0:sx1].copy()
    piece_m = mask[sy0:sy1, sx0:sx1]
    piece[~piece_m] = 0
    piece[piece_m, 3] = 255
    canvas[pad : pad + h, pad : pad + w] = piece
    return canvas, (sx0, sy0, sx1, sy1)


def is_human_body(canvas) -> bool:
    """True if this looks like Cino (skin / hoodie / shoes), not a lone cup/slash."""
    r, g, b, a = canvas[..., 0], canvas[..., 1], canvas[..., 2], canvas[..., 3]
    vis = a > 40
    if vis.sum() < 400:
        return False
    skin = vis & (r > 70) & (g > 32) & (b < r) & (g < r * 0.95)
    white = vis & (r > 180) & (g > 180) & (b > 180)
    # zipper / cup can be white; require skin OR a tall body
    bh = canvas.shape[0] - 2 * PAD
    bw = canvas.shape[1] - 2 * PAD
    if skin.sum() >= 60:
        return True
    # standing silhouette, not a wide splash
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
    # lone horn
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


def extract_sheet(key: str, kind: str, min_col_sep=80):
    path = SHEETS[key]
    rgb = np.array(Image.open(path).convert("RGB"))
    mask = fg_mask(rgb)
    rgba = np.dstack([rgb, np.where(mask, 255, 0).astype(np.uint8)])
    cells = []
    for ri, (y0, y1) in enumerate(ROWS[key]):
        xocc = mask[y0:y1].mean(axis=0)
        spans = valley_spans(xocc, min_sep=min_col_sep, valley_max=0.18, peak_min=0.12)
        spans = merge_small_spans(spans, mask[y0:y1], frac=0.30)
        row_cells = []
        for x0, x1 in spans:
            got = crop_cell(rgba, mask, y0, y1, x0 - 10, x1 + 10)
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
            row_cells.append({"canvas": canvas, "ox": ox, "oy": oy, "box": box, "h": canvas.shape[0], "w": canvas.shape[1]})
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
    sheet = Image.new("RGBA", (cols * tw, rows * (th + 16)), (10, 10, 14, 255))
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
    print("extracting...")
    move = extract_sheet("move", "human", min_col_sep=90)
    atk = extract_sheet("atk", "human", min_col_sep=70)
    b1 = extract_sheet("bull1", "bull", min_col_sep=68)
    b2 = extract_sheet("bull2", "bull", min_col_sep=68)

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
            entries.append({"file": f"/mugen/frames/cino/{fn}", "i": i, "ox": int(ox), "oy": int(oy), "w": int(w), "h": int(h)})
            qc.append({"canvas": canvas})
        atlas["anims"][name] = entries
        scaled[name] = qc
    ATLAS.write_text(json.dumps(atlas, indent=2))
    print("wrote", ATLAS)
    if (OUT / "idle_00.png").exists():
        Image.open(OUT / "idle_00.png").save("/workspace/public/mugen/portraits/cino.png")

    contact({k: scaled[k] for k in ["idle", "walk", "run", "jumpStart", "jumpLoop", "jumpLand", "lightJab", "kick", "leanSplash", "heavySwing", "candleRush"] if scaled.get(k)}, QC / "human.png")
    contact({k: scaled[k] for k in ["overdrive", "bullIdle", "bullWalk", "bullRun", "bullJump", "bullLand", "bullAttack", "bullSlash", "bullSpecial", "bullSuper"] if scaled.get(k)}, QC / "bull.png", cols=8)

    dest = Path("/workspace/public/mugen/assets")
    dest.mkdir(parents=True, exist_ok=True)
    for k, p in SHEETS.items():
        shutil.copy(p, dest / f"cino-v2-{k}.jpg")
    print("frames", len(list(OUT.glob("*.png"))))


if __name__ == "__main__":
    main()
