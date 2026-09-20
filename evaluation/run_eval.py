#!/usr/bin/env python3
"""
AI-103 Evaluation Script Skeleton — Day 3
==========================================

Sends the questions from ``evaluation/evaluation_set.json`` to the
``POST /chat`` API endpoint and logs structured results for later
correctness and grounding scoring.

Usage
-----
Basic run (requires the backend server to be running):

    python evaluation/run_eval.py

Override the API URL (when Ravish's backend is deployed):

    python evaluation/run_eval.py --api-url http://<backend-host>/chat

Or via environment variable:

    CHAT_API_URL=http://<backend-host>/chat python evaluation/run_eval.py

Dry-run (validates the evaluation set without calling the API):

    python evaluation/run_eval.py --dry-run

Filter by category:

    python evaluation/run_eval.py --category answerable
    python evaluation/run_eval.py --category edge_case

Output
------
Results are written to::

    evaluation/results/run_<YYYYMMDD_HHMMSS>.jsonl

Each line is one JSON object (one question):

    {
        "run_id":            "run_20260920_160000",
        "question_id":       "LEAVE-001",
        "category":          "answerable",
        "policy":            "leave",
        "question":          "How many days ...",
        "expected_source":   "leave-policy.md",
        "expected_facts":    ["Employees are entitled to ..."],
        "http_status":       200,
        "latency_ms":        412,
        "answer":            "You are entitled to 18 days ...",
        "citations":         [{"document_id": "...", "title": "...", "source_file": "..."}],
        "error":             null,
        "correctness_score": null,   // ← filled in by later grading step
        "grounding_score":   null,   // ← filled in by later grading step
        "notes":             ""      // ← free-text for manual reviewer
    }

Scores are ``null`` in this skeleton — they will be populated by a
subsequent grading script once the live backend is integrated.

Dependencies
------------
Only standard library modules are used (``urllib.request`` for HTTP) so
this script runs without any extra installation step.  No external packages
required.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths (relative to repo root)
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).parent.parent
_EVAL_SET = _REPO_ROOT / "evaluation" / "evaluation_set.json"
_RESULTS_DIR = _REPO_ROOT / "evaluation" / "results"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
_DEFAULT_API_URL = os.getenv("CHAT_API_URL", "http://localhost:8000/chat")
_REQUEST_TIMEOUT_S = 30     # seconds per question
_RETRY_ATTEMPTS = 2         # number of retries on transient errors
_RETRY_DELAY_S = 2.0        # delay between retries


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_evaluation_set(path: Path) -> dict:
    """Load and validate the evaluation set JSON."""
    if not path.exists():
        logger.error("Evaluation set not found: %s", path)
        sys.exit(1)

    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)

    if "evaluation_set" not in data:
        logger.error("Invalid evaluation set: missing top-level 'evaluation_set' key.")
        sys.exit(1)

    questions = data["evaluation_set"].get("questions", [])
    if not questions:
        logger.error("No questions found in evaluation set.")
        sys.exit(1)

    logger.info(
        "Loaded evaluation set v%s — %d questions.",
        data["evaluation_set"].get("version", "?"),
        len(questions),
    )
    return data


def call_chat_api(
    api_url: str,
    question: str,
    *,
    timeout: int = _REQUEST_TIMEOUT_S,
    attempts: int = _RETRY_ATTEMPTS,
) -> tuple[int, dict | None, float, str | None]:
    """
    POST *question* to *api_url* and return ``(http_status, body, latency_ms, error)``.

    Parameters
    ----------
    api_url:
        Full URL for the POST /chat endpoint.
    question:
        The question string to send.
    timeout:
        Per-request timeout in seconds.
    attempts:
        Total number of attempts (including retries).

    Returns
    -------
    tuple of (http_status, response_body_dict, latency_ms, error_message)
        ``http_status`` is ``None`` on a network-level error.
        ``response_body_dict`` is ``None`` when the request failed.
        ``error_message`` is ``None`` on success.
    """
    payload = json.dumps({"question": question}).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    req = urllib.request.Request(api_url, data=payload, headers=headers, method="POST")

    last_error: str | None = None

    for attempt in range(1, attempts + 1):
        t_start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                latency_ms = round((time.perf_counter() - t_start) * 1000, 1)
                status = resp.status
                body = json.loads(resp.read().decode("utf-8"))
                return status, body, latency_ms, None

        except urllib.error.HTTPError as exc:
            latency_ms = round((time.perf_counter() - t_start) * 1000, 1)
            # Read error body for context (non-2xx HTTP responses).
            try:
                error_body = json.loads(exc.read().decode("utf-8"))
                detail = error_body.get("detail", str(exc))
            except Exception:
                detail = str(exc)
            last_error = f"HTTP {exc.code}: {detail}"
            return exc.code, None, latency_ms, last_error

        except urllib.error.URLError as exc:
            latency_ms = round((time.perf_counter() - t_start) * 1000, 1)
            last_error = f"Network error (attempt {attempt}/{attempts}): {exc.reason}"
            logger.warning(last_error)
            if attempt < attempts:
                time.sleep(_RETRY_DELAY_S)

        except Exception as exc:  # noqa: BLE001
            latency_ms = round((time.perf_counter() - t_start) * 1000, 1)
            last_error = f"Unexpected error (attempt {attempt}/{attempts}): {exc}"
            logger.warning(last_error)
            if attempt < attempts:
                time.sleep(_RETRY_DELAY_S)

    return None, None, 0.0, last_error  # type: ignore[return-value]


def build_result_record(
    *,
    run_id: str,
    q: dict,
    http_status: int | None,
    body: dict | None,
    latency_ms: float,
    error: str | None,
) -> dict:
    """Assemble a structured result record for a single question."""
    answer = body.get("answer", "") if body else ""
    citations = body.get("citations", []) if body else []

    return {
        "run_id": run_id,
        "question_id": q.get("id", ""),
        "category": q.get("category", ""),
        "policy": q.get("policy", ""),
        "question": q.get("question", ""),
        "expected_source": q.get("expected_source", ""),
        "expected_facts": q.get("expected_facts", []),
        "http_status": http_status,
        "latency_ms": latency_ms,
        "answer": answer,
        "citations": citations,
        "error": error,
        # ── Scoring fields — to be populated by the grading script ──────────
        "correctness_score": None,  # float 0.0–1.0 | "pass" | "fail"
        "grounding_score": None,    # float 0.0–1.0 | "pass" | "fail"
        "notes": "",                # free-text for manual reviewer
    }


def print_summary(results: list[dict]) -> None:
    """Print a human-readable summary table to stdout."""
    total = len(results)
    success = sum(1 for r in results if r["http_status"] == 200)
    failed = total - success
    avg_latency = (
        sum(r["latency_ms"] for r in results if r["http_status"] == 200) / max(success, 1)
    )

    width = 80
    print("\n" + "=" * width)
    print(f"  Evaluation Run Summary")
    print("=" * width)
    print(f"  Questions sent  : {total}")
    print(f"  Successful (200): {success}")
    print(f"  Failed / Error  : {failed}")
    print(f"  Avg latency     : {avg_latency:.0f} ms  (successful calls only)")
    print("-" * width)
    print(f"  {'ID':<12} {'Category':<14} {'Status':>6}  {'Latency':>8}  {'Preview'}")
    print("-" * width)
    for r in results:
        status_str = str(r["http_status"]) if r["http_status"] else "ERR"
        answer_preview = (r["answer"][:40] + "…") if len(r["answer"]) > 40 else r["answer"]
        if not answer_preview and r["error"]:
            answer_preview = f"[{r['error'][:40]}]"
        print(
            f"  {r['question_id']:<12} {r['category']:<14} {status_str:>6}  "
            f"{r['latency_ms']:>7.0f}ms  {answer_preview}"
        )
    print("=" * width + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI-103 evaluation script — calls POST /chat for each evaluation question.",
    )
    parser.add_argument(
        "--api-url",
        default=_DEFAULT_API_URL,
        help=f"Full URL of the POST /chat endpoint (default: {_DEFAULT_API_URL}).",
    )
    parser.add_argument(
        "--category",
        choices=["answerable", "edge_case", "knowledge_gap", "out_of_scope"],
        default=None,
        help="Run only questions of the specified category.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the evaluation set and print questions without calling the API.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=_REQUEST_TIMEOUT_S,
        metavar="SECONDS",
        help=f"Per-question request timeout in seconds (default: {_REQUEST_TIMEOUT_S}).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # ── Load evaluation set ─────────────────────────────────────────────────
    data = load_evaluation_set(_EVAL_SET)
    questions = data["evaluation_set"]["questions"]

    # ── Filter by category if requested ────────────────────────────────────
    if args.category:
        questions = [q for q in questions if q.get("category") == args.category]
        logger.info("Filtered to category '%s': %d questions.", args.category, len(questions))

    if not questions:
        logger.warning("No questions to run after filtering.")
        return

    # ── Dry-run mode ────────────────────────────────────────────────────────
    if args.dry_run:
        print(f"\n{'='*60}")
        print(f"  DRY RUN — {len(questions)} question(s) would be sent to:")
        print(f"  {args.api_url}")
        print(f"{'='*60}")
        for q in questions:
            print(f"  [{q.get('category','?'):>13}]  {q['id']}: {q['question'][:60]}")
        print(f"{'='*60}\n")
        return

    # ── Prepare output ──────────────────────────────────────────────────────
    run_ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id = f"run_{run_ts}"
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = _RESULTS_DIR / f"{run_id}.jsonl"

    logger.info("Run ID      : %s", run_id)
    logger.info("API URL     : %s", args.api_url)
    logger.info("Output file : %s", output_path.relative_to(_REPO_ROOT))
    logger.info("Questions   : %d", len(questions))

    # ── Run evaluation ──────────────────────────────────────────────────────
    results: list[dict] = []

    with output_path.open("w", encoding="utf-8") as out_fh:
        for i, q in enumerate(questions, start=1):
            q_id = q.get("id", f"Q{i:03d}")
            logger.info("[%d/%d] %s — %s", i, len(questions), q_id, q["question"][:60])

            http_status, body, latency_ms, error = call_chat_api(
                args.api_url,
                q["question"],
                timeout=args.timeout,
            )

            if error:
                logger.warning("  → %s", error)
            else:
                logger.info("  → %d  %s ms", http_status, latency_ms)

            record = build_result_record(
                run_id=run_id,
                q=q,
                http_status=http_status,
                body=body,
                latency_ms=latency_ms,
                error=error,
            )
            results.append(record)

            # Write immediately so partial results are preserved on interruption.
            out_fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            out_fh.flush()

    # ── Print summary ───────────────────────────────────────────────────────
    print_summary(results)
    logger.info("Results written to: %s", output_path)


if __name__ == "__main__":
    main()
