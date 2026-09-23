"use client";

import { useEffect, useRef } from "react";
import { Message } from "@/types/chat";
import MessageBubble from "./MessageBubble";

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
}

export default function MessageList({ messages, isLoading }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length, isLoading]);

  return (
    <div
      className="canvas-texture flex-1 overflow-y-auto bg-[var(--color-canvas)]"
      role="log"
      aria-live="polite"
      aria-label="Conversation"
    >
      <div className="mx-auto flex max-w-3xl flex-col gap-5 px-4 py-6 sm:px-6 min-w-0 w-full">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {isLoading && (
          <div className="flex items-center gap-2.5">
            <div
              aria-hidden="true"
              className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-[var(--color-ink)]"
            >
              <svg viewBox="0 0 32 32" className="h-3.5 w-3.5">
                <path
                  d="M10 21V11.5L16 16.5L22 11.5V21"
                  stroke="var(--color-paper)"
                  strokeWidth="2.4"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  fill="none"
                />
              </svg>
            </div>
            <div
              className="flex items-center gap-2 rounded-2xl rounded-tl-sm border border-[var(--color-border)] bg-[var(--color-paper)] px-4 py-2.5 text-sm text-[var(--color-muted)] shadow-[0_1px_2px_rgba(18,21,27,0.04)]"
              role="status"
            >
              <span className="flex gap-1" aria-hidden="true">
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--color-seal)] [animation-delay:-0.3s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--color-seal)] [animation-delay:-0.15s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--color-seal)]" />
              </span>
              Thinking...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
