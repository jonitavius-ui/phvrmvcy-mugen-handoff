#!/usr/bin/env python3
"""Slice approved Cino Human GOLD contact strips → RGBA frames + atlas anim update.
NO image generation. Expand-only pad. Fixed feet origin per clip.
Atlas body target: CINO_ATLAS_BODY_HEIGHT ≈ 106 (zoom 2 → 212 canvas).
redraw2: checkerboard→true alpha; ONE body scale from idle head (no per-frame ATLAS stretch).
"""
from __future__ import annotations
from collections import deque
from pathlib import Path
import json
import shutil
import numpy as np
from PIL import Image

PREVIEWS = Path("/workspace/mugen-redraw/cino-human/previews")
BODY_OUT = Path("/workspace/mugen-redraw/cino-human/body")
PUBLIC = Path("/workspace/mugen-ship/handoff-redraw/public/mugen")
FRAMES = PUBLIC / "frames/cino"
REDRAW = FRAMES / "redraw"
ATLAS_PATH = PUBLIC / "atlas/cino.json"
CACHE = "redraw2"
ATLAS_BODY = 106.0  # feet→crown in atlas px
PAD = 10
MIN_AREA = 800
BRIGHT_THR = 195  # mean RGB for bg candidates
FLOOD_DELTA = 42  # max |channel| delta from seed for bg flood

STRIPS = {
    "IDLE_GOLD.png": {
        "expect": 9,
        "clips": [("idle", 0, 9)],
    },
    "WALK_GOLD.png": {
        "expect": 8,
        "clips": [("walk", 0, 8)],
    },
    "RUN_GOLD.png": {
        "expect": 7,
        "clips": [("run", 0, 7)],
    },
    "CROUCH_JUMP_GOLD.png": {
        "expect": 9,
        # crouch: deep crouch pose (idx4) + a couple intermediates; jump air/land
        "clips": [
            ("crouch", 3, 5),       # deep crouch frames
            ("crouchWalk", 2, 4),
            ("jumpStart", 4, 5),    # deepest crouch as takeoff
            ("jumpLoop", 5, 7),     # air tucked frames
            ("jumpLand", 7, 9),     # land + recover (last may be stand)
        ],
    },
    "COMBAT_GOLD.png": {
        "expect": 14,  # 3+3+5+3
        "clips": [
            ("lightJab", 0, 3),
            ("heavySwing", 3, 6),
            ("kick", 6, 11),
            ("block", 11, 14),
        ],
    },
    "HURT_KD_GOLD.png": {
        "expect": 10,  # 3+3+4
        "clips": [
            ("hit", 0, 3),
            ("knockdown", 3, 6),
            ("getUp", 6, 10),
        ],
    },
    "SPECIALS_BODY_GOLD.png": {
        "expect": 8,
        "clips": [
            ("leanSplash", 0, 4),
            ("candleRush", 2, 7),
            ("uppercut", 0, 8),
            ("chartBreaker", 0, 7),
            ("overdrive", 0, 8),
            ("pillStorm", 0, 4),
            ("shadowClones", 2, 8),
            ("airAttack", 3, 6),
        ],
    },
}


def _chroma(f: np.ndarray) -> np.ndarray:
    return np.maximum(
        np.maximum(np.abs(f[..., 0] - f[..., 1]), np.abs(f[..., 1] - f[..., 2])),
        np.abs(f[..., 0] - f[..., 2]),
    )


