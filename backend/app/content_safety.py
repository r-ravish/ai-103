"""
Azure AI Content Safety — thin wrapper for the Enterprise Knowledge Agent.

This module provides a ``ContentSafetyClient`` class that wraps the Azure AI
Content Safety SDK.  It is intentionally kept simple so it can be wired into
the FastAPI application with minimal coupling.

Runtime behaviour:
  • When ``AZURE_CONTENT_SAFETY_ENDPOINT`` **is** set:
    - Text is screened against all four harm categories (Hate, Sexual,
      Violence, SelfHarm) on every call to ``screen_text()``.
    - A ``SafetyResult(blocked=True)`` is returned when any category severity
      meets or exceeds the configured threshold.
  • When ``AZURE_CONTENT_SAFETY_ENDPOINT`` is **not** set:
    - ``ContentSafetyClient`` is initialised in *passthrough mode*.
    - Every ``screen_text()`` call returns ``SafetyResult(blocked=False)``
      immediately — the agent keeps working without Azure credentials.
    - A single ``INFO`` log message is emitted at startup to make the mode
      explicit.

Configuration (via environment variables / ``.env``):

  AZURE_CONTENT_SAFETY_ENDPOINT   (required for live screening)
      e.g. https://<resource-name>.cognitiveservices.azure.com/

  AZURE_CONTENT_SAFETY_API_KEY    (required for live screening)
      Use a Key Vault reference or set only in ``.env`` (never commit).

  AZURE_CONTENT_SAFETY_API_VERSION  (optional, default: 2024-09-01)

  AZURE_CONTENT_SAFETY_SEVERITY_THRESHOLD  (optional, default: 2)
      Integer 0–6.  Responses at or above this severity are blocked.
      2 = Low (strict, recommended for enterprise HR context).
      4 = Medium.  6 = High (permissive).

No credentials should ever be committed to the repository.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment-variable configuration
# ---------------------------------------------------------------------------
_ENDPOINT: str | None = os.getenv("AZURE_CONTENT_SAFETY_ENDPOINT")
_API_KEY: str | None = os.getenv("AZURE_CONTENT_SAFETY_API_KEY")
_API_VERSION: str = os.getenv("AZURE_CONTENT_SAFETY_API_VERSION", "2024-09-01")
_SEVERITY_THRESHOLD: int = int(
    os.getenv("AZURE_CONTENT_SAFETY_SEVERITY_THRESHOLD", "2")
)

# The four harm categories evaluated by Azure AI Content Safety.
_ALL_CATEGORIES = ("Hate", "Sexual", "Violence", "SelfHarm")

# Safe-refusal message returned to the caller when content is blocked.
_BLOCKED_RESPONSE = (
    "I'm not able to process that request. "
    "Please ask a question related to company policies and procedures."
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class SafetyResult:
    """Outcome of a single content safety screening call.

    Attributes
    ----------
    blocked:
        ``True`` when the text was blocked by the safety filter.
    categories:
        Mapping of ``category_name → severity_score`` (0–6) for every
        category that was evaluated.  Empty when in passthrough mode.
    reason:
        Human-readable explanation when ``blocked=True``; ``None`` otherwise.
    safe_response:
        Pre-formed refusal message for the caller to return to the user when
        ``blocked=True``.
    """

    blocked: bool = False
    categories: dict[str, int] = field(default_factory=dict)
    reason: Optional[str] = None
    safe_response: str = _BLOCKED_RESPONSE


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
class ContentSafetyClient:
    """Wrapper around the Azure AI Content Safety REST API.

    Usage::

        cs = ContentSafetyClient()

        # Screen user input before sending to the LLM.
        result = cs.screen_text(user_question)
        if result.blocked:
            return result.safe_response

        # Screen LLM output before returning to the user.
        result = cs.screen_text(agent_answer)
        if result.blocked:
            return result.safe_response
    """

    def __init__(self) -> None:
        self._live: bool = False

        if not _ENDPOINT:
            logger.info(
                "AZURE_CONTENT_SAFETY_ENDPOINT not set — "
                "ContentSafetyClient running in passthrough mode (no screening)."
            )
            self._client = None
            return

        # Import lazily so the package is only required when the feature is
        # actually configured — keeps local dev lightweight.
        try:
            from azure.ai.contentsafety import ContentSafetyClient as _AzureCSClient
            from azure.core.credentials import AzureKeyCredential
        except ImportError as exc:
            raise ImportError(
                "azure-ai-contentsafety is not installed. "
                "Run: pip install azure-ai-contentsafety>=1.0.0"
            ) from exc

        if not _API_KEY:
            raise RuntimeError(
                "AZURE_CONTENT_SAFETY_ENDPOINT is set but "
                "AZURE_CONTENT_SAFETY_API_KEY is missing."
            )

        self._client = _AzureCSClient(
            endpoint=_ENDPOINT,
            credential=AzureKeyCredential(_API_KEY),
            api_version=_API_VERSION,
        )
        self._live = True
        logger.info(
            "ContentSafetyClient initialised (endpoint=%s, threshold=%d, version=%s).",
            _ENDPOINT,
            _SEVERITY_THRESHOLD,
            _API_VERSION,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def screen_text(self, text: str) -> SafetyResult:
        """Screen *text* for harmful content.

        Parameters
        ----------
        text:
            The string to evaluate.  Typically either the user's question
            (input screening) or the agent's answer (output screening).

        Returns
        -------
        SafetyResult
            ``blocked=True`` when the text violates the configured severity
            threshold.  ``blocked=False`` when the text is safe (or when the
            client is in passthrough mode).
        """
        if not self._live or self._client is None:
            # Passthrough mode — nothing to check.
            return SafetyResult(blocked=False)

        try:
            return self._call_api(text)
        except Exception:
            # If the Safety API is unreachable, log a warning but allow the
            # request to proceed rather than blocking all traffic.  Adjust
            # this policy to ``raise`` if you prefer fail-closed behaviour.
            logger.warning(
                "Content Safety API call failed — allowing request to proceed.",
                exc_info=True,
            )
            return SafetyResult(blocked=False)

    @property
    def is_live(self) -> bool:
        """``True`` when the client is connected to the Azure API."""
        return self._live

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _call_api(self, text: str) -> SafetyResult:
        """Make the actual Azure Content Safety API call."""
        from azure.ai.contentsafety.models import AnalyzeTextOptions, TextCategory

        _CATEGORY_MAP = {
            "Hate": TextCategory.HATE,
            "Sexual": TextCategory.SEXUAL,
            "Violence": TextCategory.VIOLENCE,
            "SelfHarm": TextCategory.SELF_HARM,
        }

        options = AnalyzeTextOptions(
            text=text,
            categories=list(_CATEGORY_MAP.values()),
            output_type="FourSeverityLevels",
        )

        response = self._client.analyze_text(options)

        categories: dict[str, int] = {}
        blocked_categories: list[str] = []

        for label in response.categories_analysis:
            # Convert enum to friendly name for logging.
            name = label.category.value if hasattr(label.category, "value") else str(label.category)
            severity = label.severity or 0
            categories[name] = severity

            if severity >= _SEVERITY_THRESHOLD:
                blocked_categories.append(f"{name}(severity={severity})")

        if blocked_categories:
            reason = f"Content blocked — categories exceeded threshold: {', '.join(blocked_categories)}"
            logger.warning("Content Safety blocked text: %s", reason)
            return SafetyResult(
                blocked=True,
                categories=categories,
                reason=reason,
                safe_response=_BLOCKED_RESPONSE,
            )

        logger.debug("Content Safety passed — categories: %s", categories)
        return SafetyResult(blocked=False, categories=categories)
