#!/usr/bin/env python3
"""Pack Sheet1 Human movement onto per-clip uniform canvases.

Tay cleanup law: expand canvas only (never shrink/scale art); lock feet
origin within each clip. CINO_BASE_HEIGHT=212 unchanged.

Does NOT touch Bull idle / combat / FX / SB.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image

ROOT = Path("/workspace")
FRAMES = ROOT / "public/mugen/frames/cino"
ATLAS_PATH = ROOT / "public/mugen/atlas/cino.json"
EXTRACT = ROOT / "mugen-extract/cino-v2"
UNIFORM_DIR = EXTRACT / "sheet1-uniform"
VERSION = "uniform1"
CINO_BASE_HEIGHT = 212

# Authoritative pack targets (Lead).
PACK = {
    "IDLE": {"w": 197, "h": 274, "ox": 64, "oy": 261, "engine": "idle", "count": 11},
    "WALK": {"w": 293, "h": 251, "ox": 132, "oy": 238, "engine": "walk", "count": 9},
    "RUN": {"w": 416, "h": 215, "ox": 224, "oy": 202, "engine": "run", "count": 8},
    "CROUCH": {"w": 164, "h": 195, "ox": 76, "oy": 182, "engine": "crouch", "count": 2},
    "JUMP_START": {"w": 164, "h": 191, "ox": 93, "oy": 178, "engine": "jumpStart", "count": 1},
    "JUMP_AIR": {"w": 187, "h": 193, "ox": 97, "oy": 180, "engine": "jumpLoop", "count": 3},
    "JUMP_LAND": {"w": 167, "h": 185, "ox": 75, "oy": 172, "engine": "jumpLand", "count": 3},
}

# Engine aliases that reuse the same movement art (keep them uniform too).
ALIASES = {
    "dash": "RUN",
    "backdash": "RUN",
    "crouchWalk": "CROUCH",
    "block": "CROUCH",
    "knockdown": "JUMP_LAND",
    "getUp": "JUMP_LAND",
}

S1_FILES = {
    "IDLE": [f"s1_{i:03d}_IDLE.png" for i in range(1, 12)],
    "WALK": [f"s1_{i:03d}_WALK.png" for i in range(12, 21)],
    "RUN": [f"s1_{i:03d}_RUN.png" for i in range(21, 29)],
    "CROUCH": ["s1_029_CROUCH.png", "s1_030_CROUCH.png"],
    "JUMP_START": ["s1_031_JUMP_START.png"],
    "JUMP_AIR": ["s1_032_JUMP_AIR.png", "s1_033_JUMP_AIR.png", "s1_034_JUMP_AIR.png"],
    "JUMP_LAND": ["s1_035_JUMP_LAND.png", "s1_036_JUMP_LAND.png", "s1_037_JUMP_LAND.png"],
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def gameplay_path(file_url: str) -> Path:
    rel = file_url.split("?", 1)[0]
    if rel.startswith("/mugen/"):
        return ROOT / "public" / rel.lstrip("/")
    return ROOT / rel


def pack_frame(src: Image.Image, src_ox: int, src_oy: int, spec: dict) -> Image.Image:
    W, H, OX, OY = spec["w"], spec["h"], spec["ox"], spec["oy"]
    sw, sh = src.size
    dx = OX - src_ox
    dy = OY - src_oy
    if dx < 0 or dy < 0 or dx + sw > W or dy + sh > H:
        raise SystemExit(
            f"CLIP (would shrink/crop art): src={sw}x{sh} ox/oy={src_ox},{src_oy} "
            f"-> dest={dx},{dy} canvas={W}x{H} origin={OX},{OY}"
        )
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    canvas.paste(src, (dx, dy), src)
    return canvas


def bump_file(url: str) -> str:
    base = url.split("?", 1)[0]
    return f"{base}?v={VERSION}"


def update_frame_entry(fr: dict, spec: dict) -> None:
    fr["ox"] = spec["ox"]
    fr["oy"] = spec["oy"]
    fr["w"] = spec["w"]
    fr["h"] = spec["h"]
    if "file" in fr and "/mugen/frames/cino/" in fr["file"]:
        fr["file"] = bump_file(fr["file"])


def main() -> None:
    atlas = json.loads(ATLAS_PATH.read_text())
    anims = atlas["anims"]

    bull_before = json.dumps(anims["bullIdle"], sort_keys=True)
    bull_pngs = sorted(FRAMES.glob("bullIdle_*.png"))
    bull_hashes = {p.name: sha256(p) for p in bull_pngs}

    packed_paths: list[Path] = []
    report = []

    def pack_anim(anim_name: str, clip: str) -> None:
        spec = PACK[clip]
        frames = anims[anim_name]
        if clip in PACK and anim_name == spec["engine"] and len(frames) != spec["count"]:
            raise SystemExit(f"{anim_name}: expected {spec['count']} frames, got {len(frames)}")
        for fr in frames:
            src_path = gameplay_path(fr["file"])
            if not src_path.exists():
                raise SystemExit(f"missing {src_path}")
            src = Image.open(src_path).convert("RGBA")
            if src.size != (fr["w"], fr["h"]):
                raise SystemExit(
                    f"atlas/png size mismatch {src_path.name}: png={src.size} atlas={fr['w']}x{fr['h']}"
                )
            out = pack_frame(src, int(fr["ox"]), int(fr["oy"]), spec)
            out.save(src_path, format="PNG")
            packed_paths.append(src_path)
            update_frame_entry(fr, spec)
            report.append(
                {
                    "anim": anim_name,
                    "clip": clip,
                    "i": fr.get("i"),
                    "file": src_path.name,
                    "canvas": [spec["w"], spec["h"]],
                    "origin": [spec["ox"], spec["oy"]],
                    "srcWas": [src.size[0], src.size[1]],
                }
            )

    for clip, spec in PACK.items():
        pack_anim(spec["engine"], clip)
    for anim_name, clip in ALIASES.items():
        pack_anim(anim_name, clip)

    atlas["version"] = VERSION
    atlas.setdefault("scale", {})["CINO_BASE_HEIGHT"] = CINO_BASE_HEIGHT
    sheet1 = atlas.setdefault("sheet1", {})
    sheet1["CINO_BASE_HEIGHT"] = CINO_BASE_HEIGHT
    sheet1["uniform"] = True
    sheet1["uniformVersion"] = VERSION
    sheet1["uniformLaw"] = "expand canvas only; never shrink/scale art; shared feet origin per clip"
    clips_meta = sheet1.setdefault("clips", {})
    for clip, spec in PACK.items():
        entry = clips_meta.setdefault(clip, {})
        entry["engineAnim"] = spec["engine"]
        entry["count"] = spec["count"]
        entry["canvas"] = {"w": spec["w"], "h": spec["h"]}
        entry["origin"] = {"ox": spec["ox"], "oy": spec["oy"]}

    ATLAS_PATH.write_text(json.dumps(atlas, indent=2) + "\n")

    # Extract mirrors + keep sheet1 aliases in sync.
    uni_frames = UNIFORM_DIR / "frames"
    uni_frames.mkdir(parents=True, exist_ok=True)
    src_alias_dir = EXTRACT / "sheet1/frames"
    for clip, names in S1_FILES.items():
        spec = PACK[clip]
        engine = spec["engine"]
        for i, name in enumerate(names):
            src = gameplay_path(anims[engine][i]["file"])
            shutil.copy2(src, uni_frames / name)
            if src_alias_dir.exists():
                shutil.copy2(src, src_alias_dir / name)

    def patch_map(path: Path) -> None:
        if not path.exists():
            return
        data = json.loads(path.read_text())
        clips = data.get("clips") or {}
        # sheet atlas uses anims keyed by engine name
        if "anims" in data:
            for clip, spec in PACK.items():
                engine = spec["engine"]
                frames = data["anims"].get(engine) or []
                for fr in frames:
                    fr["ox"] = spec["ox"]
                    fr["oy"] = spec["oy"]
                    fr["w"] = spec["w"]
                    fr["h"] = spec["h"]
        if clips:
            for clip, spec in PACK.items():
                c = clips.get(clip)
                if not c:
                    continue
                c["canvas"] = {"w": spec["w"], "h": spec["h"]}
                c["origin"] = {"ox": spec["ox"], "oy": spec["oy"]}
                for fr in c.get("frames") or []:
                    fr["ox"] = spec["ox"]
                    fr["oy"] = spec["oy"]
                    fr["w"] = spec["w"]
                    fr["h"] = spec["h"]
        data["version"] = VERSION
        data["CINO_BASE_HEIGHT"] = CINO_BASE_HEIGHT
        path.write_text(json.dumps(data, indent=2) + "\n")

    patch_map(EXTRACT / "sheet1/anim_map.json")
    patch_map(EXTRACT / "sheet1/atlas.json")
    patch_map(ROOT / "public/mugen/atlas/cino-anim-map.json")
    patch_map(ROOT / "public/mugen/atlas/cino-sheet1-atlas.json")

    uni_atlas = {
        "id": "cino-sheet1-uniform",
        "version": VERSION,
        "CINO_BASE_HEIGHT": CINO_BASE_HEIGHT,
        "law": "expand canvas only; never shrink/scale art; shared feet origin per clip",
        "pack": {k: {kk: vv for kk, vv in v.items() if kk in ("w", "h", "ox", "oy", "engine", "count")} for k, v in PACK.items()},
        "clips": {},
    }
    for clip, spec in PACK.items():
        engine = spec["engine"]
        uni_atlas["clips"][clip] = {
            "engineAnim": engine,
            "count": spec["count"],
            "canvas": {"w": spec["w"], "h": spec["h"]},
            "origin": {"ox": spec["ox"], "oy": spec["oy"]},
            "frames": [
                {
                    "file": f"frames/{S1_FILES[clip][i]}",
                    "gameplay": anims[engine][i]["file"],
                    "i": i,
                    "ox": spec["ox"],
                    "oy": spec["oy"],
                    "w": spec["w"],
                    "h": spec["h"],
                    "s1": anims[engine][i].get("s1"),
                }
                for i in range(spec["count"])
            ],
        }
    (UNIFORM_DIR / "atlas.json").write_text(json.dumps(uni_atlas, indent=2) + "\n")
    shutil.copy2(EXTRACT / "sheet1/anim_map.json", UNIFORM_DIR / "anim_map.json")

    # Integrity: Sheet1 clips uniform; bullIdle unchanged.
    atlas2 = json.loads(ATLAS_PATH.read_text())
    for clip, spec in PACK.items():
        frames = atlas2["anims"][spec["engine"]]
        sizes = {(f["w"], f["h"]) for f in frames}
        origins = {(f["ox"], f["oy"]) for f in frames}
        if sizes != {(spec["w"], spec["h"])} or origins != {(spec["ox"], spec["oy"])}:
            raise SystemExit(f"{clip} not uniform: sizes={sizes} origins={origins}")
        for f in frames:
            p = gameplay_path(f["file"])
            im = Image.open(p)
            if im.size != (spec["w"], spec["h"]):
                raise SystemExit(f"{p.name} png {im.size} != canvas {spec['w']}x{spec['h']}")

    bull_after = json.dumps(atlas2["anims"]["bullIdle"], sort_keys=True)
    if bull_after != bull_before:
        raise SystemExit("bullIdle atlas entries changed — abort")
    for p in bull_pngs:
        if sha256(p) != bull_hashes[p.name]:
            raise SystemExit(f"{p.name} pixels changed — abort")
    if atlas2["version"] == "six4":
        raise SystemExit("version still six4")
    if atlas2["scale"]["CINO_BASE_HEIGHT"] != CINO_BASE_HEIGHT:
        raise SystemExit("CINO_BASE_HEIGHT mutated")

    print(f"packed {len(report)} frames  version={atlas2['version']}")
    for clip, spec in PACK.items():
        print(
            f"  {clip:11s} n={spec['count']:2d}  {spec['w']}x{spec['h']}  "
            f"ox={spec['ox']} oy={spec['oy']}"
        )
    print("bullIdle unchanged:", len(bull_pngs), "pngs + atlas entries")


if __name__ == "__main__":
    main()
