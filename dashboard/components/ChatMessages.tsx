"use client";

import { useEffect, useRef, useCallback } from "react";
import { useQuery } from "convex/react";
import { api } from "../convex/_generated/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MarkdownRenderer } from "./MarkdownRenderer";

function relativeTime(timestamp: string): string {
  const diff = Date.now() - new Date(timestamp).getTime();
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

interface ChatMessagesProps {
  agentName: string;
}

export function ChatMessages({ agentName }: ChatMessagesProps) {
  const messages = useQuery(api.chats.listByAgent, { agentName });
  const scrollEndRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const prevCountRef = useRef(0);

  const scrollAreaRef = useCallback((node: HTMLDivElement | null) => {
    if (node) {
      const viewport = node.querySelector(
        "[data-radix-scroll-area-viewport]"
      ) as HTMLDivElement | null;
      if (viewport) {
        viewportRef.current = viewport;
      }
    }
  }, []);

  // Auto-scroll when new messages arrive
  useEffect(() => {
    if (!messages) return;
    if (messages.length > prevCountRef.current) {
      requestAnimationFrame(() => {
        scrollEndRef.current?.scrollIntoView({ behavior: "smooth" });
      });
    }
    prevCountRef.current = messages.length;
  }, [messages]);

  // Check if the last message is from the user with status "processing"
  const isProcessing =
    messages &&
    messages.length > 0 &&
    messages[messages.length - 1].status === "processing";

  if (messages === undefined) {
    return (
      <div className="flex-1 p-4">
        <p className="text-xs text-muted-foreground italic">Loading...</p>
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center p-4">
        <p className="text-xs text-muted-foreground text-center italic">
          Start a conversation with @{agentName}
        </p>
      </div>
    );
  }

  return (
    <ScrollArea ref={scrollAreaRef} className="flex-1 min-h-0">
      <div className="space-y-2 p-3">
        {messages.map((msg) => {
          const isUser = msg.authorType === "user";
          return (
            <div
              key={msg._id}
              className={`flex ${isUser ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                  isUser
                    ? "bg-primary/10 text-foreground"
                    : "bg-muted text-foreground"
                }`}
              >
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className="text-[10px] font-medium text-muted-foreground">
                    {msg.authorName}
                  </span>
                  <span className="text-[10px] text-muted-foreground/60">
                    {relativeTime(msg.timestamp)}
                  </span>
                </div>
                {isUser ? (
                  <p className="whitespace-pre-wrap break-words text-xs leading-relaxed">
                    {msg.content}
                  </p>
                ) : (
                  <MarkdownRenderer
                    content={msg.content}
                    className="text-xs [&_pre]:max-w-full [&_pre]:overflow-x-auto"
                  />
                )}
              </div>
            </div>
          );
        })}

        {/* Typing indicator */}
        {isProcessing && (
          <div className="flex justify-start">
            <div className="bg-muted rounded-lg px-3 py-2">
              <div className="flex items-center gap-1">
                <span
                  className="h-1.5 w-1.5 rounded-full bg-muted-foreground/50 animate-bounce"
                  style={{ animationDelay: "0ms" }}
                />
                <span
                  className="h-1.5 w-1.5 rounded-full bg-muted-foreground/50 animate-bounce"
                  style={{ animationDelay: "150ms" }}
                />
                <span
                  className="h-1.5 w-1.5 rounded-full bg-muted-foreground/50 animate-bounce"
                  style={{ animationDelay: "300ms" }}
                />
              </div>
            </div>
          </div>
        )}

        <div ref={scrollEndRef} />
      </div>
    </ScrollArea>
  );
}
