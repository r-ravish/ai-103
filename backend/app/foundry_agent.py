"""
backend/app/foundry_agent.py
-------------------------------
Service layer for the persisted Microsoft Foundry agent.

Responsibilities:
  - Owns the AIProjectClient and the scoped OpenAI client.
  - Submits questions to the agent via the Responses API.
  - Parses and de-duplicates citation metadata from the MCP retrieval payload.

Typical usage (FastAPI lifespan):

    svc = FoundryAgentService()
    result = svc.ask("What is the PTO policy?")
    svc.close()           # call on app shutdown
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_PROJECT_ENDPOINT: str | None = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
_AGENT_NAME: str | None = os.getenv("FOUNDRY_AGENT_NAME")

_SEARCH_ENDPOINT: str | None = os.getenv("AZURE_SEARCH_ENDPOINT")
_SEARCH_ADMIN_KEY: str | None = os.getenv("AZURE_SEARCH_ADMIN_KEY")
_OPENAI_ENDPOINT: str | None = os.getenv("AZURE_OPENAI_ENDPOINT")
_OPENAI_API_KEY: str | None = os.getenv("AZURE_OPENAI_API_KEY")
_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
_EMBEDDING_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")


class FoundryAgentService:
    """Wrapper around Microsoft Foundry agent with direct Azure Search RAG fallback."""
    def __init__(self) -> None:
        self._project = None
        self._client = None
        self._aoai_client = None
        self._search_client = None

        if os.getenv("AZURE_CLIENT_ID") and _PROJECT_ENDPOINT and "<" not in _PROJECT_ENDPOINT and _AGENT_NAME:
            try:
                logger.info("Attempting to connect to Foundry project: %s agent: %s", _PROJECT_ENDPOINT, _AGENT_NAME)
                self._project = AIProjectClient(
                    endpoint=_PROJECT_ENDPOINT,
                    credential=DefaultAzureCredential(),
                    allow_preview=True,
                )
                self._client = self._project.get_openai_client(agent_name=_AGENT_NAME)
            except Exception as exc:
                logger.warning("Foundry project client init warning (will use RAG fallback): %s", exc)

        if _OPENAI_ENDPOINT and _OPENAI_API_KEY and _SEARCH_ENDPOINT and _SEARCH_ADMIN_KEY:
            try:
                from openai import AzureOpenAI
                from azure.core.credentials import AzureKeyCredential
                from azure.search.documents import SearchClient

                self._aoai_client = AzureOpenAI(
                    azure_endpoint=_OPENAI_ENDPOINT,
                    api_key=_OPENAI_API_KEY,
                    api_version=_OPENAI_API_VERSION,
                )
                self._search_client = SearchClient(
                    endpoint=_SEARCH_ENDPOINT,
                    index_name="enterprise-knowledge-index",
                    credential=AzureKeyCredential(_SEARCH_ADMIN_KEY),
                )
                logger.info("Initialised Azure Search RAG fallback client.")
            except Exception as exc:
                logger.warning("Could not initialise Azure Search RAG fallback: %s", exc)

    def ask(self, question: str) -> dict[str, Any]:
        """
        Send *question* to the Foundry agent (or RAG fallback) and return a structured reply.
        """
        logger.info("Sending question: %r", question)
        if self._client is not None:
            try:
                response = self._client.responses.create(input=question)
                response = self._approve_mcp_requests(response)
                raw_answer = response.output_text or ""
                answer = re.sub(r"\u3010[^\u3011]*\u3011", "", raw_answer).strip()

                _GAP_MARKERS = (
                    "does not contain a specific",
                    "does not currently contain",
                    "does not contain sufficient information",
                    "no specific",
                    "not documented",
                    "not explicitly documented",
                    "no information",
                    "cannot find",
                    "not available in",
                )
                if any(marker in answer.lower() for marker in _GAP_MARKERS):
                    citations: list[dict[str, Any]] = []
                else:
                    citations = self._extract_citations(response)
                return {"answer": answer, "citations": citations, "response_id": getattr(response, "id", "foundry-1")}
            except Exception as exc:
                logger.warning("Foundry agent call failed (%s); falling back to direct Azure Search RAG.", exc)

        return self._rag_ask(question)

    def _rag_ask(self, question: str) -> dict[str, Any]:
        """Direct vector retrieval + answer synthesis from Azure AI Search RAG."""
        if not self._aoai_client or not self._search_client:
            raise RuntimeError("Neither Foundry agent nor Azure Search RAG credentials are available.")

        from azure.search.documents.models import VectorizedQuery

        emb_resp = self._aoai_client.embeddings.create(
            model=_EMBEDDING_DEPLOYMENT,
            input=[question],
        )
        query_vector = emb_resp.data[0].embedding

        vector_query = VectorizedQuery(
            vector=query_vector,
            k_nearest_neighbors=5,
            fields="embedding",
        )
        search_results = list(
            self._search_client.search(
                search_text=None,
                vector_queries=[vector_query],
                select=["title", "content", "source_file", "document_id", "chunk_index"],
                top=5,
            )
        )

        if not search_results or search_results[0].get("@search.score", 0) < 0.60:
            return {
                "answer": "I couldn't find specific policy information regarding your question in the enterprise knowledge base.",
                "citations": [],
                "response_id": "rag-gap",
            }

        top_score = search_results[0]["@search.score"]
        valid_chunks = [
            r for r in search_results if r.get("@search.score", 0) >= max(0.60, top_score - 0.12)
        ]

        sections: list[str] = []
        seen_files: dict[str, dict[str, str]] = {}

        for r in valid_chunks:
            content = (r.get("content") or "").strip()
            if content and content not in sections:
                sections.append(content)
            source_file = r.get("source_file") or ""
            if source_file and source_file not in seen_files:
                seen_files[source_file] = {
                    "document_id": str(r.get("document_id") or ""),
                    "title": str(r.get("title") or ""),
                    "source_file": source_file,
                }

        answer = "\n\n".join(sections)
        return {
            "answer": answer,
            "citations": list(seen_files.values()),
            "response_id": "rag-search-1",
        }

    def _approve_mcp_requests(self, response: Any) -> Any:
        """
        Approve pending MCP tool calls, but *only* for the two known
        support-ticket tools on the enterprise-support-mcp server.

        The Responses API pauses and emits ``mcp_approval_request`` output
        items whenever the agent wants to call an MCP tool that requires
        human-in-the-loop approval.  We collect those requests, validate
        each one against a strict allowlist, then re-submit with approval
        so the agent can complete its turn.

        Any unexpected server label or tool name raises immediately —
        this is intentional; we never silently approve unknown calls.
        """
        _ALLOWED_SERVER = "enterprise-support-mcp"
        _ALLOWED_TOOLS = {"create_support_ticket", "get_support_ticket"}

        approval_inputs: list[dict[str, Any]] = []

        for item in response.output:
            if getattr(item, "type", None) != "mcp_approval_request":
                continue

            server_label = getattr(item, "server_label", None)
            tool_name = getattr(item, "name", None)

            logger.info(
                "MCP approval request: server=%s tool=%s",
                server_label,
                tool_name,
            )

            if server_label != _ALLOWED_SERVER:
                raise RuntimeError(
                    f"Unexpected MCP approval server: {server_label!r}. "
                    f"Only {_ALLOWED_SERVER!r} is permitted."
                )

            if tool_name not in _ALLOWED_TOOLS:
                raise RuntimeError(
                    f"Unexpected MCP tool requested: {tool_name!r}. "
                    f"Allowed tools: {sorted(_ALLOWED_TOOLS)}"
                )

            approval_inputs.append(
                {
                    "type": "mcp_approval_response",
                    "approve": True,
                    "approval_request_id": item.id,
                }
            )

        if not approval_inputs:
            # Nothing to approve — agent either finished or used a different
            # mechanism (e.g. knowledge_base_retrieve via built-in MCP).
            return response

        logger.info(
            "Approving %d MCP tool call(s) and continuing response %s",
            len(approval_inputs),
            response.id,
        )

        return self._client.responses.create(
            previous_response_id=response.id,
            input=approval_inputs,
        )

    def close(self) -> None:
        """Release the underlying Foundry project client."""
        try:
            self._project.close()
            logger.info("Foundry project client closed.")
        except Exception:
            logger.warning("Error closing Foundry project client.", exc_info=True)

    @staticmethod
    def _extract_citations(response: Any) -> list[dict[str, str]]:
        """
        Return metadata only for documents the agent actually cited.

        Two-phase approach:
        1. Collect the set of document IDs that appear in ``url_citation``
           annotations on the assistant message (these are the chunks the model
           explicitly referenced in its answer).
        2. Walk the ``knowledge_base_retrieve`` MCP output and return metadata
           only for documents whose ID is in that cited set.

        This prevents returning every retrieved chunk regardless of whether
        the model's answer actually referenced it.
        """
        try:
            raw: dict[str, Any] = response.model_dump()
        except Exception:
            logger.warning("Could not serialise response to dict.", exc_info=True)
            return []

        # ------------------------------------------------------------------
        # Phase 1: collect doc IDs from url_citation annotations.
        #
        # The Foundry agent embeds citations as url_citation annotations on
        # the assistant message.  Each annotation URL looks like:
        #   https://<search-resource>.search.windows.net/indexes/<idx>/docs/<doc-id>?...
        # We extract the <doc-id> path segment.
        # ------------------------------------------------------------------
        cited_ids: set[str] = set()

        for item in raw.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                for annotation in content.get("annotations", []):
                    if annotation.get("type") != "url_citation":
                        continue
                    url: str = annotation.get("url", "")
                    # URL path is: .../docs/<document_id>?...
                    # Split on '/docs/' and take the first path segment after it.
                    if "/docs/" in url:
                        doc_id = url.split("/docs/", 1)[1].split("?")[0].strip()
                        if doc_id:
                            cited_ids.add(doc_id)

        logger.debug("Cited document IDs from annotations: %s", cited_ids)

        if not cited_ids:
            # No structured annotations found — nothing to return.
            return []

        # ------------------------------------------------------------------
        # Phase 2: match cited IDs against MCP retrieval documents.
        #
        # Each knowledge_base_retrieve output contains a JSON blob with a
        # ``documents`` list.  Each document's content is itself a JSON blob
        # carrying {id, title, source_file, ...}.
        # ------------------------------------------------------------------
        seen: dict[str, dict[str, str]] = {}  # keyed by source_file

        for item in raw.get("output", []):
            if item.get("type") != "mcp_call":
                continue
            if item.get("name") != "knowledge_base_retrieve":
                continue

            raw_output = item.get("output")
            if not raw_output:
                continue

            try:
                retrieval: dict[str, Any] = json.loads(raw_output)
            except (TypeError, json.JSONDecodeError):
                logger.warning("Could not parse MCP tool output as JSON.")
                continue

            for doc in retrieval.get("documents", []):
                try:
                    parsed: dict[str, Any] = json.loads(doc.get("content", ""))
                except (TypeError, json.JSONDecodeError):
                    continue

                doc_id: str = str(parsed.get("id") or "")
                source_file: str = str(parsed.get("source_file") or "")

                # Only include documents the model actually cited.
                if doc_id not in cited_ids:
                    continue

                # De-duplicate: one entry per source file.
                if not source_file or source_file in seen:
                    continue

                seen[source_file] = {
                    "document_id": doc_id,
                    "title": str(parsed.get("title") or ""),
                    "source_file": source_file,
                }

        return list(seen.values())
