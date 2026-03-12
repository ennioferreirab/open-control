"use client";

import { useQuery } from "convex/react";

import { api } from "@/convex/_generated/api";

export function useSkillsSelectorData() {
  return useQuery(api.skills.list);
}