def checker_mask(rgb: np.ndarray) -> np.ndarray:
    """Detect baked gray/white transparency-checker pixels (incl. interior gaps)."""
    f = rgb.astype(np.float32)
    mean = f.mean(axis=2)
    chroma = _chroma(f)
    gray = chroma <= 18
    # light gray / white checker range (clothing is much darker)
    light = gray & (mean >= 115) & (mean <= 255)
    h, w = mean.shape
    alt = np.zeros((h, w), bool)
    # alternating neighbor pairs (classic checker)
    pairs = [
        (light[:, :-1], light[:, 1:], mean[:, :-1], mean[:, 1:], (slice(None), slice(0, w - 1)), (slice(None), slice(1, w))),
        (light[:-1, :], light[1:, :], mean[:-1, :], mean[1:, :], (slice(0, h - 1), slice(None)), (slice(1, h), slice(None))),
        (light[:-1, :-1], light[1:, 1:], mean[:-1, :-1], mean[1:, 1:], (slice(0, h - 1), slice(0, w - 1)), (slice(1, h), slice(1, w))),
        (light[:-1, 1:], light[1:, :-1], mean[:-1, 1:], mean[1:, :-1], (slice(0, h - 1), slice(1, w)), (slice(1, h), slice(0, w - 1))),
    ]
    for m1, m2, mu1, mu2, sl1, sl2 in pairs:
        hit = m1 & m2 & (np.abs(mu1 - mu2) >= 18)
        alt[sl1] |= hit
        alt[sl2] |= hit
    # near-white solid checker cells
    near_white = gray & (mean >= 220)
    return light & (alt | near_white | (mean >= 150))


def remove_checkerboard_rgba(rgba: np.ndarray) -> np.ndarray:
    """Punch checkerboard + near-transparent fringe to true alpha=0."""
    out = rgba.copy()
    rgb = out[..., :3]
    a = out[..., 3]
    chk = checker_mask(rgb)
    mean = rgb.astype(np.float32).mean(axis=2)
    chroma = _chroma(rgb.astype(np.float32))
    gray = chroma <= 18
    # edge flood through checker / bright gray / existing alpha holes
    h, w = a.shape
    seed = np.zeros((h, w), bool)
    seed[0, :] = seed[-1, :] = seed[:, 0] = seed[:, -1] = True
    conduit = chk | (a == 0) | (gray & (mean >= 140)) | (mean >= 230)
    seen = np.zeros((h, w), bool)
    q = deque(zip(*np.where(seed & conduit)))
    # also start from any checker cell (interior gaps between legs)
    q.extend(zip(*np.where(chk)))
    kill = np.zeros((h, w), bool)
    while q:
        y, x = q.popleft()
        if seen[y, x]:
            continue
        seen[y, x] = True
        if not conduit[y, x] and not chk[y, x]:
            continue
        if chk[y, x] or (gray[y, x] and mean[y, x] >= 140 and a[y, x] > 0) or (
            mean[y, x] >= 230 and chroma[y, x] <= 20 and a[y, x] > 0
        ):
            kill[y, x] = True
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx]:
                if conduit[ny, nx] or chk[ny, nx]:
                    q.append((ny, nx))
    kill |= chk
    out[..., 3] = np.where(kill, 0, a)
    # near-transparent fringe adjacent to empty
    a2 = out[..., 3]
    trans = a2 == 0
    # 4-neighborhood dilate
    dil = trans.copy()
    dil[1:, :] |= trans[:-1, :]
    dil[:-1, :] |= trans[1:, :]
    dil[:, 1:] |= trans[:, :-1]
    dil[:, :-1] |= trans[:, 1:]
    fringe = dil & (a2 > 0) & ((a2 < 100) | (gray & (mean >= 100) & (a2 < 220)))
    out[..., 3] = np.where(fringe, 0, out[..., 3])
    out[..., 3] = np.where(out[..., 3] >= 40, 255, 0).astype(np.uint8)
    return out


