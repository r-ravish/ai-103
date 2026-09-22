"use client";

import { useRef } from "react";
import Header from "@/components/Header";
import Chat, { ChatHandle } from "@/components/Chat";

export default function Home() {
  const chatRef = useRef<ChatHandle>(null);

  return (
    <div className="flex h-full flex-1 flex-col">
      <Header onNewChat={() => chatRef.current?.handleNewChat()} />
      <main className="flex min-h-0 flex-1 flex-col">
        <Chat ref={chatRef} />
      </main>
    </div>
  );
}
