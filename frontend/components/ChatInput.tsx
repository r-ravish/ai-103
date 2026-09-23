"use client";

import { useRef, useState, KeyboardEvent } from "react";
import { ArrowUp } from "lucide-react";

interface ChatInputProps {
  onSend: (content: string) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const trimmed = value.trim();
  const canSend = trimmed.length > 0 && !disabled;

  function handleSend() {
    if (!canSend) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleInput() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }

  return (
    <div className="border-t border-[var(--color-border)] bg-[var(--color-paper)] px-4 py-4 sm:px-6">
      <form
        className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-[var(--color-border)] bg-[var(--color-canvas)] p-1.5 pl-4 transition-colors focus-within:border-[var(--color-seal)]"
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
      >
        <label htmlFor="chat-input" className="sr-only">
          Ask a question
        </label>
        <textarea
          id="chat-input"
          ref={textareaRef}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            handleInput();
          }}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about company policy…"
          rows={1}
          disabled={disabled}
          style={{ outline: "none", border: "none", boxShadow: "none" }}
          className="max-h-40 flex-1 resize-none border-0 bg-transparent py-2 text-[15px] text-[var(--color-ink)] placeholder:text-[var(--color-muted)] outline-none !outline-none focus:outline-none focus:!outline-none focus-visible:outline-none focus-visible:!outline-none focus:ring-0 focus-visible:ring-0 disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={!canSend}
          aria-label="Send message"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--color-ink)] text-[var(--color-paper)] transition-opacity disabled:cursor-not-allowed disabled:bg-[var(--color-border-strong)] disabled:opacity-100"
        >
          <ArrowUp className="h-4 w-4" strokeWidth={2} aria-hidden="true" />
        </button>
      </form>
    </div>
  );
}
