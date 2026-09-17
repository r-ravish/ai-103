# Evaluation

Evaluation module for the AI-103 Enterprise Knowledge Agent.

## Contents

| File | Description |
|---|---|
| [`evaluation_set.json`](evaluation_set.json) | Machine-readable evaluation set (15 questions) — primary source of truth for automated testing |
| [`evaluation_set.md`](evaluation_set.md) | Human-readable companion; derived from the JSON and the pilot policy documents |
| [`content_safety.md`](content_safety.md) | Content safety preparation notes, test scenarios, and Azure AI Content Safety integration guidance |

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
