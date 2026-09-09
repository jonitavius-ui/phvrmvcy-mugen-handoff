/* @ts-nocheck */
/* Separate-layer VFX. Check JS, not TS — same contract as engine.js. */
/**
 * Separate-layer VFX for PHVRMVCY MUGEN.
 *
 * Cino is the roster template. Other characters copy this pattern:
 *   1. Put transparent PNG frames + atlas.json in public/mugen/vfx/<id>/
 *   2. List that id in VFX_CHARS (or give them their own atlas later).
 *   3. Do NOT bake FX into body sheets / hitboxes. Body scale stays 212px
 *      (engine paint() draws atlas frames at 2x). VFX sprites may be huge.
 *
 * Layers live on fight.fx and are drawn behind/above fighters, never inside
 * eU.paint(). Transform FX is spawned only while moveId === "bullForm".
 */
export const VFX_ATLAS_URL = "/mugen/vfx/cino/atlas.json";
export const VFX_CHARS = new Set(["cino"]);

const BEHIND = new Set(["chargeAura", "dashTrail", "candleTrail", "speedStreak"]);
const GROUND = new Set(["shockwave"]);

let atlas = null;
const images = new Map();
let ready = false;

export function createState() {
  return { layers: [], cutin: null };
}

export function reset(fight) {
  fight.fx = createState();
}

export function ensure(fight) {
  if (!fight.fx) fight.fx = createState();
  return fight.fx;
}

export async function load() {
  try {
    const res = await fetch(VFX_ATLAS_URL);
    if (!res.ok) return;
    atlas = await res.json();
    const files = new Set();
    for (const frames of Object.values(atlas.anims || {})) {
      for (const f of frames) files.add(f.file);
    }
    await Promise.all(
      [...files].map(
        (src) =>
          new Promise((resolve) => {
            const img = new Image();
            img.onload = () => resolve();
            img.onerror = () => resolve();
            img.src = src;
            images.set(src, img);
          }),
      ),
    );
    ready = true;
  } catch (e) {
    ready = false;
  }
}

function isCino(f) {
  return f && f.def && VFX_CHARS.has(f.def.id);
}

function animFrames(name) {
  return (atlas && atlas.anims && atlas.anims[name]) || [];
}

function animLife(name) {
  return animFrames(name).reduce((s, f) => s + (f.dur || 2), 0) || 8;
}

function zFor(name) {
  if (BEHIND.has(name)) return "behind";
  if (GROUND.has(name)) return "behind";
  return "front";
}

function spawn(fight, name, x, y, opts) {
  const o = opts || {};
  const frames = animFrames(name);
  if (!frames.length) return;
  const fx = ensure(fight);
  if (fx.layers.length > 56) fx.layers.splice(0, fx.layers.length - 48);
  const life = o.life || animLife(name);
  fx.layers.push({
    anim: name,
    x,
    y,
    facing: o.facing || 1,
    scale: o.scale == null ? 1 : o.scale,
    t: 0,
    life,
    max: life,
    z: o.z || zFor(name),
    additive: o.additive !== false,
    follow: o.follow || null,
    followY: o.followY || 0,
    alpha: o.alpha == null ? 1 : o.alpha,
    rot: o.rot || 0,
  });
}

function extraParticles(fight, x, y, color, n, kind) {
  const k = kind || "spark";
  for (let i = 0; i < n; i++) {
    const a = (Math.PI * 2 * i) / n + Math.random() * 0.4;
    const spd = 2.4 + (i % 4);
    fight.particles.push({
      alive: true,
      x,
      y,
      vx: Math.cos(a) * spd,
      vy: Math.sin(a) * spd - 1.1,
      life: 14 + (i % 8),
      max: 22,
      r: k === "slash" ? 26 + (i % 10) : 2 + (i % 3),
      color,
      kind: k,
    });
  }
}

function hitTier(attacker, hit) {
  const mv = attacker && attacker.moveId && attacker.def.moves[attacker.moveId];
  const tags = (mv && mv.tags) || [];
  const cat = (mv && mv.category) || "";
  if (cat === "super" || tags.includes("super")) return "super";
  if (cat === "special" || tags.includes("special")) return "special";
  if (tags.includes("kick")) return "kick";
  if (tags.includes("heavy")) return "heavy";
  return "light";
}

