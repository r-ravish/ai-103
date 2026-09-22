"use client";

import { useRef } from "react";
import Header from "@/components/Header";
import Chat, { ChatHandle } from "@/components/Chat";
import TicketSidebar from "@/components/TicketSidebar";

export default function Home() {
  const chatRef = useRef<ChatHandle>(null);

  return (
    <div className="flex h-full flex-1 flex-col">
      <Header />
      <main className="flex min-h-0 flex-1 relative overflow-hidden">
        <Chat ref={chatRef} />
        <TicketSidebar />
      </main>
    </div>
  );
}
