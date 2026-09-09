# Sheet1 Human Cino anim map

CINO_BASE_HEIGHT = 212 (idle feet → crown, NOT hair tip). One character scale for all Human gameplay anims.

Source on this VM: `public/mugen/assets/cino-sheet1-movement.jpg` (image 1 human movement). Specialist PNG `01-human-basic-movement.png` was not present as a named file; 1536×1024 attachments were other roster sheets.

Gameplay frames: `public/mugen/frames/cino/` (idle/walk/run/crouch/jump*). Aliases: `mugen-extract/cino-v2/sheet1/frames/s1_*.png`.

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
