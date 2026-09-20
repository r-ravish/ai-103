# Evaluation

Evaluation module for the AI-103 Enterprise Knowledge Agent.

## Contents

| File | Description |
|---|---|
| [`evaluation_set.json`](evaluation_set.json) | Machine-readable evaluation set (15 questions) — primary source of truth for automated testing |
| [`evaluation_set.md`](evaluation_set.md) | Human-readable companion; derived from the JSON and the pilot policy documents |
| [`content_safety.md`](content_safety.md) | Content safety preparation notes, test scenarios, and Azure AI Content Safety integration guidance |
| [`run_eval.py`](run_eval.py) | **Day 3 evaluation script skeleton** — sends questions to `POST /chat`, captures answers and citations, writes JSONL results |
| [`results/`](results/) | Run output directory (git-ignored `*.jsonl` files; `.gitkeep` preserves the folder) |

## Question Categories

| Category | Count | Purpose |
|---|---|---|
| Answerable | 8 | Direct retrieval with verifiable corpus-backed answers |
| Edge Case | 4 | Boundary conditions and conditional policy reasoning |
| Knowledge Gap | 2 | Topics absent from the corpus (agent must not hallucinate) |
| Out-of-Scope | 1 | Outside the enterprise policy domain entirely |
| **Total** | **15** | |

## Policy Coverage

| Policy Document | source_file | Eval Questions |
|---|---|---|
| Employee Leave Policy | `leave-policy.md` | LEAVE-001, LEAVE-002, LEAVE-003, LEAVE-004, LEAVE-005 |
| Employee Expense Reimbursement Policy | `reimbursement-policy.md` | REIMB-001, REIMB-002, REIMB-003 |
| Work From Home Policy | `work-from-home-policy.md` | WFH-001, WFH-002, WFH-003 |
| Information Technology Security Policy | `it-security-policy.md` | SEC-001 |
| Employee Benefits Guide | `employee-benefits.md` | EDGE-001 |
| VPN (knowledge gap — no corpus content) | — | VPN-001 |
| Outside domain (out-of-scope) | — | OOS-001 |

## Knowledge-Gap Principle

The ingestion contract (`docs/ingestion-contract.md`) explicitly records:

> _"A VPN-related query was tested as a knowledge-gap case; the closest semantic result was
> returned, but the pilot corpus does not contain a VPN-specific requirement. This demonstrates
> that retrieval alone must not be treated as proof that sufficient evidence exists to answer
> a question."_

`VPN-001` is the canonical test for this behaviour. `LEAVE-005` is the second knowledge-gap
test, covering a within-domain gap (parental leave is not in the corpus).

## Content Safety

Content safety preparation covers 12 test scenarios (CS-001 through CS-012) across:

- Prompt injection resistance (CS-001 – CS-003)
- Sensitive / inappropriate content (CS-004 – CS-006)
- Off-topic scope boundary (CS-007 – CS-009)
- Policy hallucination guardrails (CS-010 – CS-012)

See [`content_safety.md`](content_safety.md) for Azure AI Content Safety integration notes,
configuration guidance, and safe refusal templates.

---

## Running the Evaluation Script

### Prerequisites

- Python 3.10+ (standard library only — no extra packages required)
- Backend server running at `http://localhost:8000` **or** set `CHAT_API_URL`

### Dry-run (no API needed)

Validates the evaluation set loads correctly and lists all questions:

```bash
python evaluation/run_eval.py --dry-run
```

### Full run against local backend

Start the backend first:

```bash
cd backend
uvicorn app.main:app --reload
```

Then in a second terminal:

```bash
python evaluation/run_eval.py
```

### Run against the deployed backend (Day 3+)

```bash
python evaluation/run_eval.py --api-url https://<backend-host>/chat
# or
CHAT_API_URL=https://<backend-host>/chat python evaluation/run_eval.py
```

### Filter by category

```bash
python evaluation/run_eval.py --category answerable
python evaluation/run_eval.py --category edge_case
```

### Output

Results are written to `evaluation/results/run_<YYYYMMDD_HHMMSS>.jsonl`
(one JSON object per line, one line per question).

Each record contains:

| Field | Type | Notes |
|---|---|---|
| `run_id` | `string` | e.g. `run_20260920_160000` |
| `question_id` | `string` | e.g. `LEAVE-001` |
| `category` | `string` | `answerable` / `edge_case` / `knowledge_gap` / `out_of_scope` |
| `question` | `string` | The question sent to the API |
| `expected_facts` | `list[str]` | Ground-truth facts from `evaluation_set.json` |
| `http_status` | `int \| null` | HTTP response code; `null` on network error |
| `latency_ms` | `float` | End-to-end request latency |
| `answer` | `string` | Agent's answer |
| `citations` | `list[dict]` | `document_id`, `title`, `source_file` |
| `error` | `string \| null` | Error description on failure |
| `correctness_score` | `null` | **Placeholder** — filled by grading script (Day 3+) |
| `grounding_score` | `null` | **Placeholder** — filled by grading script (Day 3+) |
| `notes` | `string` | Free-text for manual reviewer |

> **Note:** `correctness_score` and `grounding_score` are `null` in this
> skeleton. They will be populated by a subsequent grading step once the
> live backend is connected on Day 3.