export function onHit(fight, hit, attacker) {
  if (!hit || !atlas) return;
  const blocked = !!hit.blocked;
  const x = hit.x;
  const y = hit.y;
  if (!isCino(attacker)) return;
  const tier = blocked ? "light" : hitTier(attacker, hit);
  const map = (atlas.hooks && atlas.hooks.onHit) || {};
  const anim = map[tier] || "hitsparkLight";
  const scale = blocked ? 0.7 : tier === "super" ? 1.35 : tier === "special" ? 1.15 : tier === "heavy" ? 1.05 : 0.85;
  spawn(fight, anim, x, y, { scale, facing: attacker.facing || 1 });
  extraParticles(fight, x, y, blocked ? "#c8c8c8" : "#39ff14", blocked ? 4 : tier === "super" ? 16 : 10, "spark");
  if (!blocked && (tier === "heavy" || tier === "kick" || tier === "special" || tier === "super")) {
    fight.sparks.push({
      alive: true,
      x,
      y,
      vx: 0,
      vy: 0,
      life: 8,
      max: 8,
      r: tier === "super" ? 64 : 36,
      color: "#39ff14",
      kind: "slash",
    });
  }
  const mv = attacker.moveId;
  if (!blocked && (mv === "leanSplash" || (attacker.def.moves[mv] || {}).anim === "leanSplash")) {
    spawn(fight, "leanSplash", x, y, { scale: 1.1, facing: attacker.facing });
  }
  if (!blocked && (mv === "chartBreaker" || mv === "crouchHeavy" || mv === "bullForm" || mv === "overdrive")) {
    spawn(fight, "shockwave", attacker.x, 458, { scale: mv === "overdrive" || mv === "bullForm" ? 1.25 : 0.95, facing: attacker.facing });
  }
  if (!blocked && (tier === "special" || tier === "super")) {
    spawn(fight, "lightning", x, y, { scale: 0.85, facing: attacker.facing });
    spawn(fight, "plasma", x, y - 8, { scale: 0.9, facing: attacker.facing });
  }
}

function startMove(fight, f) {
  const id = f.moveId;
  if (!id || !atlas) return;
  const hooks = (atlas.hooks && atlas.hooks.onStart) || {};
  const list = hooks[id] || [];
  const facing = f.facing || 1;
  for (const name of list) {
    if (name === "cutin") {
      ensure(fight).cutin = {
        life: 52,
        max: 52,
        side: f.side,
        portrait: f.def.portrait,
        title: id === "overdrive" ? "RX OVERDRIVE" : f.def.short,
        facing,
        accent: f.def.accent2 || "#39ff14",
      };
      fight.flash = Math.min(8, Math.max(fight.flash || 0, 6));
      fight.shake = Math.max(fight.shake || 0, 14);
      continue;
    }
    const ground = name === "shockwave";
    const aura = name === "chargeAura";
    const trail = name === "speedStreak" || name === "dashTrail" || name === "candleTrail";
    const x = ground || aura ? f.x : trail ? f.x - 28 * facing : f.x + 16 * facing;
    const y = ground ? 458 : trail ? f.y - 68 : aura ? f.y : f.y - 86;
    spawn(fight, name, x, y, {
      facing,
      follow: aura ? f : null,
      followY: 0,
      scale: name === "superBurst" ? 0.68 : name === "transformBurst" ? 0.88 : name === "superRing" ? 0.92 : 1,
      alpha: name === "superBurst" ? 0.82 : 1,
      z: aura ? "behind" : zFor(name),
    });
  }
  if (id === "bullForm") {
    extraParticles(fight, f.x, f.y - 80, "#b44cff", 14, "spark");
    extraParticles(fight, f.x, f.y - 40, "#39ff14", 10, "spark");
    fight.flash = Math.min(8, Math.max(fight.flash || 0, 5));
    fight.shake = Math.max(fight.shake || 0, 12);
    fight.sparks.push({
      alive: true,
      x: f.x,
      y: f.y - 70,
      vx: 0,
      vy: 0,
      life: 16,
      max: 16,
      r: 90,
      color: "#b44cff",
      kind: "aura",
    });
  }
  if (id === "overdrive") {
    extraParticles(fight, f.x, f.y - 90, "#39ff14", 14, "spark");
  }
}

