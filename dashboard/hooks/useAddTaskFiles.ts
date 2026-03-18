"use client";

import { useMutation } from "convex/react";
import { api } from "@/convex/_generated/api";

/** Wraps the tasks.addTaskFiles mutation. */
export function useAddTaskFiles() {
  return useMutation(api.tasks.addTaskFiles);
}
