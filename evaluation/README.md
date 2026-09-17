# Evaluation

Evaluation module for the AI-103 Enterprise Knowledge Agent.

## Contents

| File | Description |
|---|---|
| [`evaluation_set.json`](evaluation_set.json) | Machine-readable evaluation set (15 questions) — use this for automated testing |
| [`evaluation_set.md`](evaluation_set.md) | Human-readable evaluation set with expected answers, sources, and scoring criteria |
| [`content_safety.md`](content_safety.md) | Content safety configuration, test scenarios (12 cases), and Azure AI integration notes |

## Quick Start

The evaluation set covers 3 question types against the 5 pilot policy documents:

- **Answerable** (7 questions) — direct retrieval with verifiable answers
- **Edge Case** (4 questions) — boundary conditions and conditional reasoning
- **Out-of-Scope / Knowledge Gap** (4 questions) — topics not covered by the corpus

Content safety preparation includes 12 test scenarios across prompt injection, sensitive content, scope boundaries, and hallucination guardrails.

## Policy Coverage

| Policy Document | Eval Questions | Content Safety Scenarios |
|---|---|---|
| Leave Policy | EVAL-001, 002, 003, 012, 014 | CS-012 |
| Reimbursement Policy | EVAL-004, 005 | CS-010 |
| Work From Home Policy | EVAL-006, 007 | — |
| IT Security Policy | EVAL-008, 009 | — |
| Employee Benefits | EVAL-010, 015 | CS-011 |
| VPN (Knowledge Gap) | EVAL-011 | — |
| Cross-cutting Safety | — | CS-001 through CS-009 |
