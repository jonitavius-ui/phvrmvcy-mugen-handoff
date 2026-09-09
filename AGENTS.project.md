# PHVRMVCY MUGEN — project notes for the next Grok

This repo is a **TanStack Start** app. The fighter lives at **`/mugen`**.

**Read `docs/HANDOFF.md` first.** That file is the map of Cino, SB Cookin, lobby, player select, stages, controls, and character registration.

## Tonight's stable build

- Playable roster: **NEW Cino v2 (long dreads) + original SB Cookin only** (`eE=[eH,eM]` in `src/game/engine.js`)
- Cino boot paths are the v2 extract (`frames/cino`, `atlas/cino.json?v=six4`, `portraits/cino.png`, `eH.selectSprite`). Do **not** restore the short-hair set from `_archive/cino-old/`
- Do **not** rebuild lobby, player-select chrome, HUD, combat engine, or stages / SB Cookin
- Extra generated fighters + archived old Cino are in `public/mugen/_archive/` (not loaded)
- User source uploads: `/workspace/attachments/` (keep)

## Start

```
sh /workspace/startup.sh
```

Preview must stay on `0.0.0.0:8080` via `npm run dev`.
