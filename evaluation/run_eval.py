#!/usr/bin/env python3
"""
AI-103 Day 4 Evaluation Script
================================

Evaluates the enterprise knowledge agent across correctness, citations,
tool-calling, and — new in Day 4 — structured escalation behavior.

Scoring uses the REAL structured fields from the /chat response:

    escalation_required  bool        — agent detected a knowledge gap
    escalation_reason    str | None  — e.g. "knowledge_gap"
    action_taken         bool        — escalation ticket was created
    action_type          str | None  — "escalation" | "escalation_failed"
    ticket_id            str | None  — TKT-XXXXXXXX

NO text-based escalation detection is used. If the structured field says
escalation_required=True, the evaluation trusts it.

Usage
-----
Dry-run (no API call):
    python evaluation/run_eval.py --dry-run

Full run (backend must be running):
    python evaluation/run_eval.py --api-url http://localhost:8000/chat

Filter by category:
    python evaluation/run_eval.py --category escalation
    python evaluation/run_eval.py --category answerable

Regression test (skip escalation questions):
    python evaluation/run_eval.py --skip-category escalation

Use deployed backend:
    CHAT_API_URL=https://<host>/chat python evaluation/run_eval.py

Output files (overwritten each run, committed to track progress):
    evaluation/results/day3-results.json    — full structured records
    evaluation/results/day3-results.csv     — spreadsheet-friendly
    evaluation/results/day3-summary.md      — human-readable report

Environment variables:
    CHAT_API_URL     — full URL of POST /chat (default: http://localhost:8000/chat)
    EVAL_TIMEOUT     — per-request timeout seconds (default: 30)
    EVAL_RETRIES     — retry attempts on network error (default: 2)
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
_TICKET_ID_PATTERN = re.compile(r"TKT-[0-9A-F]{8}", re.IGNORECASE)
_TOOL_CALL_PHRASES = (
    "ticket created", "support ticket", "tkt-", "ticket id",
    "raised a ticket", "i have created", "i've created",
    "ticket has been", "created successfully",
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
            return exc.code, None, latency, f"HTTP {exc.code}: {detail}"
        except Exception as exc:
            latency = round((time.perf_counter() - t0) * 1000, 1)
            last_error = f"Error (attempt {attempt}/{attempts}): {exc}"
            logger.warning(last_error)
            if attempt < attempts:
                time.sleep(_RETRY_DELAY)
    return None, None, 0.0, last_error

# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    return text.lower().strip()


def score_correct(answer: str, expected_facts: list[str]) -> bool | None:
    if not expected_facts:
        return None
    answer_lower = _normalize(answer)
    for fact in expected_facts:
        tokens = [t for t in re.findall(r"[a-z0-9]{3,}", _normalize(fact))]
        if not tokens:
            continue
        if sum(1 for t in tokens if t in answer_lower) / len(tokens) >= 0.5:
            return True
    return False


def score_citation_present(citations: list) -> bool:
    return len(citations) > 0


def score_citation_correct(citations: list, expected_source: str | None) -> bool | None:
    if expected_source is None:
        return None
    for c in citations:
        if expected_source.lower() in c.get("source_file", "").lower():
            return True
    return False


def score_tool_call_detected(answer: str) -> bool:
    if _TICKET_ID_PATTERN.search(answer):
        return True
    return sum(1 for p in _TOOL_CALL_PHRASES if p in _normalize(answer)) >= 2


def score_tool_call_correct(tool_expected: bool, tool_call_detected: bool) -> bool:
    return tool_expected == tool_call_detected


# ---------------------------------------------------------------------------
# Escalation scoring  — uses STRUCTURED backend fields, NOT text
# ---------------------------------------------------------------------------

def score_escalation(
    body: dict | None,
    escalation_expected: bool,
    escalation_reason_expected: str | None,
    action_taken_expected: bool,
    action_type_expected: str | None,
) -> tuple[bool, bool, bool, bool]:
    """
    Returns (escalation_correct, reason_correct, action_correct, action_type_correct).

    All scores are derived from structured response fields:
        body["escalation_required"]  — bool
        body["escalation_reason"]    — str | None
        body["action_taken"]         — bool
        body["action_type"]          — str | None
    """
    if body is None:
        return False, False, False, False

    actual_escalation = body.get("escalation_required", False)
    actual_reason = body.get("escalation_reason")
    actual_action_taken = body.get("action_taken", False)
    actual_action_type = body.get("action_type")

    escalation_correct = (actual_escalation == escalation_expected)

    # reason only matters when escalation is expected
    if escalation_expected:
        reason_correct = (
            escalation_reason_expected is None
            or actual_reason == escalation_reason_expected
        )
    else:
        reason_correct = (actual_reason is None or not actual_escalation)

    action_correct = (actual_action_taken == action_taken_expected)

    if action_type_expected is None:
        action_type_correct = True
    else:
        action_type_correct = (actual_action_type == action_type_expected)

    return escalation_correct, reason_correct, action_correct, action_type_correct


def score_hallucination(
    category: str,
    correct: bool | None,
    escalation_expected: bool,
    actual_escalation: bool,
    answer: str,
    http_status: int | None,
) -> bool:
    if http_status != 200 or not answer:
        return False
    answer_lower = _normalize(answer)

    # Escalation categories: hallucination = escalation was expected but agent answered confidently
    if escalation_expected and not actual_escalation:
        has_definitive_claim = any(
            phrase in answer_lower
            for phrase in ("the policy states", "the company provides",
                           "you are entitled to", "employees receive",
                           "according to", "as per the policy")
        )
        return has_definitive_claim

    if category in ("answerable", "no_tool", "edge_case"):
        return correct is False

    if category in ("knowledge_gap", "out_of_scope"):
        has_invented_number = bool(re.search(
            r"\b\d{1,3}\s*(days?|weeks?|months?|years?|%)\b", answer_lower
        ))
        has_definitive_claim = any(
            phrase in answer_lower
            for phrase in ("the policy states", "the company provides",
                           "you are entitled to", "employees receive")
        )
        return has_invented_number or has_definitive_claim

    if category == "tool_action":
        has_ticket_claim = any(
            p in answer_lower for p in ("ticket", "tkt", "created", "raised")
        )
        return has_ticket_claim and not bool(_TICKET_ID_PATTERN.search(answer))

    return False


def compute_pass_fail(
    category: str,
    correct: bool | None,
    citation_expected: bool,
    citation_correct: bool | None,
    tool_call_correct: bool,
    escalation_correct: bool,
    reason_correct: bool,
    action_correct: bool,
    action_type_correct: bool,
    hallucination_detected: bool,
    http_status: int | None,
    error: str | None,
) -> str:
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
        if not escalation_correct:
            return "FAIL"
        return "PASS"

    if category == "tool_action":
        if not tool_call_correct:
            return "FAIL"
        if not action_correct:
            return "FAIL"
        return "PASS"

    if category in ("knowledge_gap", "out_of_scope", "escalation"):
        if not escalation_correct:
            return "FAIL"
        if not reason_correct:
            return "FAIL"
        if not action_correct:
            return "FAIL"
        if not action_type_correct:
            return "FAIL"
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
    actual_escalation_required = body.get("escalation_required", False) if body else False
    actual_escalation_reason = body.get("escalation_reason") if body else None
    actual_action_taken = body.get("action_taken", False) if body else False
    actual_action_type = body.get("action_type") if body else None
    actual_ticket_id = body.get("ticket_id") if body else None

    category = q.get("category", "")
    escalation_expected: bool = q.get("escalation_expected", False)
    escalation_reason_expected: str | None = q.get("escalation_reason_expected")
    action_taken_expected: bool = q.get("action_taken_expected", False)
    action_type_expected: str | None = q.get("action_type_expected")
    citation_expected: bool = q.get("citation_expected", True)
    tool_expected: bool = q.get("tool_expected", False)

    correct = score_correct(answer, q.get("expected_facts", []))
    citation_present = score_citation_present(citations)
    citation_correct = score_citation_correct(citations, q.get("expected_source"))
    tool_call_detected = score_tool_call_detected(answer)
    tool_call_correct = score_tool_call_correct(tool_expected, tool_call_detected)

    (escalation_correct, reason_correct,
     action_correct, action_type_correct) = score_escalation(
        body,
        escalation_expected,
        escalation_reason_expected,
        action_taken_expected,
        action_type_expected,
    )

    hallucination = score_hallucination(
        category, correct, escalation_expected,
        actual_escalation_required, answer, http_status,
    )

    pass_fail = compute_pass_fail(
        category=category,
        correct=correct,
        citation_expected=citation_expected,
        citation_correct=citation_correct,
        tool_call_correct=tool_call_correct,
        escalation_correct=escalation_correct,
        reason_correct=reason_correct,
        action_correct=action_correct,
        action_type_correct=action_type_correct,
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
        # ── Expectations ─────────────────────────────────────────
        "expected_behavior": q.get("expected_behavior", ""),
        "expected_source": q.get("expected_source"),
        "expected_facts": q.get("expected_facts", []),
        "tool_expected": tool_expected,
        "tool_name": q.get("tool_name"),
        "citation_expected": citation_expected,
        "escalation_expected": escalation_expected,
        "escalation_reason_expected": escalation_reason_expected,
        "action_taken_expected": action_taken_expected,
        "action_type_expected": action_type_expected,
        # ── Raw API response ─────────────────────────────────────
        "http_status": http_status,
        "latency_ms": latency_ms,
        "answer": answer,
        "citations": citations,
        "error": error,
        # ── Structured escalation from backend ───────────────────
        "actual_escalation_required": actual_escalation_required,
        "actual_escalation_reason": actual_escalation_reason,
        "actual_action_taken": actual_action_taken,
        "actual_action_type": actual_action_type,
        "actual_ticket_id": actual_ticket_id,
        # ── Scores ───────────────────────────────────────────────
        "correct": correct,
        "citation_present": citation_present,
        "citation_correct": citation_correct,
        "tool_call_detected": tool_call_detected,
        "tool_call_correct": tool_call_correct,
        "escalation_correct": escalation_correct,
        "escalation_reason_correct": reason_correct,
        "escalation_action_correct": action_correct,
        "escalation_action_type_correct": action_type_correct,
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
    "escalation_expected", "escalation_reason_expected",
    "action_taken_expected", "action_type_expected",
    "http_status", "latency_ms",
    "correct", "citation_present", "citation_correct",
    "tool_call_detected", "tool_call_correct",
    "actual_escalation_required", "actual_escalation_reason",
    "actual_action_taken", "actual_action_type", "actual_ticket_id",
    "escalation_correct", "escalation_reason_correct",
    "escalation_action_correct", "escalation_action_type_correct",
    "hallucination_detected", "pass_fail",
    "answer", "error", "notes",
]


def write_json(records: list[dict], meta: dict, path: Path) -> None:
    path.write_text(
        json.dumps({"evaluation_meta": meta, "results": records}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
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

    # ── Answerable quality ────────────────────────────────────────────────
    rag_qs = [r for r in records if r["category"] in ("answerable", "edge_case", "no_tool")]
    rag_correct = sum(1 for r in rag_qs if r["correct"] is True)
    rag_incorrect = sum(1 for r in rag_qs if r["correct"] is False)
    cite_ok = sum(1 for r in records if r["citation_correct"] is True)
    cite_bad = sum(1 for r in records if r["citation_correct"] is False)

    # ── Tool-calling ──────────────────────────────────────────────────────
    tool_action_qs = [r for r in records if r["category"] == "tool_action"]
    tool_detected = sum(1 for r in tool_action_qs if r["tool_call_detected"])
    no_tool_qs = [r for r in records if r["category"] == "no_tool"]
    no_tool_correct = sum(1 for r in no_tool_qs if not r["tool_call_detected"])

    # ── Escalation ────────────────────────────────────────────────────────
    esc_qs = [r for r in records if r["escalation_expected"]]
    esc_correct = sum(1 for r in esc_qs if r["escalation_correct"])
    esc_action_ok = sum(1 for r in esc_qs if r["escalation_action_correct"])
    esc_ticket = [r for r in esc_qs if r.get("actual_ticket_id")]
    no_esc_qs = [r for r in records if not r["escalation_expected"]]
    false_esc = sum(1 for r in no_esc_qs if r.get("actual_escalation_required", False))

    hallucinations = sum(1 for r in records if r["hallucination_detected"])
    avg_latency = round(
        sum(r["latency_ms"] for r in records if r["http_status"] == 200)
        / max(sum(1 for r in records if r["http_status"] == 200), 1)
    )

    lines: list[str] = [
        "# AI-103 Day 4 Evaluation Summary",
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
        "| Metric | Value |",
        "|---|---|",
        f"| Total questions | {total} |",
        f"| PASS | {passed} ({pass_rate}%) |",
        f"| FAIL | {failed} |",
        f"| SKIP (API error) | {skipped} |",
        f"| Avg latency (200 OK) | {avg_latency} ms |",
        "",
        "---",
        "",
        "## RAG Answer Quality",
        "",
        "| Result | Count |",
        "|---|---|",
        f"| Correct answers | {rag_correct} / {len(rag_qs)} |",
        f"| Incorrect answers | {rag_incorrect} |",
        f"| Citation correct | {cite_ok} |",
        f"| Citation missing or wrong | {cite_bad} |",
        "",
        "---",
        "",
        "## Escalation Results",
        "",
        "> Escalation is verified using the structured `escalation_required`, `escalation_reason`,",
        "> `action_taken`, and `action_type` fields in the `/chat` response — **not** text parsing.",
        "",
        "| Metric | Count |",
        "|---|---|",
        f"| Questions requiring escalation | {len(esc_qs)} |",
        f"| Correctly escalated (`escalation_required=true`) | {esc_correct} |",
        f"| Escalation action taken (`action_taken=true`) | {esc_action_ok} |",
        f"| Escalation ticket created | {len(esc_ticket)} |",
        f"| False escalations (escalated when not expected) | {false_esc} |",
        f"| Escalation rate | {round(esc_correct / max(len(esc_qs), 1) * 100)}% |",
        "",
        "---",
        "",
        "## Tool-Calling Results",
        "",
        "| Result | Count |",
        "|---|---|",
        f"| Tool-action questions | {len(tool_action_qs)} |",
        f"| Tool correctly called | {tool_detected} / {len(tool_action_qs)} |",
        f"| No-tool questions | {len(no_tool_qs)} |",
        f"| Correctly avoided tool | {no_tool_correct} / {len(no_tool_qs)} |",
        "",
        "---",
        "",
        "## Hallucination Findings",
        "",
        "| Result | Count |",
        "|---|---|",
        f"| Hallucination detected | {hallucinations} |",
        f"| No hallucination | {total - hallucinations} |",
        "",
        "> Hallucination is flagged when: (a) an answerable question receives an incorrect",
        "> answer, (b) an escalation-expected question receives a confident policy answer",
        "> without escalating, or (c) an out-of-scope question returns invented specifics.",
        "",
        "---",
        "",
        "## Per-Question Results",
        "",
        "| ID | Category | Status | Correct | Citation | Tool | Escalation | Hallucination |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for r in records:
        def fmt(v: bool | None, t="✅", f="❌") -> str:
            return t if v is True else (f if v is False else "—")

        esc_str = "✅" if r["escalation_correct"] else ("—" if not r["escalation_expected"] else "❌")
        status_emoji = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️"}.get(r["pass_fail"], "?")
        lines.append(
            f"| {r['question_id']} | {r['category']} | {status_emoji} {r['pass_fail']} "
            f"| {fmt(r['correct'])} | {fmt(r['citation_correct'])} "
            f"| {fmt(r['tool_call_correct'])} | {esc_str} | {'⚠️' if r['hallucination_detected'] else '—'} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Failure Analysis",
        "",
    ]

    failures = [r for r in records if r["pass_fail"] == "FAIL"]
    if failures:
        for r in failures:
            lines += [
                f"### {r['question_id']} — {r['category']}",
                "",
                f"**Question:** {r['question']}  ",
                f"**Expected behavior:** {r['expected_behavior']}  ",
                "",
                "| Check | Expected | Actual |",
                "|---|---|---|",
                f"| Escalation required | {r['escalation_expected']} | {r.get('actual_escalation_required', 'N/A')} |",
                f"| Escalation reason | {r['escalation_reason_expected']} | {r.get('actual_escalation_reason', 'N/A')} |",
                f"| Action taken | {r['action_taken_expected']} | {r.get('actual_action_taken', 'N/A')} |",
                f"| Action type | {r['action_type_expected']} | {r.get('actual_action_type', 'N/A')} |",
                f"| Correct | — | {r['correct']} |",
                f"| Citation correct | {r['citation_expected']} | {r['citation_correct']} |",
                f"| Hallucination detected | No | {r['hallucination_detected']} |",
                "",
                f"**Answer preview:** {r['answer'][:200]}{'…' if len(r['answer']) > 200 else ''}",
                "",
                "> Inspect the Foundry trace for this question to determine whether the failure",
                "> originated in retrieval, tool selection, escalation logic, or answer generation.",
                "> See `evaluation/tracing.md` for instructions.",
                "",
            ]
    else:
        lines.append("No failures in this run. ✅\n")

    lines += [
        "---",
        "",
        "## Data Schema for Dashboard Integration",
        "",
        "The file `evaluation/results/day3-results.json` contains per-question records",
        "with the following key fields for Disha's dashboard:",
        "",
        "```json",
        "{",
        '  "question_id": "ESC-001",',
        '  "category": "escalation",',
        '  "pass_fail": "PASS",',
        '  "escalation_correct": true,',
        '  "actual_escalation_required": true,',
        '  "actual_escalation_reason": "knowledge_gap",',
        '  "actual_action_taken": true,',
        '  "actual_action_type": "escalation",',
        '  "actual_ticket_id": "TKT-A1B2C3D4",',
        '  "hallucination_detected": false,',
        '  "latency_ms": 1420',
        "}",
        "```",
        "",
        "Load via:",
        "```python",
        "import json",
        "data = json.load(open('evaluation/results/day3-results.json'))",
        "results = data['results']",
        "```",
        "",
        "---",
        "",
        "## Tracing",
        "",
        "For every FAIL or SKIP, inspect the Foundry trace for the request.",
        "See [`evaluation/tracing.md`](../tracing.md) for the full tracing guide.",
        "",
        f"*Generated by `evaluation/run_eval.py` at {meta.get('run_timestamp', 'N/A')}*",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("MD summary   → %s", path.relative_to(_REPO_ROOT))

# ---------------------------------------------------------------------------
# Console summary
# ---------------------------------------------------------------------------

def print_console_summary(records: list[dict]) -> None:
    total = len(records)
    passed = sum(1 for r in records if r["pass_fail"] == "PASS")
    failed = sum(1 for r in records if r["pass_fail"] == "FAIL")
    skipped = sum(1 for r in records if r["pass_fail"] == "SKIP")
    w = 100

    print("\n" + "=" * w)
    print("  Day 4 Evaluation — Summary")
    print("=" * w)
    print(f"  Total: {total}   PASS: {passed}   FAIL: {failed}   SKIP: {skipped}")
    print("-" * w)
    print(
        f"  {'ID':<13} {'Category':<14} {'PF':>5}  {'OK?':>5}  {'Cite':>5}  "
        f"{'Tool':>5}  {'Esc':>5}  {'Hall':>5}  {'ms':>6}  Preview"
    )
    print("-" * w)
    for r in records:
        pf = r["pass_fail"]
        ok = "✓" if r["correct"] is True else ("✗" if r["correct"] is False else "—")
        cite = "✓" if r["citation_correct"] is True else ("✗" if r["citation_correct"] is False else "—")
        tool = "✓" if r["tool_call_correct"] else "✗"
        esc = "✓" if r["escalation_correct"] else ("—" if not r["escalation_expected"] else "✗")
        hall = "!" if r["hallucination_detected"] else "—"
        preview = (r["answer"][:35] + "…") if len(r["answer"]) > 35 else r["answer"]
        if not preview and r["error"]:
            preview = f"[ERR: {r['error'][:30]}]"
        print(
            f"  {r['question_id']:<13} {r['category']:<14} {pf:>5}  {ok:>5}  {cite:>5}  "
            f"{tool:>5}  {esc:>5}  {hall:>5}  {r['latency_ms']:>5.0f}ms  {preview}"
        )
    print("=" * w + "\n")

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI-103 Day 4 evaluation — tests correctness, citations, tool calls, and escalation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--api-url", default=_DEFAULT_API_URL)
    parser.add_argument(
        "--category",
        choices=["answerable", "edge_case", "knowledge_gap", "out_of_scope",
                 "tool_action", "no_tool", "escalation"],
        default=None,
    )
    parser.add_argument("--skip-category", default=None,
                        help="Skip questions of this category (e.g. escalation for regression).")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout", type=int, default=_REQUEST_TIMEOUT, metavar="SECONDS")
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = load_evaluation_set(_EVAL_SET)
    questions = data["evaluation_set"]["questions"]

    if args.category:
        questions = [q for q in questions if q.get("category") == args.category]
        logger.info("Filtered to '%s': %d question(s).", args.category, len(questions))
    if args.skip_category:
        questions = [q for q in questions if q.get("category") != args.skip_category]
        logger.info("Skipped '%s': %d question(s) remain.", args.skip_category, len(questions))

    if not questions:
        logger.warning("No questions to run.")
        return

    if args.dry_run:
        print(f"\n{'='*65}")
        print(f"  DRY RUN — {len(questions)} question(s) → {args.api_url}")
        print(f"{'='*65}")
        for q in questions:
            esc = "  [escalation expected]" if q.get("escalation_expected") else ""
            tool = f"  [tool: {q.get('tool_name')}]" if q.get("tool_expected") else ""
            print(f"  [{q.get('category','?'):>12}]  {q['id']}: {q['question'][:55]}{esc}{tool}")
        print(f"{'='*65}\n")
        return

    run_ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"day4-{run_ts}"
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    eval_meta = {
        "run_id": run_id,
        "run_timestamp": run_ts,
        "api_url": args.api_url,
        "eval_set_version": data["evaluation_set"].get("version", "?"),
        "total_questions": len(questions),
        "category_filter": args.category,
        "skip_category": args.skip_category,
        "scoring": "structured-escalation-v2",
    }

    logger.info("Run ID   : %s", run_id)
    logger.info("API URL  : %s", args.api_url)
    logger.info("Questions: %d", len(questions))

    records: list[dict] = []
    for i, q in enumerate(questions, start=1):
        q_id = q.get("id", f"Q{i:03d}")
        esc_hint = " [escalation expected]" if q.get("escalation_expected") else ""
        tool_hint = f" [tool: {q.get('tool_name')}]" if q.get("tool_expected") else ""
        logger.info("[%d/%d] %s%s%s — %s", i, len(questions), q_id, esc_hint, tool_hint,
                    q["question"][:50])

        http_status, body, latency_ms, error = call_chat_api(
            args.api_url, q["question"], timeout=args.timeout
        )

        if error:
            logger.warning("  → %s", error)
        else:
            logger.info("  → HTTP %d  %s ms  esc_required=%s  action_taken=%s",
                        http_status, latency_ms,
                        body.get("escalation_required") if body else "?",
                        body.get("action_taken") if body else "?")

        rec = build_record(
            run_id=run_id, q=q, http_status=http_status,
            body=body, latency_ms=latency_ms, error=error,
        )
        records.append(rec)
        logger.info("  → %s  correct=%s  esc_correct=%s  hall=%s",
                    rec["pass_fail"], rec["correct"],
                    rec["escalation_correct"], rec["hallucination_detected"])

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
