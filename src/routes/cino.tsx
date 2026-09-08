import { createFileRoute, Link } from "@tanstack/react-router";

export const Route = createFileRoute("/cino")({ component: CinoPage });

function CinoPage() {
  return (
    <main className="flex min-h-[100dvh] flex-col items-center justify-center bg-[#050208] px-6 text-center text-white">
      <p className="font-mono text-[10px] tracking-[0.3em] text-[#39ff14]">CINO DIGITAL / PHVRMVCY</p>
      <h1 className="mt-3 font-display text-4xl tracking-tight">3D WORLD</h1>
      <p className="mt-2 max-w-md font-mono text-xs text-purple-300">
        The 3D gallery lives on the original Cino site. This update keeps the fighter intact.
      </p>
      <Link
        to="/"
        className="mt-6 border border-[#39ff14] px-4 py-2 font-display text-xs tracking-[0.2em] text-[#39ff14]"
      >
        BACK TO MUGEN
      </Link>
    </main>
  );
}
