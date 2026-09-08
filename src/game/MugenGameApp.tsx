import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import { GameEngine, INITIAL_SNAP, STAGES, createStage } from "./engine.js";
import { bindHold, lockGameGestures, preventMenu } from "./touch";

type Snap = typeof INITIAL_SNAP;

type Engine = GameEngine & {
  sfx: { muted: boolean; toggle: () => boolean };
  session: {
    roster: Array<{
      id: string;
      short: string;
      style: string;
      accent: string;
      portrait: string;
      selectSprite?: string;
    }>;
    selectIndex: number;
    stageIndex: number;
    stageId: string;
  };
  snapshot: () => Snap;
  boot: () => Promise<void>;
  attach: () => void;
  detach: () => void;
  tapCpu: () => void;
  tapP2: () => void;
  tapHowTo: () => void;
  tapConfirm: () => void;
  tapTitle: () => void;
  tapPause: () => void;
  input: { p1: { set: (k: string, v: boolean) => void } };
};

const P1_HELP = [
  { keys: "A / D", action: "Walk (F/B flip with facing)" },
  { keys: "W / S", action: "Jump / Crouch" },
  { keys: "J / pad A", action: "Light Jab" },
  { keys: "K / pad B", action: "Heavy Swing" },
  { keys: "L / pad C", action: "Special 1 (Cino splash / SB coin)" },
  { keys: "Space / pad D", action: "Power (Cino rush / SB zone)" },
  { keys: "Shift", action: "Block" },
  { keys: "↓→ + C", action: "Special 1" },
  { keys: "↓← + C", action: "Special 2 (Chart Breaker)" },
  { keys: "↓→ + D", action: "Super (full meter)" },
  { keys: "→→", action: "Dash" },
  { keys: "QCF / DP / QCB", action: "Advanced MUGEN motions" },
];

const P2_HELP = [
  { keys: "← →", action: "Walk (F/B facing-relative)" },
  { keys: "↑ ↓", action: "Jump / Crouch" },
  { keys: "U / Num1", action: "Light (x)" },
  { keys: "I / Num2", action: "Heavy (y)" },
  { keys: "O / Num3", action: "Kick (a)" },
  { keys: "[ / Num4", action: "Special (D)" },
  { keys: "P / Num0", action: "Block" },
];

const neon = "border border-[#39ff14] bg-[#39ff14]/15 px-4 py-2 font-display text-xs tracking-[0.2em] text-[#39ff14] hover:bg-[#39ff14]/25";
const ghost = "border border-purple-600 px-4 py-2 font-display text-xs tracking-[0.2em] text-purple-100 hover:border-[#39ff14]";

const LOBBY_ITEMS = [
  { id: "cpu", title: "VS CPU", sub: "PRACTICE  ·  LEVEL UP  ·  HONE YOUR SKILLS" },
  { id: "p2", title: "LOCAL VS", sub: "PLAYER 1 VS PLAYER 2" },
  { id: "select", title: "CHARACTER SELECT", sub: "BUILD YOUR ROSTER" },
  { id: "moves", title: "MOVE LIST", sub: "KNOW YOUR WEAPONS" },
  { id: "training", title: "TRAINING", sub: "LAB  ·  COMBOS  ·  SETTINGS" },
  { id: "options", title: "OPTIONS", sub: "AUDIO  ·  HUD  ·  CONTROLS  ·  MORE" },
] as const;

