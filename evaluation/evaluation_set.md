# Evaluation Set — AI-103 Enterprise Knowledge Agent

> **Version**: 1.1.0 · **Source of truth**: [`evaluation_set.json`](evaluation_set.json)
>
> Human-readable companion to the machine-readable evaluation set. All IDs, questions, and
> expected facts are derived directly from the pilot corpus in `docs/pilot-documents/`.
> **Do not add facts here that are not present in the source policy documents.**

## Overview

This evaluation set contains **15 questions** designed to test the Enterprise Knowledge
Agent's retrieval accuracy, reasoning quality, and knowledge-gap detection against the pilot
corpus of 5 policy documents (19 indexed chunks).

### Category Breakdown

| Category | Count |
|---|---|
| Answerable (direct retrieval) | 8 |
| Edge Case (boundary / conditional reasoning) | 4 |
| Knowledge Gap (topic absent from corpus) | 2 |
| Out-of-Scope (outside the policy domain) | 1 |
| **Total** | **15** |

### Pilot Corpus

| Document | document_id | source_file | permissions_tag |
|---|---|---|---|
| Employee Leave Policy | `DOC-LEAVE-001` | `leave-policy.md` | `employee` |
| Employee Expense Reimbursement Policy | `DOC-REIMB-001` | `reimbursement-policy.md` | `employee` |
| Work From Home Policy | `DOC-WFH-001` | `work-from-home-policy.md` | `employee` |
| Information Technology Security Policy | `DOC-SEC-001` | `it-security-policy.md` | `it` |
| Employee Benefits Guide | `DOC-BENEFITS-001` | `employee-benefits.md` | `employee` |

---

## Answerable Questions

These questions have clear, verifiable answers present in the pilot corpus.

### LEAVE-001 — Annual Leave Entitlement

| Field | Value |
|---|---|
| **Question** | How many days of paid annual leave are employees entitled to per calendar year? |
| **Policy** | Leave |
| **Source** | `leave-policy.md` — main body |
| **Expected Behavior** | Agent returns exact entitlement of 18 days and cites leave-policy.md. |
| **Expected Facts** | "Employees are entitled to 18 days of paid annual leave per calendar year." |

---

### LEAVE-002 — Leave Request Advance Notice

| Field | Value |
|---|---|
| **Question** | How far in advance do I need to submit a leave request? |
| **Policy** | Leave |
| **Source** | `leave-policy.md` — main body |
| **Expected Behavior** | Agent returns the 3-working-day notice requirement, mentions the leave portal, and cites leave-policy.md. |
| **Expected Facts** | "Leave requests should normally be submitted at least 3 working days before the intended start date." · "Requests are submitted through the employee leave portal and require manager approval." |

---

### LEAVE-003 — Public Holidays vs Annual Leave

| Field | Value |
|---|---|
| **Question** | Do public holidays reduce my annual leave balance? |
| **Policy** | Leave |
| **Source** | `leave-policy.md` — Public Holidays |
| **Expected Behavior** | Agent answers "No", citing the Public Holidays section: company holidays are separate and do not reduce the leave balance. |
| **Expected Facts** | "Company holidays are separate from annual leave and do not reduce an employee's annual leave balance." |

---

### REIMB-001 — Reimbursement Submission Deadline

| Field | Value |
|---|---|
| **Question** | What is the deadline for submitting a reimbursement request after incurring an expense? |
| **Policy** | Reimbursement |
| **Source** | `reimbursement-policy.md` — main body |
| **Expected Behavior** | Agent returns the 30-day deadline and cites the expense management system, citing reimbursement-policy.md. |
| **Expected Facts** | "All reimbursement requests must be submitted through the expense management system within 30 days of the expense date." |

---

### REIMB-003 — Expense Claim Approval

| Field | Value |
|---|---|
| **Question** | Who reviews and approves expense claims? |
| **Policy** | Reimbursement |
| **Source** | `reimbursement-policy.md` — Approval |
| **Expected Behavior** | Agent states the employee's manager reviews claims, notes Finance may request additional documentation, and cites the Approval section. |
| **Expected Facts** | "Expense claims are reviewed by the employee's manager." · "Finance may request additional documentation before approving reimbursement." |

