"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Home,
  MessageSquare,
  UploadCloud,
  LogOut,
  User as UserIcon,
  Shield,
  PenSquare,
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";

interface HeaderProps {
}

export default function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();

  const handleHomeClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    if (pathname === "/") {
      window.location.href = "/";
    } else {
      router.push("/");
    }
  };

  return (
    <header className="border-b border-[var(--color-border)] bg-[var(--color-paper)] sticky top-0 z-30 shadow-xs">
      <div className="flex w-full items-center justify-between px-4 py-3 sm:px-6">
        {/* Click logo/title to go back to Home page */}
        <Link
          href="/"
          onClick={handleHomeClick}
          className="flex items-center gap-2.5 hover:opacity-85 transition-opacity group cursor-pointer"
          title="Return to Chat Home"
        >
          <svg
            aria-hidden="true"
            viewBox="0 0 32 32"
            className="h-8 w-8 shrink-0 group-hover:scale-105 transition-transform duration-200"
          >
            <rect
              x="1"
              y="1"
              width="30"
              height="30"
              rx="7"
              fill="var(--color-ink)"
            />
            <path
              d="M10 21V11.5L16 16.5L22 11.5V21"
              stroke="var(--color-paper)"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
              fill="none"
            />
          </svg>
          <div className="flex flex-col">
            <h1
              className="text-[17px] font-medium tracking-tight text-[var(--color-ink)]"
              style={{ fontFamily: "var(--font-stack-serif)" }}
            >
              Enterprise Knowledge Agent
            </h1>
            <span className="text-[11px] text-[var(--color-muted)] font-sans -mt-0.5">
              Internal Policy & Knowledge Hub
            </span>
          </div>
        </Link>

        {/* Navigation & User Status */}
        <div className="flex items-center gap-3">
          <nav className="flex items-center gap-1 bg-[var(--color-canvas)] p-1 rounded-lg border border-[var(--color-border)]">
            <Link
              href="/"
              onClick={handleHomeClick}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
                pathname === "/"
                  ? "bg-white text-[var(--color-ink)] shadow-xs"
                  : "text-[var(--color-muted)] hover:text-[var(--color-ink)]"
              }`}
            >
              <Home className="h-3.5 w-3.5" />
              Home
            </Link>
            {user?.role === "admin" && (
              <Link
                href="/admin"
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
                  pathname.startsWith("/admin")
                    ? "bg-white text-[var(--color-ink)] shadow-xs"
                    : "text-[var(--color-muted)] hover:text-[var(--color-ink)]"
                }`}
              >
                <UploadCloud className="h-3.5 w-3.5" />
                Onboarding
              </Link>
            )}

          </nav>

          {/* User profile / Logout */}
          {user ? (
            <div className="flex items-center gap-2 border-l border-[var(--color-border)] pl-3 ml-1">
              <button
                onClick={() => logout()}
                title="Sign out"
                className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-[var(--color-muted)] hover:text-[var(--color-ink)] hover:bg-[var(--color-canvas)] rounded-lg border border-[var(--color-border)] transition-colors cursor-pointer"
              >
                <LogOut className="h-3.5 w-3.5" />
                <span className="hidden md:inline">Sign out</span>
              </button>
            </div>
          ) : (
            <div className="hidden sm:flex items-center gap-1.5 text-xs font-medium text-[var(--color-muted)] px-2.5 py-1 rounded-md border border-[var(--color-border)] bg-[var(--color-canvas)]">
              <UserIcon className="h-3.5 w-3.5" />
              <span>Not signed in</span>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
