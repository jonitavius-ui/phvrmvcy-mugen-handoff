import { createFileRoute } from "@tanstack/react-router";
import { MugenGameApp } from "@/game/MugenGameApp";

export const Route = createFileRoute("/mugen")({ component: Page });

function Page() {
  return <MugenGameApp />;
}
