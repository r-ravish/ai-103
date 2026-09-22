"""
backend/scripts/seed_pilot_documents.py
---------------------------------------
Registers the 5 pre-existing pilot documents into PostgreSQL (documents table).
These 5 documents were already embedded and indexed in Azure AI Search during Day 1.
Registering them ensures the admin UI accurately reflects all active documents in the
Azure AI Search index.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from dotenv import load_dotenv

load_dotenv(os.path.join(_BACKEND, ".env"))


async def seed_documents() -> None:
    from sqlalchemy import select
    from db.database import AsyncSessionLocal
    from db.models import Document, DocumentStatus, User
    from scripts.ingest_pilot_documents import build_chunks_for_file

    project_root = Path(_BACKEND).parent
    docs_dir = project_root / "docs" / "pilot-documents"

    if not docs_dir.exists():
        print(f"[seed_documents] Directory not found: {docs_dir}")
        return

    async with AsyncSessionLocal() as session:
        admin = (await session.execute(select(User).where(User.email == "admin@company.com"))).scalar_one_or_none()
        admin_id = admin.id if admin else None

        for md_file in sorted(docs_dir.glob("*.md")):
            doc_id = md_file.stem
            existing = (await session.execute(select(Document).where(Document.document_id == doc_id))).scalar_one_or_none()
            if existing is not None:
                print(f"[seed_documents] Document {doc_id!r} already registered, skipping.")
                continue

            chunks = build_chunks_for_file(md_file)
            title = chunks[0]["title"] if chunks else doc_id.replace("-", " ").title()

            doc = Document(
                document_id=doc_id,
                filename=md_file.name,
                title=title,
                status=DocumentStatus.ingested,
                chunks_count=len(chunks),
                storage_path=str(md_file.resolve()),
                uploaded_by_id=admin_id,
                uploaded_at=datetime.now(timezone.utc),
            )
            session.add(doc)
            print(f"[seed_documents] Registered {doc_id} ({len(chunks)} chunks): {title}")

        await session.commit()
        print("[seed_documents] All pilot documents registered successfully.")


if __name__ == "__main__":
    asyncio.run(seed_documents())