export function MugenGameApp() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const shellRef = useRef<HTMLDivElement>(null);
  const engineRef = useRef<Engine | null>(null);
  const [snap, setSnap] = useState<Snap>(INITIAL_SNAP as Snap);
  const [ready, setReady] = useState(false);
  const [panel, setPanel] = useState<null | "training" | "options">(null);
  const onSnap = useCallback((next: Snap) => setSnap(next), []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const engine = new GameEngine(canvas, onSnap) as Engine;
    engineRef.current = engine;
    let dead = false;
    engine.boot().then(() => {
      if (dead) return;
      engine.attach();
      setReady(true);
      setSnap(engine.snapshot());
    });
    const unlock = shellRef.current ? lockGameGestures(shellRef.current) : undefined;
    return () => {
      dead = true;
      engine.detach();
      unlock?.();
    };
  }, [onSnap]);

  const engine = engineRef.current;
  const inFight = snap.mode === "fight" || snap.mode === "pause" || snap.mode === "ko";
  const onTitle = snap.mode === "title";

  return (
    <div
      id="mugen"
      ref={shellRef}
      className="game-play-shell relative flex min-h-[100dvh] flex-col overflow-hidden bg-[#050208] text-white"
      onContextMenu={preventMenu}
    >
      {!onTitle && (
        <header className="relative z-20 flex items-center justify-between gap-2 border-b border-purple-800/60 bg-black/75 px-2 py-1.5 backdrop-blur-md sm:px-3">
          <div className="min-w-0">
            <p className="font-display text-[11px] tracking-[0.28em] text-[#39ff14] sm:text-xs">CINO DIGITAL / PHVRMVCY</p>
            <p className="font-terminal text-[9px] tracking-[0.2em] text-purple-300/80">
              {inFight ? `${snap.p1Name} vs ${snap.p2Name} · ${snap.stageName}` : "MUGEN  ·  RISK NOTHING. GAIN EVERYTHING."}
            </p>
          </div>
          <div className="flex items-center gap-1.5">
            <Link to="/" className="border border-purple-800/70 px-2 py-1 font-mono text-[10px] uppercase tracking-widest text-purple-200 hover:border-[#39ff14]">
              HUD
            </Link>
            <Link to="/cino" className="border border-purple-800/70 px-2 py-1 font-mono text-[10px] uppercase tracking-widest text-purple-200 hover:border-[#39ff14]">
              3D
            </Link>
            <button
              type="button"
              onClick={() => {
                engine?.sfx.toggle();
                if (engine) setSnap({ ...engine.snapshot(), muted: engine.sfx.muted });
              }}
              className="border border-purple-800/70 px-2 py-1 font-mono text-[10px] text-purple-100"
            >
              {snap.muted ? "SFX OFF" : "SFX ON"}
            </button>
            <button type="button" onClick={() => engine?.tapPause()} className="border border-[#39ff14]/50 px-2 py-1 font-mono text-[10px] text-[#39ff14]">
              {snap.mode === "pause" ? "RESUME" : "PAUSE"}
            </button>
          </div>
        </header>
      )}

      <div className="relative z-10 min-h-[240px] flex-1" data-game-stage="">
        <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" />
        {!ready && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-[#050208] font-display text-sm tracking-[0.28em] text-[#39ff14]">
            LOADING TRVP EXCHANGE…
          </div>
        )}
        {snap.mode === "title" && (
          <LobbyHome
            muted={snap.muted}
            panel={panel}
            onCpu={() => { setPanel(null); engine?.tapCpu(); }}
            onP2={() => { setPanel(null); engine?.tapP2(); }}
            onSelect={() => { setPanel(null); engine?.tapCpu(); }}
            onHowTo={() => { setPanel(null); engine?.tapHowTo(); }}
            onTraining={() => setPanel(panel === "training" ? null : "training")}
            onOptions={() => setPanel(panel === "options" ? null : "options")}
            onToggleSfx={() => {
              engine?.sfx.toggle();
              if (engine) setSnap({ ...engine.snapshot(), muted: engine.sfx.muted });
            }}
            onClosePanel={() => setPanel(null)}
          />
        )}
        {snap.mode === "select" && <SelectOverlay snap={snap} engine={engine} />}
        {snap.mode === "stage" && <StageOverlay snap={snap} engine={engine} />}
        {snap.mode === "howto" && <HowTo onBack={() => engine?.tapTitle()} />}
        {snap.mode === "victory" && (
          <div className="pointer-events-auto absolute inset-0 z-40 flex items-center justify-center bg-black/55 p-3">
            <div className="w-full max-w-md border border-[#39ff14]/70 bg-[#0a0612]/95 px-4 py-5 text-center">
              <p className="font-display text-sm tracking-[0.22em] text-[#39ff14]">{snap.banner || "MATCH OVER"}</p>
              <p className="mt-2 font-display text-3xl">{snap.winner === 1 ? snap.p2Name : snap.p1Name} WINS</p>
              <p className="mt-2 font-mono text-xs text-purple-200">COOKIN THE CHARTS</p>
              <div className="mt-4 flex justify-center gap-2">
                <button type="button" onClick={() => engine?.tapCpu()} className={neon}>REMATCH</button>
                <button type="button" onClick={() => engine?.tapTitle()} className={ghost}>TITLE</button>
              </div>
            </div>
          </div>
        )}
      </div>

      {(snap.mode === "fight" || snap.mode === "pause") && <MoveStrip p1Id={snap.p1Id} />}
      {!onTitle && <TouchBar engine={engine} />}
      {!onTitle && (
        <p className="relative z-20 border-t border-purple-900/70 bg-black px-2 py-1 font-mono text-[9px] uppercase tracking-[0.14em] text-purple-300/70">
          2D arcade fighter · sprites from Cino / SB sheets · fake SOL only · PHVRMVCY WORLDWIDE
        </p>
      )}
    </div>
  );
}

