export default function Header() {
  return (
    <header className="border-b border-[var(--color-border)] bg-[var(--color-paper)]">
      <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-4 sm:px-6">
        <div className="flex items-center gap-2.5">
          <svg
            aria-hidden="true"
            viewBox="0 0 32 32"
            className="h-7 w-7 shrink-0"
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
          <h1
            className="text-[17px] font-medium tracking-tight text-[var(--color-ink)]"
            style={{ fontFamily: "var(--font-stack-serif)" }}
          >
            Enterprise Knowledge Agent
          </h1>
        </div>
        <div
          className="flex items-center gap-1.5 text-xs font-medium text-[var(--color-muted)]"
          aria-label="Environment status: Pilot"
        >
          <span
            aria-hidden="true"
            className="h-1.5 w-1.5 rounded-full bg-[var(--color-seal)]"
          />
          Pilot
        </div>
      </div>
    </header>
  );
}
