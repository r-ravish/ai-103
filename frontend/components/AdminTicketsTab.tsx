"use client";

import { useEffect, useState, useTransition } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Filter,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Tag,
  Trash2,
  User,
  X,
  FileText,
  Check,
} from "lucide-react";

export interface EmployeeSummary {
  id: number;
  employee_code: string;
  name: string;
  email: string;
  role: string;
}

export interface EscalationEventSummary {
  id: number;
  question: string;
  reason: string | null;
  created_at: string;
}

export interface TicketAdminItem {
  id: number;
  ticket_id: string;
  title: string;
  description: string;
  priority: "low" | "medium" | "high";
  status: "open" | "in_progress" | "resolved" | "closed";
  is_acknowledged: boolean;
  acknowledged_at: string | null;
  admin_notes: string | null;
  admin_response: string | null;
  created_at: string;
  employee: EmployeeSummary | null;
  acknowledged_by: EmployeeSummary | null;
  escalation_events: EscalationEventSummary[];
}

export interface TicketListAdminResponse {
  tickets: TicketAdminItem[];
  total: number;
  open_count: number;
  in_progress_count: number;
  resolved_count: number;
  acknowledged_count: number;
}

export default function AdminTicketsTab() {
  const [data, setData] = useState<TicketListAdminResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [ackFilter, setAckFilter] = useState<string>("all");
  const [priorityFilter, setPriorityFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [editingNotes, setEditingNotes] = useState<Record<string, string>>({});
  const [editingResponses, setEditingResponses] = useState<Record<string, string>>({});
  const [updatingTicketId, setUpdatingTicketId] = useState<string | null>(null);
  const [feedbackMsg, setFeedbackMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [, startTransition] = useTransition();

  // Create ticket modal state
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newPriority, setNewPriority] = useState<"low" | "medium" | "high">("medium");
  const [newEmployeeEmail, setNewEmployeeEmail] = useState("");
  const [newIsAcknowledged, setNewIsAcknowledged] = useState(false);
  const [newAdminNotes, setNewAdminNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function fetchTickets() {
    setIsLoading(true);
    try {
      const params = new URLSearchParams();
      if (statusFilter !== "all") params.append("status", statusFilter);
      if (ackFilter === "acknowledged") params.append("acknowledged", "true");
      if (ackFilter === "pending") params.append("acknowledged", "false");
      if (priorityFilter !== "all") params.append("priority", priorityFilter);
      if (searchQuery.trim()) params.append("search", searchQuery.trim());

      const res = await fetch(`/api/admin/tickets?${params.toString()}`, {
        credentials: "include",
      });
      if (res.ok) {
        const json: TicketListAdminResponse = await res.json();
        setData(json);
        // Initialize note draft state
        const drafts: Record<string, string> = {};
        const responseDrafts: Record<string, string> = {};
        json.tickets.forEach((t) => {
          drafts[t.ticket_id] = t.admin_notes || "";
          responseDrafts[t.ticket_id] = t.admin_response || "";
        });
        setEditingNotes(drafts);
        setEditingResponses(responseDrafts);
      } else {
        console.error("Failed to fetch admin tickets:", res.statusText);
      }
    } catch (err) {
      console.error("Error fetching tickets:", err);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    fetchTickets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, ackFilter, priorityFilter]);

  function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    fetchTickets();
  }

  async function handleToggleAcknowledged(ticket: TicketAdminItem) {
    const nextState = !ticket.is_acknowledged;
    setUpdatingTicketId(ticket.ticket_id);
    try {
      const res = await fetch(`/api/admin/tickets/${ticket.ticket_id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          is_acknowledged: nextState,
          status: nextState && ticket.status === "open" ? "in_progress" : ticket.status,
        }),
      });

      if (!res.ok) throw new Error("Failed to update status");
      const updated: TicketAdminItem = await res.json();

      startTransition(() => {
        setData((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            acknowledged_count: nextState ? prev.acknowledged_count + 1 : prev.acknowledged_count - 1,
            tickets: prev.tickets.map((t) => (t.ticket_id === updated.ticket_id ? updated : t)),
          };
        });
      });

      setFeedbackMsg({
        type: "success",
        text: `Concern ${ticket.ticket_id} marked as ${nextState ? "taken into account" : "pending review"}.`,
      });
      setTimeout(() => setFeedbackMsg(null), 3500);
    } catch (err) {
      setFeedbackMsg({ type: "error", text: "Failed to update acknowledgment status." });
    } finally {
      setUpdatingTicketId(null);
    }
  }

  async function handleStatusChange(ticketId: string, nextStatus: string) {
    setUpdatingTicketId(ticketId);
    try {
      const res = await fetch(`/api/admin/tickets/${ticketId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ status: nextStatus }),
      });

      if (!res.ok) throw new Error("Failed to update status");
      const updated: TicketAdminItem = await res.json();

      startTransition(() => {
        setData((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            tickets: prev.tickets.map((t) => (t.ticket_id === updated.ticket_id ? updated : t)),
          };
        });
      });

      setFeedbackMsg({ type: "success", text: `Status for ${ticketId} updated to ${nextStatus}.` });
      setTimeout(() => setFeedbackMsg(null), 3000);
    } catch (err) {
      setFeedbackMsg({ type: "error", text: "Failed to update ticket status." });
    } finally {
      setUpdatingTicketId(null);
    }
  }

  async function handleSaveNotes(ticketId: string) {
    const noteText = editingNotes[ticketId] ?? "";
    setUpdatingTicketId(ticketId);
    try {
      const res = await fetch(`/api/admin/tickets/${ticketId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ admin_notes: noteText }),
      });

      if (!res.ok) throw new Error("Failed to save note");
      const updated: TicketAdminItem = await res.json();

      startTransition(() => {
        setData((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            tickets: prev.tickets.map((t) => (t.ticket_id === updated.ticket_id ? updated : t)),
          };
        });
      });

      setFeedbackMsg({ type: "success", text: `Admin note saved for ${ticketId}.` });
      setTimeout(() => setFeedbackMsg(null), 3000);
    } catch (err) {
      setFeedbackMsg({ type: "error", text: "Failed to save note." });
    } finally {
      setUpdatingTicketId(null);
    }
  }

  async function handleSaveResponse(ticketId: string) {
    const responseText = editingResponses[ticketId] ?? "";
    setUpdatingTicketId(ticketId);
    try {
      const res = await fetch(`/api/admin/tickets/${ticketId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ admin_response: responseText }),
      });

      if (!res.ok) throw new Error("Failed to save response");
      const updated: TicketAdminItem = await res.json();

      startTransition(() => {
        setData((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            tickets: prev.tickets.map((t) => (t.ticket_id === updated.ticket_id ? updated : t)),
          };
        });
      });

      setFeedbackMsg({ type: "success", text: `Employee response saved for ${ticketId}. The employee will see this when checking their ticket.` });
      setTimeout(() => setFeedbackMsg(null), 4000);
    } catch (err) {
      setFeedbackMsg({ type: "error", text: "Failed to save response." });
    } finally {
      setUpdatingTicketId(null);
    }
  }

  async function handleDeleteTicket(ticketId: string) {
    if (!window.confirm(`Are you sure you want to delete ticket ${ticketId}? This cannot be undone.`)) {
      return;
    }
    try {
      const res = await fetch(`/api/admin/tickets/${ticketId}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!res.ok) throw new Error("Failed to delete ticket");

      setFeedbackMsg({ type: "success", text: `Ticket ${ticketId} deleted.` });
      setTimeout(() => setFeedbackMsg(null), 3000);
      await fetchTickets();
    } catch (err) {
      setFeedbackMsg({ type: "error", text: "Failed to delete ticket." });
    }
  }

  async function handleCreateTicket(e: React.FormEvent) {
    e.preventDefault();
    if (!newTitle.trim() || !newDescription.trim()) return;

    setIsSubmitting(true);
    try {
      const res = await fetch("/api/admin/tickets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          title: newTitle.trim(),
          description: newDescription.trim(),
          priority: newPriority,
          employee_email: newEmployeeEmail.trim() || undefined,
          is_acknowledged: newIsAcknowledged,
          admin_notes: newAdminNotes.trim() || undefined,
        }),
      });

      if (!res.ok) throw new Error("Failed to create ticket");

      setFeedbackMsg({ type: "success", text: "New concern ticket logged successfully." });
      setTimeout(() => setFeedbackMsg(null), 3500);

      // Reset form
      setNewTitle("");
      setNewDescription("");
      setNewEmployeeEmail("");
      setNewAdminNotes("");
      setNewIsAcknowledged(false);
      setIsCreateOpen(false);

      await fetchTickets();
    } catch (err) {
      setFeedbackMsg({ type: "error", text: "Failed to log concern ticket." });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Feedback Banner */}
      {feedbackMsg && (
        <div
          className={`flex items-center gap-2 rounded-xl border px-4 py-3 text-xs font-medium transition-all ${
            feedbackMsg.type === "success"
              ? "border-[var(--color-seal)]/30 bg-[var(--color-seal-soft)] text-[var(--color-seal)]"
              : "border-[var(--color-flag-border)] bg-[var(--color-flag-surface)] text-[var(--color-flag)]"
          }`}
        >
          {feedbackMsg.type === "success" ? (
            <CheckCircle2 className="h-4 w-4 shrink-0" />
          ) : (
            <AlertCircle className="h-4 w-4 shrink-0" />
          )}
          <span>{feedbackMsg.text}</span>
        </div>
      )}

      {/* KPI Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
        <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-paper)] p-4 shadow-xs">
          <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-muted)]">
            Total Concerns
          </span>
          <div className="mt-1 text-2xl font-semibold text-[var(--color-ink)]">
            {data?.total ?? 0}
          </div>
          <span className="text-[11px] text-[var(--color-muted)]">Recorded tokens</span>
        </div>

        <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-paper)] p-4 shadow-xs">
          <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-flag)]">
            Open / Pending
          </span>
          <div className="mt-1 text-2xl font-semibold text-[var(--color-flag)]">
            {data?.open_count ?? 0}
          </div>
          <span className="text-[11px] text-[var(--color-muted)]">Requires review</span>
        </div>

        <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-paper)] p-4 shadow-xs">
          <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-seal)]">
            Taken into Account
          </span>
          <div className="mt-1 text-2xl font-semibold text-[var(--color-seal)]">
            {data?.acknowledged_count ?? 0}
          </div>
          <span className="text-[11px] text-[var(--color-muted)]">Acknowledged by Admin</span>
        </div>

        <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-paper)] p-4 shadow-xs">
          <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-ink-soft)]">
            Resolved / Closed
          </span>
          <div className="mt-1 text-2xl font-semibold text-[var(--color-ink-soft)]">
            {data?.resolved_count ?? 0}
          </div>
          <span className="text-[11px] text-[var(--color-muted)]">Addressed & finalized</span>
        </div>
      </div>

      {/* Action and Filter Toolbar */}
      <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-paper)] p-4 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          {/* Status Tabs */}
          <div className="flex flex-wrap items-center gap-1.5">
            {[
              { id: "all", label: "All" },
              { id: "open", label: "Open" },
              { id: "in_progress", label: "In Progress" },
              { id: "resolved", label: "Resolved" },
              { id: "closed", label: "Closed" },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setStatusFilter(tab.id)}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all cursor-pointer ${
                  statusFilter === tab.id
                    ? "bg-[var(--color-ink)] text-white shadow-xs"
                    : "bg-[var(--color-canvas)] text-[var(--color-muted)] hover:text-[var(--color-ink)] border border-[var(--color-border)]"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 self-end sm:self-auto">
            <button
              onClick={() => setIsCreateOpen(true)}
              className="flex items-center gap-1.5 rounded-xl bg-[var(--color-ink)] px-3.5 py-2 text-xs font-medium text-white shadow-xs hover:bg-[var(--color-ink-soft)] transition-colors cursor-pointer"
            >
              <Plus className="h-3.5 w-3.5" />
              Log Concern
            </button>

            <button
              onClick={fetchTickets}
              disabled={isLoading}
              title="Refresh tickets"
              className="flex items-center gap-1 px-3 py-2 text-xs font-medium text-[var(--color-muted)] hover:text-[var(--color-ink)] rounded-xl border border-[var(--color-border)] bg-[var(--color-canvas)] transition-all cursor-pointer"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>
        </div>

        {/* Filters and Search Bar */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 pt-3 border-t border-[var(--color-border)]">
          {/* Acknowledgment Filter */}
          <div className="flex items-center gap-1.5 text-xs text-[var(--color-muted)]">
            <Filter className="h-3.5 w-3.5 shrink-0" />
            <select
              value={ackFilter}
              onChange={(e) => setAckFilter(e.target.value)}
              className="rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-ink)] focus:outline-none focus:border-[var(--color-seal)] cursor-pointer"
            >
              <option value="all">All Considerations</option>
              <option value="acknowledged">Taken Into Account</option>
              <option value="pending">Pending Consideration</option>
            </select>
          </div>

          {/* Priority Filter */}
          <div className="flex items-center gap-1.5 text-xs text-[var(--color-muted)]">
            <Tag className="h-3.5 w-3.5 shrink-0" />
            <select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              className="rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-ink)] focus:outline-none focus:border-[var(--color-seal)] cursor-pointer"
            >
              <option value="all">All Priorities</option>
              <option value="high">High Priority</option>
              <option value="medium">Medium Priority</option>
              <option value="low">Low Priority</option>
            </select>
          </div>

          {/* Search Input */}
          <form onSubmit={handleSearchSubmit} className="flex-1 flex items-center gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-[var(--color-muted)]" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search token, concern, employee code, name..."
                className="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-canvas)] pl-8 pr-3 py-1.5 text-xs text-[var(--color-ink)] placeholder-[var(--color-muted)] focus:outline-none focus:border-[var(--color-seal)]"
              />
            </div>
            {searchQuery && (
              <button
                type="button"
                onClick={() => {
                  setSearchQuery("");
                  setTimeout(fetchTickets, 50);
                }}
                className="text-xs text-[var(--color-muted)] hover:text-[var(--color-ink)] px-2 py-1.5 cursor-pointer"
              >
                Clear
              </button>
            )}
            <button
              type="submit"
              className="rounded-xl border border-[var(--color-border)] bg-[var(--color-canvas)] px-3 py-1.5 text-xs font-medium text-[var(--color-ink)] hover:bg-[var(--color-border)] transition-colors cursor-pointer"
            >
              Search
            </button>
          </form>
        </div>
      </div>

      {/* Ticket / Concern Cards List */}
      {isLoading ? (
        <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-paper)] p-12 text-center text-sm text-[var(--color-muted)] flex items-center justify-center gap-2">
          <RefreshCw className="h-4 w-4 animate-spin" />
          Loading employee concerns and tokens...
        </div>
      ) : !data || data.tickets.length === 0 ? (
        <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-paper)] p-12 text-center space-y-3">
          <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--color-canvas)] text-[var(--color-muted)]">
            <FileText className="h-5 w-5" />
          </div>
          <h3 className="text-base font-medium text-[var(--color-ink)]">No concern tokens found</h3>
          <p className="text-xs text-[var(--color-muted)] max-w-sm mx-auto">
            {searchQuery || statusFilter !== "all" || ackFilter !== "all"
              ? "No tickets match your filter criteria. Try resetting filters."
              : "No support tickets or employee concerns have been logged yet."}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {data.tickets.map((ticket) => {
            const isPending = updatingTicketId === ticket.ticket_id;
            return (
              <div
                key={ticket.ticket_id}
                className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-paper)] p-5 shadow-xs transition-all hover:border-[var(--color-border-strong)] space-y-4"
              >
                {/* Top Row: Token ID, Badges, Time, Delete */}
                <div className="flex flex-wrap items-center justify-between gap-2.5 border-b border-[var(--color-border)] pb-3">
                  <div className="flex items-center gap-2">
                    {/* Token ID Monospace Chip */}
                    <span className="font-mono text-xs font-bold px-2 py-0.5 rounded-md bg-[var(--color-canvas)] text-[var(--color-ink)] border border-[var(--color-border)]">
                      {ticket.ticket_id}
                    </span>

                    {/* Priority Badge */}
                    <span
                      className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full border ${
                        ticket.priority === "high"
                          ? "border-red-200 bg-red-50 text-red-700"
                          : ticket.priority === "medium"
                          ? "border-amber-200 bg-amber-50 text-amber-700"
                          : "border-gray-200 bg-gray-50 text-gray-700"
                      }`}
                    >
                      {ticket.priority} priority
                    </span>

                    {/* Status Badge */}
                    <span
                      className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full border ${
                        ticket.status === "open"
                          ? "border-amber-300 bg-amber-50 text-amber-800"
                          : ticket.status === "in_progress"
                          ? "border-blue-300 bg-blue-50 text-blue-800"
                          : ticket.status === "resolved"
                          ? "border-[var(--color-seal)]/30 bg-[var(--color-seal-soft)] text-[var(--color-seal)]"
                          : "border-gray-300 bg-gray-100 text-gray-700"
                      }`}
                    >
                      {ticket.status.replace("_", " ")}
                    </span>
                  </div>

                  <div className="flex items-center gap-3 text-xs text-[var(--color-muted)]">
                    <span className="flex items-center gap-1 text-[11px]">
                      <Clock className="h-3 w-3" />
                      {new Date(ticket.created_at).toLocaleString(undefined, {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>

                    <button
                      onClick={() => handleDeleteTicket(ticket.ticket_id)}
                      title="Delete / Dismiss ticket"
                      className="text-[var(--color-muted)] hover:text-red-600 transition-colors p-1 rounded hover:bg-red-50 cursor-pointer"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>

                {/* Employee Attribution Chip (Anti-Misuse & Audit) */}
                <div className="flex flex-wrap items-center justify-between gap-3 bg-[var(--color-canvas)] rounded-xl p-3 border border-[var(--color-border)]">
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-white border border-[var(--color-border)] text-[var(--color-ink)]">
                      <User className="h-3.5 w-3.5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-[var(--color-ink)]">
                          {ticket.employee?.name || "System Escalation"}
                        </span>
                        <span className="font-mono text-[11px] font-bold text-[var(--color-ink-soft)] px-1.5 py-0.2 rounded bg-white border border-[var(--color-border)]">
                          {ticket.employee?.employee_code || "SYSTEM"}
                        </span>
                        <span className="inline-flex items-center gap-0.5 text-[10px] text-[var(--color-seal)] font-medium bg-[var(--color-seal-soft)] px-1.5 py-0.2 rounded border border-[var(--color-seal)]/20">
                          <ShieldCheck className="h-2.5 w-2.5" />
                          Verified
                        </span>
                      </div>
                      <div className="text-[11px] text-[var(--color-muted)] font-sans">
                        {ticket.employee?.email || "Generated via knowledge gap policy escalation"}
                      </div>
                    </div>
                  </div>

                  {/* Taken Into Account Action Toggle Button */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleToggleAcknowledged(ticket)}
                      disabled={isPending}
                      className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-xl border transition-all cursor-pointer ${
                        ticket.is_acknowledged
                          ? "bg-[var(--color-seal-soft)] border-[var(--color-seal)]/40 text-[var(--color-seal)] hover:bg-emerald-100"
                          : "bg-white border-[var(--color-border)] text-[var(--color-muted)] hover:text-[var(--color-ink)] hover:border-[var(--color-seal)] shadow-xs"
                      }`}
                    >
                      {ticket.is_acknowledged ? (
                        <>
                          <Check className="h-3.5 w-3.5 stroke-[2.5]" />
                          <span>Taken into Account</span>
                        </>
                      ) : (
                        <>
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          <span>Take into Account</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {/* Concern Content: Title & Details */}
                <div className="space-y-1.5">
                  <h4
                    className="text-base font-semibold text-[var(--color-ink)]"
                    style={{ fontFamily: "var(--font-stack-serif)" }}
                  >
                    {ticket.title}
                  </h4>
                  <p className="text-xs text-[var(--color-ink-soft)] leading-relaxed whitespace-pre-wrap bg-white/60 p-3 rounded-xl border border-[var(--color-border)]">
                    {ticket.description}
                  </p>
                </div>

                {/* Acknowledgment metadata if taken into account */}
                {ticket.is_acknowledged && ticket.acknowledged_by && (
                  <div className="flex items-center gap-1.5 text-[11px] text-[var(--color-seal)] font-medium">
                    <CheckCircle2 className="h-3 w-3" />
                    <span>
                      Taken into account by {ticket.acknowledged_by.name} ({ticket.acknowledged_by.employee_code})
                      {ticket.acknowledged_at && ` on ${new Date(ticket.acknowledged_at).toLocaleDateString()}`}
                    </span>
                  </div>
                )}

                {/* Admin Management Section: Status, Notes, and Employee Response */}
                <div className="border-t border-[var(--color-border)] pt-3.5 space-y-3.5">
                  {/* Status row */}
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-medium text-[var(--color-muted)]">
                      Update Status:
                    </span>
                    <select
                      value={ticket.status}
                      onChange={(e) => handleStatusChange(ticket.ticket_id, e.target.value)}
                      disabled={isPending}
                      className="rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] px-2 py-1 text-xs font-medium text-[var(--color-ink)] focus:outline-none focus:border-[var(--color-seal)] cursor-pointer"
                    >
                      <option value="open">Open</option>
                      <option value="in_progress">In Progress</option>
                      <option value="resolved">Resolved</option>
                      <option value="closed">Closed</option>
                    </select>
                  </div>

                  {/* Response to Employee — VISIBLE TO EMPLOYEE */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[11px] font-semibold text-[var(--color-ink)]">
                          Response to Employee
                        </span>
                        <span className="inline-flex items-center gap-0.5 rounded-full bg-[var(--color-seal-soft)] border border-[var(--color-seal)]/20 px-2 py-0.5 text-[10px] font-medium text-[var(--color-seal)]">
                          Visible to employee
                        </span>
                      </div>
                      <button
                        onClick={() => handleSaveResponse(ticket.ticket_id)}
                        disabled={isPending}
                        className="flex items-center gap-1 text-xs font-medium bg-[var(--color-seal)] text-white px-3 py-1 rounded-lg hover:opacity-90 transition-opacity cursor-pointer"
                      >
                        Save Response
                      </button>
                    </div>
                    <textarea
                      rows={2}
                      value={editingResponses[ticket.ticket_id] ?? ""}
                      onChange={(e) =>
                        setEditingResponses({
                          ...editingResponses,
                          [ticket.ticket_id]: e.target.value,
                        })
                      }
                      placeholder="Write a brief 1–2 line reply for the employee (e.g. 'We have reviewed your concern and updated the policy — please re-read the IT Security document.')…"
                      className="w-full rounded-xl border border-[var(--color-seal)]/30 bg-[var(--color-seal-soft)]/30 p-2.5 text-xs text-[var(--color-ink)] placeholder-[var(--color-muted)] focus:outline-none focus:border-[var(--color-seal)]"
                    />
                  </div>

                  {/* Internal Admin Notes — NOT visible to employee */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[11px] font-semibold text-[var(--color-ink)]">
                          Internal Admin Notes
                        </span>
                        <span className="inline-flex items-center gap-0.5 rounded-full bg-[var(--color-canvas)] border border-[var(--color-border)] px-2 py-0.5 text-[10px] font-medium text-[var(--color-muted)]">
                          Internal only
                        </span>
                      </div>
                      <button
                        onClick={() => handleSaveNotes(ticket.ticket_id)}
                        disabled={isPending}
                        className="flex items-center gap-1 text-xs font-medium bg-[var(--color-ink)] text-white px-3 py-1 rounded-lg hover:bg-[var(--color-ink-soft)] transition-colors cursor-pointer"
                      >
                        Save Note
                      </button>
                    </div>
                    <textarea
                      rows={2}
                      value={editingNotes[ticket.ticket_id] ?? ""}
                      onChange={(e) =>
                        setEditingNotes({
                          ...editingNotes,
                          [ticket.ticket_id]: e.target.value,
                        })
                      }
                      placeholder="Add internal review notes, action steps, or escalation plan (not shown to the employee)…"
                      className="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-canvas)] p-2.5 text-xs text-[var(--color-ink)] placeholder-[var(--color-muted)] focus:outline-none focus:border-[var(--color-seal)]"
                    />
                  </div>
                </div>
              </div>

            );
          })}
        </div>
      )}

      {/* Modal: Log New Concern Manually */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="max-w-lg w-full rounded-2xl border border-[var(--color-border)] bg-[var(--color-paper)] p-6 shadow-lg space-y-4">
            <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-3">
              <h3
                className="text-lg font-semibold text-[var(--color-ink)]"
                style={{ fontFamily: "var(--font-stack-serif)" }}
              >
                Log Employee Concern / Ticket
              </h3>
              <button
                onClick={() => setIsCreateOpen(false)}
                className="text-[var(--color-muted)] hover:text-[var(--color-ink)] p-1 rounded cursor-pointer"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleCreateTicket} className="space-y-3.5">
              <div>
                <label className="block text-xs font-medium text-[var(--color-ink)] mb-1">
                  Concern Title *
                </label>
                <input
                  type="text"
                  required
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="e.g. Health Insurance Pre-Authorization Clarification"
                  className="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-canvas)] px-3 py-2 text-xs text-[var(--color-ink)] focus:outline-none focus:border-[var(--color-seal)]"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-[var(--color-ink)] mb-1">
                  Concern Description *
                </label>
                <textarea
                  rows={3}
                  required
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  placeholder="Detailed description of the question, issue, or ambiguity raised..."
                  className="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-canvas)] px-3 py-2 text-xs text-[var(--color-ink)] focus:outline-none focus:border-[var(--color-seal)]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-[var(--color-ink)] mb-1">
                    Priority
                  </label>
                  <select
                    value={newPriority}
                    onChange={(e) => setNewPriority(e.target.value as "low" | "medium" | "high")}
                    className="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-canvas)] px-3 py-2 text-xs text-[var(--color-ink)] focus:outline-none focus:border-[var(--color-seal)] cursor-pointer"
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-[var(--color-ink)] mb-1">
                    Employee Email (Attribution)
                  </label>
                  <input
                    type="email"
                    value={newEmployeeEmail}
                    onChange={(e) => setNewEmployeeEmail(e.target.value)}
                    placeholder="employee@company.com"
                    className="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-canvas)] px-3 py-2 text-xs text-[var(--color-ink)] focus:outline-none focus:border-[var(--color-seal)]"
                  />
                </div>
              </div>

              <div>
                <label className="flex items-center gap-2 cursor-pointer text-xs font-medium text-[var(--color-ink)]">
                  <input
                    type="checkbox"
                    checked={newIsAcknowledged}
                    onChange={(e) => setNewIsAcknowledged(e.target.checked)}
                    className="rounded border-[var(--color-border)] text-[var(--color-seal)] focus:ring-0"
                  />
                  <span>Mark as already Taken into Account</span>
                </label>
              </div>

              <div>
                <label className="block text-xs font-medium text-[var(--color-ink)] mb-1">
                  Initial Admin Notes (Optional)
                </label>
                <input
                  type="text"
                  value={newAdminNotes}
                  onChange={(e) => setNewAdminNotes(e.target.value)}
                  placeholder="Notes on plan or resolution steps..."
                  className="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-canvas)] px-3 py-2 text-xs text-[var(--color-ink)] focus:outline-none focus:border-[var(--color-seal)]"
                />
              </div>

              <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-[var(--color-border)]">
                <button
                  type="button"
                  onClick={() => setIsCreateOpen(false)}
                  className="px-4 py-2 text-xs font-medium text-[var(--color-muted)] hover:text-[var(--color-ink)] rounded-xl border border-[var(--color-border)] cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-white bg-[var(--color-ink)] rounded-xl hover:bg-[var(--color-ink-soft)] transition-colors cursor-pointer"
                >
                  {isSubmitting ? "Saving..." : "Create Ticket Token"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