function LobbyHome({
  muted,
  panel,
  onCpu,
  onP2,
  onSelect,
  onHowTo,
  onTraining,
  onOptions,
  onToggleSfx,
  onClosePanel,
}: {
  muted: boolean;
  panel: null | "training" | "options";
  onCpu: () => void;
  onP2: () => void;
  onSelect: () => void;
  onHowTo: () => void;
  onTraining: () => void;
  onOptions: () => void;
  onToggleSfx: () => void;
  onClosePanel: () => void;
}) {
  const [index, setIndex] = useState(0);
  const indexRef = useRef(0);
  const panelRef = useRef(panel);
  const locked = useRef(false);
  indexRef.current = index;
  panelRef.current = panel;

  const fire = useCallback((id: (typeof LOBBY_ITEMS)[number]["id"]) => {
    if (id === "cpu") onCpu();
    else if (id === "p2") onP2();
    else if (id === "select") onSelect();
    else if (id === "moves") onHowTo();
    else if (id === "training") onTraining();
    else onOptions();
  }, [onCpu, onP2, onSelect, onHowTo, onTraining, onOptions]);

  useEffect(() => {
    const confirm = () => {
      if (panelRef.current) {
        onClosePanel();
        return;
      }
      fire(LOBBY_ITEMS[indexRef.current].id);
    };
    const move = (dir: number) => {
      if (panelRef.current) return;
      setIndex((i) => (i + dir + LOBBY_ITEMS.length) % LOBBY_ITEMS.length);
    };
    const onKey = (e: KeyboardEvent) => {
      const k = e.key;
      if (k === "ArrowDown" || k === "s" || k === "S") {
        e.preventDefault();
        move(1);
      } else if (k === "ArrowUp" || k === "w" || k === "W") {
        e.preventDefault();
        move(-1);
      } else if (k === "Enter" || k === "j" || k === "J" || k === " ") {
        e.preventDefault();
        confirm();
      } else if ((k === "Escape" || k === "Backspace") && panelRef.current) {
        e.preventDefault();
        onClosePanel();
      }
    };
    window.addEventListener("keydown", onKey, true);
    let raf = 0;
    const poll = () => {
      const pads = typeof navigator !== "undefined" && navigator.getGamepads ? navigator.getGamepads() : [];
      const pad = pads[0];
      if (pad) {
        const up = pad.buttons[12]?.pressed || (pad.axes[1] ?? 0) < -0.55;
        const down = pad.buttons[13]?.pressed || (pad.axes[1] ?? 0) > 0.55;
        const ok = pad.buttons[0]?.pressed || pad.buttons[9]?.pressed;
        const back = pad.buttons[1]?.pressed || pad.buttons[8]?.pressed;
        if (up || down || ok || back) {
          if (!locked.current) {
            locked.current = true;
            if (back && panelRef.current) onClosePanel();
            else if (ok) confirm();
            else if (down) move(1);
            else if (up) move(-1);
          }
        } else locked.current = false;
      }
      raf = requestAnimationFrame(poll);
    };
    raf = requestAnimationFrame(poll);
    return () => {
      window.removeEventListener("keydown", onKey, true);
      cancelAnimationFrame(raf);
    };
  }, [fire, onClosePanel]);

  return (
    <div className="pointer-events-none absolute inset-0 z-30 overflow-hidden bg-[#07010c]">
      <img
        src="/mugen/stages/lobby-bg.jpg"
        alt=""
        className="pointer-events-none absolute inset-0 h-full w-full object-cover object-[center_38%]"
      />
      <div className="lobby-scan pointer-events-none absolute inset-0 mix-blend-soft-light opacity-35" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[42%] bg-gradient-to-b from-black/25 via-transparent to-transparent" />
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-[58%] bg-gradient-to-t from-black/70 via-[#120018]/45 to-transparent" />

      <div className="pointer-events-auto absolute inset-x-0 bottom-[6%] flex flex-col items-center px-3 sm:bottom-[7%]">
        <nav className="flex w-full max-w-[34rem] flex-col gap-1.5" aria-label="Main menu">
          {LOBBY_ITEMS.map((item, i) => {
            const on = i === index;
            return (
              <button
                key={item.id}
                type="button"
                onMouseEnter={() => setIndex(i)}
                onClick={() => fire(item.id)}
                className={`lobby-btn min-h-11 sm:min-h-12 ${on ? "lobby-btn-on" : ""}`}
              >
                <span className="block font-display text-sm leading-none tracking-[0.2em] sm:text-lg">{item.title}</span>
                <span className={`mt-0.5 block font-mono text-[8px] tracking-[0.2em] ${on ? "text-[#d8ff9a]" : "text-purple-200/75"}`}>
                  {item.sub}
                </span>
              </button>
            );
          })}
        </nav>
        <p className="mt-3 font-display text-[11px] tracking-[0.36em] text-white/75 sm:text-sm">PRESS START / TAP TO ENTER</p>
        <p className="mt-1 font-mono text-[8px] tracking-[0.18em] text-purple-300/70">↑↓ / W S  ·  ENTER / J / A  ·  TOUCH</p>
      </div>

      {panel === "training" && (
        <div className="pointer-events-auto absolute inset-0 z-40 flex items-end justify-center bg-black/55 p-3 sm:items-center">
          <div className="game-scroll-panel max-h-[70vh] w-full max-w-lg overflow-auto border border-[#39ff14]/50 bg-[#0a0612]/95 p-4">
            <p className="font-display text-lg tracking-[0.22em] text-[#39ff14]">TRAINING LAB</p>
            <p className="mt-1 font-mono text-[10px] text-purple-300">Same fighter engine. Lab notes only.</p>
            <div className="mt-3 space-y-1">
              {P1_HELP.map((row) => (
                <p key={row.keys} className="font-mono text-[11px] text-white">
                  <span className="text-[#39ff14]">{row.keys}</span> — {row.action}
                </p>
              ))}
            </div>
            <button type="button" onClick={onClosePanel} className={`${neon} mt-4`}>BACK</button>
          </div>
        </div>
      )}

      {panel === "options" && (
        <div className="pointer-events-auto absolute inset-0 z-40 flex items-end justify-center bg-black/55 p-3 sm:items-center">
          <div className="w-full max-w-md border border-purple-500/60 bg-[#0a0612]/95 p-4">
            <p className="font-display text-lg tracking-[0.22em] text-[#c44cff]">OPTIONS</p>
            <button type="button" onClick={onToggleSfx} className={`${ghost} mt-4 w-full text-left`}>
              AUDIO · {muted ? "SFX OFF" : "SFX ON"}
            </button>
            <p className="mt-3 font-mono text-[10px] leading-5 text-purple-300">
              HUD and touch pad appear after the match starts. Keyboard map is in MOVE LIST.
            </p>
            <button type="button" onClick={onClosePanel} className={`${neon} mt-4`}>BACK</button>
          </div>
        </div>
      )}
    </div>
  );
}

function SelectOverlay({ snap, engine }: { snap: Snap; engine: Engine | null }) {
  const roster = engine?.session.roster ?? [];
  return (
    <div className="pointer-events-auto absolute inset-0 z-30 flex flex-col items-center justify-center bg-black/50 p-3">
      <p className="font-display text-sm tracking-[0.28em] text-[#39ff14]">SELECT YOUR HUSTLER</p>
      <p className="mt-1 font-mono text-[10px] text-purple-200">{snap.kind === "cpu" ? "CPU GETS THE OTHER" : "P2 GETS THE OTHER"}</p>
      <div className="mt-4 flex max-h-[58vh] flex-wrap justify-center gap-2 overflow-y-auto">
        {roster.map((fighter, index) => (
          <button
            type="button"
            key={fighter.id}
            onClick={() => {
              if (!engine) return;
              engine.session.selectIndex = index;
              engine.tapConfirm();
            }}
            className={`w-40 border p-2 text-left ${index === snap.selectIndex ? "border-[#39ff14] bg-[#39ff14]/10" : "border-purple-700 bg-black/60"}`}
          >
            <img src={fighter.selectSprite || fighter.portrait} alt="" className="mx-auto h-24 w-20 object-contain" />
            <p className="mt-2 font-display text-sm" style={{ color: fighter.accent }}>{fighter.short}</p>
            <p className="font-mono text-[9px] text-purple-300">{fighter.style}</p>
          </button>
        ))}
      </div>
      <p className="mt-3 font-mono text-[10px] text-purple-300">A/D change · J / ENTER confirm</p>
      <button type="button" onClick={() => engine?.tapTitle()} className={`${ghost} mt-3`}>BACK</button>
    </div>
  );
}

function StageOverlay({ snap, engine }: { snap: Snap; engine: Engine | null }) {
  return (
    <div className="pointer-events-auto absolute inset-0 z-30 flex flex-col items-center justify-center bg-black/55 p-3">
      <p className="font-display text-sm tracking-[0.28em] text-[#39ff14]">SELECT STAGE</p>
      <p className="mt-1 font-mono text-[10px] text-purple-200">{snap.stageName}</p>
      <div className="mt-3 grid w-full max-w-3xl grid-cols-2 gap-2 sm:grid-cols-3">
        {STAGES.map((stage, index) => (
          <button
            type="button"
            key={stage.id}
            onClick={() => {
              if (!engine) return;
              engine.session.stageIndex = index;
              engine.tapConfirm();
            }}
            className={`border p-2 text-left ${index === snap.stageIndex ? "border-[#39ff14] bg-[#39ff14]/10" : "border-purple-700 bg-black/60"}`}
          >
            <StageThumb id={stage.id} />
            <p className="mt-1 font-display text-sm" style={{ color: stage.accent }}>{stage.short}</p>
            <p className="font-mono text-[8px] text-purple-300">{stage.tag}</p>
          </button>
        ))}
      </div>
      <button type="button" onClick={() => engine?.tapTitle()} className={`${ghost} mt-3`}>TITLE</button>
    </div>
  );
}

function StageThumb({ id }: { id: string }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const stage = createStage(id) as { load: () => void; draw: (c: CanvasRenderingContext2D, t: number, x: number, s: number) => void };
    stage.load();
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = (now - start) / 1000;
      ctx.setTransform(canvas.width / 960, 0, 0, canvas.height / 540, 0, 0);
      stage.draw(ctx, t, 480, 0);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [id]);
  return <canvas ref={ref} width={240} height={96} className="h-16 w-full bg-black object-cover" />;
}

