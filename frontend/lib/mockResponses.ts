import { Citation } from "@/types/chat";

/**
 * Mock response layer.
 *
 * This stands in for the real agent backend (retrieval + generation +
 * citation assembly). It exists so the chat UI can be built and reviewed
 * before the backend is ready, without the frontend hard-coding any
 * assumption about the real API shape.
 *
 * Matching here is intentionally simple keyword matching, per the task
 * brief — it is not meant to simulate real retrieval quality. The pilot
 * corpus referenced (leave, reimbursement, work-from-home) and the VPN
 * knowledge-gap case both come directly from docs/ingestion-contract.md
 * ("Pilot validation" section), including the fact that a VPN query was
 * tested and correctly surfaced as a gap rather than answered.
 *
 * When the real backend exists, this file is the seam to replace:
 * getMockResponse's signature and return shape should carry over to a
 * function that calls the actual agent API.
 */

export interface MockResponse {
  content: string;
  citations: Citation[];
  isKnowledgeGap: boolean;
}

const LEAVE_RESPONSE: MockResponse = {
  content:
    "[Mock response based on the pilot Leave Policy document] Full-time employees accrue paid annual leave, which can be requested through the standard leave process and is subject to manager approval. Once the real backend is connected, this answer will be generated from retrieved, up-to-date policy content rather than this fixed mock text.",
  citations: [
    {
      id: "cit-leave-1",
      title: "Leave Policy",
      sourceFile: "leave-policy.md",
      documentId: "leave-policy",
      documentType: "policy",
      chunkIndex: 0,
    },
  ],
  isKnowledgeGap: false,
};

const REIMBURSEMENT_RESPONSE: MockResponse = {
  content:
    "[Mock response based on the pilot Reimbursement Policy document] To claim a reimbursement, submit an expense request with supporting receipts through the designated process, ahead of the applicable submission deadline. This is placeholder content — the real backend will replace it with an answer generated from the current policy text.",
  citations: [
    {
      id: "cit-reimb-1",
      title: "Reimbursement Policy",
      sourceFile: "reimbursement-policy.md",
      documentId: "reimbursement-policy",
      documentType: "policy",
      chunkIndex: 0,
    },
  ],
  isKnowledgeGap: false,
};

const WFH_RESPONSE: MockResponse = {
  content:
    "[Mock response based on the pilot Work From Home Policy document] Employees may work from home under the conditions set out in the work-from-home policy, which covers eligibility and expectations while working remotely. This is placeholder content standing in for a future backend-generated answer.",
  citations: [
    {
      id: "cit-wfh-1",
      title: "Work From Home Policy",
      sourceFile: "work-from-home-policy.md",
      documentId: "work-from-home-policy",
      documentType: "policy",
      chunkIndex: 0,
    },
  ],
  isKnowledgeGap: false,
};

const KNOWLEDGE_GAP_RESPONSE: MockResponse = {
  content:
    "I couldn't find sufficient information in the available pilot knowledge base to answer that question.",
  citations: [],
  isKnowledgeGap: true,
};

/**
 * Very small keyword router. Order matters slightly: check more specific
 * terms before falling through to the knowledge-gap default.
 */
export function getMockResponse(question: string): MockResponse {
  const q = question.toLowerCase();

  if (q.includes("leave")) {
    return LEAVE_RESPONSE;
  }

  if (q.includes("reimburs")) {
    return REIMBURSEMENT_RESPONSE;
  }

  if (
    q.includes("work from home") ||
    q.includes("wfh") ||
    q.includes("remote")
  ) {
    return WFH_RESPONSE;
  }

  // Explicitly known out-of-scope case from the pilot validation notes,
  // as well as any other unmatched question: surface a knowledge gap
  // rather than inventing an answer.
  return KNOWLEDGE_GAP_RESPONSE;
}

/** Artificial delay so the loading state is visible, per task brief. */
export const MOCK_RESPONSE_DELAY_MS = 900;
