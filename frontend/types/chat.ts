/**
 * Frontend-local data model for the chat shell.
 *
 * These types are NOT a backend API contract. They exist so the UI has
 * something concrete to render against while the real agent backend is
 * built. Field names on `Citation` intentionally mirror the retrieval
 * metadata listed in `docs/ingestion-contract.md` ("Retrieval contract"
 * section) so that swapping mock data for a real backend response later
 * is a mapping exercise, not a UI rewrite.
 *
 * Do not add fields here that assume a specific backend response shape
 * that hasn't been agreed yet (e.g. no Azure Search score fields, no
 * Foundry-specific metadata). If the backend contract evolves, update
 * this file deliberately and re-check the mapping in lib/mockResponses.ts.
 */

export type MessageRole = "user" | "assistant";

/**
 * A single citation backing a grounded assistant answer.
 *
 * Only `id` and `title` are required for the UI to render something
 * useful. Everything else is optional metadata the ingestion contract
 * says retrieved chunks *can* expose (title, content, source_file,
 * source_path, document_id, chunk_index, document_type) — carried here
 * under the same names so a real backend response can be dropped in
 * with minimal translation.
 */
export interface Citation {
  /** Unique id for this citation within a message (not the Search index key). */
  id: string;
  /** Human-readable document/section title, e.g. "Leave Policy". */
  title: string;
  /** Optional snippet of the cited content. */
  content?: string;
  /** Original source filename, e.g. "leave-policy.md". */
  sourceFile?: string;
  /** Source location, per ingestion contract (repo path in the pilot). */
  sourcePath?: string;
  /** Stable id of the source document. */
  documentId?: string;
  /** Zero-based chunk ordering within the source document. */
  chunkIndex?: number;
  /** Logical source type, e.g. "policy", "faq", "ticket-data". */
  documentType?: string;
}

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  /** Present only on assistant messages; empty/omitted for user messages. */
  citations?: Citation[];
  /**
   * True when the assistant could not find sufficient grounded evidence
   * to answer the question. This is a distinct, honest state — never
   * an error state and never a fabricated answer.
   */
  isKnowledgeGap?: boolean;
  timestamp: number;
}