def flood_light_bg(rgb: np.ndarray) -> np.ndarray:
    """Return RGBA with light edge-connected background + checkerboard keyed to alpha=0."""
    h, w = rgb.shape[:2]
    f = rgb.astype(np.float32)
    mean = f.mean(axis=2)
    chroma = _chroma(f)
    chk = checker_mask(rgb)
    # seeds: bright border pixels OR checkerboard
    bg_cand = (mean >= BRIGHT_THR) | chk
    seen = np.zeros((h, w), bool)
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if bg_cand[y, x]:
                q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if bg_cand[y, x]:
                q.append((y, x))
    # also seed interior checker so between-leg gaps key even if enclosed
    q.extend(zip(*np.where(chk)))
    ext = np.zeros((h, w), bool)
    while q:
        y, x = q.popleft()
        if y < 0 or y >= h or x < 0 or x >= w or seen[y, x]:
            continue
        seen[y, x] = True
        if chk[y, x]:
            ext[y, x] = True
            q.extend(((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)))
            continue
        # allow flood into near-seed bright / checker light cells
        if mean[y, x] < BRIGHT_THR - 35 and not (chroma[y, x] <= 18 and mean[y, x] >= 130):
            continue
        # reject dark character pixels
        if mean[y, x] < 150 and (f[y, x].max() - f[y, x].min()) > 30:
            continue
        if mean[y, x] < BRIGHT_THR and not (
            abs(float(f[y, x, 0]) - float(f[y, x, 1])) < 18
            and abs(float(f[y, x, 1]) - float(f[y, x, 2])) < 18
        ):
            # saturated color → keep as sprite
            if f[y, x].max() - f[y, x].min() > 35:
                continue
        ext[y, x] = True
        q.extend(((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)))
    a = np.where(ext | chk, 0, 255).astype(np.uint8)
    rgba = np.dstack([rgb, a])
    return remove_checkerboard_rgba(rgba)


def components(mask: np.ndarray, min_area: int = MIN_AREA):
    h, w = mask.shape
    seen = np.zeros_like(mask, bool)
    comps = []
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or seen[y, x]:
                continue
            q = deque([(y, x)])
            seen[y, x] = True
            cells = []
            while q:
                cy, cx = q.popleft()
                cells.append((cy, cx))
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
            if len(cells) < min_area:
                continue
            ys = [c[0] for c in cells]
            xs = [c[1] for c in cells]
            comps.append(
                {
                    "y0": min(ys),
                    "y1": max(ys) + 1,
                    "x0": min(xs),
                    "x1": max(xs) + 1,
                    "area": len(cells),
                    "cells": cells,
                }
            )
    comps.sort(key=lambda c: c["x0"])
    return comps


def valley_split(rgba: np.ndarray, n: int):
    """Split by column occupancy valleys when CC merges sprites."""
    alpha = rgba[..., 3] > 40
    # ignore top label band (~top 12%)
    h = alpha.shape[0]
    band = alpha[int(h * 0.12) :, :]
    col = band.mean(axis=0)
    # smooth
    k = 7
    ker = np.ones(k) / k
    sm = np.convolve(col, ker, mode="same")
    # find n segments via equal-ish cuts at lowest valleys between peaks
    # start with equal width then snap to local minima
    W = len(sm)
    cuts = [0]
    for i in range(1, n):
        ideal = int(round(i * W / n))
        lo = max(cuts[-1] + 20, ideal - 40)
        hi = min(W - 20 * (n - i), ideal + 40)
        if hi <= lo:
            cuts.append(ideal)
        else:
            cuts.append(int(lo + np.argmin(sm[lo:hi])))
    cuts.append(W)
    sprites = []
    for i in range(n):
        x0, x1 = cuts[i], cuts[i + 1]
        tile = rgba[:, x0:x1].copy()
        vis = tile[..., 3] > 40
        if not vis.any():
            continue
        ys, xs = np.where(vis)
        # drop tiny top label crumbs: require body-ish height
        y0, y1 = ys.min(), ys.max() + 1
        xx0, xx1 = xs.min(), xs.max() + 1
        crop = tile[y0:y1, xx0:xx1]
        if crop[..., 3].sum() / 255 < MIN_AREA:
            continue
        sprites.append({"arr": crop, "x0": x0 + xx0, "foot_global": y1 - 1})
    return sprites


