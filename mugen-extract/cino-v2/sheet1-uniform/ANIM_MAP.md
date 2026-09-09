# Sheet1 Human Cino anim map

CINO_BASE_HEIGHT = 212 (idle feet → crown, NOT hair tip). One character scale for all Human gameplay anims.

Source: `mugen-facing/cino-v2/sheets/01-human-basic-movement.png` (1536×1024). If that PNG is absent this VM builds it from the JPEG movement master using specialist row windows (IDLE y≈41, WALK y≈325, RUN y≈588). Per-frame alpha bounds + padding. Previews: `preview-contact.png`, `preview-row-IDLE.png`, `preview-row-WALK.png`, `preview-row-RUN.png`.

Gameplay frames: `public/mugen/frames/cino/` (idle/walk/run/crouch/jump*) packed onto per-clip uniform canvases (atlas `uniform1`). Aliases: `mugen-extract/cino-v2/sheet1/frames/s1_*.png` (37) + `sheet1-uniform/`. JPEG copy: `mugen-facing/cino-v2/01-human-basic-movement.jpg`.

| Clip | Uniform canvas | Origin (feet) |
|---|---|---|
| IDLE | 197×274 | ox=64, oy=261 |
| WALK | 293×251 | ox=132, oy=238 |
| RUN | 416×215 | ox=224, oy=202 |
| CROUCH | 164×195 | ox=76, oy=182 |
| JUMP_START | 164×191 | ox=93, oy=178 |
| JUMP_AIR | 187×193 | ox=97, oy=180 |
| JUMP_LAND | 167×185 | ox=75, oy=172 |

| Clip | Frames | Loop | ms | Engine |
|---|---|---|---|---|
| IDLE | s1_001–011 (11) | yes | 100 | idle |
| WALK | s1_012–020 (9) | yes | 80 | walk |
| RUN | s1_021–028 (8) | yes | 60 | run |
| CROUCH | s1_029–030 (2) | hold last | 50 | crouch |
| JUMP_START | s1_031 (1) | no | 50 | jumpStart |
| JUMP_AIR | s1_032–034 (3) | airborne | 70 | jumpLoop |
| JUMP_LAND | s1_035–037 (3) | no | 55 | jumpLand |

Walk is a real 9-frame cycle (not sliding idle). Jump: JUMP_START → JUMP_AIR → JUMP_LAND.

Public copies for the engine feed: `public/mugen/atlas/cino-anim-map.json` + `cino-anim-map-compact.json`. Gameplay atlas `cino.json` tags each movement frame with `s1` / `clip` / `ms`.

Soft-watch RUN `s1_025`: specialist native origin was ~221/246 (~90% right). Tight-crop gameplay was ox=49 / w=108 (~45%). Uniform pack keeps that feet placement by expand-only padding onto the shared RUN canvas **416×215, ox=224, oy=202** (same origin as the other seven run frames). **No further ox adjust.**
