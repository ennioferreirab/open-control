"use client";

import { ReactNode } from "react";
// eslint-disable-next-line no-restricted-imports -- root provider must import from convex/react directly
import { ConvexProvider, ConvexReactClient } from "convex/react";

const convex = new ConvexReactClient(process.env.NEXT_PUBLIC_CONVEX_URL!);

<<<<<<< HEAD
export function ConvexClientProvider({ children }: { children: ReactNode }) {
=======
export default function ConvexClientProvider({ children }: { children: ReactNode }) {
>>>>>>> worktree-agent-aacc91e7
  return <ConvexProvider client={convex}>{children}</ConvexProvider>;
}
