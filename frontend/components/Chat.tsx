"use client";

import { useState } from "react";
import { RotateCcw } from "lucide-react";
import { useState, useEffect, useCallback, useImperativeHandle, forwardRef } from "react";
import { RotateCcw } from "lucide-react";
import { Message } from "@/types/chat";
import { sendChatMessage, fetchConversations, fetchConversation } from "@/lib/api";
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

/** Handle exposed to the parent page so the Header can trigger a New Chat. */
export interface ChatHandle {
  handleNewChat: () => void;
}

const Chat = forwardRef<ChatHandle>(function Chat(_props, ref) {
  const { user, refreshUser } = useAuth();
  const { messages, setMessages, conversationId, setConversationId, isHydrated, clearSession } = useChatSession();
  const { messages, setMessages, clearMessages } = useChatSession();
  const [isLoading, setIsLoading] = useState(false);
  /** True while we are loading the most-recent persisted conversation. */
  const [isRestoring, setIsRestoring] = useState(false);

  // ── On mount / user change: restore the most-recent conversation ───────────
  useEffect(() => {
    if (!user) {
      // User logged out — clear everything.
      clearSession();
      return;
    }

    if (!isHydrated) return; // Wait for sessionStorage to load

    if (messages.length > 0) return; // Active session exists

    let cancelled = false;

    async function restoreLatest() {
      setIsRestoring(true);
      try {
        if (sessionStorage.getItem("force_new_chat") === "true") {
          return;
        }
        const conversations = await fetchConversations();
        if (cancelled || conversations.length === 0) return;

        const latest = conversations[0]; // already sorted newest-first
        const msgs = await fetchConversation(latest.id);
        if (cancelled) return;

        if (msgs.length > 0) {
          setMessages(msgs);
          setConversationId(latest.id);
        }
      } catch {
        // Non-fatal: just start fresh
      } finally {
        if (!cancelled) setIsRestoring(false);
      }
    }

    restoreLatest();
    return () => { cancelled = true; };
  }, [user, isHydrated, messages.length, setMessages, setConversationId, clearSession]);

  // ── New Chat: wipe current state and start a fresh conversation ───────────
  const handleNewChat = useCallback(() => {
    clearSession();
  }, [clearSession]);

  // Expose handleNewChat to the parent via ref.
  useImperativeHandle(ref, () => ({ handleNewChat }), [handleNewChat]);

  // ── Send a message ────────────────────────────────────────────────────────
  async function handleSend(content: string) {
    const userMessage: Message = {
      id: createId(),
      role: "user",
      content,
      timestamp: Date.now(),
    };

    if (typeof window !== "undefined") {
      sessionStorage.removeItem("force_new_chat");
    }

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const result = await sendChatMessage(content, conversationId);

      // On the first turn of a new conversation, capture the returned ID.
      if (result.conversationId != null && conversationId == null) {
        setConversationId(result.conversationId);
      }

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
      {isRestoring ? (
        <div className="canvas-texture min-h-0 flex-1 bg-[var(--color-canvas)] flex items-center justify-center">
          <span className="text-xs text-[var(--color-muted)] animate-pulse">Restoring your last conversation…</span>
        </div>
      ) : messages.length === 0 ? (
        <div className="canvas-texture min-h-0 flex-1 bg-[var(--color-canvas)]">
          <EmptyState onSelectSuggestion={handleSend} />
        </div>
      ) : (
        <div className="relative flex min-h-0 flex-1 flex-col">
          {/* New Chat button — top-right corner, visible when conversation is active */}
          <div className="absolute right-3 top-2 z-10">
            <button
              type="button"
              onClick={handleNewChat}
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
        <ChatInput onSend={handleSend} disabled={isLoading || isRestoring} />
      ) : (
        <ChatAuthPrompt />
      )}
    </div>
  );
});

export default Chat;
