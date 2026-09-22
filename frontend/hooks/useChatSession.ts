import { useState, useEffect, useCallback } from "react";
import { Message } from "@/types/chat";

const SESSION_KEY = "chat_session_state";

interface ChatSessionState {
  messages: Message[];
  conversationId: number | null;
}

export function useChatSession() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [isHydrated, setIsHydrated] = useState(false);

  // Load from sessionStorage on mount
  useEffect(() => {
    if (typeof window !== "undefined") {
      const stored = sessionStorage.getItem(SESSION_KEY);
      if (stored) {
        try {
          const parsed = JSON.parse(stored) as ChatSessionState;
          setMessages(parsed.messages || []);
          setConversationId(parsed.conversationId || null);
        } catch (e) {
          console.error("Failed to parse chat session state", e);
        }
      }
      setIsHydrated(true);
    }
  }, []);

  // Save to sessionStorage whenever messages or conversationId change
  useEffect(() => {
    if (isHydrated && typeof window !== "undefined") {
      const state: ChatSessionState = { messages, conversationId };
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(state));
    }
  }, [messages, conversationId, isHydrated]);

  const clearSession = useCallback(() => {
    setMessages([]);
    setConversationId(null);
    if (typeof window !== "undefined") {
      sessionStorage.removeItem(SESSION_KEY);
      sessionStorage.setItem("force_new_chat", "true");
    }
  }, []);

  return {
    messages,
    setMessages,
    conversationId,
    setConversationId,
    isHydrated,
    clearSession,
  };
/**
 * frontend/hooks/useChatSession.ts
 * ----------------------------------
 * Persists chat messages to sessionStorage so the conversation survives
 * client-side navigations (e.g. admin switching to /admin and back).
 *
 * sessionStorage is chosen over localStorage so the history is automatically
 * cleared when the browser tab closes — matching the expected UX of a chat
 * session rather than a permanent log.
 */
"use client";

import { useState, useEffect, useCallback } from "react";
import { Message } from "@/types/chat";

const SESSION_KEY = "chat_messages";

function loadFromStorage(): Message[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as Message[];
  } catch {
    return [];
  }
}

function saveToStorage(messages: Message[]): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(messages));
  } catch {
    // quota exceeded or private-mode restriction — silently ignore
  }
}

export function useChatSession() {
  const [messages, setMessages] = useState<Message[]>(() => loadFromStorage());

  // Whenever messages change, persist them to sessionStorage
  useEffect(() => {
    saveToStorage(messages);
  }, [messages]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    if (typeof window !== "undefined") {
      sessionStorage.removeItem(SESSION_KEY);
    }
  }, []);

  return { messages, setMessages, clearMessages };
}
