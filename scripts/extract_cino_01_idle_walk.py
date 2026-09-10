#!/usr/bin/env python3
"""CINO_01_IDLE_WALK — frames 1-3 idle, 4-7 walk. JPEG: border-flood only."""
from collections import deque
from pathlib import Path
import json
import shutil
import numpy as np
from PIL import Image

SRC = Path("/workspace/attachments/7469DAEF-9E0A-4C23-8B9A-4618211D1D82.jpg")
ROOT = Path("/workspace/public/mugen")
OUT = ROOT / "frames/cino"
ASSET = ROOT / "assets/CINO_01_IDLE_WALK.jpg"
ASSET.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(SRC, ASSET)

rgb = np.array(Image.open(SRC).convert("RGB"))
H, W = rgb.shape[:2]
N = 7
TARGET_BODY = 119  # match current in-game Cino idle body
PAD_SRC = 20

def flood_cell(tile, thr=14):
    h, w = tile.shape[:2]
    mag = np.linalg.norm(tile.astype(np.float32), axis=2)
    bg = mag < thr
    seen = np.zeros((h, w), bool)
    q = deque()
    for x in range(w):
        if bg[0, x]:
            q.append((0, x))
        if bg[h - 1, x]:
            q.append((h - 1, x))
    for y in range(h):
        if bg[y, 0]:
            q.append((y, 0))
        if bg[y, w - 1]:
            q.append((y, w - 1))
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
    a = np.where(ext, 0, 255).astype(np.uint8)
    return np.dstack([tile, a])

# exclusive equal-width cells, then union-crop with padding (NOT tight per-part)
cells = []
for i in range(N):
    x0 = int(round(i * W / N))
    x1 = int(round((i + 1) * W / N))
    arr = flood_cell(rgb[:, x0:x1])
    vis = arr[..., 3] > 40
    ys, xs = np.where(vis)
    if not vis.any():
        raise SystemExit(f"empty cell {i}")
    y0, y1 = max(0, ys.min() - PAD_SRC), min(H, ys.max() + 1 + PAD_SRC)
    xx0, xx1 = max(0, xs.min() - PAD_SRC), min(arr.shape[1], xs.max() + 1 + PAD_SRC)
    crop = arr[y0:y1, xx0:xx1]
    cells.append({"i": i, "arr": crop, "foot": int(ys.max() - y0), "cx": int((xs.min() + xs.max()) // 2 - xx0),
                  "body": int(ys.max() - ys.min() + 1)})
    print(f"cell{i} body={cells[-1]['body']} crop={crop.shape[1]}x{crop.shape[0]}")

scale = TARGET_BODY / max(c["body"] for c in cells)
print("scale", scale)

def scale_rgba(arr, s):
    im = Image.fromarray(arr, "RGBA")
    nw = max(1, int(round(arr.shape[1] * s)))
    nh = max(1, int(round(arr.shape[0] * s)))
    out = np.array(im.resize((nw, nh), Image.Resampling.LANCZOS))
    # JPEG has no true alpha; keep Cino solid, bg gone
    out[..., 3] = np.where(out[..., 3] >= 32, 255, 0).astype(np.uint8)
    return out

scaled = []
for c in cells:
    arr = scale_rgba(c["arr"], scale)
    vis = arr[..., 3] > 40
    ys, xs = np.where(vis)
    scaled.append({
        "arr": arr,
        "crown": int(ys.min()),
        "foot": int(ys.max()),
        "cx": int((xs.min() + xs.max()) // 2),
        "body": int(ys.max() - ys.min() + 1),
    })

PAD = 12
max_up = max(s["foot"] - s["crown"] for s in scaled)
max_left = max(s["cx"] for s in scaled)
max_right = max(s["arr"].shape[1] - s["cx"] for s in scaled)
cw = int(max_left + max_right + 2 * PAD)
ch = int(max_up + 8 + 2 * PAD)
ox = int(max_left + PAD)
oy = int(max_up + PAD)
print(f"canvas {cw}x{ch} ox,oy={ox},{oy} bodies={[s['body'] for s in scaled]}")

packed = []
for s in scaled:
    canvas = np.zeros((ch, cw, 4), np.uint8)
    x = ox - s["cx"]
    y = oy - s["foot"]
    sh, sw = s["arr"].shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(cw, x + sw), min(ch, y + sh)
    canvas[y0:y1, x0:x1] = s["arr"][y0 - y : y0 - y + (y1 - y0), x0 - x : x0 - x + (x1 - x0)]
    packed.append(canvas)

def write(name, frames):
    recs = []
    for i, arr in enumerate(frames):
        fn = OUT / f"{name}_{i:02d}.png"
        Image.fromarray(arr, "RGBA").save(fn)
        recs.append({"file": f"/mugen/frames/cino/{name}_{i:02d}.png?v=g1", "i": i, "ox": ox, "oy": oy, "w": cw, "h": ch})
    return recs

idle = write("idle", packed[:3])
walk = write("walk", packed[3:])

atlas = json.loads((ROOT / "atlas/cino.json").read_text())
atlas["anims"]["idle"] = idle
atlas["anims"]["walk"] = walk
# keep backwalk as mirrored walk if it previously aliased walk files
if "backwalk" in atlas["anims"]:
    atlas["anims"]["backwalk"] = [
        {**f, "file": f["file"]} for f in reversed(walk)
    ]
(ROOT / "atlas/cino.json").write_text(json.dumps(atlas, indent=2))
print("idle", len(idle), "walk", len(walk))

# contact for QA
from PIL import Image as I
th = 160
ims = [I.fromarray(p).resize((max(1, int(p.shape[1] * th / p.shape[0])), th)) for p in packed]
sheet = I.new("RGBA", (sum(i.width for i in ims) + 4 * len(ims), th + 8), (12, 0, 18, 255))
x = 2
for im in ims:
    sheet.paste(im, (x, 4), im)
    x += im.width + 4
sheet.save("/tmp/qa_cino01.png")
print("qa /tmp/qa_cino01.png")