function activeMove(fight, f) {
  const id = f.moveId;
  if (!id || !atlas) return;
  const spec = ((atlas.hooks && atlas.hooks.onActive) || {})[id];
  if (!spec) return;
  const every = spec.every || 4;
  if (fight.time % every !== 0) return;
  const kinds = spec.kinds || [];
  const facing = f.facing || 1;
  for (const name of kinds) {
    const trail = name === "speedStreak" || name === "dashTrail" || name === "candleTrail";
    spawn(fight, name, f.x - (trail ? 36 * facing : 0), trail ? f.y - 70 : f.y - 64, {
      facing,
      scale: name === "candleTrail" ? 0.7 : 0.85,
      alpha: 0.9,
    });
  }
}

function dashFx(fight, f) {
  if (!atlas || f.dashT <= 0) return;
  if (fight.time % 2 !== 0) return;
  const facing = f.dashDir || f.facing || 1;
  spawn(fight, "dashTrail", f.x - 20 * facing, f.y - 62, { facing, scale: 0.9, alpha: 0.85 });
  spawn(fight, "speedStreak", f.x - 10 * facing, f.y - 78, { facing, scale: 0.8, alpha: 0.75 });
}

function landFx(fight, f) {
  if (f.landT === 12) spawn(fight, "shockwave", f.x, 458, { scale: 0.55, facing: f.facing || 1, alpha: 0.8 });
}

function tickFighter(fight, f) {
  if (!isCino(f)) return;
  if (f.moveId && f.moveT === 1) startMove(fight, f);
  if (f.moveId) activeMove(fight, f);
  if (f.dashT > 0) dashFx(fight, f);
  landFx(fight, f);
}

function tickLayers(fight) {
  const fx = ensure(fight);
  for (const layer of fx.layers) {
    layer.t += 1;
    layer.life -= 1;
    if (layer.follow && layer.follow.x != null) {
      layer.x = layer.follow.x;
      layer.y = layer.follow.y + (layer.followY || 0);
      layer.facing = layer.follow.facing || layer.facing;
    }
  }
  fx.layers = fx.layers.filter((l) => l.life > 0);
  if (fx.cutin) {
    fx.cutin.life -= 1;
    if (fx.cutin.life <= 0) fx.cutin = null;
  }
}

function projectileFx(fight) {
  for (const p of fight.projectiles || []) {
    const owner = p.owner === 0 ? fight.p1 : fight.p2;
    if (!isCino(owner)) continue;
    if (p.kind === "lean") {
      if (p.frame === 0) spawn(fight, "leanSplash", p.x, p.y, { scale: 0.85, facing: owner.facing });
      else if (fight.time % 4 === 0) spawn(fight, "leanSplash", p.x, p.y, { scale: 0.45, facing: owner.facing, alpha: 0.7 });
    } else if (p.kind === "shock" && p.frame === 0) {
      spawn(fight, "shockwave", p.x, 458, { scale: 1.1, facing: owner.facing });
      spawn(fight, "lightning", p.x, p.y, { scale: 0.9, facing: owner.facing });
    }
  }
}

export function onSim(fight) {
  if (!ready || !atlas) return;
  ensure(fight);
  tickFighter(fight, fight.p1);
  tickFighter(fight, fight.p2);
  projectileFx(fight);
  tickLayers(fight);
}

function frameAt(layer) {
  const frames = animFrames(layer.anim);
  if (!frames.length) return null;
  const spent = layer.max - layer.life;
  let acc = 0;
  for (const fr of frames) {
    acc += fr.dur || 2;
    if (spent < acc) return fr;
  }
  return frames[frames.length - 1];
}

