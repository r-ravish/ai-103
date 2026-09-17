# Enterprise Knowledge Agent — Frontend

Chat UI shell for AI-103. This is a **frontend-only shell**: all assistant
responses currently come from a local mock layer (`lib/mockResponses.ts`),
not a real backend. No Azure/Foundry calls are made from this app.

## Running locally

```bash
npm install
npm run dev
```

Then open http://localhost:3000.

## What's mocked vs. real

- Real: UI, chat state, input handling, citation rendering, knowledge-gap
  state, loading state, empty state, suggested questions.
- Mocked: assistant answers. `lib/mockResponses.ts` does simple keyword
  matching on the question text (leave / reimbursement / work-from-home /
  everything else -> knowledge gap) and returns canned content plus
  citation metadata.

## Dependencies

Beyond the Next.js/React/Tailwind defaults, this adds `lucide-react` for
icons (document icons on citations, topic icons on suggested questions,
the send button). No other runtime dependencies.

## Data model

See `types/chat.ts`. The `Citation` fields (`title`, `content`,
`sourceFile`, `sourcePath`, `documentId`, `chunkIndex`, `documentType`)
intentionally mirror the retrieval metadata named in
`../docs/ingestion-contract.md`, so wiring up a real backend later should
mostly be a mapping exercise in `lib/mockResponses.ts` (or wherever the
real API call replaces `getMockResponse`), not a UI rewrite.

## Structure

```
app/            Next.js App Router entry (layout, page, global styles)
components/     UI components (Header, Chat, MessageList, MessageBubble,
                ChatInput, CitationList, EmptyState, SuggestedQuestions)
lib/            Mock data layer
types/          Frontend-local TypeScript types (not a backend contract)
```
