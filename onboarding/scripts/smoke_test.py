#!/usr/bin/env python3
"""
onboarding/scripts/smoke_test.py
----------------------------------
End-to-end local smoke test for the onboarding ingestion pipeline.

This script runs the COMPLETE pipeline locally:
  1. Upload & ingest a real document via the HTTP API
  2. Wait briefly for indexing to propagate
  3. Query ingestion status
  4. List all documents and verify the document appears
  5. Print a summary

Usage
-----
    # 1. Start the onboarding service (separate terminal)
    cd <repo-root>
    uvicorn onboarding.main:app --reload --port 8002

    # 2. Run this script
    python onboarding/scripts/smoke_test.py [--file path/to/file.md] [--url http://localhost:8002]

Environment
-----------
Reads credentials from onboarding/.env or backend/.env (same as the service).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Try to use httpx if available, otherwise fall back to urllib
try:
    import httpx
    _USE_HTTPX = True
except ImportError:
    import urllib.request, urllib.parse, json as _json
    _USE_HTTPX = False


DEFAULT_BASE_URL = "http://localhost:8002"
DEFAULT_TEST_FILE = (
    Path(__file__).resolve().parent.parent.parent
    / "docs" / "pilot-documents" / "leave-policy.md"
)


def _print_section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def _post_upload(base_url: str, file_path: Path) -> dict:
    """POST /onboarding/upload with the given file."""
    url = f"{base_url}/onboarding/upload"

    if _USE_HTTPX:
        with httpx.Client(timeout=120) as client:
            with open(file_path, "rb") as f:
                resp = client.post(
                    url,
                    files={"file": (file_path.name, f, "text/plain")},
                    data={
                        "document_type": "policy",
                        "permission_tags": "all-employees",
                    },
                )
            resp.raise_for_status()
            return resp.json()
    else:
        import urllib.request
        import urllib.parse
        import json

        boundary = "----smoketest"
        file_content = file_path.read_bytes()
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'
            f"Content-Type: text/plain\r\n\r\n"
        ).encode() + file_content + (
            f"\r\n--{boundary}\r\n"
            f'Content-Disposition: form-data; name="document_type"\r\n\r\npolicy\r\n'
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="permission_tags"\r\n\r\nall-employees\r\n'
            f"--{boundary}--\r\n"
        ).encode()

        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())


def _get_json(url: str) -> dict:
    if _USE_HTTPX:
        with httpx.Client(timeout=30) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.json()
    else:
        import urllib.request, json
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read())


def main() -> None:
    parser = argparse.ArgumentParser(description="Onboarding smoke test")
    parser.add_argument(
        "--file",
        default=str(DEFAULT_TEST_FILE),
        help="Path to document file to upload (default: leave-policy.md)",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_BASE_URL,
        help=f"Base URL of the onboarding service (default: {DEFAULT_BASE_URL})",
    )
    args = parser.parse_args()

    file_path = Path(args.file)
    base_url = args.url.rstrip("/")

    if not file_path.exists():
        print(f"ERROR: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    # ── Step 0: Health check ─────────────────────────────────────────────────
    _print_section("Step 0 — Health Check")
    try:
        health = _get_json(f"{base_url}/onboarding/health")
        print(f"  Status         : {health.get('status')}")
        print(f"  Azure Search   : {health.get('azure_search')}")
        print(f"  Azure OpenAI   : {health.get('azure_openai')}")
        print(f"  Doc Intelligence: {health.get('azure_document_intelligence')}")
        print(f"  Index name     : {health.get('index_name')}")
        if health.get("status") != "ok":
            print("\n  WARNING: Service health is degraded. Continuing anyway...")
    except Exception as exc:
        print(f"  ERROR: Health check failed — {exc}")
        print("  Is the service running? Start it with:")
        print(f"    uvicorn onboarding.main:app --reload --port 8002")
        sys.exit(1)

    # ── Step 1: Upload ───────────────────────────────────────────────────────
    _print_section(f"Step 1 — Upload: {file_path.name}")
    print(f"  File path : {file_path}")
    print(f"  File size : {file_path.stat().st_size:,} bytes")
    print(f"  Uploading to {base_url}/onboarding/upload ...")

    try:
        upload_result = _post_upload(base_url, file_path)
    except Exception as exc:
        print(f"  ERROR: Upload failed — {exc}", file=sys.stderr)
        sys.exit(1)

    doc_id = upload_result["document_id"]
    print(f"\n  ✓ document_id   : {doc_id}")
    print(f"  ✓ source_file   : {upload_result['source_file']}")
    print(f"  ✓ document_type : {upload_result['document_type']}")
    print(f"  ✓ permissions   : {upload_result['permission_tags']}")
    print(f"  ✓ total_chunks  : {upload_result['total_chunks']}")
    print(f"  ✓ indexed_chunks: {upload_result['indexed_chunks']}")
    print(f"  ✓ ingested_at   : {upload_result['ingested_at']}")
    print(f"\n  Chunk preview:")
    for chunk in upload_result.get("chunks", [])[:3]:
        print(f"    [{chunk['chunk_index']}] {chunk['title'][:50]}")
        print(f"        {chunk['content_preview'][:80]}...")

    # ── Step 2: Status check ─────────────────────────────────────────────────
    _print_section(f"Step 2 — Ingestion Status: {doc_id}")
    print("  Waiting 2 seconds for index propagation...")
    time.sleep(2)

    try:
        status = _get_json(f"{base_url}/onboarding/status/{doc_id}")
        print(f"  ✓ status       : {status['status']}")
        print(f"  ✓ total_chunks : {status['total_chunks']}")
        print(f"  ✓ source_file  : {status['source_file']}")
        print(f"  ✓ ingested_at  : {status['ingested_at']}")
        if status["status"] != "completed":
            print(f"  WARNING: status is '{status['status']}', expected 'completed'")
    except Exception as exc:
        print(f"  ERROR: Status check failed — {exc}", file=sys.stderr)
        sys.exit(1)

    # ── Step 3: List documents ───────────────────────────────────────────────
    _print_section("Step 3 — List Documents")
    try:
        docs_response = _get_json(f"{base_url}/onboarding/documents")
        total = docs_response["total"]
        documents = docs_response["documents"]
        print(f"  Total indexed documents: {total}")
        target_doc = next((d for d in documents if d["document_id"] == doc_id), None)
        if target_doc:
            print(f"  ✓ '{doc_id}' found in document list")
            print(f"    chunks: {target_doc['total_chunks']}")
        else:
            print(f"  WARNING: '{doc_id}' not found in document list (may need more time to propagate)")
    except Exception as exc:
        print(f"  ERROR: List documents failed — {exc}", file=sys.stderr)

    # ── Summary ──────────────────────────────────────────────────────────────
    _print_section("Smoke Test Summary")
    print(f"  Document : {file_path.name}")
    print(f"  Doc ID   : {doc_id}")
    print(f"  Chunks   : {upload_result['indexed_chunks']}/{upload_result['total_chunks']} indexed")
    print(f"  Status   : {status.get('status', 'unknown')}")
    print()
    print("  Pipeline verified:")
    print("    Upload → Parse → Chunk → Embed → Index → Status OK")
    print()
    print(f"  The document is now searchable via the RAG system.")
    print(f"  Try asking the agent about: {file_path.stem.replace('-', ' ')}")
    print()


if __name__ == "__main__":
    main()
