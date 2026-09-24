"use client";

import { useState, useEffect } from "react";
import { AlertCircle, CheckCircle2, UserPlus, RefreshCw, User, Users, Trash2 } from "lucide-react";

export default function AdminEmployeesTab() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  interface Employee {
    id: number;
    name: string;
    email: string;
    role: string;
  }

  const [users, setUsers] = useState<Employee[]>([]);
  const [isLoadingUsers, setIsLoadingUsers] = useState(true);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  async function fetchUsers() {
    setIsLoadingUsers(true);
    try {
      const res = await fetch("/api/admin/users", { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setUsers(data);
      }
    } catch (err) {
      console.error("Failed to fetch users", err);
    } finally {
      setIsLoadingUsers(false);
    }
  }

  // Fetch on mount
  useEffect(() => {
    fetchUsers();
  }, []);

  async function handleDeleteUser(id: number, userEmail: string) {
    if (!window.confirm(`Are you sure you want to delete employee ${userEmail}?`)) return;
    setDeletingId(id);
    try {
      const res = await fetch(`/api/admin/users/${id}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to delete user");
      }
      setFeedbackMsg({ type: "success", text: `Deleted employee ${userEmail}.` });
      fetchUsers();
    } catch (err) {
      setFeedbackMsg({ type: "error", text: err instanceof Error ? err.message : "Error deleting user." });
    } finally {
      setDeletingId(null);
    }
  }

  async function handleCreateUser(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !email.trim() || password.length < 8) {
      setFeedbackMsg({ type: "error", text: "Please fill all fields. Password must be at least 8 characters." });
      return;
    }

    setIsSubmitting(true);
    setFeedbackMsg(null);

    try {
      const res = await fetch("/api/admin/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          name: name.trim(),
          email: email.trim(),
          password: password,
        }),
      });

      if (!res.ok) {
        let errText = "Failed to create employee.";
        try {
          const errData = await res.json();
          if (typeof errData.detail === "string") errText = errData.detail;
        } catch {
          // Ignore
        }
        throw new Error(errText);
      }

      setFeedbackMsg({ type: "success", text: `Successfully generated credentials for ${email}.` });
      setName("");
      setEmail("");
      setPassword("");
      fetchUsers();
    } catch (err) {
      setFeedbackMsg({ type: "error", text: err instanceof Error ? err.message : "An error occurred." });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="space-y-8">
      <div className="pb-1">
        <h3
          className="text-lg font-medium text-[var(--color-ink)]"
          style={{ fontFamily: "var(--font-stack-serif)" }}
        >
          Employee Management
        </h3>
        <p className="mt-0.5 text-xs text-[var(--color-muted)]">
          Generate credentials for new employees so they can access the knowledge agent.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
        {/* Left Side: Create Form */}
        <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-paper)] p-6 shadow-xs w-full">
          <div className="flex items-center gap-2.5 border-b border-[var(--color-border)] pb-4 mb-5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--color-seal-soft)] text-[var(--color-seal)]">
              <UserPlus className="h-4 w-4" />
            </div>
            <div>
              <h3 className="text-base font-medium text-[var(--color-ink)]">
                Create Employee Account
              </h3>
              <p className="text-xs text-[var(--color-muted)]">
                Employees cannot sign up themselves. Admins must generate their ID and password.
              </p>
            </div>
          </div>

          <form onSubmit={handleCreateUser} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-[var(--color-ink)] mb-1">
                Full Name
              </label>
              <div className="relative">
                <User className="absolute left-3 top-2.5 h-4 w-4 text-[var(--color-muted)]" />
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-canvas)] pl-9 pr-3 py-2 text-sm text-[var(--color-ink)] focus:outline-none focus:border-[var(--color-seal)] transition-colors"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[var(--color-ink)] mb-1">
                Employee Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-canvas)] px-3 py-2 text-sm text-[var(--color-ink)] focus:outline-none focus:border-[var(--color-seal)] transition-colors"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[var(--color-ink)] mb-1">
                Initial Password
              </label>
              <input
                type="text"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={8}
                className="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-canvas)] px-3 py-2 text-sm text-[var(--color-ink)] focus:outline-none focus:border-[var(--color-seal)] transition-colors"
                required
              />
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full flex items-center justify-center gap-2 rounded-xl bg-[var(--color-ink)] px-6 py-2.5 text-sm font-medium text-white shadow-xs hover:bg-[var(--color-ink-soft)] disabled:opacity-50 disabled:cursor-not-allowed transition-all cursor-pointer mt-2"
            >
              {isSubmitting ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  Creating Account...
                </>
              ) : (
                <>
                  <UserPlus className="h-4 w-4" />
                  Generate Credentials
                </>
              )}
            </button>

            {/* Status Message */}
            {feedbackMsg && (
              <div
                className={`flex items-start gap-2.5 rounded-xl border px-4 py-3 text-xs font-medium transition-all ${
                  feedbackMsg.type === "success"
                    ? "border-[var(--color-seal)]/30 bg-[var(--color-seal-soft)] text-[var(--color-seal)]"
                    : "border-[var(--color-flag-border)] bg-[var(--color-flag-surface)] text-[var(--color-flag)]"
                }`}
              >
                {feedbackMsg.type === "success" ? (
                  <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
                ) : (
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                )}
                <span>{feedbackMsg.text}</span>
              </div>
            )}
          </form>
        </div>

        {/* Right Side: Employee List */}
        <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-paper)] p-6 shadow-xs w-full">
          <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-4 mb-5">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--color-canvas)] text-[var(--color-ink)]">
                <Users className="h-4 w-4" />
              </div>
              <div>
                <h3 className="text-base font-medium text-[var(--color-ink)]">
                  Active Employees
                </h3>
                <p className="text-xs text-[var(--color-muted)]">
                  {users.length} {users.length === 1 ? 'employee' : 'employees'} registered
                </p>
              </div>
            </div>
            <button
              onClick={fetchUsers}
              disabled={isLoadingUsers}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-[var(--color-muted)] hover:text-[var(--color-ink)] rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-canvas)] transition-all cursor-pointer"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isLoadingUsers ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>

          {isLoadingUsers ? (
            <div className="py-12 text-center text-sm text-[var(--color-muted)]">
              Loading employees...
            </div>
          ) : users.length === 0 ? (
            <div className="py-12 text-center text-sm text-[var(--color-muted)]">
              No employees found. Generate one to the left.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-[var(--color-border)] text-[var(--color-muted)] font-medium">
                    <th className="pb-3 pt-1 px-3">Name</th>
                    <th className="pb-3 pt-1 px-3">Email</th>
                    <th className="pb-3 pt-1 px-3">Role</th>
                    <th className="pb-3 pt-1 px-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--color-border)]">
                  {users.map((u) => (
                    <tr key={u.id} className="hover:bg-[var(--color-canvas)]/50 transition-colors">
                      <td className="py-3 px-3 font-medium text-[var(--color-ink)]">
                        {u.name}
                      </td>
                      <td className="py-3 px-3 text-[var(--color-muted)]">
                        {u.email}
                      </td>
                      <td className="py-3 px-3">
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-[var(--color-seal-soft)] px-2.5 py-0.5 text-[10px] font-medium text-[var(--color-seal)] border border-[var(--color-seal)]/20 uppercase">
                          {u.role}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right">
                        <button
                          onClick={() => handleDeleteUser(u.id, u.email)}
                          disabled={deletingId === u.id}
                          className="inline-flex items-center gap-1 text-xs text-[var(--color-muted)] hover:text-red-600 p-1.5 rounded-lg hover:bg-red-50 transition-colors cursor-pointer disabled:opacity-50"
                        >
                          {deletingId === u.id ? (
                            <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Trash2 className="h-3.5 w-3.5" />
                          )}
                          <span className="hidden sm:inline text-[11px]">Delete</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
