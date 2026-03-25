"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { createPortal } from "react-dom";
import type {
  MentionNavigation,
  MentionTextareaElement,
} from "@/features/thread/lib/mentionNavigation";

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
  inline?: boolean;
}

export function AgentMentionAutocomplete({
  agents,
  query,
  onSelect,
  onClose,
  anchorRef,
  inline = false,
}: AgentMentionAutocompleteProps) {
  const [focusState, setFocusState] = useState({ index: 0, query });
  const listRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState<{
    isAbove: boolean;
    left: number;
    top: number;
  } | null>(null);

  const filtered = agents.filter((a) => {
    const q = query.toLowerCase();
    return (
      a.name.toLowerCase().startsWith(q) || (a.displayName || a.name).toLowerCase().startsWith(q)
    );
  });

  const focusedIndex = focusState.query === query ? focusState.index : 0;

  // Scroll focused item into view
  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const item = list.children[focusedIndex] as HTMLElement | undefined;
    item?.scrollIntoView?.({ block: "nearest" });
  }, [focusedIndex]);

  const navigateDown = useCallback(() => {
    if (filtered.length === 0) return;
    setFocusState((prev) => ({
      index: ((prev.query === query ? prev.index : 0) + 1) % filtered.length,
      query,
    }));
  }, [filtered.length, query]);

  const navigateUp = useCallback(() => {
    if (filtered.length === 0) return;
    setFocusState((prev) => ({
      index: ((prev.query === query ? prev.index : 0) - 1 + filtered.length) % filtered.length,
      query,
    }));
  }, [filtered.length, query]);

  const selectFocused = useCallback((): boolean => {
    if (filtered.length > 0 && focusedIndex < filtered.length) {
      onSelect(filtered[focusedIndex].name);
      return true;
    }
    return false;
  }, [filtered, focusedIndex, onSelect]);

  // Expose navigation methods via a stable ref on the DOM element
  // ThreadInput reads these via anchorRef.current.__mentionNav
  useEffect(() => {
    const el = anchorRef.current as MentionTextareaElement | null;
    if (!el) return;

    const mentionNavigation: MentionNavigation = {
      close: onClose,
      navigateDown,
      navigateUp,
      selectFocused,
    };

    el.__mentionNav = mentionNavigation;
    return () => {
      el.__mentionNav = undefined;
    };
  }, [anchorRef, navigateDown, navigateUp, selectFocused, onClose]);

  // Compute position relative to the textarea (portal mode only)
  useEffect(() => {
    if (inline) return;
    const el = anchorRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const spaceAbove = rect.top;
    const dropdownHeight = 200;

    if (spaceAbove > dropdownHeight) {
      setPosition({ isAbove: true, top: rect.top - 4, left: rect.left });
    } else {
      setPosition({ isAbove: false, top: rect.bottom + 4, left: rect.left });
    }
  }, [anchorRef, query, inline]);

  const listContent =
    filtered.length === 0 ? (
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
            e.preventDefault();
            onSelect(agent.name);
          }}
          onMouseEnter={() => setFocusState({ index: i, query })}
        >
          <span>{agent.name}</span>
          {agent.role && <span className="text-xs text-muted-foreground ml-2">{agent.role}</span>}
        </div>
      ))
    );

  // Inline mode: render directly in flow, no portal
  if (inline) {
    return (
      <div
        data-testid="mention-autocomplete"
        className="bg-popover text-popover-foreground border border-border rounded-md shadow-md max-h-[200px] overflow-y-auto"
        ref={listRef}
      >
        {listContent}
      </div>
    );
  }

  // Portal mode: fixed positioning
  if (!position) return null;

  const dropdown = (
    <div
      data-testid="mention-autocomplete"
      className="fixed bg-popover text-popover-foreground border border-border rounded-md shadow-md z-[100] w-[240px] max-h-[200px] overflow-y-auto animate-in fade-in-0 zoom-in-95"
      style={{
        top: position.top,
        left: position.left,
        ...(position.isAbove ? { transform: "translateY(-100%)" } : {}),
      }}
      ref={listRef}
    >
      {listContent}
    </div>
  );

  return createPortal(dropdown, document.body);
}