function HowTo({ onBack }: { onBack: () => void }) {
  return (
    <div className="pointer-events-auto absolute inset-0 z-30 flex items-end justify-center bg-black/60 p-3 sm:items-center">
      <div className="game-scroll-panel max-h-[78vh] w-full max-w-2xl overflow-auto border border-purple-600/60 bg-[#0a0612]/95 p-4">
        <p className="font-display text-lg tracking-[0.22em] text-[#39ff14]">MOVE LIST</p>
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          <div>
            <p className="font-display text-sm text-[#c44cff]">PLAYER 1</p>
            {P1_HELP.map((row) => (
              <p key={row.keys} className="mt-1 font-mono text-[11px] text-white">
                <span className="text-[#39ff14]">{row.keys}</span> — {row.action}
              </p>
            ))}
          </div>
          <div>
            <p className="font-display text-sm text-[#c44cff]">PLAYER 2</p>
            {P2_HELP.map((row) => (
              <p key={row.keys} className="mt-1 font-mono text-[11px] text-white">
                <span className="text-[#39ff14]">{row.keys}</span> — {row.action}
              </p>
            ))}
          </div>
        </div>
        <button type="button" onClick={onBack} className={`${neon} mt-4`}>BACK</button>
      </div>
    </div>
  );
}

function MoveStrip({ p1Id }: { p1Id: string }) {
  const pack = p1Id === "sb"
    ? {
        cards: [
          { button: "A", name: "Light Jab", detail: "fast / low dmg" },
          { button: "B", name: "Heavy Swing", detail: "slow / knockback" },
          { button: "C", name: "Coin Flip", detail: "gold projectile" },
          { button: "D", name: "Liquidity Zone", detail: "chart trap" },
        ],
        commands: "↓→ + C Coin Flip  ·  ↓← + C Chart Breaker  ·  ↓→ + D SB Cookin Supreme",
      }
    : {
        cards: [
          { button: "A", name: "Light Jab", detail: "fast / low dmg" },
          { button: "B", name: "Heavy Swing", detail: "slow / knockback" },
          { button: "C", name: "Lean Splash", detail: "purple projectile" },
          { button: "D", name: "Green Candle Rush", detail: "dash smash" },
        ],
        commands: "↓→ + C Lean Splash  ·  ↓← + C Chart Breaker  ·  ↓→ + D RX Overdrive",
      };
  return (
    <div className="relative z-20 border-t border-purple-900/70 bg-black/85 px-2 py-1.5">
      <p className="font-mono text-[9px] tracking-[0.22em] text-[#39ff14]">MOVES / COMMANDS</p>
      <div className="mt-1 grid grid-cols-4 gap-1">
        {pack.cards.map((card) => (
          <div key={card.button} className="border border-purple-800/70 bg-black/50 px-1 py-1">
            <p className="font-mono text-[10px] text-[#39ff14]">
              {card.button} <span className="text-white">{card.name}</span>
            </p>
            <p className="font-mono text-[8px] text-purple-300">{card.detail}</p>
          </div>
        ))}
      </div>
      <p className="mt-1 font-mono text-[9px] text-purple-200">{pack.commands}</p>
    </div>
  );
}

