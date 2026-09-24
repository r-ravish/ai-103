"use client";

import { useEffect, useState } from "react";
import { MessageSquare, Plus, Loader2 } from "lucide-react";
import { fetchConversations } from "@/lib/api";
import { Conversation } from "@/types/chat";
import { useAuth } from "@/lib/auth-context";

interface ChatSidebarProps {
  onSelectConversation: (id: number) => void;
  onNewChat: () => void;
  updateTrigger: number;
}

export default function ChatSidebar({ onSelectConversation, onNewChat, updateTrigger }: ChatSidebarProps) {
  const { user } = useAuth();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!user) {
      setConversations([]);
      return;
    }

    let cancelled = false;
    async function load() {
      setIsLoading(true);
      try {
        const data = await fetchConversations();
        if (!cancelled) setConversations(data);
      } catch (err) {
        console.error("Failed to load conversations", err);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [user, updateTrigger]);

  if (!user) return null;

  return (
    <div className="w-64 border-r border-[var(--color-border)] bg-[var(--color-paper)] flex flex-col h-full shrink-0 transition-all">
      <div className="p-3 border-b border-[var(--color-border)]">
        <button
          onClick={onNewChat}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--color-seal)] px-4 py-2.5 text-xs font-medium text-white hover:bg-[var(--color-seal-soft)] transition-colors shadow-sm cursor-pointer"
        >
          <Plus className="h-4 w-4" />
          New Chat
        </button>
      </div>
      
      <div className="flex-1 overflow-y-auto p-2">
        <div className="px-2 pb-2 pt-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--color-muted)]">
          Recent History
        </div>
        {isLoading ? (
          <div className="flex justify-center p-4">
            <Loader2 className="h-4 w-4 animate-spin text-[var(--color-muted)]" />
          </div>
        ) : conversations.length === 0 ? (
          <div className="px-2 py-4 text-center text-xs text-[var(--color-muted)]">
            No previous chats
          </div>
        ) : (
          <ul className="space-y-1">
            {conversations.map((conv) => (
              <li key={conv.id}>
                <button
                  onClick={() => onSelectConversation(conv.id)}
                  className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13px] text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)] hover:text-[var(--color-ink)] transition-colors"
                >
                  <MessageSquare className="h-3.5 w-3.5 shrink-0 text-[var(--color-muted)]" />
                  <span className="truncate">{conv.title || "New conversation"}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
