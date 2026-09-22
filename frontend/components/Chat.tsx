"use client";

import { useState } from "react";
import { RotateCcw } from "lucide-react";
import { Message } from "@/types/chat";
import { sendChatMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useChatSession } from "@/hooks/useChatSession";
import MessageList from "./MessageList";
import ChatInput from "./ChatInput";
import ChatAuthPrompt from "./ChatAuthPrompt";
import EmptyState from "./EmptyState";

function createId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export default function Chat() {
  const { user, refreshUser } = useAuth();
  const { messages, setMessages, clearMessages } = useChatSession();
  const [isLoading, setIsLoading] = useState(false);

  async function handleSend(content: string) {
    const userMessage: Message = {
      id: createId(),
      role: "user",
      content,
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const result = await sendChatMessage(content);

      const assistantMessage: Message = {
        id: createId(),
        role: "assistant",
        content: result.answer,
        citations: result.citations,
        isKnowledgeGap: result.isKnowledgeGap,
        actionTaken: result.actionTaken,
        actionName: result.actionName,
        ticketId: result.ticketId,
        isEscalated: result.isEscalated,
        escalationReason: result.escalationReason,
        timestamp: Date.now(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error("Failed to fetch response from agent API:", error);
      const errorMessageText =
        error instanceof Error && error.message
          ? error.message
          : "Something went wrong producing a response. Please try again.";

      if (errorMessageText.toLowerCase().includes("not authenticated")) {
        await refreshUser();
      }

      const errorMessage: Message = {
        id: createId(),
        role: "assistant",
        content: errorMessageText,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {messages.length === 0 ? (
        <div className="canvas-texture min-h-0 flex-1 bg-[var(--color-canvas)]">
          <EmptyState onSelectSuggestion={handleSend} />
        </div>
      ) : (
        <div className="relative flex min-h-0 flex-1 flex-col">
          {/* New Chat button — top-right corner, visible when conversation is active */}
          <div className="absolute right-3 top-2 z-10">
            <button
              type="button"
              onClick={clearMessages}
              title="Clear conversation and start fresh"
              className="flex items-center gap-1.5 rounded-xl border border-[var(--color-border)] bg-[var(--color-paper)]/80 px-2.5 py-1.5 text-[11px] font-medium text-[var(--color-muted)] backdrop-blur-sm transition-all hover:border-[var(--color-border-strong)] hover:text-[var(--color-ink)] shadow-xs cursor-pointer"
            >
              <RotateCcw className="h-3 w-3" />
              New Chat
            </button>
          </div>
          <MessageList messages={messages} isLoading={isLoading} />
        </div>
      )}

      {user ? (
        <ChatInput onSend={handleSend} disabled={isLoading} />
      ) : (
        <ChatAuthPrompt />
      )}
    </div>
  );
}