function TouchBar({ engine }: { engine: Engine | null }) {
  const hold = (key: string) => bindHold((down) => engine?.input.p1.set(key, down));
  return (
    <div className="game-touch-bar relative z-20 flex items-end justify-between gap-3 border-t border-purple-900/70 bg-black/70 px-3 py-2" data-testid="mugen-touch">
      <DPad engine={engine} />
      <div className="mb-1 flex flex-col items-center gap-1">
        <button type="button" className="rounded-full border border-purple-700/70 px-3 py-1 font-mono text-[9px] text-purple-200" {...hold("block")}>BLK</button>
        <button type="button" className="rounded-full border border-[#39ff14]/50 px-3 py-1 font-mono text-[9px] text-[#39ff14]" onClick={() => engine?.tapConfirm()}>GO</button>
      </div>
      <div className="relative h-[118px] w-[132px]">
        <FaceBtn label="A" className="absolute bottom-1 left-8" color="#c44cff" {...hold("light")} />
        <FaceBtn label="B" className="absolute right-1 top-8" color="#39ff14" {...hold("heavy")} />
        <FaceBtn label="C" className="absolute left-1 top-8" color="#c44cff" {...hold("kick")} />
        <FaceBtn label="D" className="absolute left-8 top-0" color="#39ff14" {...hold("special")} />
      </div>
    </div>
  );
}

