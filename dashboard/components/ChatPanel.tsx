"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { InteractiveChatTabs } from "@/features/interactive/components/InteractiveChatTabs";
import { getInteractiveAgentProvider } from "@/features/interactive/hooks/useInteractiveAgentProvider";
import { useSendChat } from "@/hooks/useSendChat";
import { SendHorizontal, X } from "lucide-react";
import { AgentMentionAutocomplete, type MentionAgent } from "./AgentMentionAutocomplete";
import { ChatMessages } from "./ChatMessages";
import { useSelectableAgents } from "@/hooks/useSelectableAgents";

export function ChatPanel() {
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [mentionQuery, setMentionQuery] = useState<string | null>(null);
  const [mentionStartIndex, setMentionStartIndex] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const contentRef = useRef(content);
  const mentionStartIndexRef = useRef(mentionStartIndex);
  const mentionQueryRef = useRef(mentionQuery);
  const blurTimeoutRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const sendChat = useSendChat();
  const selectableAgents = useSelectableAgents();
  const selectedAgentDoc = selectableAgents?.find((agent) => agent.name === selectedAgent) ?? null;
  const interactiveProvider = getInteractiveAgentProvider(selectedAgentDoc);

  // Keep refs in sync
  useEffect(() => {
    contentRef.current = content;
  }, [content]);
  useEffect(() => {
    mentionStartIndexRef.current = mentionStartIndex;
  }, [mentionStartIndex]);
  useEffect(() => {
    mentionQueryRef.current = mentionQuery;
  }, [mentionQuery]);
  useEffect(() => () => clearTimeout(blurTimeoutRef.current), []);

  const filteredAgents: MentionAgent[] = (selectableAgents ?? []).map((a) => ({
    name: a.name,
    displayName: a.displayName ?? undefined,
    role: a.role ?? undefined,
  }));

  const handleTextChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    setContent(value);

    const cursorPos = e.target.selectionStart ?? value.length;

    // Find the last @ before cursor preceded by start-of-input or whitespace
    let atIndex = -1;
    for (let i = cursorPos - 1; i >= 0; i--) {
      if (value[i] === "@") {
        if (i === 0 || /\s/.test(value[i - 1])) {
          atIndex = i;
        }
        break;
      }
      if (/\s/.test(value[i])) break;
    }

    if (atIndex >= 0) {
      const q = value.slice(atIndex + 1, cursorPos);
      if (/[^a-zA-Z0-9_-]/.test(q)) {
        setMentionQuery(null);
      } else {
        setMentionStartIndex(atIndex);
        setMentionQuery(q);
      }
    } else {
      setMentionQuery(null);
    }
  }, []);

  const handleMentionSelect = useCallback((agentName: string) => {
    const currentContent = contentRef.current;
    const startIdx = mentionStartIndexRef.current;
    const mQuery = mentionQueryRef.current;
    const before = currentContent.slice(0, startIdx);
    const after = currentContent.slice(startIdx + 1 + (mQuery?.length ?? 0));
    const newContent = `${before}@${agentName} ${after}`;
    setContent(newContent);
    setSelectedAgent(agentName);
    setMentionQuery(null);

    requestAnimationFrame(() => {
      const el = textareaRef.current;
      if (el) {
        el.focus();
        const pos = before.length + 1 + agentName.length + 1;
        el.selectionStart = pos;
        el.selectionEnd = pos;
      }
    });
  }, []);

  const handleSend = async () => {
    const trimmed = content.trim();
    if (!trimmed || !selectedAgent) return;

    // Parse @mentions: use the last mentioned agent if valid
    let agentForSubmit = selectedAgent;
    const mentionMatches = trimmed.match(/@(\w[\w-]*)/g);
    if (mentionMatches) {
      const lastMention = mentionMatches[mentionMatches.length - 1].slice(1);
      if (filteredAgents.some((a) => a.name === lastMention)) {
        agentForSubmit = lastMention;
        setSelectedAgent(lastMention);
      }
    }

    setIsSubmitting(true);
    try {
      await sendChat({
        agentName: agentForSubmit,
        authorName: "User",
        authorType: "user",
        content: trimmed,
        status: "pending",
        timestamp: new Date().toISOString(),
      });
      setContent("");
    } catch (err) {
      console.error("Failed to send chat:", err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (mentionQuery !== null) {
      const nav = (
        textareaRef.current as
          | (HTMLTextAreaElement & {
              __mentionNav?: {
                navigateDown: () => void;
                navigateUp: () => void;
                selectFocused: () => boolean;
                close: () => void;
              };
            })
          | null
      )?.__mentionNav;
      if (nav) {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          nav.navigateDown();
          return;
        }
        if (e.key === "ArrowUp") {
          e.preventDefault();
          nav.navigateUp();
          return;
        }
        if (e.key === "Enter" || e.key === "Tab") {
          const selected = nav.selectFocused();
          if (selected !== false) {
            e.preventDefault();
          }
          return;
        }
        if (e.key === "Escape") {
          e.preventDefault();
          nav.close();
          return;
        }
      }
    }

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (content.trim() && selectedAgent && !isSubmitting) {
        handleSend();
      }
    }
  };

  // No agent selected: prompt state
  if (!selectedAgent) {
    return (
      <div className="flex flex-1 flex-col justify-end p-4 gap-3">
        <p className="text-xs text-muted-foreground text-center">
          Type @ to select an agent and start a conversation
        </p>
        {mentionQuery !== null && (
          <AgentMentionAutocomplete
            inline
            agents={filteredAgents}
            query={mentionQuery}
            onSelect={handleMentionSelect}
            onClose={() => setMentionQuery(null)}
            anchorRef={textareaRef}
          />
        )}
        <Textarea
          ref={textareaRef}
          placeholder="@agent-name..."
          value={content}
          onChange={handleTextChange}
          onKeyDown={handleKeyDown}
          onFocus={() => clearTimeout(blurTimeoutRef.current)}
          onBlur={() => {
            blurTimeoutRef.current = setTimeout(() => setMentionQuery(null), 150);
          }}
          className="text-sm min-h-[60px] max-h-[100px] resize-none"
        />
      </div>
    );
  }

  const chatView = (
    <>
      <ChatMessages agentName={selectedAgent} />

      {mentionQuery !== null && (
        <div className="shrink-0 px-2">
          <AgentMentionAutocomplete
            inline
            agents={filteredAgents}
            query={mentionQuery}
            onSelect={handleMentionSelect}
            onClose={() => setMentionQuery(null)}
            anchorRef={textareaRef}
          />
        </div>
      )}

      <div className="shrink-0 border-t border-border p-2">
        <div className="flex gap-1.5">
          <Textarea
            ref={textareaRef}
            placeholder={`Message @${selectedAgent}...`}
            value={content}
            onChange={handleTextChange}
            onKeyDown={handleKeyDown}
            onFocus={() => clearTimeout(blurTimeoutRef.current)}
            onBlur={() => {
              blurTimeoutRef.current = setTimeout(() => setMentionQuery(null), 150);
            }}
            className="text-sm min-h-[56px] max-h-[120px] resize-none"
            disabled={isSubmitting}
          />
          <Button
            size="icon"
            variant="default"
            className="h-[56px] w-9 shrink-0"
            onClick={handleSend}
            disabled={!content.trim() || isSubmitting}
          >
            <SendHorizontal className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </>
  );

  return (
    <div className="flex flex-1 flex-col min-h-0 min-w-0">
      {/* Locked header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border shrink-0">
        <span className="text-xs font-medium text-foreground truncate">
          Chatting with <span className="text-primary">@{selectedAgent}</span>
        </span>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={() => {
            setSelectedAgent(null);
            setContent("");
          }}
          aria-label="Close chat"
        >
          <X className="h-3 w-3" />
        </Button>
      </div>

      <InteractiveChatTabs
        key={`${selectedAgent}:${interactiveProvider ?? "chat"}`}
        agentName={selectedAgent}
        interactiveProvider={interactiveProvider}
        chatView={chatView}
      />
    </div>
  );
}
