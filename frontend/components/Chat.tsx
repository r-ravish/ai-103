"use client";

import { useState } from "react";
import { Message } from "@/types/chat";
import { getMockResponse, MOCK_RESPONSE_DELAY_MS } from "@/lib/mockResponses";
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
      // Artificial delay so the loading state is visible. This is the
      // seam where a real backend call (fetch to the agent API) would
      // replace getMockResponse — the rest of the flow stays the same.
      await new Promise((resolve) =>
        setTimeout(resolve, MOCK_RESPONSE_DELAY_MS)
      );

      const mock = getMockResponse(content);

      const assistantMessage: Message = {
        id: createId(),
        role: "assistant",
        content: mock.content,
        citations: mock.citations,
        isKnowledgeGap: mock.isKnowledgeGap,
        timestamp: Date.now(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      // Mock data should never throw, but don't swallow it silently if
      // something unexpected happens — surface a visible assistant
      // message rather than failing silently, without pretending it's
      // a knowledge-gap or a normal grounded answer.
      console.error("Failed to produce a mock assistant response:", error);
      const errorMessage: Message = {
        id: createId(),
        role: "assistant",
        content:
          "Something went wrong producing a response. Please try again.",
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