function drawLayer(ctx, layer) {
  const fr = frameAt(layer);
  if (!fr) return;
  const img = images.get(fr.file);
  if (!img || !img.complete || !img.naturalWidth) return;
  const t = Math.max(0, layer.life / layer.max);
  ctx.save();
  ctx.translate(layer.x, layer.y);
  ctx.scale(layer.facing * layer.scale, layer.scale);
  if (layer.rot) ctx.rotate(layer.rot);
  ctx.globalAlpha = (layer.alpha || 1) * Math.min(1, t * 1.35);
  if (layer.additive) ctx.globalCompositeOperation = "lighter";
  ctx.imageSmoothingEnabled = true;
  ctx.drawImage(img, 0, 0, img.naturalWidth, img.naturalHeight, -fr.ox, -fr.oy, fr.w, fr.h);
  ctx.restore();
}

export function drawBehind(ctx, fight) {
  if (!ready || !fight || !fight.fx) return;
  for (const layer of fight.fx.layers) {
    if (layer.z === "behind") drawLayer(ctx, layer);
  }
}

export function drawFront(ctx, fight) {
  if (!ready || !fight || !fight.fx) return;
  for (const layer of fight.fx.layers) {
    if (layer.z !== "behind") drawLayer(ctx, layer);
  }
}

export function drawOverlay(ctx, fight, sprites) {
  const cut = fight && fight.fx && fight.fx.cutin;
  if (!cut) return;
  const t = cut.life / cut.max;
  const intro = 1 - Math.min(1, (cut.max - cut.life) / 8);
  const fade = t < 0.18 ? t / 0.18 : 1;
  const left = cut.side === 0;
  const x = left ? 36 : 960 - 36 - 440;
  const y = 86;
  const w = 440;
  const h = 236;
  const slide = (left ? -1 : 1) * 80 * intro;
  ctx.save();
  ctx.globalAlpha = 0.22 * fade;
  ctx.fillStyle = "#050208";
  ctx.fillRect(0, 0, 960, 540);
  ctx.globalAlpha = 0.8 * fade;
  ctx.fillRect(0, 0, 960, 28);
  ctx.fillRect(0, 512, 960, 28);
  ctx.restore();

  ctx.save();
  ctx.translate(slide, 0);
  ctx.globalAlpha = fade;
  ctx.fillStyle = "rgba(8,0,16,0.78)";
  ctx.fillRect(x, y, w, h);
  ctx.strokeStyle = cut.accent || "#39ff14";
  ctx.lineWidth = 2;
  ctx.strokeRect(x, y, w, h);

  const portrait = sprites && sprites.image && sprites.image(cut.portrait);
  if (portrait && portrait.naturalWidth) {
    ctx.save();
    ctx.beginPath();
    ctx.rect(x + 8, y + 8, w - 16, h - 16);
    ctx.clip();
    const zoom = 1.55;
    const dw = (h - 16) * zoom * (portrait.naturalWidth / portrait.naturalHeight);
    const dh = (h - 16) * zoom;
    const dx = left ? x + 18 : x + w - 18 - dw;
    const dy = y - dh * 0.08;
    if (!left) {
      ctx.translate(dx + dw, dy);
      ctx.scale(-1, 1);
      ctx.drawImage(portrait, 0, 0, dw, dh);
    } else {
      ctx.drawImage(portrait, dx, dy, dw, dh);
    }
    ctx.restore();
  }

  const frame = animFrames("cutinFrame")[0];
  const fimg = frame && images.get(frame.file);
  if (fimg && fimg.naturalWidth) {
    ctx.globalCompositeOperation = "lighter";
    ctx.globalAlpha = 0.95 * fade;
    ctx.drawImage(fimg, x - 8, y - 6, w + 16, h + 12);
    ctx.globalCompositeOperation = "source-over";
  }

  ctx.fillStyle = "#39ff14";
  ctx.font = "bold 22px sans-serif";
  ctx.shadowColor = "#39ff14";
  ctx.shadowBlur = 14;
  ctx.textAlign = left ? "left" : "right";
  ctx.fillText(cut.title || "RX OVERDRIVE", left ? x + 18 : x + w - 18, y + h - 18);
  ctx.shadowBlur = 0;
  ctx.font = "bold 11px monospace";
  ctx.fillStyle = "#c44cff";
  ctx.fillText("CINO  ·  SUPER", left ? x + 18 : x + w - 18, y + 22);
  ctx.textAlign = "left";
  ctx.restore();
}
