"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { createPortal } from "react-dom";

export interface MentionAgent {
  name: string;
  displayName?: string;
  role?: string;
}

interface AgentMentionAutocompleteProps {
  agents: MentionAgent[];
  query: string;
  onSelect: (agentName: string) => void;
  onClose: () => void;
  anchorRef: React.RefObject<HTMLTextAreaElement | null>;
}

export function AgentMentionAutocomplete({
  agents,
  query,
  onSelect,
  onClose,
  anchorRef,
}: AgentMentionAutocompleteProps) {
  const [focusedIndex, setFocusedIndex] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);

  const filtered = agents.filter((a) => {
    const q = query.toLowerCase();
    return (
      a.name.toLowerCase().startsWith(q) ||
      (a.displayName || a.name).toLowerCase().startsWith(q)
    );
  });

  // Reset focused index when query changes
  useEffect(() => {
    setFocusedIndex(0);
  }, [query]);

  // Scroll focused item into view
  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const item = list.children[focusedIndex] as HTMLElement | undefined;
    item?.scrollIntoView?.({ block: "nearest" });
  }, [focusedIndex]);

  const navigateDown = useCallback(() => {
    if (filtered.length === 0) return;
    setFocusedIndex((prev) => (prev + 1) % filtered.length);
  }, [filtered.length]);

  const navigateUp = useCallback(() => {
    if (filtered.length === 0) return;
    setFocusedIndex((prev) => (prev - 1 + filtered.length) % filtered.length);
  }, [filtered.length]);

  const selectFocused = useCallback(() => {
    if (filtered.length > 0 && focusedIndex < filtered.length) {
      onSelect(filtered[focusedIndex].name);
    }
  }, [filtered, focusedIndex, onSelect]);

  // Expose navigation methods via a stable ref on the DOM element
  // ThreadInput reads these via anchorRef.current.__mentionNav
  useEffect(() => {
    const el = anchorRef.current;
    if (!el) return;
    (el as any).__mentionNav = { navigateDown, navigateUp, selectFocused, close: onClose };
    return () => {
      if (el) (el as any).__mentionNav = undefined;
    };
  }, [anchorRef, navigateDown, navigateUp, selectFocused, onClose]);

  // Compute position relative to the textarea
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);

  useEffect(() => {
    const el = anchorRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const spaceAbove = rect.top;
    const dropdownHeight = 200;

    if (spaceAbove > dropdownHeight) {
      // Position above
      setPosition({ top: rect.top + window.scrollY - 4, left: rect.left + window.scrollX });
    } else {
      // Position below
      setPosition({ top: rect.bottom + window.scrollY + 4, left: rect.left + window.scrollX });
    }
  }, [anchorRef, query]);

  if (!position) return null;

  const dropdown = (
    <div
      data-testid="mention-autocomplete"
      className="fixed bg-popover text-popover-foreground border border-border rounded-md shadow-md z-50 w-[240px] max-h-[200px] overflow-y-auto animate-in fade-in-0 zoom-in-95"
      style={{ top: position.top, left: position.left, transform: "translateY(-100%)" }}
      ref={listRef}
    >
      {filtered.length === 0 ? (
        <div className="px-3 py-2 text-xs text-muted-foreground">No matching agents</div>
      ) : (
        filtered.map((agent, i) => (
          <div
            key={agent.name}
            data-testid={`mention-option-${agent.name}`}
            className={`px-3 py-1.5 text-sm cursor-pointer flex items-center justify-between ${
              i === focusedIndex ? "bg-accent" : ""
            }`}
            onMouseDown={(e) => {
              e.preventDefault(); // prevent textarea blur
              onSelect(agent.name);
            }}
            onMouseEnter={() => setFocusedIndex(i)}
          >
            <span>{agent.displayName || agent.name}</span>
            {agent.role && (
              <span className="text-xs text-muted-foreground ml-2">{agent.role}</span>
            )}
          </div>
        ))
      )}
    </div>
  );

  return createPortal(dropdown, document.body);
}
