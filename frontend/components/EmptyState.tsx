import SuggestedQuestions from "./SuggestedQuestions";

interface EmptyStateProps {
  onSelectSuggestion: (question: string) => void;
}

export default function EmptyState({ onSelectSuggestion }: EmptyStateProps) {
  return (
    <div className="mx-auto flex h-full max-w-md flex-col items-center justify-center px-4 py-10 text-center">
      <svg aria-hidden="true" viewBox="0 0 32 32" className="h-10 w-10">
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
      <h2
        className="mt-4 text-xl font-medium tracking-tight text-[var(--color-ink)]"
        style={{ fontFamily: "var(--font-stack-serif)" }}
      >
        Ask about company policy
      </h2>
      <p className="mt-1.5 max-w-xs text-[15px] leading-relaxed text-[var(--color-muted)]">
        Answers are grounded in the pilot knowledge base and cited back to
        their source document.
      </p>
      <div className="w-full text-left">
        <SuggestedQuestions onSelect={onSelectSuggestion} />
      </div>
    </div>
  );
}
