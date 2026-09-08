# PHVRMVCY MUGEN — Stable Handoff Build

**Tonight's ship:** Cino (unchanged) + original SB Cookin + current lobby + current player select + all current stages.

Playable route: `/mugen`

**Source repo (this exact build):** https://github.com/jonitavius-ui/phvrmvcy-mugen-handoff  
Commit: `cf6cfac` — *Stable handoff: Cino + original SB Cookin, current lobby/select/stages.*

Dev preview: `sh /workspace/startup.sh` → `npm run dev` on port 8080  
Production build: `npm run build` (verified 2026-09-08, Nitro Vercel preset).

---

## Do not break

- Cino sprites, bull form (`DOWN + C`), attacks, FX
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
| **Cino portrait** | `public/mugen/portraits/cino.png` |
| **Cino source sheet** | `public/mugen/assets/cino-sheet.png` |
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
