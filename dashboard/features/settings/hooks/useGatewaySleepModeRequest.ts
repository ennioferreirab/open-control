"use client";

import { useMutation } from "convex/react";
import { api } from "@/convex/_generated/api";

export function useGatewaySleepModeRequest() {
  return useMutation(api.settings.requestGatewaySleepMode);
}
