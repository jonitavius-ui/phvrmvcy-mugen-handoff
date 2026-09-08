# PHVRMVCY MUGEN — project notes for the next Grok

This repo is a **TanStack Start** app. The fighter lives at **`/mugen`**.

**Read `docs/HANDOFF.md` first.** That file is the map of Cino, SB Cookin, lobby, player select, stages, controls, and character registration.

## Tonight's stable build

- Playable roster: **Cino + original SB Cookin only** (`eE=[eH,eM]` in `src/game/engine.js`)
- Do **not** rebuild Cino, lobby, player-select chrome, HUD, combat, or stages
- Extra generated fighters are in `public/mugen/_archive/` (not loaded)
- User source uploads: `/workspace/attachments/` (keep)

## Start

```
sh /workspace/startup.sh
```

Preview must stay on `0.0.0.0:8080` via `npm run dev`.
