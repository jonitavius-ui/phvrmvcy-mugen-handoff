# PHVRMVCY MUGEN — Stable Handoff Build

**Tonight's ship:** Cino six-sheet replacement (Human + permanent Bull) + original SB Cookin + current lobby + current player select + all current stages.

Playable route: `/mugen`

**Source repo (this exact build):** https://github.com/jonitavius-ui/phvrmvcy-mugen-handoff

## Roster scale law (Human Cino = 100%)

Tay global roster law — locked in engine + extract. Future fighters (SB Cookin, etc.) normalize against this later. **Do not start those fighters now.**

| Constant | Value | Role |
|---|---|---|
| `CINO_BASE_HEIGHT` | 212 | Scale Align **LOCKED**. Human idle **body**: feet/ground → crown of **head**, not hair tip. Median 212. Reference `s1_001_IDLE`. Never `s1_010` drink pose (221) |
| `CINO_OPAQUE_WITH_HAIR` | 249 | Diagnostic only. Hair tip / opaque-with-hair. **Never** use for body scale |
| `CINO_BASE_SCALE` | 1 | Roster **BASE SCALE / 100%**. Side-by-side lock for every later fighter |
| `CINO_SPRITE_ZOOM` | 2 | `paint()` / `drawFighter` atlas zoom (named constant — never a magic `2`) |
| `CINO_ATLAS_BODY_HEIGHT` | 106 | Atlas-space body px so `106 × 2 = 212` on canvas |
| `CINO_BULL_SCALE` | 1.18 | After ↓+C: modest bulk. Still a playable fighter — **not** screen-sized |
| `CINO_FX_SCALE` | 1.75 | Lean Splash / Green Candle / energy sphere / bull-head / super **VFX layers only** |

**Measure from character body only** on neutral standing/idle. Never from full PNG dimensions, transparent padding, hair-only extent (opaque-with-hair ≈249 is diagnostic only), or special-effect frames. Scale Align inventory **37/37 qa_pass**. Prefer median **212**. **`s1_010_IDLE` drink pose (221) is excluded** from the lock. Reference frame: `s1_001_IDLE.png`. Authoritative meta: `mugen-extract/cino-v2/sheet1/meta/human-cino-base-scale.json` (in-repo copy: `public/mugen/atlas/human-cino-base-scale.json`). This VM’s JPEG idle 0–4 median (~221 native px) is a source-resolution measure only — it is **not** the drink-pose outlier and is scaled so on-canvas crown = 212.

**ONE character scale** across ALL of that fighter’s gameplay animations. Do not independently resize each frame (causes grow/shrink during attacks). Preserve aspect ratio — never stretch.

**CHARACTER SCALE ≠ EFFECT SCALE.** Cino’s body stays normal fighter size while Lean Splash / Green Candle / energy sphere / bull manifestations / supers / projectiles may be enormous on separate `fx*` layers.

**Bull Cino** (after ↓+C) may be somewhat larger and bulkier, but still moves, jumps, attacks, and gets hit as a normal playable fighter. Transform (`bullForm`) uses bull scale so the sequence does not snap-grow on idle.

**Feet** aligned to the same stage ground plane (`y = 458`).

Engine hook: `eH.scale` in `src/game/engine.js`. Extract: `scripts/extract_cino_v2.py` (one `scale` for Human anims, `scale * CINO_BULL_SCALE` for bull anims, `scale * CINO_FX_SCALE` for `fx*`). Meta: `public/mugen/atlas/cino-scale.json`.

### Cino v2 wiring gold criteria (Chief of Staff / MUGEN Lead)

- [x] Human Cino establishes roster **BASE SCALE = 100%** (`CINO_BASE_SCALE = 1`)
- [x] Scale Align lock: `CINO_BASE_HEIGHT = 212` median; reference `s1_001_IDLE`; **exclude** `s1_010_IDLE` drink pose (221); Sheet1 37/37 qa_pass
- [x] **ONE** scale constant across all Human Cino animations (no per-anim stretch)
- [x] VFX independent and may be huge (`CINO_FX_SCALE`, `fx*` layers)
- [x] Bull form somewhat bulkier only, still playable-sized — not a giant (`CINO_BULL_SCALE = 1.18`)
- [x] No stretch/squash to fake size (uniform scale, aspect preserved)
- [x] Named engine constants for later side-by-side tests against Human Cino idle height
- [x] SB / lobby / stages / controls unchanged; Sheet1 movement + ↓+C permanent Bull still in

Sheet1 movement clips: IDLE 11 @100ms · WALK 9 @80ms · RUN 8 @60ms · CROUCH 2 hold-last · JUMP_START 1 · JUMP_AIR 3 · JUMP_LAND 3.

Dev preview: `sh /workspace/startup.sh` → `npm run dev` on port 8080  
Production build: `npm run build` (Nitro Vercel preset).

---

## Do not break

- Cino six-sheet sprites, bull form (`DOWN + C` permanent), attacks, FX (do not revert to the old Cino set)
- Lobby / title screen UI and background
- Player select **screen** (layout/chrome) — roster is just shorter
- HUD, combat engine, controls
- Current stages (TRVP Exchange, Prime, SpaceX Mars, Trap House, Cino Bank)

