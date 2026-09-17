import { CalendarDays, Receipt, House } from "lucide-react";

const SUGGESTIONS = [
  { text: "What is the leave policy?", icon: CalendarDays },
  { text: "How do I claim reimbursement?", icon: Receipt },
  { text: "What is the work from home policy?", icon: House },
];

interface SuggestedQuestionsProps {
  onSelect: (question: string) => void;
}

export default function SuggestedQuestions({
  onSelect,
}: SuggestedQuestionsProps) {
  return (
    <div className="mt-6 w-full">
      <p className="text-xs font-medium text-[var(--color-muted)]">
        Try asking
      </p>
      <ul className="mt-2.5 flex flex-col gap-2">
        {SUGGESTIONS.map(({ text, icon: Icon }) => (
          <li key={text}>
            <button
              type="button"
              onClick={() => onSelect(text)}
              className="group flex w-full items-center gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-paper)] px-4 py-3 text-left text-sm text-[var(--color-ink)] transition-colors hover:border-[var(--color-seal)] hover:bg-[var(--color-seal-soft)]"
            >
              <Icon
                aria-hidden="true"
                className="h-4 w-4 shrink-0 text-[var(--color-muted)] transition-colors group-hover:text-[var(--color-seal)]"
                strokeWidth={1.75}
              />
              {text}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
