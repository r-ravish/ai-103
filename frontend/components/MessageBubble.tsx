"use client";

import { FileQuestion } from "lucide-react";
import { Message } from "@/types/chat";
import CitationList from "./CitationList";

interface MessageBubbleProps {
  message: Message;
}

function Timestamp({ value }: { value: number }) {
  const label = new Date(value).toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
  return (
    <span className="mt-1 block text-[11px] text-[var(--color-muted)]">
      {label}
    </span>
  );
}

function AssistantMark() {
  return (
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
  );
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] sm:max-w-[70%]">
          <div
            className="rounded-2xl rounded-br-sm bg-[var(--color-user-bubble)] px-4 py-2.5 text-[15px] leading-relaxed text-[var(--color-user-bubble-text)]"
            role="group"
            aria-label="Your message"
          >
            <p className="whitespace-pre-wrap">{message.content}</p>
          </div>
          <div className="text-right">
            <Timestamp value={message.timestamp} />
          </div>
        </div>
      </div>
    );
  }

  // Assistant message. Knowledge-gap responses get a visually distinct
  // treatment (icon + label + amber flag border) rather than the
  // standard answer card, and rather than anything that looks like an
  // error/crash.
  if (message.isKnowledgeGap) {
    return (
      <div className="flex items-start gap-2.5">
        <AssistantMark />
        <div className="max-w-[85%] sm:max-w-[70%]">
          <div
            className="flex gap-2.5 rounded-2xl rounded-tl-sm border-l-4 border-[var(--color-flag-border)] bg-[var(--color-flag-surface)] px-4 py-3"
            role="group"
            aria-label="Assistant response: knowledge gap"
          >
            <FileQuestion
              aria-hidden="true"
              className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-flag)]"
              strokeWidth={1.75}
            />
            <div>
              <p className="text-[13px] font-medium text-[var(--color-flag)]">
                No matching policy found
              </p>
              <p className="mt-0.5 whitespace-pre-wrap text-[15px] leading-relaxed text-[var(--color-ink)]">
                {message.content}
              </p>
            </div>
          </div>
          <Timestamp value={message.timestamp} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-2.5">
      <AssistantMark />
      <div className="max-w-[85%] sm:max-w-[70%]">
        <div
          className="rounded-2xl rounded-tl-sm border border-[var(--color-border)] bg-[var(--color-paper)] px-4 py-3 shadow-[0_1px_2px_rgba(18,21,27,0.04)]"
          role="group"
          aria-label="Assistant response"
        >
          <p
            className="whitespace-pre-wrap text-[15px] leading-relaxed text-[var(--color-ink)]"
            style={{ fontFamily: "var(--font-stack-serif)" }}
          >
            {message.content}
          </p>
          {message.actionTaken && (
            <div className="mt-2.5 flex items-center gap-2 rounded-lg border border-[var(--color-seal)]/30 bg-[var(--color-seal-soft)] px-3 py-1.5 text-xs font-medium text-[var(--color-seal)]">
              <span className="h-2 w-2 rounded-full bg-[var(--color-seal)]" />
              <span>{message.actionName || "Action Executed"}</span>
              {message.ticketId && (
                <span className="font-mono bg-white/60 px-1.5 py-0.5 rounded border border-[var(--color-seal)]/20">
                  {message.ticketId}
                </span>
              )}
            </div>
          )}
          {message.isEscalated && (
            <div className="mt-2.5 flex items-center gap-2 rounded-lg border border-[var(--color-flag-border)] bg-[var(--color-flag-surface)] px-3 py-1.5 text-xs font-medium text-[var(--color-flag)]">
              <span className="h-2 w-2 rounded-full bg-[var(--color-flag)]" />
              <span>Escalated to Human Support</span>
              {message.escalationReason && (
                <span className="text-[11px] opacity-80">
                  ({message.escalationReason})
                </span>
              )}
            </div>
          )}
          {message.citations && <CitationList citations={message.citations} />}
        </div>
        <Timestamp value={message.timestamp} />
      </div>
    </div>
  );
}
