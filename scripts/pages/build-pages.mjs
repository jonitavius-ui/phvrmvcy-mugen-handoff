import * as esbuild from "esbuild";
import { mkdirSync } from "node:fs";

mkdirSync("dist-pages", { recursive: true });

await esbuild.build({
  entryPoints: ["scripts/pages/mugen-pages-entry.tsx"],
  bundle: true,
  outfile: "dist-pages/game.js",
  format: "iife",
  platform: "browser",
  target: ["es2019"],
  jsx: "automatic",
  minify: true,
  sourcemap: false,
  define: {
    "process.env.NODE_ENV": '"production"',
  },
  alias: {
    "@tanstack/react-router": "./scripts/pages/router-stub.ts",
    "@/game/MugenGameApp": "./src/game/MugenGameApp.tsx",
  },
  loader: {
    ".js": "jsx",
  },
  logLevel: "info",
});

console.log("built dist-pages/game.js");
