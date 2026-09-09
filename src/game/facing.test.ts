import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  applyFacing,
  canUpdateFacing,
  facingToward,
  flipBox,
  screenToFB,
  spriteFlipX,
} from "./facing.js";

function fighter(partial: Record<string, unknown>) {
  return {
    hp: 1000,
    state: "idle",
    moveId: null,
    dashT: 0,
    stun: 0,
    blockstun: 0,
    facing: 1,
    x: 250,
    ...partial,
  };
}

describe("facingToward", () => {
  it("left fighter faces right, right fighter faces left", () => {
    assert.equal(facingToward(250, 710, 1), 1);
    assert.equal(facingToward(710, 250, -1), -1);
  });

  it("updates after a side swap / cross", () => {
    assert.equal(facingToward(720, 240, 1), -1);
    assert.equal(facingToward(240, 720, -1), 1);
  });

  it("keeps current facing inside the overlap deadzone", () => {
    assert.equal(facingToward(400, 404, 1), 1);
    assert.equal(facingToward(400, 404, -1), -1);
  });
});

describe("canUpdateFacing / applyFacing", () => {
  it("turns during landing after a jump-over (landT must not lock facing)", () => {
    const p1 = fighter({ x: 720, facing: 1, landT: 12, state: "jumpLand" });
    const p2 = fighter({ x: 240, facing: -1, side: 1 });
    assert.equal(canUpdateFacing(p1), true);
    applyFacing(p1, p2);
    applyFacing(p2, p1);
    assert.equal(p1.facing, -1);
    assert.equal(p2.facing, 1);
  });

  it("does not turn mid-attack", () => {
    const p1 = fighter({ x: 720, facing: 1, moveId: "standLight" });
    applyFacing(p1, fighter({ x: 240 }));
    assert.equal(p1.facing, 1);
  });
});

describe("screenToFB", () => {
  it("maps D to forward while facing right", () => {
    assert.equal(screenToFB(false, true, false, false, 1), "F");
    assert.equal(screenToFB(true, false, false, false, 1), "B");
  });

  it("keeps F toward the opponent after a cross (facing left)", () => {
    assert.equal(screenToFB(true, false, false, false, -1), "F");
    assert.equal(screenToFB(false, true, false, false, -1), "B");
    assert.equal(screenToFB(false, true, false, true, -1), "DB");
    assert.equal(screenToFB(true, false, false, true, -1), "DF");
  });
});

describe("spriteFlipX / flipBox", () => {
  it("flips the same instance with scaleX ±1, never a second sheet", () => {
    assert.equal(spriteFlipX(1), 1);
    assert.equal(spriteFlipX(-1), -1);
  });

  it("mirrors authored-right hitboxes around the fighter origin", () => {
    const box = { x: 14, y: 70, w: 58, h: 28 };
    const right = flipBox(250, 458, 1, box);
    const left = flipBox(710, 458, -1, box);
    assert.equal(right.x, 250 + 14);
    assert.equal(left.x, 710 - 14 - 58);
    assert.equal(right.w, left.w);
    assert.equal(right.h, left.h);
  });
});