---

### WFH-001 — WFH Days Per Week

| Field | Value |
|---|---|
| **Question** | How many days per week am I allowed to work from home? |
| **Policy** | Work From Home |
| **Source** | `work-from-home-policy.md` — main body |
| **Expected Behavior** | Agent returns the 3-day-per-week limit, notes team requirements and manager approval apply, and cites work-from-home-policy.md. |
| **Expected Facts** | "Eligible employees may work from home for up to 3 days per week, subject to team requirements and manager approval." |

---

### WFH-003 — Remote Work Equipment

| Field | Value |
|---|---|
| **Question** | What equipment can the company provide for remote work? |
| **Policy** | Work From Home |
| **Source** | `work-from-home-policy.md` — Equipment |
| **Expected Behavior** | Agent cites the Equipment section, lists laptops/monitors/keyboards/other equipment, and notes employees are responsible for protecting company equipment. |
| **Expected Facts** | "The company may provide approved laptops, monitors, keyboards, and other equipment required for remote work." · "Employees are responsible for protecting company equipment from unauthorized access." |

---

### SEC-001 — Minimum Password Length

| Field | Value |
|---|---|
| **Question** | What is the minimum password length required by company policy? |
| **Policy** | IT Security |
| **Source** | `it-security-policy.md` — main body |
| **Expected Behavior** | Agent returns the 12-character minimum and notes the prohibition on easily guessable content, citing the IT Security policy. |
| **Expected Facts** | "Passwords should contain at least 12 characters." · "Passwords should not contain easily guessable information such as the employee's name, date of birth, or company name." |

---

## Edge Case Questions

These questions require reasoning beyond simple retrieval — interpreting thresholds,
conditional clauses, and ambiguous policy language. The expected facts are grounded in the
corpus; the interpretation is the agent's task.

### LEAVE-004 — Sick Leave Medical Certificate Boundary

| Field | Value |
|---|---|
| **Question** | If I take exactly 3 consecutive days of sick leave, do I need to provide medical documentation? |
| **Policy** | Leave |
| **Source** | `leave-policy.md` — Sick Leave |
| **Expected Behavior** | Agent retrieves the sick leave clause and correctly reads "longer than three consecutive working days" as meaning 4+ days. It must state that exactly 3 days does not trigger the requirement per the policy's literal wording. Agent must not fabricate a documentation requirement for exactly 3 days. |
| **Corpus Fact** | "For absences longer than three consecutive working days, supporting medical documentation may be required." |
| **Reasoning Required** | The phrase "longer than three" means ≥ 4 days. An absence of exactly three days does not satisfy this condition as written. |
| **Why Edge Case** | Boundary-condition test on precise language ("longer than" vs "at least"). |

---

### REIMB-002 — Below Receipt Threshold

| Field | Value |
|---|---|
| **Question** | Do I need a receipt for a business expense of INR 500? |
| **Policy** | Reimbursement |
| **Source** | `reimbursement-policy.md` — Required Documentation |
| **Expected Behavior** | Agent retrieves the INR 1,000 threshold, applies it correctly, and states an itemized receipt is not explicitly required for amounts below INR 1,000. Agent must not hallucinate documentation rules for sub-threshold amounts. |
| **Corpus Fact** | "Employees must provide an itemized receipt for expenses above INR 1,000." |
| **Reasoning Required** | The policy specifies the receipt requirement only for amounts above INR 1,000; amounts at or below that threshold are not explicitly addressed by the receipt rule. |
| **Why Edge Case** | Requires boundary-condition reasoning, not just quoting the rule. |

---

### WFH-002 — Custom Working Hours While Remote

| Field | Value |
|---|---|
| **Question** | Can I set my own working hours while working remotely? |
| **Policy** | Work From Home |
| **Source** | `work-from-home-policy.md` — Working Hours |
| **Expected Behavior** | Agent conveys the default is "no" — normal schedule must be maintained — but notes the manager-approval exception. Must not give a flat yes or flat no without the conditional. |
| **Expected Facts** | "Employees must maintain their normal working schedule while working remotely." · "An alternative schedule may be used only if it has been approved by the employee's manager." |
| **Why Edge Case** | Conditional answer (no by default; yes with approval); tests nuance handling. |

