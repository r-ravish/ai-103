import Header from "@/components/Header";
import Chat from "@/components/Chat";

export default function Home() {
  return (
    <div className="flex h-full flex-1 flex-col">
      <Header />
      <main className="flex min-h-0 flex-1 flex-col">
        <Chat />
      </main>
    </div>
  );
}
