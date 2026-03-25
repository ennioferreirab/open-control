const AVATAR_COLORS = [
  "bg-blue-500",
  "bg-emerald-500",
  "bg-violet-500",
  "bg-amber-500",
  "bg-rose-500",
  "bg-cyan-500",
  "bg-indigo-500",
  "bg-teal-500",
];

/**
 * Get 2-character initials from an agent name or display name.
 * Handles slug format ("brand-reviewer" → "BR"), space-separated ("Brand Reviewer" → "BR"),
 * and single words ("orchestrator" → "OR"). Returns "??" for empty/null/undefined input.
 */
export function getInitials(nameOrDisplayName: string | undefined | null): string {
  if (!nameOrDisplayName) return "??";
  const name = nameOrDisplayName.trim();
  if (!name) return "??";

  // Handle slug format: "brand-reviewer" → "BR", "code-monkey" → "CM"
  if (name.includes("-")) {
    const parts = name.split("-").filter(Boolean);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return parts[0].substring(0, 2).toUpperCase();
  }

  // Handle space-separated: "Brand Reviewer" → "BR"
  const words = name.split(/\s+/).filter(Boolean);
  if (words.length >= 2) {
    return (words[0][0] + words[1][0]).toUpperCase();
  }

  // Single word: "orchestrator" → "OR"
  return name.substring(0, 2).toUpperCase();
}

/**
 * Deterministic color from agent name hash.
 * Returns a Tailwind bg color class (e.g., "bg-blue-500").
 */
export function getAvatarColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}