def extract_sprites(path: Path, expect: int):
    rgb = np.array(Image.open(path).convert("RGB"))
    rgba = flood_light_bg(rgb)
    # kill top label purple text (high sat purple in top 15%)
    h = rgba.shape[0]
    top = rgba[: int(h * 0.14)]
    f = top[..., :3].astype(np.float32)
    # purple-ish: R and B high-ish, G lower, or magenta text
    purp = (f[..., 0] > 80) & (f[..., 2] > 80) & (f[..., 1] < f[..., 0] * 0.85) & (f[..., 0] - f[..., 1] > 25)
    top_a = top[..., 3].copy()
    top_a[purp] = 0
    rgba[: int(h * 0.14), ..., 3] = top_a
    # also remove thin black ground line near bottom if present (keep feet)
    mask = rgba[..., 3] > 40
    comps = components(mask, MIN_AREA)
    # filter out very short/wide label leftovers
    comps = [c for c in comps if (c["y1"] - c["y0"]) > 40 and c["area"] > MIN_AREA]
    sprites = []
    if len(comps) == expect:
        for c in comps:
            arr = rgba[c["y0"] : c["y1"], c["x0"] : c["x1"]].copy()
            # mask to this component only
            local = np.zeros(arr.shape[:2], bool)
            for y, x in c["cells"]:
                local[y - c["y0"], x - c["x0"]] = True
            arr[~local, 3] = 0
            sprites.append({"arr": arr, "x0": c["x0"], "foot_global": c["y1"] - 1})
    else:
        print(f"  CC got {len(comps)} want {expect} → valley_split")
        sprites = valley_split(rgba, expect)
        if len(sprites) != expect:
            # last resort: equal cells
            print(f"  valley got {len(sprites)} → equal cells")
            W = rgba.shape[1]
            sprites = []
            for i in range(expect):
                x0 = int(round(i * W / expect))
                x1 = int(round((i + 1) * W / expect))
                tile = rgba[:, x0:x1]
                vis = tile[..., 3] > 40
                if not vis.any():
                    continue
                ys, xs = np.where(vis)
                crop = tile[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
                sprites.append({"arr": crop, "x0": x0 + xs.min(), "foot_global": ys.max()})
    print(f"  extracted {len(sprites)}/{expect} from {path.name}")
    return sprites, rgba


def body_metrics(arr: np.ndarray):
    vis = arr[..., 3] > 40
    ys, xs = np.where(vis)
    if not vis.any():
        return None
    crown, foot = int(ys.min()), int(ys.max())
    cx = int((xs.min() + xs.max()) // 2)
    return {"crown": crown, "foot": foot, "cx": cx, "body": foot - crown + 1, "arr": arr}


def scale_rgba(arr: np.ndarray, s: float) -> np.ndarray:
    im = Image.fromarray(arr, "RGBA")
    nw = max(1, int(round(arr.shape[1] * s)))
    nh = max(1, int(round(arr.shape[0] * s)))
    out = np.array(im.resize((nw, nh), Image.Resampling.LANCZOS))
    out[..., 3] = np.where(out[..., 3] >= 40, 255, 0).astype(np.uint8)
    return remove_checkerboard_rgba(out)


def head_width(arr: np.ndarray) -> int:
    """Opaque width of upper ~18% of silhouette — body-scale proxy (not hair tip)."""
    a = arr[..., 3] > 40
    ys, xs = np.where(a)
    if len(ys) == 0:
        return 0
    y0, y1 = int(ys.min()), int(ys.max())
    band = a[y0 : y0 + max(3, int((y1 - y0) * 0.18))]
    cols = np.where(band.any(axis=0))[0]
    return int(cols.max() - cols.min() + 1) if len(cols) else 0


def normalize_head_scale(arr: np.ndarray, target_head: float) -> np.ndarray:
    """Rescale so head width matches idle lock. Never stretch a clip to ATLAS_BODY height."""
    hw = head_width(arr)
    if hw < 6 or target_head < 6:
        return arr
    s = float(target_head) / float(hw)
    # only correct meaningful drift (>8%)
    if abs(s - 1.0) < 0.08:
        return arr
    # clamp extreme corrections
    s = float(np.clip(s, 0.45, 1.55))
    return scale_rgba(arr, s)


def pack_clip(frames_m: list, name: str):
    """Uniform canvas, expand-only, shared feet origin (ox, oy)."""
    scaled = []
    for m in frames_m:
        if m is None:
            continue
        scaled.append(m)
    if not scaled:
        return []
    max_up = max(s["foot"] - s["crown"] for s in scaled)
    max_left = max(s["cx"] for s in scaled)
    max_right = max(s["arr"].shape[1] - s["cx"] for s in scaled)
    # also account for below-foot (shadows)
    max_down = max(s["arr"].shape[0] - 1 - s["foot"] for s in scaled)
    cw = int(max_left + max_right + 2 * PAD)
    ch = int(max_up + max_down + 2 * PAD)
    ox = int(max_left + PAD)
    oy = int(max_up + PAD)
    out = []
    for i, s in enumerate(scaled):
        canvas = np.zeros((ch, cw, 4), np.uint8)
        dest_x = ox - s["cx"]
        dest_y = oy - (s["foot"] - s["crown"]) - s["crown"]  # place crown relative
        # better: foot at oy
        dest_y = oy - s["foot"]
        ah, aw = s["arr"].shape[:2]
        # clip if needed (shouldn't with expand-only)
        x0 = max(0, dest_x)
        y0 = max(0, dest_y)
        x1 = min(cw, dest_x + aw)
        y1 = min(ch, dest_y + ah)
        sx0 = x0 - dest_x
        sy0 = y0 - dest_y
        canvas[y0:y1, x0:x1] = s["arr"][sy0 : sy0 + (y1 - y0), sx0 : sx0 + (x1 - x0)]
        out.append({"i": i, "arr": canvas, "ox": ox, "oy": oy, "w": cw, "h": ch})
    return out


def main():
    BODY_OUT.mkdir(parents=True, exist_ok=True)
    REDRAW.mkdir(parents=True, exist_ok=True)
    all_clip_frames = {}  # name -> list packed
    gaps = []
    raw_by_strip = {}

    # Pass 1: extract all sprites, compute global scale from IDLE standing body
    idle_sprites, _ = extract_sprites(PREVIEWS / "IDLE_GOLD.png", STRIPS["IDLE_GOLD.png"]["expect"])
    if len(idle_sprites) < 1:
        raise SystemExit("IDLE extract failed")
    # use first idle (standing, not max sip tilt) for scale — prefer frame 0 or last
    idle0 = body_metrics(idle_sprites[0]["arr"])
    # exclude extreme sip if taller — use median body of idle frames
    idle_bodies = []
    for sp in idle_sprites:
        m = body_metrics(sp["arr"])
        if m:
            idle_bodies.append(m["body"])
    ref_body = float(np.median(idle_bodies))
    scale = ATLAS_BODY / ref_body
    # idle head lock after global scale (median of idle frames)
    idle_heads = []
    for sp in idle_sprites:
        m = body_metrics(sp["arr"])
        if not m:
            continue
        sc = scale_rgba(m["arr"], scale)
        idle_heads.append(head_width(sc))
    idle_head = float(np.median([h for h in idle_heads if h >= 6]))
    print(f"IDLE median body={ref_body} scale={scale:.4f} → atlas {ATLAS_BODY}; idle_head={idle_head}")

    for strip_name, meta in STRIPS.items():
        sprites, _ = extract_sprites(PREVIEWS / strip_name, meta["expect"])
        if len(sprites) != meta["expect"]:
            gaps.append(f"{strip_name}: got {len(sprites)} expected {meta['expect']}")
        metrics = []
        for sp in sprites:
            m = body_metrics(sp["arr"])
            if not m:
                metrics.append(None)
                continue
            scaled = scale_rgba(m["arr"], scale)
            # ONE body scale lock: match idle head width (fixes jump/combat giant frames)
            if strip_name != "IDLE_GOLD.png":
                scaled = normalize_head_scale(scaled, idle_head)
            sm = body_metrics(scaled)
            metrics.append(sm)
        raw_by_strip[strip_name] = metrics
        for clip_name, a, b in meta["clips"]:
            subset = [m for m in metrics[a:b] if m]
            if not subset:
                gaps.append(f"{clip_name}: empty from {strip_name}[{a}:{b}]")
                continue
            packed = pack_clip(subset, clip_name)
            all_clip_frames[clip_name] = packed
            # write body SoT + public redraw + replace live gameplay names
            for fr in packed:
                fn = f"{clip_name}_{fr['i']:02d}.png"
                Image.fromarray(fr["arr"], "RGBA").save(BODY_OUT / fn)
                Image.fromarray(fr["arr"], "RGBA").save(REDRAW / fn)
                Image.fromarray(fr["arr"], "RGBA").save(FRAMES / fn)
            print(f"  clip {clip_name}: {len(packed)} frames canvas {packed[0]['w']}x{packed[0]['h']} ox={packed[0]['ox']} oy={packed[0]['oy']}")

    # dash/backdash/taunt/win aliases from locomotion
    aliases = {
        "dash": "run",
        "backdash": "run",
        "taunt": "idle",
        "win": "idle",
        "crouchWalk": "crouchWalk" if "crouchWalk" in all_clip_frames else "crouch",
    }
    for dst, src in aliases.items():
        if src in all_clip_frames and dst not in all_clip_frames:
            all_clip_frames[dst] = all_clip_frames[src]

    # Update atlas JSON — only human anims covered; keep bull + greenBull/fx
    with open(ATLAS_PATH) as f:
        atlas = json.load(f)

    keep_prefixes = ("bull", "fx", "greenBull", "s6")
    # also keep greenBull anim name and fxGreenUlt

    def is_keep(anim_name: str) -> bool:
        if anim_name in ("greenBull", "fxGreenUlt", "fxSplash", "fxBeam", "fxCrystal", "fxBullHead", "fxSuper"):
            return True
        if anim_name.startswith("bull"):
            return True
        return False

    for anim, frames in all_clip_frames.items():
        entries = []
        for fr in frames:
            fn = f"/mugen/frames/cino/{anim}_{fr['i']:02d}.png?v={CACHE}"
            entries.append(
                {
                    "file": fn,
                    "i": fr["i"],
                    "ox": fr["ox"],
                    "oy": fr["oy"],
                    "w": fr["w"],
                    "h": fr["h"],
                    "ms": 100,
                    "redraw": True,
                }
            )
        atlas["anims"][anim] = entries

    # bump cache query on non-redraw kept? leave bull/s6 as-is
    atlas["version"] = CACHE
    atlas["redraw"] = {
        "cache": CACHE,
        "source": "cino-human/previews/*_GOLD.png",
        "swapped": sorted(all_clip_frames.keys()),
        "kept": [k for k in atlas["anims"] if is_keep(k)],
        "gaps": gaps,
        "atlasBody": ATLAS_BODY,
        "scaleFromIdleMedian": scale,
    }
    # update file refs that still point at old idle for select — engine separate
    with open(ATLAS_PATH, "w") as f:
        json.dump(atlas, f, indent=2)
        f.write("\n")

    # copy gold previews into assets for provenance
    assets = PUBLIC / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for name in STRIPS:
        shutil.copy2(PREVIEWS / name, assets / f"cino-redraw-{name}")

    meta_out = {
        "cache": CACHE,
        "clips": {k: len(v) for k, v in all_clip_frames.items()},
        "gaps": gaps,
        "scale": scale,
        "ref_body_idle_median": ref_body,
        "idle_head_lock": idle_head,
        "fixes": ["checkerboard_true_alpha", "one_body_scale_head_lock"],
    }
    (BODY_OUT / "SHIP_META.json").write_text(json.dumps(meta_out, indent=2))
    (REDRAW / "SHIP_META.json").write_text(json.dumps(meta_out, indent=2))
    print("GAPS:", gaps)
    print("CLIPS:", meta_out["clips"])
    print("DONE")


if __name__ == "__main__":
    main()