function FaceBtn({
  label,
  className,
  color,
  ...rest
}: {
  label: string;
  className: string;
  color: string;
} & ReturnType<typeof bindHold>) {
  return (
    <button
      type="button"
      className={`h-11 w-11 rounded-full border bg-black/40 font-mono text-[11px] text-white ${className}`}
      style={{ borderColor: color, boxShadow: `0 0 10px ${color}55` }}
      {...rest}
    >
      {label}
    </button>
  );
}

function DPad({ engine }: { engine: Engine | null }) {
  const held = useRef({ left: 0, right: 0, up: 0, down: 0 });
  const bind = (...keys: Array<"left" | "right" | "up" | "down">) =>
    bindHold((down) => {
      for (const key of keys) {
        held.current[key] = Math.max(0, held.current[key] + (down ? 1 : -1));
        engine?.input.p1.set(key, held.current[key] > 0);
      }
    });
  const cell = "flex h-9 w-9 items-center justify-center border border-white/25 bg-black/50 font-mono text-[11px] text-white active:bg-[#39ff14]/30";
  const diag = `${cell} text-[9px] text-white/70`;
  return (
    <div className="grid grid-cols-3 grid-rows-3 gap-0.5" data-testid="mugen-dpad" data-game-control="true" aria-label="Digital D-pad">
      <button type="button" className={diag} aria-label="Up-back" {...bind("up", "left")}>◤</button>
      <button type="button" className={cell} aria-label="Jump" {...bind("up")}>▲</button>
      <button type="button" className={diag} aria-label="Up-forward" {...bind("up", "right")}>◥</button>
      <button type="button" className={cell} aria-label="Back / Left" {...bind("left")}>◀</button>
      <span className="flex items-center justify-center font-mono text-[8px] uppercase tracking-widest text-purple-400">pad</span>
      <button type="button" className={cell} aria-label="Forward / Right" {...bind("right")}>▶</button>
      <button type="button" className={diag} aria-label="Down-back" {...bind("down", "left")}>◣</button>
      <button type="button" className={cell} aria-label="Crouch" {...bind("down")}>▼</button>
      <button type="button" className={diag} aria-label="Down-forward" {...bind("down", "right")}>◢</button>
    </div>
  );
}
