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

## Connecting to the backend

The frontend communicates with the backend `POST /chat` endpoint via `lib/api.ts`.

- By default, Next.js rewrites proxy `/api/chat` to `http://localhost:8000/chat`.
- Set `BACKEND_URL` in `.env.local` to point the Next.js server rewrite to a different backend host (e.g. `BACKEND_URL=http://localhost:8000`).
- Alternatively, set `NEXT_PUBLIC_API_URL` to send browser requests directly to a custom endpoint (e.g. `NEXT_PUBLIC_API_URL=http://localhost:8000/chat`).

## Dependencies

Beyond the Next.js/React/Tailwind defaults, this adds `lucide-react` for
icons (document icons on citations, topic icons on suggested questions,
the send button). No other runtime dependencies.

## Data model

See `types/chat.ts`. The `Citation` fields (`title`, `content`,
`sourceFile`, `sourcePath`, `documentId`, `chunkIndex`, `documentType`)
mirror the retrieval metadata returned from the knowledge base and mapped
by `lib/api.ts`.

## Structure

```
app/            Next.js App Router entry (layout, page, global styles)
components/     UI components (Header, Chat, MessageList, MessageBubble,
                ChatInput, CitationList, EmptyState, SuggestedQuestions)
lib/            API client (api.ts) and mock responses (mockResponses.ts)
types/          TypeScript types (chat.ts)
```
