"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  useCommandPaletteSearch,
  type CommandPaletteAction,
  type CategoryFilter,
} from "@/hooks/useCommandPaletteSearch";
import { CommandPaletteResultItem } from "@/components/CommandPaletteResultItem";

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onAction: (action: CommandPaletteAction) => void;
}

const FILTER_LABELS: { value: CategoryFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "task", label: "Tasks" },
  { value: "agent", label: "Agents" },
  { value: "squad", label: "Squads" },
];

export function CommandPalette({ isOpen, onClose, onAction }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>("all");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const prefersReducedMotion = useReducedMotion();

  const { groups, flatResults } = useCommandPaletteSearch(isOpen, query, categoryFilter);

  // Refs for scrolling selected item into view
  const itemRefs = useRef<Map<number, HTMLButtonElement>>(new Map());

  // Reset state when palette opens — React "store previous prop" pattern
  const [prevIsOpen, setPrevIsOpen] = useState(false);
  if (isOpen !== prevIsOpen) {
    setPrevIsOpen(isOpen);
    if (isOpen) {
      setQuery("");
      setCategoryFilter("all");
      setSelectedIndex(0);
    }
  }

  // Reset selectedIndex when query or filter changes — inline in handlers
  const handleQueryChange = useCallback((value: string) => {
    setQuery(value);
    setSelectedIndex(0);
  }, []);

  const handleFilterChange = useCallback((value: CategoryFilter) => {
    setCategoryFilter(value);
    setSelectedIndex(0);
  }, []);

  // Keyboard navigation — subscribe to keydown events
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.min(prev + 1, flatResults.length - 1));
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.max(prev - 1, 0));
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        if (flatResults.length > 0) {
          setSelectedIndex((prev) => {
            if (flatResults[prev]) {
              onAction(flatResults[prev].action);
            }
            return prev;
          });
        }
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose, onAction, flatResults]);

  // Scroll selected item into view when selectedIndex changes via keyboard
  useEffect(() => {
    const el = itemRefs.current.get(selectedIndex);
    if (el) {
      el.scrollIntoView({ block: "nearest" });
    }
  }, [selectedIndex]);

  // Pre-compute a map from result.id → flat index for keyboard navigation
  const resultIndexMap = new Map<string, number>();
  {
    let idx = 0;
    for (const group of groups) {
      for (const result of group.results) {
        resultIndexMap.set(result.id, idx++);
      }
    }
  }

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
                onChange={(e) => handleQueryChange(e.target.value)}
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

            {/* Results area */}
            <div className="max-h-[400px] overflow-y-auto p-2">
              {groups.length === 0 && query.trim() ? (
                <div className="px-3 py-8 text-center text-sm text-muted-foreground">
                  No results for &ldquo;{query}&rdquo;
                </div>
              ) : (
                groups.map((group) => (
                  <div key={group.category} className="mb-1">
                    <div className="px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      {group.label}
                    </div>
                    {group.results.map((result) => {
                      const idx = resultIndexMap.get(result.id) ?? -1;
                      return (
                        <CommandPaletteResultItem
                          key={result.id}
                          ref={(el) => {
                            if (el) {
                              itemRefs.current.set(idx, el);
                            } else {
                              itemRefs.current.delete(idx);
                            }
                          }}
                          result={result}
                          isSelected={idx === selectedIndex}
                          onClick={() => onAction(result.action)}
                        />
                      );
                    })}
                  </div>
                ))
              )}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between border-t border-border px-4 py-2">
              <div className="flex gap-1">
                {FILTER_LABELS.map(({ value, label }) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => handleFilterChange(value)}
                    className={cn(
                      "rounded border px-1.5 py-0.5 font-mono text-[10px] transition-colors",
                      categoryFilter === value
                        ? "border-foreground bg-muted text-foreground"
                        : "border-border text-muted-foreground hover:border-foreground/50 hover:text-foreground/70",
                    )}
                  >
                    {label}
                  </button>
                ))}
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
