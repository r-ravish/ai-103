import { Citation, Conversation, Message } from "@/types/chat";

/**
 * Backend API response structure for POST /chat.
 */
export interface BackendCitation {
  document_id?: string;
  title?: string;
  source_file?: string;
  content?: string;
  source_path?: string;
  chunk_index?: number;
  document_type?: string;
  [key: string]: unknown;
}

export interface BackendChatResponse {
  answer: string;
  citations?: BackendCitation[];
  is_knowledge_gap?: boolean;
  action_taken?: boolean;
  action_name?: string;
  ticket_id?: string;
  escalated?: boolean;
  escalation_reason?: string;
  conversation_id?: number;
  response_id?: string;
}

export interface ChatResult {
  answer: string;
  citations: Citation[];
  isKnowledgeGap: boolean;
  actionTaken?: boolean;
  actionName?: string;
  ticketId?: string;
  isEscalated?: boolean;
  escalationReason?: string;
  conversationId?: number;
}

/**
 * Known markers that indicate a knowledge gap from the agent
 * when citations are not present.
 */
const KNOWLEDGE_GAP_MARKERS = [
  "does not contain a specific",
  "does not currently contain",
  "does not contain sufficient information",
  "no specific",
  "not documented",
  "not explicitly documented",
  "no information",
  "cannot find",
  "not available in",
  "couldn't find",
  "could not find",
  "no matching policy",
  "i don't have that information",
  "i do not have that information",
  "out of scope",
];

function isGapAnswer(text: string): boolean {
  const lower = text.toLowerCase();
  return KNOWLEDGE_GAP_MARKERS.some((marker) => lower.includes(marker));
}

function resolveChatUrl(): string {
  const customUrl = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (customUrl) {
    if (customUrl.endsWith("/chat")) {
      return customUrl;
    }
    return `${customUrl.replace(/\/+$/, "")}/chat`;
  }
  // Default to relative endpoint proxied by Next.js rewrites to backend
  return "/api/chat";
}

function resolveBaseUrl(): string {
  const customUrl = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (customUrl) {
    return customUrl.replace(/\/+$/, "").replace(/\/chat$/, "");
  }
  return "/api";
}

export function mapCitation(raw: BackendCitation, index: number): Citation {
  const docId = raw.document_id || "";
  const sourceFile = raw.source_file || (raw as Record<string, unknown>).sourceFile as string | undefined;
  const title = raw.title || sourceFile || `Document ${index + 1}`;

  return {
    id: docId ? `${docId}-${index}` : `cit-${index}-${Date.now()}`,
    title,
    content: raw.content || (raw as Record<string, unknown>).content as string | undefined,
    sourceFile,
    sourcePath: raw.source_path || (raw as Record<string, unknown>).sourcePath as string | undefined,
    documentId: docId || (raw as Record<string, unknown>).documentId as string | undefined,
    chunkIndex: typeof raw.chunk_index === "number" ? raw.chunk_index : undefined,
    documentType: raw.document_type || (raw as Record<string, unknown>).documentType as string | undefined,
  };
}

/**
 * Send a user question to the backend /chat endpoint.
 *
 * @param question       The employee's question
 * @param conversationId Optional conversation ID to continue an existing session.
 *                       Pass null / undefined to start a new conversation.
 * @returns Parsed response with answer, mapped citations, and knowledge gap state
 */
export async function sendChatMessage(
  question: string,
  conversationId?: number | null,
): Promise<ChatResult> {
  const endpoint = resolveChatUrl();

  const body: Record<string, unknown> = { question };
  if (conversationId != null) {
    body.conversation_id = conversationId;
  }

  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    credentials: "include",
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    let errorMessage = `Request failed with status ${response.status}`;
    try {
      const errorData = await response.json();
      if (typeof errorData.detail === "string") {
        errorMessage = errorData.detail;
      } else if (Array.isArray(errorData.detail)) {
        errorMessage = errorData.detail
          .map((item: { msg?: string }) => item.msg || JSON.stringify(item))
          .join(", ");
      } else if (errorData.message && typeof errorData.message === "string") {
        errorMessage = errorData.message;
      }
    } catch {
      // Body is not JSON, fallback to status text if present
      if (response.statusText) {
        errorMessage = `Error ${response.status}: ${response.statusText}`;
      }
    }
    throw new Error(errorMessage);
  }

  const data: BackendChatResponse = await response.json();

  const rawCitations = Array.isArray(data.citations) ? data.citations : [];
  const citations = rawCitations.map((c, i) => mapCitation(c, i));

  // Determine if this is a knowledge gap response
  const isKnowledgeGap =
    data.is_knowledge_gap === true ||
    (citations.length === 0 && isGapAnswer(data.answer || ""));

  return {
    answer: data.answer || "",
    citations,
    isKnowledgeGap,
    actionTaken: data.action_taken,
    actionName: data.action_name,
    ticketId: data.ticket_id,
    isEscalated: data.escalated,
    escalationReason: data.escalation_reason,
    conversationId: data.conversation_id,
  };
}

// ---------------------------------------------------------------------------
// Conversation management API helpers
// ---------------------------------------------------------------------------

/**
 * Backend raw shape returned by GET /conversations.
 */
interface BackendConversationSummary {
  id: number;
  title: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
}

/**
 * Backend raw shape returned by GET /conversations/{id}.
 */
interface BackendPersistedMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  citations: BackendCitation[];
  response_id: string | null;
  created_at: string;
}

interface BackendConversationDetail {
  id: number;
  title: string | null;
  created_at: string;
  updated_at: string;
  messages: BackendPersistedMessage[];
}

/**
 * List all conversations for the authenticated user.
 */
export async function fetchConversations(): Promise<Conversation[]> {
  const base = resolveBaseUrl();
  const res = await fetch(`${base}/conversations`, {
    credentials: "include",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) return [];
  const data: BackendConversationSummary[] = await res.json();
  return data.map((c) => ({
    id: c.id,
    title: c.title,
    createdAt: c.created_at,
    updatedAt: c.updated_at,
    messageCount: c.message_count,
  }));
}

/**
 * Load the full message history for a conversation and map it to frontend Messages.
 */
export async function fetchConversation(conversationId: number): Promise<Message[]> {
  const base = resolveBaseUrl();
  const res = await fetch(`${base}/conversations/${conversationId}`, {
    credentials: "include",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) return [];
  const data: BackendConversationDetail = await res.json();

  return data.messages.map((msg, i) => {
    const citations = msg.citations
      ? msg.citations.map((c, ci) => mapCitation(c, ci))
      : [];
    return {
      id: `persisted-${msg.id}-${i}`,
      role: msg.role,
      content: msg.content,
      citations: msg.role === "assistant" ? citations : undefined,
      timestamp: new Date(msg.created_at).getTime(),
      responseId: msg.response_id ?? undefined,
    } satisfies Message;
  });
}

/**
 * Delete a conversation (and all its messages) for the authenticated user.
 */
export async function deleteConversation(conversationId: number): Promise<boolean> {
  const base = resolveBaseUrl();
  const res = await fetch(`${base}/conversations/${conversationId}`, {
    method: "DELETE",
    credentials: "include",
  });
  return res.ok || res.status === 204;
}