---

## Where things live

| What | Path |
|---|---|
| Game engine (combat, AI, input, stages, roster) | `src/game/engine.js` |
| Type stubs | `src/game/engine.d.ts` |
| React shell (lobby buttons, select overlay, HUD chrome, touch bar) | `src/game/MugenGameApp.tsx` |
| Touch helpers | `src/game/touch.ts` |
| Route | `src/routes/mugen.tsx` (also `/cino` in `src/routes/cino.tsx`) |
| **Cino frames** | `public/mugen/frames/cino/` |
| **Cino atlas** | `public/mugen/atlas/cino.json` |
| **Cino scale lock** | `public/mugen/atlas/cino-scale.json` + `human-cino-base-scale.json` (`CINO_BASE_HEIGHT=212`, `CINO_BASE_SCALE=1`) |
| **Cino portrait** | `public/mugen/portraits/cino.png` |
| **Cino source sheets** | `public/mugen/assets/cino-sheet1-movement.jpg` · `cino-sheet2-combat.jpg` · `cino-sheet3-bull-a.jpg` · `cino-sheet3-bull-b.jpg` (legacy `cino-v2-*.jpg` kept) |
| **SB frames (ORIGINAL working set)** | `public/mugen/frames/sb/` |
| **SB atlas** | `public/mugen/atlas/sb.json` |
| **SB portrait** | `public/mugen/portraits/sb.png` |
| **SB original source sheet** | `public/mugen/assets/sb-cookin-original-sheet.png` (also `sb-sheet.png`) |
| Stages (art) | `public/mugen/stages/` |
| Stage registration | `engine.js` → `eD` / `STAGES` / `eC()` |
| Lobby background | `public/mugen/stages/lobby-penthouse.jpg` + `lobby-title.jpg` |
| Character registration | `engine.js` → `eH` (Cino), `eM` (SB), playable list `eE=[eH,eM]` |
| Boot loader (atlases + portraits) | `engine.js` → `GameEngine.boot()` / `sprites.load(...)` |
| Archived extra roster (not playable) | `public/mugen/_archive/` |
| Original user uploads | `/workspace/attachments/` — **do not delete** |

---

## Playable roster

```js
eE = [eH, eM]  // Cino, SB Cookin
```

Clone stubs for Nani / Knucclez / Zilla / Ikedawg / Jugg / Evil Cino still exist in `engine.js` but are **not** in `eE` and are **not** loaded at boot.

To re-enable one later:

1. Copy frames/atlas/portrait back from `public/mugen/_archive/`
2. Add the atlas + portrait + idle sprite to `sprites.load(...)`
3. Push the character object onto `eE`

The labeled (later) SB extract is saved at `public/mugen/_archive/sb-labeled-latest/` — do not mix it with the restored original unless you mean to.

---

## Controls (do not remap)

**P1:** A/D walk · W jump · S crouch · J = A (light) · K = B (heavy) · L = C (kick/special) · Space = D · Shift block  
**Cino bull form:** Down + C (`bullForm` move, `↓+C`). Persistent until round reset.  
**Touch:** on-screen pad + A/B/C/D/BLK in `MugenGameApp.tsx`.

CPU: approaches and mixes normals; specials are cooldown-gated (keep this).

---

## Stages (keep)

`eD = [eS, ePrime, eSpace, eTrap, eCinoBank]`

| id | art |
|---|---|
| `trvp` | `public/mugen/assets/trvp-exchange-stage.png` |
| `prime` | `public/mugen/stages/cino-prime.jpg` |
| `spacex` | `public/mugen/stages/spacex-mars.jpg` |
| `traphouse` | `public/mugen/stages/trap-house.jpg` |
| `cinobank` | `public/mugen/stages/cino-bank.jpg` |

Photo stages use `ePhoto` in `engine.js` with live overlay FX. Do not remove them.

---

## Sprite protocol (Cino is the template)

1. Read PNG as RGBA. **Preserve the original alpha.** Never chroma-key, never flatten, never JPG.
2. Crop on alpha bounds.
3. Export 32-bit PNG frames.
4. Atlas JSON: `{ anims: { idle: [{file,ox,oy,w,h}, ...] } }`
5. `selectSprite` = full-body idle. `portrait` = HUD face only.
6. Mirror with canvas scale, do not duplicate L/R sheets.

---

## Editing tips

- `engine.js` is one minified-style file. Search for `eH={id:"cino"`, `eM={id:"sb"`, `eE=`, `eD=`, `function P(`, `function T(`, `controlCpu`, `bullForm`.
- After changing atlas JSON, hard-refresh — frames are loaded once in `boot()`.
- Preview: `sh /workspace/startup.sh` (binds `0.0.0.0:8080`).

## Playable link (save this)

**Play:** https://jonitavius-ui.github.io/mugen/

**Source:** https://github.com/jonitavius-ui/phvrmvcy-mugen-handoff

GitHub Pages build lives in https://github.com/jonitavius-ui/jonitavius-ui.github.io
