"use client";

import { useState } from "react";
import { Message } from "@/types/chat";
import { sendChatMessage } from "@/lib/api";
import MessageList from "./MessageList";
import ChatInput from "./ChatInput";
import EmptyState from "./EmptyState";

function createId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
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
        timestamp: Date.now(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error("Failed to fetch response from agent API:", error);
      const errorMessageText =
        error instanceof Error && error.message
          ? error.message
          : "Something went wrong producing a response. Please try again.";

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
        <MessageList messages={messages} isLoading={isLoading} />
      )}
      <ChatInput onSend={handleSend} disabled={isLoading} />
    </div>
  );
}
