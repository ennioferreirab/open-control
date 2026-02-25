import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Derive a 1-2 character initials string from an agent name.
 * Splits on whitespace, hyphens, and underscores.
 */
export function getAgentInitials(agentName: string): string {
  return agentName
    .split(/[\s\-_]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? "")
    .join("");
}
