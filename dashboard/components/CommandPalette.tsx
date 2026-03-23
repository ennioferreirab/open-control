"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
}

export function CommandPalette({ isOpen, onClose }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const prefersReducedMotion = useReducedMotion();

  // Close on Escape + reset query when opening
  useEffect(() => {
    if (!isOpen) return;
    /* eslint-disable-next-line react-hooks/set-state-in-effect -- reset on open is intentional */
    setQuery("");
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            className="fixed inset-0 z-50 bg-black/60"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          {/* Palette */}
          <motion.div
            className="fixed left-1/2 top-[20%] z-50 w-[560px] max-w-[calc(100vw-2rem)] -translate-x-1/2 overflow-hidden rounded-xl border border-border bg-card shadow-2xl"
            initial={{
              opacity: 0,
              scale: prefersReducedMotion ? 1 : 0.95,
              y: prefersReducedMotion ? 0 : -10,
            }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{
              opacity: 0,
              scale: prefersReducedMotion ? 1 : 0.95,
              y: prefersReducedMotion ? 0 : -10,
            }}
            transition={{ duration: prefersReducedMotion ? 0 : 0.15 }}
          >
            {/* Search input */}
            <div className="flex items-center gap-3 border-b border-border px-4 py-3">
              <Search className="h-4 w-4 text-muted-foreground" />
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search tasks, agents, or commands..."
                className={cn(
                  "flex-1 bg-transparent text-base text-foreground placeholder:text-muted-foreground",
                  "focus-visible:outline-none",
                )}
              />
              <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                ESC
              </kbd>
            </div>

            {/* Results placeholder */}
            <div className="max-h-[400px] overflow-y-auto p-2">
              {query ? (
                <div className="px-3 py-8 text-center text-sm text-muted-foreground">
                  Search functionality coming soon...
                </div>
              ) : (
                <div className="px-3 py-8 text-center text-sm text-muted-foreground">
                  Type to search tasks, agents, or commands
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between border-t border-border px-4 py-2">
              <div className="flex gap-1">
                <span className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                  All
                </span>
                <span className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                  Tasks
                </span>
                <span className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                  Agents
                </span>
              </div>
              <div className="flex gap-3 text-[10px] text-muted-foreground">
                <span>
                  <kbd className="font-mono">↑↓</kbd> navigate
                </span>
                <span>
                  <kbd className="font-mono">↵</kbd> select
                </span>
                <span>
                  <kbd className="font-mono">esc</kbd> close
                </span>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
