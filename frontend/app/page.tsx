"use client";

import { useRef, useState, useCallback } from "react";
import Header from "@/components/Header";
import Chat, { ChatHandle } from "@/components/Chat";
import TicketSidebar from "@/components/TicketSidebar";
import ChatSidebar from "@/components/ChatSidebar";

export default function Home() {
  const chatRef = useRef<ChatHandle>(null);
  const [chatUpdateCount, setChatUpdateCount] = useState(0);

  const handleSelectConversation = useCallback((id: number) => {
    chatRef.current?.loadConversation(id);
  }, []);

  const handleNewChat = useCallback(() => {
    chatRef.current?.handleNewChat();
  }, []);

  const handleChatUpdated = useCallback(() => {
    setChatUpdateCount((c) => c + 1);
  }, []);

  return (
    <div className="flex h-full flex-1 flex-col">
      <Header />
      <main className="flex min-h-0 flex-1 relative overflow-hidden">
        <ChatSidebar 
          onSelectConversation={handleSelectConversation}
          onNewChat={handleNewChat}
          updateTrigger={chatUpdateCount}
        />
        <Chat ref={chatRef} onChatUpdated={handleChatUpdated} />
        <TicketSidebar />
      </main>
    </div>
  );
}
