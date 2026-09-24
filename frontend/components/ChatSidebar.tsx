"use client";

import { useEffect, useState } from "react";
import { MessageSquare, Plus, Loader2, Trash2, ChevronLeft, ChevronRight } from "lucide-react";
import { fetchConversations, deleteConversation } from "@/lib/api";
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
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (!user || !isOpen) {
      if (!user) setConversations([]);
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
  }, [user, updateTrigger, isOpen]);

  const handleDelete = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    if (confirm("Are you sure you want to delete this chat?")) {
      try {
        await deleteConversation(id);
        setConversations(prev => prev.filter(c => c.id !== id));
        onNewChat();
      } catch (err) {
        console.error("Failed to delete conversation", err);
        alert("Failed to delete chat.");
      }
    }
  };

  if (!user) return null;

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="absolute left-0 top-1/2 -translate-y-1/2 bg-[var(--color-paper)] border border-[var(--color-border)] border-l-0 rounded-r-xl p-2 shadow-sm text-[var(--color-ink)] hover:bg-[var(--color-canvas)] transition-colors z-10 cursor-pointer"
        title="Open Chat History"
      >
        <div className="flex flex-col items-center gap-2">
          <MessageSquare className="w-5 h-5 text-[var(--color-seal)]" />
          <span className="text-xs font-semibold" style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}>Chat History</span>
          <ChevronRight className="w-4 h-4 text-[var(--color-muted)]" />
        </div>
      </button>
    );
  }

  return (
    <div className="w-64 border-r border-[var(--color-border)] bg-[var(--color-paper)] flex flex-col h-full shadow-[8px_0_24px_rgba(0,0,0,0.12)] transition-transform z-20 absolute left-0 top-0 animate-in slide-in-from-left-8 duration-300">
      <div className="p-4 border-b border-[var(--color-border)] flex items-center justify-between sticky top-0 bg-[var(--color-paper)] z-10">
        <div className="flex items-center gap-2">
          <MessageSquare className="w-4 h-4 text-[var(--color-seal)]" />
          <h2 className="text-sm font-semibold text-[var(--color-ink)]">Chat History</h2>
        </div>
        <button
          onClick={() => setIsOpen(false)}
          className="p-1 text-[var(--color-muted)] hover:bg-[var(--color-canvas)] rounded-md transition-colors cursor-pointer"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
      </div>

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
              <li key={conv.id} className="group relative">
                <button
                  onClick={() => onSelectConversation(conv.id)}
                  className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 pr-8 text-left text-[13px] text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)] hover:text-[var(--color-ink)] transition-colors"
                >
                  <MessageSquare className="h-3.5 w-3.5 shrink-0 text-[var(--color-muted)]" />
                  <span className="truncate">{conv.title || "New conversation"}</span>
                </button>
                <button
                  onClick={(e) => handleDelete(e, conv.id)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-[var(--color-muted)] opacity-0 hover:text-red-500 group-hover:opacity-100 transition-all cursor-pointer"
                  title="Delete chat"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
