#!/usr/bin/env python3
"""CINO_03_SPECIAL — 4 body frames: Startup, Windup, Release, Recovery. No VFX."""
from collections import deque
from pathlib import Path
import json, shutil
import numpy as np
from PIL import Image
from scipy import ndimage

SRC = Path("/workspace/attachments/AA4A174A-8CBF-4686-A144-9587533657BF.jpg")
ROOT = Path("/workspace/public/mugen")
OUT = ROOT / "frames/cino"
ASSET = ROOT / "assets/CINO_03_SPECIAL.jpg"
shutil.copy2(SRC, ASSET)

rgb = np.array(Image.open(SRC).convert("RGB"))
H, W = rgb.shape[:2]
N = 4
TARGET_BODY = 119
PAD_SRC = 22

def flood_keep_blob(tile, thr=14):
    h, w = tile.shape[:2]
    mag = np.linalg.norm(tile.astype(np.float32), axis=2)
    bg = mag < thr
    seen = np.zeros((h, w), bool)
    q = deque()
    for x in range(w):
        if bg[0, x]: q.append((0, x))
        if bg[h - 1, x]: q.append((h - 1, x))
    for y in range(h):
        if bg[y, 0]: q.append((y, 0))
        if bg[y, w - 1]: q.append((y, w - 1))
    ext = np.zeros((h, w), bool)
    while q:
        y, x = q.popleft()
        if y < 0 or y >= h or x < 0 or x >= w or seen[y, x]:
            continue
        seen[y, x] = True
        if not bg[y, x]:
            continue
        ext[y, x] = True
        q.extend(((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)))
    alpha = np.where(ext, 0, 255).astype(np.uint8)
    lab, n = ndimage.label(alpha > 40)
    if n:
        sizes = ndimage.sum(alpha > 40, lab, range(1, n + 1))
        bid = 1 + int(np.argmax(sizes))
        ys, xs = np.where(lab == bid)
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        keep = lab == bid
        for i in range(1, n + 1):
            if i == bid:
                continue
            y2, x2 = np.where(lab == i)
            if y2.min() >= y0 - 28 and y2.max() <= y1 + 14 and x2.min() >= x0 - 20 and x2.max() <= x1 + 20:
                keep = keep | (lab == i)
        alpha = np.where(keep, 255, 0).astype(np.uint8)
    return np.dstack([tile, alpha])

cells = []
for i in range(N):
    x0 = int(round(i * W / N))
    x1 = int(round((i + 1) * W / N))
    arr = flood_keep_blob(rgb[:, x0:x1])
    vis = arr[..., 3] > 40
    ys, xs = np.where(vis)
    y0 = max(0, int(ys.min()) - PAD_SRC)
    y1 = min(arr.shape[0], int(ys.max()) + 1 + PAD_SRC)
    xx0 = max(0, int(xs.min()) - PAD_SRC)
    xx1 = min(arr.shape[1], int(xs.max()) + 1 + PAD_SRC)
    crop = arr[y0:y1, xx0:xx1]
    cells.append({
        "arr": crop,
        "foot_src": int(ys.max()),
        "body": int(ys.max() - ys.min() + 1),
        "cx": int((xs.min() + xs.max()) // 2 - xx0),
    })
    print(f"cell{i} body={cells[-1]['body']} foot={ys.max()} crop={crop.shape[1]}x{crop.shape[0]}")

# standing-ish: use max body (windup/release) but scale so largest pose ~ current Cino
scale = TARGET_BODY / max(c["body"] for c in cells[:3])  # recovery crouch is shorter
print("scale", scale)

def scale_rgba(arr, s):
    im = Image.fromarray(arr, "RGBA")
    nw = max(1, int(round(arr.shape[1] * s)))
    nh = max(1, int(round(arr.shape[0] * s)))
    out = np.array(im.resize((nw, nh), Image.Resampling.LANCZOS))
    out[..., 3] = np.where(out[..., 3] >= 32, 255, 0).astype(np.uint8)
    return out

ground = max(c["foot_src"] for c in cells)
scaled = []
for i, c in enumerate(cells):
    arr = scale_rgba(c["arr"], scale)
    vis = arr[..., 3] > 40
    ys, xs = np.where(vis)
    scaled.append({
        "arr": arr,
        "crown": int(ys.min()),
        "foot": int(ys.max()),
        "cx": int((xs.min() + xs.max()) // 2),
        "air": max(0, int(round((ground - c["foot_src"]) * scale))),
        "body": int(ys.max() - ys.min() + 1),
    })
    print(f"  scaled{i} body={scaled[-1]['body']}")

PAD = 14
max_up = max(s["foot"] - s["crown"] + s["air"] for s in scaled)
max_left = max(s["cx"] for s in scaled)
max_right = max(s["arr"].shape[1] - s["cx"] for s in scaled)
cw = int(max_left + max_right + 2 * PAD)
ch = int(max_up + 8 + 2 * PAD)
ox = int(max_left + PAD)
oy = int(max_up + PAD)
print(f"canvas {cw}x{ch} ox,oy={ox},{oy}")

packed = []
for s in scaled:
    canvas = np.zeros((ch, cw, 4), np.uint8)
    x = ox - s["cx"]
    y = oy - s["foot"] - s["air"]
    sh, sw = s["arr"].shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(cw, x + sw), min(ch, y + sh)
    if x1 > x0 and y1 > y0:
        canvas[y0:y1, x0:x1] = s["arr"][y0 - y: y0 - y + (y1 - y0), x0 - x: x0 - x + (x1 - x0)]
    packed.append(canvas)

recs = []
for i, arr in enumerate(packed):
    Image.fromarray(arr, "RGBA").save(OUT / f"heavySwing_{i:02d}.png")
    recs.append({"file": f"/mugen/frames/cino/heavySwing_{i:02d}.png?v=g3", "i": i, "ox": ox, "oy": oy, "w": cw, "h": ch})

atlas = json.loads((ROOT / "atlas/cino.json").read_text())
atlas["anims"]["heavySwing"] = recs
(ROOT / "atlas/cino.json").write_text(json.dumps(atlas, indent=2))

th = 150
ims = [Image.fromarray(p).resize((max(1, int(p.shape[1] * th / p.shape[0])), th)) for p in packed]
sheet = Image.new("RGBA", (sum(i.width for i in ims) + 6 * len(ims), th + 8), (12, 0, 18, 255))
x = 3
for im in ims:
    sheet.paste(im, (x, 4), im)
    x += im.width + 6
sheet.save("/tmp/qa_cino03.png")
print("heavySwing n", len(recs))
