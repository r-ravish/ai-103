"""
onboarding/embedding.py
-----------------------
Embedding generation using the project's configured Azure OpenAI deployment
(text-embedding-3-small, 1536 dimensions — see docs/ingestion-contract.md).

Only the text-embedding-3-small deployment used by the pilot is supported.
Using a different model would break retrieval (query embeddings use the same
deployment), so this module intentionally enforces that contract.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from openai import AzureOpenAI

if TYPE_CHECKING:
    from onboarding.chunking import RawChunk

logger = logging.getLogger(__name__)


def _make_client(
    endpoint: str,
    api_key: str,
    api_version: str,
) -> AzureOpenAI:
    return AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=api_version,
    )


def generate_embeddings(
    chunks: list["RawChunk"],
    endpoint: str,
    api_key: str,
    api_version: str,
    deployment: str,
    batch_size: int = 16,
) -> list[list[float]]:
    """
    Generate embeddings for a list of :class:`~onboarding.chunking.RawChunk`
    objects.

    Parameters
    ----------
    chunks :
        Chunks whose ``content`` field will be embedded.
    endpoint, api_key, api_version :
        Azure OpenAI connection details.
    deployment :
        The Azure OpenAI deployment name (must be ``text-embedding-3-small``
        for the project index to work).
    batch_size :
        How many chunks to embed per API call (default: 16).

    Returns
    -------
    list[list[float]]
        One 1536-dimensional vector per chunk, in the same order as *chunks*.

    Raises
    ------
    RuntimeError
        If any batch fails or returns fewer embeddings than expected.
    """
    if not chunks:
        return []

    client = _make_client(endpoint, api_key, api_version)
    embeddings: list[list[float]] = []

    total_batches = (len(chunks) + batch_size - 1) // batch_size
    for batch_num, start in enumerate(range(0, len(chunks), batch_size), start=1):
        batch = chunks[start : start + batch_size]
        texts = [c.content for c in batch]

        logger.info(
            "Embedding batch %d/%d (%d chunks).",
            batch_num,
            total_batches,
            len(texts),
        )

        try:
            response = client.embeddings.create(
                model=deployment,
                input=texts,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Azure OpenAI embedding call failed for batch {batch_num}: {exc}"
            ) from exc

        if len(response.data) != len(batch):
            raise RuntimeError(
                f"Embedding response length mismatch: expected {len(batch)}, "
                f"got {len(response.data)} for batch {batch_num}."
            )

        for item in response.data:
            embeddings.append(item.embedding)

    logger.info("Generated %d embeddings.", len(embeddings))
    return embeddings
