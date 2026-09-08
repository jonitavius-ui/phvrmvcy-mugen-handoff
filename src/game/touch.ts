import type { PointerEvent, TouchEvent, SyntheticEvent } from "react";

type HoldFn = (down: boolean) => void;

function press(set: HoldFn, down: boolean, ev: PointerEvent | TouchEvent) {
  ev.preventDefault();
  set(down);
  const anyEv = ev as PointerEvent;
  if (down && anyEv.pointerId != null && anyEv.currentTarget?.setPointerCapture) {
    try {
      anyEv.currentTarget.setPointerCapture(anyEv.pointerId);
    } catch {
      /* ignore */
    }
  }
}

export function preventMenu(ev: SyntheticEvent) {
  ev.preventDefault();
}

export function bindHold(set: HoldFn) {
  return {
    onPointerDown: (ev: PointerEvent) => press(set, true, ev),
    onPointerUp: (ev: PointerEvent) => press(set, false, ev),
    onPointerCancel: (ev: PointerEvent) => press(set, false, ev),
    onPointerLeave: (ev: PointerEvent) => {
      ev.preventDefault();
      const t = ev.currentTarget as HTMLElement;
      if (!(ev.pointerId != null && t.hasPointerCapture?.(ev.pointerId))) set(false);
    },
    onLostPointerCapture: (ev: PointerEvent) => press(set, false, ev),
    onTouchStart: (ev: TouchEvent) => press(set, true, ev),
    onTouchEnd: (ev: TouchEvent) => press(set, false, ev),
    onTouchCancel: (ev: TouchEvent) => press(set, false, ev),
    onContextMenu: preventMenu,
    draggable: false as const,
    "data-game-control": "true" as const,
  };
}

export function lockGameGestures(root: HTMLElement) {
  const block = (e: Event) => e.preventDefault();
  const gated = (e: Event) => {
    const t = e.target;
    if (!(t instanceof Element)) return;
    if (t.closest(".game-scroll-panel, input, textarea, select")) return;
    if (t.closest("[data-game-control], canvas")) e.preventDefault();
  };
  root.addEventListener("contextmenu", block);
  root.addEventListener("selectstart", block);
  root.addEventListener("dragstart", block);
  root.addEventListener("touchstart", gated, { passive: false, capture: true });
  root.addEventListener("touchmove", gated, { passive: false, capture: true });
  root.addEventListener("pointerdown", gated, { passive: false, capture: true });
  return () => {
    root.removeEventListener("contextmenu", block);
    root.removeEventListener("selectstart", block);
    root.removeEventListener("dragstart", block);
    root.removeEventListener("touchstart", gated, true);
    root.removeEventListener("touchmove", gated, true);
    root.removeEventListener("pointerdown", gated, true);
  };
}
