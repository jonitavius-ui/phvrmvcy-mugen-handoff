export const TICK = 1 / 60;
/** Scale Align LOCKED. Idle feet/ground → head crown (NOT hair tip). Median 212. Exclude s1_010 drink pose. Reference s1_001_IDLE.png. */
export const CINO_BASE_HEIGHT = 212;
/** Diagnostic only. Opaque-with-hair ≈249. NEVER use for body scale. */
export const CINO_OPAQUE_WITH_HAIR = 249;
/** Roster BASE SCALE 100%. Future fighters side-by-side test idle body against this. */
export const CINO_BASE_SCALE = 1;
export const CINO_SPRITE_ZOOM = 2;
export const CINO_ATLAS_BODY_HEIGHT = 106;
export const CINO_BULL_SCALE = 1.18;
export const CINO_FX_SCALE = 1.75;
export const STAGES: Array<{ id: string; name: string; short: string; tag: string; accent: string }>;
export const ROSTER: unknown[];
export const INITIAL_SNAP: {
  mode: string;
  kind: string;
  selectIndex: number;
  stageIndex: number;
  p1Id: string;
  p2Id: string;
  p1Name: string;
  p2Name: string;
  p1Hp: number;
  p2Hp: number;
  p1HpChip: number;
  p2HpChip: number;
  p1Max: number;
  p2Max: number;
  p1Meter: number;
  p2Meter: number;
  p1Portrait: string;
  p2Portrait: string;
  p1Accent: string;
  p2Accent: string;
  round: number;
  wins: number[];
  timer: number;
  banner: string;
  combo: number;
  paused: boolean;
  muted: boolean;
  winner: number | null;
  p1Speech: string;
  p2Speech: string;
  stageId: string;
  stageName: string;
};
export function createStage(id: string): { load: () => void; draw: (ctx: CanvasRenderingContext2D, t: number, x: number, s: number) => void; def: { id: string } };
export function stageById(id: string): { id: string; name: string; tag: string; accent: string };
export class GameEngine {
  constructor(canvas: HTMLCanvasElement, onSnap?: ((snap: typeof INITIAL_SNAP) => void) | null);
  boot(): Promise<void>;
  attach(): void;
  detach(): void;
  snapshot(): typeof INITIAL_SNAP;
  tapCpu(): void;
  tapP2(): void;
  tapHowTo(): void;
  tapConfirm(): void;
  tapTitle(): void;
  tapPause(): void;
  sfx: { muted: boolean; toggle: () => boolean };
  session: {
    roster: Array<{ id: string; short: string; style: string; accent: string; portrait: string; selectSprite?: string }>;
    selectIndex: number;
    stageIndex: number;
    stageId: string;
  };
  input: { p1: { set: (key: string, value: boolean) => void } };
}
