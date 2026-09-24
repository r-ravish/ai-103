"use client";

import { useState } from "react";
import { AlertCircle, CheckCircle2, UserPlus, RefreshCw, User } from "lucide-react";

export default function AdminEmployeesTab() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

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

      <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-paper)] p-6 shadow-xs max-w-xl">
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
    </div>
  );
}
