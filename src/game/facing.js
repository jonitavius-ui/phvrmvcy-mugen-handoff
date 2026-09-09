/**
 * Opponent-relative facing for PHVRMVCY MUGEN.
 * One sprite instance is flipped with canvas scaleX; boxes/F-B use the same sign.
 */

/** Ignore tiny overlaps so fighters don't flicker while stacked. */
export const FACE_DEADZONE = 8;

/** @param {number} facing */
export function facingSign(facing) {
  return facing === 1 || facing > 0 ? 1 : -1;
}

/** @param {number} facing */
export function spriteFlipX(facing) {
  return facingSign(facing);
}

/**
 * @param {{ hp?: number, state?: string, moveId?: string | null, dashT?: number, stun?: number, blockstun?: number } | null | undefined} fighter
 */
export function canUpdateFacing(fighter) {
  if (!fighter || (fighter.hp ?? 0) <= 0) return false;
  if (fighter.state === "ko" || fighter.state === "knockdown") return false;
  if (fighter.moveId || (fighter.dashT ?? 0) > 0) return false;
  if ((fighter.stun ?? 0) > 0 || (fighter.blockstun ?? 0) > 0) return false;
  return true;
}

/**
 * @param {number} selfX
 * @param {number} otherX
 * @param {number} [current]
 */
export function facingToward(selfX, otherX, current = 1) {
  const dx = otherX - selfX;
  if (Math.abs(dx) < FACE_DEADZONE) return facingSign(current);
  return dx >= 0 ? 1 : -1;
}

/**
 * Mutates fighter.facing so they look at the opponent when they are free to turn.
 * @param {{ facing: number, x: number, hp?: number, state?: string, moveId?: string | null, dashT?: number, stun?: number, blockstun?: number }} self
 * @param {{ x: number } | null | undefined} other
 */
export function applyFacing(self, other) {
  if (!canUpdateFacing(self) || !other) return self?.facing;
  self.facing = facingToward(self.x, other.x, self.facing);
  return self.facing;
}

/**
 * Map screen left/right to MUGEN F/B using current facing.
 * Facing right: D = F, A = B. Facing left (after a cross): A = F, D = B.
 * @param {boolean} heldLeft
 * @param {boolean} heldRight
 * @param {boolean} heldUp
 * @param {boolean} heldDown
 * @param {number} facing
 */
export function screenToFB(heldLeft, heldRight, heldUp, heldDown, facing) {
  const sx = (heldRight ? 1 : 0) - (heldLeft ? 1 : 0);
  const sy = (heldDown ? 1 : 0) - (heldUp ? 1 : 0);
  const r = facingSign(facing) === 1 ? sx : -sx;
  if (r === 0 && sy === 0) return "N";
  if (r === 0 && sy < 0) return "U";
  if (r === 0 && sy > 0) return "D";
  if (r > 0 && sy === 0) return "F";
  if (r < 0 && sy === 0) return "B";
  if (r > 0 && sy < 0) return "UF";
  if (r < 0 && sy < 0) return "UB";
  if (r > 0 && sy > 0) return "DF";
  return "DB";
}

/**
 * Author boxes as if facing right; flip them around the fighter origin.
 * @param {number} originX
 * @param {number} originY
 * @param {number} facing
 * @param {{ x: number, y: number, w: number, h: number }} box
 */
export function flipBox(originX, originY, facing, box) {
  return {
    x: facingSign(facing) === 1 ? originX + box.x : originX - box.x - box.w,
    y: originY - box.y - box.h,
    w: box.w,
    h: box.h,
  };
}
