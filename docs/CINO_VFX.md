# Cino separate-layer VFX (roster template)

Cino is the VFX quality benchmark. Effects are **never baked into body sprites or hitboxes**. Human Cino stays at the established **212px** feet→crown draw scale (`paint()` still draws atlas frames at 2×). Super / transform FX may dwarf that.

## Layout

```
public/mugen/vfx/cino/          transparent PNG frames + atlas.json
src/game/vfx.js                 load / spawn / draw
src/game/engine.js              hooks only (onHit, onSim, draw layers)
```

`atlas.json` maps move events → anim names (`hooks.onHit`, `onStart`, `onActive`, `onDash`). Palette: lime `#39ff14`, purple `#b44cff`, lean `#c44cff`, cyan `#3ee8ff`.

## Draw order

1. Shadows + afterimage ghosts (`drawGhost`, additive)
2. **Behind layers** — charge aura, dash / candle trails, shockwaves
3. Fighters (unchanged body sheets)
4. Projectiles + existing particles / slash / aura / flash
5. **Front layers** — hitsparks, plasma, lightning, lean splash, super / transform bursts
6. **Overlay** — Super portrait cut-in (existing `portraits/cino.png` + energy frame)
7. HUD

Blend is canvas `"lighter"` (additive). Alpha is preserved; nothing is chroma-keyed onto Cino.

## Engine hooks (copy this)

| Event | Where | What |
|---|---|---|
| Hit (active hitbox / projectile) | `CinoVfx.onHit(fight, hit, attacker)` | Tiered hitsparks + extra particles |
| Each sim tick | `CinoVfx.onSim(fight)` | Move-start, per-frame trails, dash, land shockwave, layer tick |
| Draw | `drawBehind` / `drawFront` / `drawOverlay` | Separate layers |
| Boot | `await CinoVfx.load()` | Atlas + PNGs |
| Round reset | `fight.fx = CinoVfx.createState()` | Clear layers / cut-in |

Only characters in `VFX_CHARS` (`cino`) spawn the sprite atlas. Existing particle / flash / shake / hitstop still run for everyone.

## Bull form

`↓+C` (`bullForm`) is unchanged: persistent until round reset. Transform burst + lightning + smoke/energy play **only while `moveId === "bullForm"`**. After that, Bull uses `bullIdle` / walk / jump / attack with **no looping transform FX**.

## Super (RX Overdrive)

Full meter, `↓→↓→ + attack` (or special+heavy). Spawns a screen-scale burst + ring + charge aura, existing screen flash/shake, and a portrait cut-in that does not replace HUD.

## Copy for the next character

1. Add `public/mugen/vfx/<id>/` PNG frames (true RGBA, no flattened background).
2. Copy `atlas.json` hooks; retarget palette / anim names.
3. Add `<id>` to `VFX_CHARS` in `src/game/vfx.js` (or load a second atlas the same way).
4. Do not edit that character’s body atlas/frames except tiny spawn hooks.

Regenerate Cino frames with `python3 scripts/gen-cino-vfx.py` (Pillow + numpy).
