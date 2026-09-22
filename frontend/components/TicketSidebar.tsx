import { useState, useEffect } from "react";
import { Ticket, ChevronRight, ChevronLeft, Calendar, FileText, CheckCircle2, CircleDashed, CheckCircle } from "lucide-react";
import { useAuth } from "@/lib/auth-context";

interface TicketResponse {
  ticket_id: string;
  title: string;
  description: string;
  priority: "low" | "medium" | "high";
  status: "open" | "in_progress" | "resolved" | "closed";
  admin_response: string | null;
  created_at: string;
}

export default function TicketSidebar() {
  const { user } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [tickets, setTickets] = useState<TicketResponse[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedTicket, setSelectedTicket] = useState<TicketResponse | null>(null);

  useEffect(() => {
    if (user && isOpen) {
      fetchTickets();
    }
  }, [user, isOpen]);

  async function fetchTickets() {
    setIsLoading(true);
    try {
      const res = await fetch("/api/tickets/my", {
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        setTickets(data.tickets || []);
      }
    } catch (err) {
      console.error("Failed to fetch tickets", err);
    } finally {
      setIsLoading(false);
    }
  }

  if (!user) return null;

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed right-0 top-1/2 -translate-y-1/2 bg-[var(--color-paper)] border border-[var(--color-border)] border-r-0 rounded-l-xl p-2 shadow-sm text-[var(--color-ink)] hover:bg-[var(--color-canvas)] transition-colors z-10"
        title="Open Ticket History"
      >
        <div className="flex flex-col items-center gap-2">
          <Ticket className="w-5 h-5 text-[var(--color-seal)]" />
          <span className="text-xs font-semibold" style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}>Ticket History</span>
          <ChevronLeft className="w-4 h-4 text-[var(--color-muted)]" />
        </div>
      </button>
    );
  }

  return (
    <div className="w-80 border-l border-[var(--color-border)] bg-[var(--color-paper)] flex flex-col h-full shrink-0 shadow-[-4px_0_12px_rgba(0,0,0,0.02)] transition-all z-10 absolute right-0 top-0 sm:static">
      <div className="p-4 border-b border-[var(--color-border)] flex items-center justify-between sticky top-0 bg-[var(--color-paper)] z-10">
        <div className="flex items-center gap-2">
          <Ticket className="w-4 h-4 text-[var(--color-seal)]" />
          <h2 className="text-sm font-semibold text-[var(--color-ink)]">Ticket History</h2>
        </div>
        <button
          onClick={() => setIsOpen(false)}
          className="p-1 text-[var(--color-muted)] hover:bg-[var(--color-canvas)] rounded-md transition-colors"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {selectedTicket ? (
          <div className="space-y-4 animate-in slide-in-from-right-4 duration-200">
            <button 
              onClick={() => setSelectedTicket(null)}
              className="text-xs font-medium text-[var(--color-seal)] flex items-center gap-1 hover:underline"
            >
              <ChevronLeft className="w-3 h-3" />
              Back to list
            </button>
            
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-mono font-bold text-[var(--color-ink)]">{selectedTicket.ticket_id}</span>
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium border ${
                  selectedTicket.status === 'resolved' || selectedTicket.status === 'closed'
                    ? "bg-green-50 text-green-700 border-green-200"
                    : selectedTicket.status === 'in_progress'
                    ? "bg-amber-50 text-amber-700 border-amber-200"
                    : "bg-blue-50 text-blue-700 border-blue-200"
                }`}>
                  {selectedTicket.status.toUpperCase()}
                </span>
              </div>
              <h3 className="text-sm font-semibold text-[var(--color-ink)] mb-3">{selectedTicket.title}</h3>
              
              <div className="bg-[var(--color-canvas)] rounded-lg p-3 text-xs text-[var(--color-ink)] border border-[var(--color-border)] whitespace-pre-wrap leading-relaxed">
                {selectedTicket.description}
              </div>

              {selectedTicket.admin_response && (
                <div className="mt-4 rounded-xl border border-[var(--color-seal)]/30 bg-[var(--color-seal-soft)] overflow-hidden">
                  <div className="bg-[var(--color-seal)]/10 px-3 py-2 text-[10px] font-bold text-[var(--color-seal)] uppercase tracking-wider flex items-center gap-1.5 border-b border-[var(--color-seal)]/20">
                    <CheckCircle className="w-3 h-3" />
                    Admin Response
                  </div>
                  <div className="p-3 text-xs text-[var(--color-ink)] font-medium leading-relaxed">
                    {selectedTicket.admin_response}
                  </div>
                </div>
              )}
              
              <div className="mt-4 flex items-center gap-2 text-[10px] text-[var(--color-muted)] font-medium">
                <Calendar className="w-3 h-3" />
                {new Date(selectedTicket.created_at).toLocaleString()}
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-2 animate-in fade-in duration-200">
            {isLoading ? (
              <div className="text-center text-xs text-[var(--color-muted)] py-8">Loading tickets...</div>
            ) : tickets.length === 0 ? (
              <div className="text-center py-8">
                <div className="mx-auto w-8 h-8 rounded-full bg-[var(--color-canvas)] flex items-center justify-center mb-2">
                  <FileText className="w-4 h-4 text-[var(--color-muted)]" />
                </div>
                <p className="text-xs text-[var(--color-muted)]">No tickets found.</p>
              </div>
            ) : (
              tickets.map((ticket) => (
                <button
                  key={ticket.ticket_id}
                  onClick={() => setSelectedTicket(ticket)}
                  className="w-full text-left p-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-canvas)] hover:border-[var(--color-seal)] hover:shadow-sm transition-all group"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-mono text-xs font-bold text-[var(--color-ink)] group-hover:text-[var(--color-seal)] transition-colors">
                      {ticket.ticket_id}
                    </span>
                    {ticket.status === 'resolved' || ticket.status === 'closed' ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />
                    ) : ticket.status === 'in_progress' ? (
                      <CircleDashed className="w-3.5 h-3.5 text-amber-500" />
                    ) : (
                      <CircleDashed className="w-3.5 h-3.5 text-blue-500" />
                    )}
                  </div>
                  <div className="text-[11px] text-[var(--color-muted)] truncate mt-1">
                    {ticket.title}
                  </div>
                </button>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}
