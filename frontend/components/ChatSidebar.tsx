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
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--color-seal)] px-4 py-2.5 text-xs font-semibold text-white hover:bg-[var(--color-seal-soft)] transition-colors shadow-xs hover:shadow-sm cursor-pointer"
        >
          <Plus className="h-4 w-4" />
          Start New Chat
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
                  className="w-full text-left p-2.5 rounded-xl border border-transparent hover:border-[var(--color-border)] hover:bg-[var(--color-canvas)] transition-all flex flex-col gap-1 pr-8 hover:shadow-xs group/btn"
                >
                  <div className="flex items-center gap-2">
                    <MessageSquare className="h-3.5 w-3.5 shrink-0 text-[var(--color-seal)] group-hover/btn:text-[var(--color-seal-soft)] transition-colors" />
                    <span className="text-[13px] font-semibold text-[var(--color-ink)] truncate w-full group-hover/btn:text-[var(--color-seal)] transition-colors">{conv.title || "New conversation"}</span>
                  </div>
                  <div className="flex items-center justify-between pl-5 pr-1">
                    <span className="text-[10px] text-[var(--color-muted)] font-medium">
                      {new Date(conv.updatedAt || conv.createdAt).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} • {conv.messageCount} msg{conv.messageCount !== 1 ? 's' : ''}
                    </span>
                  </div>
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