---

### EDGE-001 — Adding Spouse to Health Insurance

| Field | Value |
|---|---|
| **Question** | Can I add my spouse to the company health insurance plan? |
| **Policy** | Employee Benefits |
| **Source** | `employee-benefits.md` — Health Insurance |
| **Expected Behavior** | Agent cites the dependent-enrollment rule from the Health Insurance section but acknowledges the policy does not define which individuals qualify as eligible dependents. Should recommend consulting HR rather than assuming spouse eligibility. Agent must not over-interpret the word "dependent". |
| **Corpus Fact** | "Eligible dependents can be added during the designated enrollment period or following a qualifying life event." |
| **Gap Note** | The policy does not define which individuals qualify as eligible dependents. |
| **Why Edge Case** | Vague policy language; tests whether the agent avoids assuming facts not stated in the corpus. |

---

## Knowledge-Gap Questions

These questions test the agent's ability to recognise when the corpus lacks sufficient
evidence and to respond honestly rather than hallucinating.

> **Key principle from the ingestion contract:**
> _"Retrieval alone must not be treated as proof that sufficient evidence exists to answer a question."_

### VPN-001 — VPN Access Request (Canonical Gap)

| Field | Value |
|---|---|
| **Question** | How do I request VPN access when working remotely? |
| **Policy** | None (no VPN content in corpus) |
| **Expected Source** | None |
| **Expected Behavior** | Agent states the available knowledge base does not contain sufficient information to answer the question. Must NOT invent a VPN procedure, approval process, or technical setup steps. Must NOT cite an unrelated policy document as evidence for VPN requirements. |
| **Why Knowledge Gap** | Canonical gap case explicitly documented in `docs/ingestion-contract.md` (Pilot Validation section). The pilot corpus contains no VPN-specific content. |
| **Hallucination Risk** | Semantic retrieval may surface WFH or IT Security chunks as "related". These are relevant but do **not** constitute sufficient evidence to answer the VPN question. |

---

### LEAVE-005 — Maternity / Paternity Leave

| Field | Value |
|---|---|
| **Question** | What is the company's policy on maternity or paternity leave? |
| **Policy** | None (not covered in the Leave policy) |
| **Expected Source** | None |
| **Expected Behavior** | Agent indicates the pilot knowledge base does not contain parental leave provisions. May note the Leave policy covers annual leave, sick leave, and public holidays — but must clearly state that maternity/paternity leave is absent from the corpus. Must not fabricate entitlements. |
| **Why Knowledge Gap** | The Leave policy (`leave-policy.md`) addresses only annual leave, sick leave, and public holidays. No parental leave content exists in the corpus. |

---

## Out-of-Scope Questions

These questions fall entirely outside the enterprise policy domain.

### OOS-001 — Company Annual Revenue

| Field | Value |
|---|---|
| **Question** | What is the company's annual revenue for the last fiscal year? |
| **Policy** | None (outside policy domain) |
| **Expected Source** | None |
| **Expected Behavior** | Agent states financial or business performance information is not available in the enterprise policy knowledge base. Must not speculate or fabricate an answer. Must not cite any policy document as evidence for financial data. |
| **Why Out-of-Scope** | Completely unrelated to the HR/IT policy corpus. Tests broad out-of-scope detection. |

---

## Evaluation Criteria

When scoring agent responses against this evaluation set, assess:

| Dimension | Description |
|---|---|
| **Retrieval Accuracy** | Did the agent retrieve the correct source document and section? |
| **Answer Correctness** | Is the factual content of the answer correct relative to the policy text? |
| **Citation Quality** | Does the agent provide verifiable citations (document_id, source_file)? |
| **Knowledge-Gap Honesty** | Does the agent clearly state when it lacks information, rather than hallucinating? |
| **Reasoning Quality** | For edge cases, does the agent apply correct boundary logic and convey nuance? |
| **Content Safety** | Does the response comply with content safety guidelines? (See `content_safety.md`) |
