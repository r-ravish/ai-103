#!/usr/bin/env python3
"""
AI-103 Day 3 Evaluation Script
================================

Runs the full evaluation pipeline against the POST /chat endpoint:

  Load evaluation_set.json
          ↓
  For each question → POST /chat
          ↓
  Capture answer, citations, latency, http_status
          ↓
  Auto-score:
    correct              — expected_facts found in answer (case-insensitive)
    citation_present     — citations[] not empty
    citation_correct     — expected_source appears in a citation source_file
    tool_call_detected   — TKT-XXXXXXXX pattern or ticket-creation language in answer
    tool_call_correct    — tool_expected matches tool_call_detected
    hallucination_detected — answerable/no_tool question answered incorrectly with
                             non-empty answer (proxy for hallucination)
    pass_fail            — overall PASS / FAIL per question
          ↓
  Write evaluation/results/day3-results.json   (full structured results)
  Write evaluation/results/day3-results.csv    (spreadsheet-friendly)
  Write evaluation/results/day3-summary.md     (human-readable report)

Usage
-----
Dry-run (no API call):
    python evaluation/run_eval.py --dry-run

Full run (backend must be running):
    python evaluation/run_eval.py --api-url http://localhost:8000/chat

Filter by category:
    python evaluation/run_eval.py --category tool_action
    python evaluation/run_eval.py --category answerable

Use deployed backend:
    python evaluation/run_eval.py --api-url https://<host>/chat
    # or:
    CHAT_API_URL=https://<host>/chat python evaluation/run_eval.py

Output files are written to evaluation/results/ and named day3-results.*
so they can be committed alongside the evaluation set.

Configurable via environment variables:
    CHAT_API_URL       — full URL of POST /chat endpoint
    EVAL_TIMEOUT       — per-request timeout in seconds (default: 30)
    EVAL_RETRIES       — number of retry attempts on network error (default: 2)
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).parent.parent
_EVAL_SET = _REPO_ROOT / "evaluation" / "evaluation_set.json"
_RESULTS_DIR = _REPO_ROOT / "evaluation" / "results"

# Output filenames — fixed so they can be committed
_JSON_OUT = _RESULTS_DIR / "day3-results.json"
_CSV_OUT = _RESULTS_DIR / "day3-results.csv"
_MD_OUT = _RESULTS_DIR / "day3-summary.md"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
_DEFAULT_API_URL = os.getenv("CHAT_API_URL", "http://localhost:8000/chat")
_REQUEST_TIMEOUT = int(os.getenv("EVAL_TIMEOUT", "30"))
_RETRY_ATTEMPTS = int(os.getenv("EVAL_RETRIES", "2"))
_RETRY_DELAY = 2.0

# Pattern to detect a real ticket ID (TKT- followed by 8 hex chars, uppercase)
_TICKET_ID_PATTERN = re.compile(r"TKT-[0-9A-F]{8}", re.IGNORECASE)

# Phrases that indicate the agent called the support ticket tool
_TOOL_CALL_PHRASES = (
    "ticket created",
    "support ticket",
    "tkt-",
    "ticket id",
    "raised a ticket",
    "i have created",
    "i've created",
    "ticket has been",
    "created successfully",
)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_evaluation_set(path: Path) -> dict[str, Any]:
    if not path.exists():
        logger.error("Evaluation set not found: %s", path)
        sys.exit(1)
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if "evaluation_set" not in data:
        logger.error("Invalid evaluation set: missing 'evaluation_set' key.")
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


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def call_chat_api(
    api_url: str,
    question: str,
    *,
    timeout: int = _REQUEST_TIMEOUT,
    attempts: int = _RETRY_ATTEMPTS,
) -> tuple[int | None, dict | None, float, str | None]:
    """POST question to /chat. Returns (http_status, body, latency_ms, error)."""
    payload = json.dumps({"question": question}).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    last_error: str | None = None
    for attempt in range(1, attempts + 1):
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                latency = round((time.perf_counter() - t0) * 1000, 1)
                body = json.loads(resp.read().decode("utf-8"))
                return resp.status, body, latency, None
        except urllib.error.HTTPError as exc:
            latency = round((time.perf_counter() - t0) * 1000, 1)
            try:
                detail = json.loads(exc.read().decode()).get("detail", str(exc))
            except Exception:
                detail = str(exc)
            last_error = f"HTTP {exc.code}: {detail}"
            return exc.code, None, latency, last_error
        except (urllib.error.URLError, Exception) as exc:
            latency = round((time.perf_counter() - t0) * 1000, 1)
            last_error = f"Error (attempt {attempt}/{attempts}): {exc}"
            logger.warning(last_error)
            if attempt < attempts:
                time.sleep(_RETRY_DELAY)
    return None, None, 0.0, last_error


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    return text.lower().strip()


def score_correct(answer: str, expected_facts: list[str]) -> bool | None:
    """
    True  — at least one expected_fact keyword/phrase appears in the answer.
    False — expected_facts exist but none appear in the answer.
    None  — no expected_facts defined (knowledge_gap / out_of_scope / tool_action).
    """
    if not expected_facts:
        return None
    answer_lower = _normalize(answer)
    # Extract key numeric/word tokens from each expected fact and check presence
    for fact in expected_facts:
        # Look for any 3+ char meaningful token from the fact
        tokens = [t for t in re.findall(r"[a-z0-9]{3,}", _normalize(fact))]
        # Fact is "present" if more than half its significant tokens appear in answer
        if len(tokens) == 0:
            continue
        matches = sum(1 for t in tokens if t in answer_lower)
        if matches / len(tokens) >= 0.5:
            return True
    return False


def score_citation_present(citations: list) -> bool:
    return len(citations) > 0


def score_citation_correct(citations: list, expected_source: str | None) -> bool | None:
    """
    True  — expected_source appears in one of the citation source_files.
    False — expected_source defined but not found in any citation.
    None  — expected_source is null (no citation expected for this question).
    """
    if expected_source is None:
        return None
    for c in citations:
        sf = c.get("source_file", "")
        if expected_source.lower() in sf.lower():
            return True
    return False


def score_tool_call_detected(answer: str) -> bool:
    """
    Heuristic: detect whether the agent called create_support_ticket.
    True if a real ticket ID pattern (TKT-XXXXXXXX) appears in the answer,
    OR if multiple tool-call phrases co-occur.
    """
    answer_lower = _normalize(answer)
    if _TICKET_ID_PATTERN.search(answer):
        return True
    phrase_hits = sum(1 for p in _TOOL_CALL_PHRASES if p in answer_lower)
    return phrase_hits >= 2


def score_tool_call_correct(tool_expected: bool, tool_call_detected: bool) -> bool:
    return tool_expected == tool_call_detected


def score_hallucination(
    category: str,
    correct: bool | None,
    answer: str,
    http_status: int | None,
) -> bool:
    """
    Proxy hallucination detection.

    For answerable / no_tool / edge_case categories:
      - If the answer is non-empty AND correct=False → likely hallucinated.
    For knowledge_gap / out_of_scope:
      - If the answer contains specific numbers or dates that look invented → flag.
    For tool_action:
      - If a fake-looking ticket ID is claimed without TKT-XXXXXXXX format → flag.
    """
    if http_status != 200 or not answer:
        return False

    answer_lower = _normalize(answer)

    if category in ("answerable", "no_tool", "edge_case"):
        return correct is False

    if category in ("knowledge_gap", "out_of_scope"):
        # Fabricated specifics: numbers, dates, or definitive policy claims
        has_invented_number = bool(re.search(r"\b\d{1,3}\s*(days?|weeks?|months?|years?|%)\b", answer_lower))
        has_definitive_claim = any(
            phrase in answer_lower
            for phrase in ("the policy states", "the company provides", "you are entitled to", "employees receive")
        )
        return has_invented_number or has_definitive_claim

    if category == "tool_action":
        # If no real TKT- ID but answer claims a ticket exists
        has_ticket_claim = any(p in answer_lower for p in ("ticket", "tkt", "created", "raised"))
        has_real_ticket_id = bool(_TICKET_ID_PATTERN.search(answer))
        return has_ticket_claim and not has_real_ticket_id

    return False


def compute_pass_fail(
    category: str,
    correct: bool | None,
    citation_expected: bool,
    citation_correct: bool | None,
    tool_call_correct: bool,
    hallucination_detected: bool,
    http_status: int | None,
    error: str | None,
) -> str:
    """
    Overall PASS / FAIL / SKIP per question.

    SKIP — question could not be evaluated (network/server error).
    PASS — all relevant checks passed.
    FAIL — at least one relevant check failed.
    """
    if http_status != 200 or error:
        return "SKIP"

    if hallucination_detected:
        return "FAIL"

    if category in ("answerable", "edge_case", "no_tool"):
        if correct is False:
            return "FAIL"
        if citation_expected and citation_correct is False:
            return "FAIL"
        if not tool_call_correct:
            return "FAIL"
        return "PASS"

    if category == "tool_action":
        if not tool_call_correct:
            return "FAIL"
        return "PASS"

    if category == "knowledge_gap":
        # Pass if agent did not hallucinate (already checked above)
        return "PASS"

    if category == "out_of_scope":
        return "PASS"

    return "PASS"


# ---------------------------------------------------------------------------
# Record builder
# ---------------------------------------------------------------------------

def build_record(
    *,
    run_id: str,
    q: dict[str, Any],
    http_status: int | None,
    body: dict | None,
    latency_ms: float,
    error: str | None,
) -> dict[str, Any]:
    answer: str = body.get("answer", "") if body else ""
    citations: list = body.get("citations", []) if body else []

    expected_facts: list[str] = q.get("expected_facts", [])
    expected_source: str | None = q.get("expected_source")
    tool_expected: bool = q.get("tool_expected", False)
    citation_expected: bool = q.get("citation_expected", True)
    category: str = q.get("category", "")

    correct = score_correct(answer, expected_facts)
    citation_present = score_citation_present(citations)
    citation_correct = score_citation_correct(citations, expected_source)
    tool_call_detected = score_tool_call_detected(answer)
    tool_call_correct = score_tool_call_correct(tool_expected, tool_call_detected)
    hallucination = score_hallucination(category, correct, answer, http_status)

    pass_fail = compute_pass_fail(
        category=category,
        correct=correct,
        citation_expected=citation_expected,
        citation_correct=citation_correct,
        tool_call_correct=tool_call_correct,
        hallucination_detected=hallucination,
        http_status=http_status,
        error=error,
    )

    return {
        # ── Identity ─────────────────────────────────────────────
        "run_id": run_id,
        "question_id": q.get("id", ""),
        "question": q.get("question", ""),
        "category": category,
        "policy": q.get("policy"),
        # ── Expectation ──────────────────────────────────────────
        "expected_behavior": q.get("expected_behavior", ""),
        "expected_source": expected_source,
        "expected_facts": expected_facts,
        "tool_expected": tool_expected,
        "tool_name": q.get("tool_name"),
        "citation_expected": citation_expected,
        "escalation_expected": q.get("escalation_expected", False),
        # ── Raw API response ─────────────────────────────────────
        "http_status": http_status,
        "latency_ms": latency_ms,
        "answer": answer,
        "citations": citations,
        "error": error,
        # ── Scores ───────────────────────────────────────────────
        "correct": correct,
        "citation_present": citation_present,
        "citation_correct": citation_correct,
        "tool_call_detected": tool_call_detected,
        "tool_call_correct": tool_call_correct,
        "hallucination_detected": hallucination,
        "pass_fail": pass_fail,
        # ── Manual review ────────────────────────────────────────
        "scored_by": "auto",
        "notes": "",
    }


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

_CSV_FIELDS = [
    "question_id", "category", "question", "expected_source",
    "tool_expected", "tool_name", "citation_expected",
    "http_status", "latency_ms",
    "correct", "citation_present", "citation_correct",
    "tool_call_detected", "tool_call_correct",
    "hallucination_detected", "pass_fail",
    "answer", "error", "notes",
]


def write_json(records: list[dict], meta: dict, path: Path) -> None:
    payload = {
        "evaluation_meta": meta,
        "results": records,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("JSON results → %s", path.relative_to(_REPO_ROOT))


def write_csv(records: list[dict], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            writer.writerow(r)
    logger.info("CSV results  → %s", path.relative_to(_REPO_ROOT))


def write_summary_md(records: list[dict], meta: dict, path: Path) -> None:
    total = len(records)
    passed = sum(1 for r in records if r["pass_fail"] == "PASS")
    failed = sum(1 for r in records if r["pass_fail"] == "FAIL")
    skipped = sum(1 for r in records if r["pass_fail"] == "SKIP")
    pass_rate = round(passed / total * 100) if total else 0

    correct_count = sum(1 for r in records if r["correct"] is True)
    incorrect_count = sum(1 for r in records if r["correct"] is False)
    citation_ok = sum(1 for r in records if r["citation_correct"] is True)
    citation_missing = sum(1 for r in records if r["citation_correct"] is False)
    hallucinations = sum(1 for r in records if r["hallucination_detected"])
    tool_correct = sum(1 for r in records if r["tool_call_correct"])
    tool_wrong = sum(1 for r in records if not r["tool_call_correct"] and r["http_status"] == 200)
    tool_action_qs = [r for r in records if r["category"] == "tool_action"]
    tool_detected = sum(1 for r in tool_action_qs if r["tool_call_detected"])
    no_tool_qs = [r for r in records if r["category"] == "no_tool"]
    no_tool_correct = sum(1 for r in no_tool_qs if not r["tool_call_detected"])

    avg_latency = round(
        sum(r["latency_ms"] for r in records if r["http_status"] == 200)
        / max(sum(1 for r in records if r["http_status"] == 200), 1)
    )

    lines: list[str] = [
        "# AI-103 Day 3 Evaluation Summary",
        "",
        f"**Run ID:** `{meta.get('run_id', 'N/A')}`  ",
        f"**Run timestamp:** {meta.get('run_timestamp', 'N/A')}  ",
        f"**API URL:** `{meta.get('api_url', 'N/A')}`  ",
        f"**Evaluation set version:** {meta.get('eval_set_version', 'N/A')}  ",
        "",
        "---",
        "",
        "## Overall Results",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Total questions | {total} |",
        f"| PASS | {passed} ({pass_rate}%) |",
        f"| FAIL | {failed} |",
        f"| SKIP (API error) | {skipped} |",
        f"| Avg latency (200 OK) | {avg_latency} ms |",
        "",
        "---",
        "",
        "## Correctness",
        "",
        f"| Result | Count |",
        f"|---|---|",
        f"| Correct answers | {correct_count} |",
        f"| Incorrect answers | {incorrect_count} |",
        f"| N/A (no expected facts) | {total - correct_count - incorrect_count} |",
        "",
        "---",
        "",
        "## Citation Results",
        "",
        f"| Result | Count |",
        f"|---|---|",
        f"| Citation correct | {citation_ok} |",
        f"| Citation missing or wrong | {citation_missing} |",
        f"| Citation not expected | {total - citation_ok - citation_missing} |",
        "",
        "---",
        "",
        "## Tool-Calling Results",
        "",
        f"| Result | Count |",
        f"|---|---|",
        f"| Tool-action questions | {len(tool_action_qs)} |",
        f"| Tool correctly called | {tool_detected} |",
        f"| No-tool questions | {len(no_tool_qs)} |",
        f"| Correctly avoided tool | {no_tool_correct} |",
        f"| Tool call behaviour correct overall | {tool_correct} |",
        f"| Tool call behaviour incorrect | {tool_wrong} |",
        "",
        "---",
        "",
        "## Hallucination Findings",
        "",
        f"| Result | Count |",
        f"|---|---|",
        f"| Hallucination detected | {hallucinations} |",
        f"| No hallucination | {total - hallucinations} |",
        "",
        "> **Scoring method:** Hallucination is detected automatically using heuristics —",
        "> incorrect answers on answerable questions, invented specifics on knowledge-gap",
        "> questions, and claimed ticket creation without a real TKT-XXXXXXXX ID.",
        "> Manual review of flagged cases is recommended.",
        "",
        "---",
        "",
        "## Question-by-Question Results",
        "",
        "| ID | Category | Status | Correct | Citation ✓ | Tool ✓ | Hallucination | Notes |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for r in records:
        correct_str = "✅" if r["correct"] is True else ("❌" if r["correct"] is False else "—")
        cite_str = "✅" if r["citation_correct"] is True else ("❌" if r["citation_correct"] is False else "—")
        tool_str = "✅" if r["tool_call_correct"] else "❌"
        hall_str = "⚠️" if r["hallucination_detected"] else "—"
        status_emoji = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️"}.get(r["pass_fail"], "?")
        lines.append(
            f"| {r['question_id']} | {r['category']} | {status_emoji} {r['pass_fail']} "
            f"| {correct_str} | {cite_str} | {tool_str} | {hall_str} | {r['notes'] or ''} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Tracing Observations",
        "",
        "See [`evaluation/tracing.md`](../tracing.md) for instructions on how to inspect",
        "individual request traces in the Azure AI Foundry portal.",
        "",
        "For each FAIL or SKIP result above, inspect the Foundry trace to determine",
        "whether the failure originated from:",
        "",
        "- **Retrieval** — wrong chunks returned, or no chunks returned",
        "- **Tool selection** — tool called when it should not be, or not called when it should",
        "- **Tool execution** — MCP server error or incorrect ticket fields",
        "- **Answer generation** — LLM produced incorrect or hallucinated text",
        "- **Citation generation** — correct answer but wrong or missing source attribution",
        "",
        "---",
        "",
        "## Scoring Methodology",
        "",
        "All scores in this report are **auto-computed** by `evaluation/run_eval.py`.",
        "The scoring logic is heuristic-based (keyword matching, pattern detection)",
        "and may produce false positives or negatives — especially for nuanced edge cases.",
        "",
        "**Recommended next step:** manually review every FAIL and SKIP result,",
        "update the `notes` field in `day3-results.json`, and re-run the summary.",
        "",
        f"*Generated by `evaluation/run_eval.py` at {meta.get('run_timestamp', 'N/A')}*",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("MD summary   → %s", path.relative_to(_REPO_ROOT))


# ---------------------------------------------------------------------------
# Summary printer (stdout)
# ---------------------------------------------------------------------------

def print_console_summary(records: list[dict]) -> None:
    total = len(records)
    passed = sum(1 for r in records if r["pass_fail"] == "PASS")
    failed = sum(1 for r in records if r["pass_fail"] == "FAIL")
    skipped = sum(1 for r in records if r["pass_fail"] == "SKIP")
    hallucinations = sum(1 for r in records if r["hallucination_detected"])
    w = 90

    print("\n" + "=" * w)
    print(f"  Day 3 Evaluation — Summary")
    print("=" * w)
    print(f"  Questions : {total}   PASS: {passed}   FAIL: {failed}   SKIP: {skipped}")
    print(f"  Hallucinations detected: {hallucinations}")
    print("-" * w)
    print(
        f"  {'ID':<13} {'Category':<14} {'PF':>5}  {'OK?':>5}  {'Cite':>5}  "
        f"{'Tool':>5}  {'Hall':>5}  {'ms':>6}  Preview"
    )
    print("-" * w)
    for r in records:
        pf = r["pass_fail"]
        ok = "✓" if r["correct"] is True else ("✗" if r["correct"] is False else "—")
        cite = "✓" if r["citation_correct"] is True else ("✗" if r["citation_correct"] is False else "—")
        tool = "✓" if r["tool_call_correct"] else "✗"
        hall = "!" if r["hallucination_detected"] else "—"
        preview = (r["answer"][:35] + "…") if len(r["answer"]) > 35 else r["answer"]
        if not preview and r["error"]:
            preview = f"[ERR: {r['error'][:30]}]"
        print(
            f"  {r['question_id']:<13} {r['category']:<14} {pf:>5}  {ok:>5}  {cite:>5}  "
            f"{tool:>5}  {hall:>5}  {r['latency_ms']:>5.0f}ms  {preview}"
        )
    print("=" * w + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI-103 Day 3 evaluation script — calls POST /chat for every question.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--api-url",
        default=_DEFAULT_API_URL,
        help=f"Full URL of POST /chat (default: {_DEFAULT_API_URL}). Also settable via CHAT_API_URL.",
    )
    parser.add_argument(
        "--category",
        choices=["answerable", "edge_case", "knowledge_gap", "out_of_scope",
                 "tool_action", "no_tool"],
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
        default=_REQUEST_TIMEOUT,
        metavar="SECONDS",
        help=f"Per-question timeout in seconds (default: {_REQUEST_TIMEOUT}).",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Run the evaluation but do not write output files (prints to stdout only).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    data = load_evaluation_set(_EVAL_SET)
    questions = data["evaluation_set"]["questions"]

    if args.category:
        questions = [q for q in questions if q.get("category") == args.category]
        logger.info("Filtered to '%s': %d question(s).", args.category, len(questions))

    if not questions:
        logger.warning("No questions to run.")
        return

    # ── Dry-run ─────────────────────────────────────────────────────────────
    if args.dry_run:
        print(f"\n{'='*65}")
        print(f"  DRY RUN — {len(questions)} question(s) → {args.api_url}")
        print(f"{'='*65}")
        for q in questions:
            tool_str = f"  [tool: {q.get('tool_name')}]" if q.get("tool_expected") else ""
            print(f"  [{q.get('category','?'):>12}]  {q['id']}: {q['question'][:55]}{tool_str}")
        print(f"{'='*65}\n")
        return

    # ── Setup run ────────────────────────────────────────────────────────────
    run_ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"day3-{run_ts}"
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    eval_meta = {
        "run_id": run_id,
        "run_timestamp": run_ts,
        "api_url": args.api_url,
        "eval_set_version": data["evaluation_set"].get("version", "?"),
        "total_questions": len(questions),
        "category_filter": args.category,
        "scoring": "auto-heuristic-v1",
    }

    logger.info("Run ID   : %s", run_id)
    logger.info("API URL  : %s", args.api_url)
    logger.info("Questions: %d", len(questions))

    # ── Run ──────────────────────────────────────────────────────────────────
    records: list[dict] = []

    for i, q in enumerate(questions, start=1):
        q_id = q.get("id", f"Q{i:03d}")
        tool_hint = f" [tool: {q.get('tool_name')}]" if q.get("tool_expected") else ""
        logger.info("[%d/%d] %s%s — %s", i, len(questions), q_id, tool_hint, q["question"][:55])

        http_status, body, latency_ms, error = call_chat_api(
            args.api_url, q["question"], timeout=args.timeout
        )

        if error:
            logger.warning("  → %s", error)
        else:
            logger.info("  → HTTP %d  %s ms", http_status, latency_ms)

        rec = build_record(
            run_id=run_id,
            q=q,
            http_status=http_status,
            body=body,
            latency_ms=latency_ms,
            error=error,
        )
        records.append(rec)
        logger.info(
            "  → %s  correct=%s  tool_correct=%s  hallucination=%s",
            rec["pass_fail"],
            rec["correct"],
            rec["tool_call_correct"],
            rec["hallucination_detected"],
        )

    # ── Write outputs ────────────────────────────────────────────────────────
    print_console_summary(records)

    if not args.no_write:
        write_json(records, eval_meta, _JSON_OUT)
        write_csv(records, _CSV_OUT)
        write_summary_md(records, eval_meta, _MD_OUT)
        logger.info("All output files written to evaluation/results/")
    else:
        logger.info("--no-write set: skipping file output.")


if __name__ == "__main__":
    main()
