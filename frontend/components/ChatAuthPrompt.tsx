"use client";

import { useState } from "react";
import { Lock, UserPlus, LogIn, AlertCircle, ArrowRight, Loader2 } from "lucide-react";
import { useAuth } from "@/lib/auth-context";

interface ChatAuthPromptProps {
  onSuccess?: () => void;
}

export default function ChatAuthPrompt({ onSuccess }: ChatAuthPromptProps) {
  const { login, signup } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!email || !password) {
      setError("Please fill in all required fields.");
      return;
    }

    if (mode === "signup" && !name.trim()) {
      setError("Please enter your name.");
      return;
    }

    if (mode === "signup" && password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    setIsSubmitting(true);

    try {
      if (mode === "login") {
        const res = await login(email, password);
        if (!res.success) {
          setError(res.error || "Invalid email or password.");
        } else {
          onSuccess?.();
        }
      } else {
        const res = await signup(name, email, password);
        if (!res.success) {
          setError(res.error || "Registration failed. Please check your inputs.");
        } else {
          onSuccess?.();
        }
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="border-t border-[var(--color-border)] bg-[var(--color-paper)] px-4 py-4 sm:px-6 shadow-xs">
      <div className="mx-auto max-w-3xl rounded-2xl border border-[var(--color-border)] bg-[var(--color-canvas)] p-4 sm:p-5">
        {/* Header & Mode Switcher */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[var(--color-border)] pb-3 mb-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--color-seal-soft)] text-[var(--color-seal)] shrink-0">
              <Lock className="h-4 w-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-[var(--color-ink)]">
                {mode === "login" ? "Sign in to ask questions" : "Create employee account"}
              </h3>
              <p className="text-xs text-[var(--color-muted)]">
                {mode === "login"
                  ? "Authentication is required to query internal company policies & guidelines"
                  : "All new accounts are given Employee access immediately"}
              </p>
            </div>
          </div>

          {/* Toggle between Login and Signup */}
          <div className="flex items-center bg-[var(--color-paper)] p-0.5 rounded-lg border border-[var(--color-border)] self-start sm:self-auto">
            <button
              type="button"
              onClick={() => {
                setMode("login");
                setError(null);
              }}
              className={`flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-md transition-all cursor-pointer ${
                mode === "login"
                  ? "bg-[var(--color-ink)] text-white shadow-xs"
                  : "text-[var(--color-muted)] hover:text-[var(--color-ink)]"
              }`}
            >
              <LogIn className="h-3.5 w-3.5" />
              Sign in
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("signup");
                setError(null);
              }}
              className={`flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-md transition-all cursor-pointer ${
                mode === "signup"
                  ? "bg-[var(--color-ink)] text-white shadow-xs"
                  : "text-[var(--color-muted)] hover:text-[var(--color-ink)]"
              }`}
            >
              <UserPlus className="h-3.5 w-3.5" />
              Create account
            </button>
          </div>
        </div>

        {/* Error notification */}
        {error && (
          <div className="mb-4 flex items-start gap-2 rounded-xl border border-[var(--color-flag-border)] bg-[var(--color-flag-surface)] p-2.5 text-xs text-[var(--color-flag)]">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-3">
          {mode === "signup" && (
            <div>
              <label className="block text-xs font-medium text-[var(--color-ink-soft)] mb-1">
                Full Name or Employee ID
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. EMP-1048"
                required
                disabled={isSubmitting}
                className="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-paper)] px-3 py-2 text-xs text-[var(--color-ink)] placeholder:text-[var(--color-muted)] focus:border-[var(--color-seal)] focus:outline-none transition-colors"
              />
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-[var(--color-ink-soft)] mb-1">
                Work Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                required
                disabled={isSubmitting}
                className="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-paper)] px-3 py-2 text-xs text-[var(--color-ink)] placeholder:text-[var(--color-muted)] focus:border-[var(--color-seal)] focus:outline-none transition-colors"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-[var(--color-ink-soft)] mb-1">
                Password {mode === "signup" && <span className="text-[var(--color-muted)]">(min 8 chars)</span>}
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={mode === "signup" ? "••••••••" : "Enter password"}
                required
                disabled={isSubmitting}
                className="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-paper)] px-3 py-2 text-xs text-[var(--color-ink)] placeholder:text-[var(--color-muted)] focus:border-[var(--color-seal)] focus:outline-none transition-colors"
              />
            </div>
          </div>

          <div className="flex items-center justify-between pt-1">
            <span className="text-[11px] text-[var(--color-muted)]">
              {mode === "login"
                ? "First time here? Switch to 'Create account' to get started."
                : "Accounts are provisioned with standard employee access."}
            </span>

            <button
              type="submit"
              disabled={isSubmitting}
              className="flex items-center gap-1.5 rounded-xl bg-[var(--color-ink)] px-4 py-2 text-xs font-medium text-white shadow-xs hover:bg-[var(--color-ink-soft)] disabled:opacity-50 disabled:cursor-not-allowed transition-all cursor-pointer shrink-0"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  {mode === "login" ? "Signing in…" : "Creating account…"}
                </>
              ) : (
                <>
                  {mode === "login" ? "Sign in" : "Create account"}
                  <ArrowRight className="h-3.5 w-3.5" />
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
