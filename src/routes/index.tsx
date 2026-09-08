import { createFileRoute } from "@tanstack/react-router";
import { MugenGameApp } from "@/game/MugenGameApp";

export const Route = createFileRoute("/")({ component: Home });

function Home() {
  return <MugenGameApp />;
}
