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


class FoundryAgentService:
    """Thin wrapper around the persisted Microsoft Foundry agent."""
    def __init__(self) -> None:
        if not _PROJECT_ENDPOINT or "<" in _PROJECT_ENDPOINT:
            raise RuntimeError("FOUNDRY_PROJECT_ENDPOINT is missing or still contains a placeholder.")
        if not _AGENT_NAME:
            raise RuntimeError("FOUNDRY_AGENT_NAME is missing from environment.")

        logger.info("Connecting to Foundry project: %s  agent: %s", _PROJECT_ENDPOINT, _AGENT_NAME)

        self._project = AIProjectClient(
            endpoint=_PROJECT_ENDPOINT,
            credential=DefaultAzureCredential(),
            allow_preview=True,
        )
        self._client = self._project.get_openai_client(agent_name=_AGENT_NAME)

    def ask(self, question: str) -> dict[str, Any]:
        """
        Send *question* to the Foundry agent and return a structured reply.

        Returns
        -------
        dict with keys:
          ``answer``      – plain-text response from the agent
          ``citations``   – list of unique source-document metadata dicts
          ``response_id`` – Foundry response ID (useful for debugging)
        """
        logger.info("Sending question to agent: %r", question)
        response = self._client.responses.create(input=question)

        # If the agent needs to call an MCP tool (e.g. create_support_ticket),
        # it will pause and emit mcp_approval_request items.  Approve only the
        # two known support-ticket tools and re-submit so the agent can finish.
        response = self._approve_mcp_requests(response)

        raw_answer = response.output_text or ""
        # Strip inline citation markers like 【4:0†work-from-home-policy.md】
        # so the frontend receives clean prose and uses the structured
        # citations array instead.
        answer = re.sub(r"\u3010[^\u3011]*\u3011", "", raw_answer).strip()

        # ------------------------------------------------------------------
        # Knowledge-gap guard.
        #
        # Even when the model answers "I don't have that information", the
        # retrieval step may still return chunks and attach url_citation
        # annotations that reference whatever vaguely related docs it found.
        # We check the answer text for phrases that signal a genuine gap and
        # suppress citations in that case, so the frontend never shows
        # misleading source references alongside a "not found" reply.
        # ------------------------------------------------------------------
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

        is_knowledge_gap = any(marker in answer.lower() for marker in _GAP_MARKERS)

        if is_knowledge_gap:
            logger.info("Knowledge gap detected — suppressing citations.")
            citations: list[dict[str, Any]] = []
        else:
            citations = self._extract_citations(response)

        logger.info("Agent replied (%d chars, %d citations)", len(answer), len(citations))
        return {"answer": answer, "citations": citations, "response_id": response.id}

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
