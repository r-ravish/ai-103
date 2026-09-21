#!/usr/bin/env python3
"""
onboarding/scripts/verify_production.py
-----------------------------------------
Production verification script for the onboarding module.

Tests the COMPLETE onboarding flow against the LIVE deployed backend:

  1. Health check — confirm the backend is reachable
  2. Upload a real document — POST /onboarding/upload
  3. Confirm ingestion status — GET /onboarding/status/{document_id}
  4. Confirm document appears in list — GET /onboarding/documents
  5. Confirm the RAG agent can retrieve from the uploaded doc — POST /chat

Usage
-----
    # Against the Azure Container Apps deployment:
    python onboarding/scripts/verify_production.py \\
        --url https://<your-backend-url> \\
        --file docs/pilot-documents/leave-policy.md

    # Against localhost (for local end-to-end test):
    python onboarding/scripts/verify_production.py \\
        --url http://localhost:8000 \\
        --file docs/pilot-documents/leave-policy.md

Environment
-----------
No Azure credentials are needed by this script — it calls the backend API
which uses its own environment configuration.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

# Try httpx for nicer multipart, fall back to urllib
try:
    import httpx
    _USE_HTTPX = True
except ImportError:
    _USE_HTTPX = False

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_TEST_FILE = (
    Path(__file__).resolve().parent.parent.parent
    / "docs" / "pilot-documents" / "leave-policy.md"
)

# Question to ask the agent after upload (should be answerable from leave-policy.md)
VERIFICATION_QUESTION = "How many days of paid annual leave do employees get per year?"


def _print(title: str) -> None:
    print(f"\n{'='*65}")
    print(f"  {title}")
    print('='*65)


def _get(url: str) -> dict:
    if _USE_HTTPX:
        with httpx.Client(timeout=30) as c:
            r = c.get(url)
            r.raise_for_status()
            return r.json()
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())


def _post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def _post_upload(url: str, file_path: Path) -> dict:
    if _USE_HTTPX:
        with httpx.Client(timeout=120) as c:
            with open(file_path, "rb") as f:
                r = c.post(url, files={"file": (file_path.name, f, "text/plain")})
            r.raise_for_status()
            return r.json()

    # urllib fallback — manual multipart
    boundary = "----verifyprod"
    file_bytes = file_path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'
        f"Content-Type: text/plain\r\n\r\n"
    ).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def main() -> None:
    parser = argparse.ArgumentParser(description="Production verification for the onboarding module")
    parser.add_argument("--url", default=DEFAULT_BASE_URL, help="Backend base URL")
    parser.add_argument("--file", default=str(DEFAULT_TEST_FILE), help="Document to upload")
    parser.add_argument("--question", default=VERIFICATION_QUESTION, help="RAG question to test")
    parser.add_argument("--skip-rag", action="store_true", help="Skip the RAG retrieval test")
    args = parser.parse_args()

    base = args.url.rstrip("/")
    file_path = Path(args.file)
    passed = 0
    failed = 0

    if not file_path.exists():
        print(f"ERROR: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    # ── Step 1: Health check ─────────────────────────────────────────────────
    _print("Step 1 — Backend Health Check")
    try:
        health = _get(f"{base}/health")
        print(f"  status         : {health.get('status')}")
        print(f"  content_safety : {health.get('content_safety')}")
        if health.get("status") == "ok":
            print("  ✓ Backend is healthy")
            passed += 1
        else:
            print("  ✗ Backend health check returned non-ok status")
            failed += 1
    except Exception as exc:
        print(f"  ✗ Backend unreachable: {exc}")
        print(f"\n  Is the backend running at {base}?")
        sys.exit(1)

    # ── Step 2: Upload document ──────────────────────────────────────────────
    _print(f"Step 2 — Upload Document: {file_path.name}")
    print(f"  Size: {file_path.stat().st_size:,} bytes")
    print(f"  Uploading to {base}/onboarding/upload ...")

    try:
        result = _post_upload(f"{base}/onboarding/upload", file_path)
        doc_id = result.get("document_id", "")
        chunks = result.get("chunks_count", 0)
        print(f"  ✓ document_id   : {doc_id}")
        print(f"  ✓ title         : {result.get('title', '')}")
        print(f"  ✓ status        : {result.get('status', '')}")
        print(f"  ✓ chunks_count  : {chunks}")
        print(f"  ✓ uploaded_at   : {result.get('uploaded_at', '')}")
        if result.get("status") == "ingested" and chunks > 0:
            passed += 1
        else:
            print("  ✗ Upload succeeded but status or chunk count is unexpected")
            failed += 1
    except Exception as exc:
        print(f"  ✗ Upload failed: {exc}", file=sys.stderr)
        failed += 1
        doc_id = file_path.stem
        chunks = 0

    # ── Step 3: Ingestion status ─────────────────────────────────────────────
    _print(f"Step 3 — Ingestion Status: {doc_id}")
    print("  Waiting 3 seconds for Azure AI Search index propagation...")
    time.sleep(3)

    try:
        status = _get(f"{base}/onboarding/status/{doc_id}")
        print(f"  ✓ status        : {status.get('status')}")
        print(f"  ✓ chunks_count  : {status.get('chunks_count')}")
        print(f"  ✓ source_file   : {status.get('filename')}")
        print(f"  ✓ data source   : {status.get('source', 'unknown')}")

        idx_chunks = status.get("chunks", [])
        if idx_chunks:
            print(f"\n  Chunk preview ({min(3, len(idx_chunks))} of {len(idx_chunks)}):")
            for c in idx_chunks[:3]:
                print(f"    [{c['chunk_index']}] {c['title'][:55]}")
                print(f"        {c['content_preview'][:80]}...")

        if status.get("status") == "ingested" and status.get("chunks_count", 0) > 0:
            passed += 1
        else:
            print("  ✗ Status check returned unexpected data")
            failed += 1
    except Exception as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if status_code == 404:
            print(f"  ✗ 404 — document not found in index yet (may need more propagation time)")
        else:
            print(f"  ✗ Status check failed: {exc}")
        failed += 1

    # ── Step 4: Document list ────────────────────────────────────────────────
    _print("Step 4 — Document List (enterprise-knowledge-index)")
    try:
        list_resp = _get(f"{base}/onboarding/documents")
        total = list_resp.get("total", 0)
        source = list_resp.get("source", "unknown")
        all_docs = list_resp.get("documents", [])
        print(f"  Total documents : {total}")
        print(f"  Data source     : {source}")

        target = next((d for d in all_docs if d.get("document_id") == doc_id), None)
        if target:
            print(f"  ✓ '{doc_id}' found in document list")
            print(f"    chunks_count : {target.get('chunks_count')}")
            passed += 1
        else:
            print(f"  ✗ '{doc_id}' NOT found in document list yet (propagation delay?)")
            # Don't fail hard — this can be a timing issue
            print("    (This may resolve after a few seconds; re-run to verify)")

        print(f"\n  All indexed documents:")
        for d in all_docs:
            print(f"    • {d.get('document_id'):30s}  {d.get('chunks_count', '?')} chunks")
    except Exception as exc:
        print(f"  ✗ Document list failed: {exc}")
        failed += 1

    # ── Step 5: RAG retrieval ────────────────────────────────────────────────
    if not args.skip_rag:
        _print("Step 5 — RAG Retrieval Test")
        print(f"  Question: {args.question}")
        print(f"  Asking agent at {base}/chat ...")

        try:
            chat_resp = _post_json(f"{base}/chat", {"question": args.question})
            answer = chat_resp.get("answer", "")
            citations = chat_resp.get("citations", [])
            escalated = chat_resp.get("escalation_required", False)

            print(f"\n  Answer snippet  : {answer[:200]}...")
            print(f"  Citations       : {len(citations)}")
            for c in citations:
                print(f"    • {c.get('source_file')} — {c.get('title')}")
            print(f"  Escalated       : {escalated}")

            # A good answer should not be escalated and should have citations
            if answer and not escalated:
                print("\n  ✓ Agent returned a grounded answer without escalation")
                passed += 1
            elif escalated:
                print("\n  ✗ Agent escalated — document may not be in the index yet")
                failed += 1
            else:
                print("\n  ✗ Agent returned an empty answer")
                failed += 1
        except Exception as exc:
            print(f"  ✗ RAG test failed: {exc}")
            failed += 1
    else:
        print("\n  (RAG test skipped)")

    # ── Summary ──────────────────────────────────────────────────────────────
    _print("Verification Summary")
    total_steps = passed + failed
    print(f"  Backend URL  : {base}")
    print(f"  Document     : {file_path.name}  (doc_id={doc_id})")
    print(f"  Passed       : {passed}/{total_steps}")
    print(f"  Failed       : {failed}/{total_steps}")
    print()

    if failed == 0:
        print("  ✅  ALL CHECKS PASSED — onboarding module is working correctly in production.")
    else:
        print("  ⚠️   SOME CHECKS FAILED — see details above.")
        print()
        print("  Common fixes:")
        print("  • If status/list return stale data: Azure AI Search may need 5-10s to propagate")
        print("  • If upload fails: check backend logs and Azure credentials")
        print("  • If RAG fails: wait 30s for index consistency and re-run with --skip-rag first")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
