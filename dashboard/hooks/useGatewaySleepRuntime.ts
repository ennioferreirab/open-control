import { useQuery } from "convex/react";

import { api } from "../convex/_generated/api";
import type { GatewaySleepRuntime } from "@/lib/gatewaySleepRuntime";

export function useGatewaySleepRuntime():
  | GatewaySleepRuntime
  | null
  | undefined {
  return useQuery(api.settings.getGatewaySleepRuntime);
}
