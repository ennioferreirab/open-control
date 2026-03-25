"use client";

import { ReactNode, useMemo } from "react";
// eslint-disable-next-line no-restricted-imports -- root provider must import from convex/react directly
import { ConvexProvider, ConvexReactClient } from "convex/react";

function getConvexUrl(): string {
  return process.env.NEXT_PUBLIC_CONVEX_URL!;
}

export function ConvexClientProvider({ children }: { children: ReactNode }) {
  const convex = useMemo(() => new ConvexReactClient(getConvexUrl()), []);
  return <ConvexProvider client={convex}>{children}</ConvexProvider>;
}
