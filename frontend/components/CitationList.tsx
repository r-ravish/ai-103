import { FileText } from "lucide-react";
import { Citation } from "@/types/chat";

interface CitationListProps {
  citations: Citation[];
}

export default function CitationList({ citations }: CitationListProps) {
  if (citations.length === 0) {
    return null;
  }

  return (
    <div className="mt-3.5 border-t border-[var(--color-border)] pt-3">
      <p className="text-[11px] font-medium text-[var(--color-muted)]">
        Sources
      </p>
      <ul className="mt-1.5 flex flex-col gap-1.5">
        {citations.map((citation) => (
          <li
            key={citation.id}
            className="flex items-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] px-2.5 py-1.5"
          >
            <FileText
              aria-hidden="true"
              className="h-3.5 w-3.5 shrink-0 text-[var(--color-seal)]"
              strokeWidth={1.75}
            />
            <span className="text-xs font-medium text-[var(--color-ink)]">
              {citation.title}
            </span>
            {citation.sourceFile && (
              <span className="text-xs text-[var(--color-muted)]">
                {citation.sourceFile}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
