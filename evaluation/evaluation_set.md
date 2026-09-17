# Evaluation Set — AI-103 Enterprise Knowledge Agent

> **Version**: 1.0.0 · **Author**: Aditya · **Date**: 2025-09-17

## Overview

This evaluation set contains **15 questions** designed to test the Enterprise Knowledge Agent's retrieval accuracy, reasoning quality, and knowledge-gap detection against the pilot corpus of 5 policy documents (19 indexed chunks).

The machine-readable version of this evaluation set is available in [`evaluation_set.json`](evaluation_set.json).

### Category Breakdown

| Category | Count |
|---|---|
| Answerable (direct retrieval) | 7 |
| Edge Case (boundary / conditional reasoning) | 4 |
| Out-of-Scope / Knowledge Gap | 4 |
| **Total** | **15** |

### Pilot Corpus Documents

| Document | ID | Tags |
|---|---|---|
| Employee Leave Policy | `DOC-LEAVE-001` | `employee` |
| Employee Expense Reimbursement Policy | `DOC-REIMB-001` | `employee` |
| Work From Home Policy | `DOC-WFH-001` | `employee` |
| Information Technology Security Policy | `DOC-SEC-001` | `it` |
| Employee Benefits Guide | `DOC-BENEFITS-001` | `employee` |

---

## Answerable Questions

These questions have clear, verifiable answers present in the pilot corpus.

### EVAL-001 — Annual Leave Entitlement

| Field | Value |
|---|---|
| **Question** | How many days of paid annual leave do employees get per year? |
| **Category** | Leave |
| **Expected Answer** | Employees are entitled to 18 days of paid annual leave per calendar year. |
| **Source** | `leave-policy.md` — main body |
| **Expected Behavior** | Direct answer citing leave policy with high confidence. |

### EVAL-002 — Leave Request Advance Notice

| Field | Value |
|---|---|
| **Question** | How far in advance should I submit a leave request? |
| **Category** | Leave |
| **Expected Answer** | At least 3 working days before the intended start date. |
| **Source** | `leave-policy.md` — main body |
| **Expected Behavior** | Retrieve the 3-working-day rule and cite leave-policy.md. |

### EVAL-003 — Public Holidays vs Annual Leave

| Field | Value |
|---|---|
| **Question** | Do public holidays count against my annual leave balance? |
| **Category** | Leave |
| **Expected Answer** | No. Company holidays are separate from annual leave and do not reduce the balance. |
| **Source** | `leave-policy.md` — Public Holidays |
| **Expected Behavior** | Clear "no" with explanation, citing the Public Holidays section. |

### EVAL-004 — Reimbursement Submission Deadline

| Field | Value |
|---|---|
| **Question** | What is the deadline for submitting a reimbursement request? |
| **Category** | Reimbursement |
| **Expected Answer** | Within 30 days of the expense date. |
| **Source** | `reimbursement-policy.md` — main body |
| **Expected Behavior** | Return the 30-day deadline and cite the reimbursement policy. |

### EVAL-006 — WFH Days Per Week

| Field | Value |
|---|---|
| **Question** | How many days per week can I work from home? |
| **Category** | Work From Home |
| **Expected Answer** | Up to 3 days per week, subject to team requirements and manager approval. |
| **Source** | `work-from-home-policy.md` — main body |
| **Expected Behavior** | Return the 3-day limit and cite work-from-home-policy.md. |

### EVAL-008 — Password Length Requirement

| Field | Value |
|---|---|
| **Question** | What is the minimum password length required by company policy? |
| **Category** | IT Security |
| **Expected Answer** | At least 12 characters. |
| **Source** | `it-security-policy.md` — main body |
| **Expected Behavior** | Return the 12-character requirement and cite the IT security policy. |

### EVAL-009 — Lost Company Device

| Field | Value |
|---|---|
| **Question** | What should I do if I lose my company laptop? |
| **Category** | IT Security |
| **Expected Answer** | Report it to the IT security team as soon as possible. |
| **Source** | `it-security-policy.md` — Security Incidents |
| **Expected Behavior** | Advise reporting to IT security immediately, cite Security Incidents section. |

---

## Edge Case Questions

These questions require the agent to reason beyond simple retrieval — interpreting thresholds, conditional clauses, and ambiguous policy language.

### EVAL-005 — Below Receipt Threshold

| Field | Value |
|---|---|
| **Question** | Do I need a receipt for a business expense of INR 500? |
| **Category** | Reimbursement |
| **Expected Answer** | The policy requires receipts for expenses above INR 1,000. INR 500 is below that threshold, so a receipt is not explicitly required. |
| **Source** | `reimbursement-policy.md` — Required Documentation |
| **Expected Behavior** | Retrieve the INR 1,000 threshold, apply it correctly, and note receipt is not strictly required. Must NOT hallucinate additional rules. |
| **Why Edge Case** | Requires boundary-condition reasoning, not just quoting. |

### EVAL-007 — Custom Working Hours While Remote

| Field | Value |
|---|---|
| **Question** | Can I set my own working hours while working remotely? |
| **Category** | Work From Home |
| **Expected Answer** | No by default — normal schedule must be maintained — but an alternative may be approved by a manager. |
| **Source** | `work-from-home-policy.md` — Working Hours |
| **Expected Behavior** | Convey the default "no" with the manager-approval exception. Must not give a flat yes or no. |
| **Why Edge Case** | Conditional answer with nuance; tests the agent's ability to handle caveats. |

### EVAL-010 — Adding Spouse to Health Insurance

| Field | Value |
|---|---|
| **Question** | Can I add my spouse to the company health insurance plan? |
| **Category** | Employee Benefits |
| **Expected Answer** | The policy mentions eligible dependents can be added during enrollment periods. It does not define who specifically qualifies — employees should check with HR. |
| **Source** | `employee-benefits.md` — Health Insurance |
| **Expected Behavior** | Cite the dependent enrollment rule but acknowledge the policy does not explicitly define "spouse" as eligible. Recommend consulting HR. |
| **Why Edge Case** | Vague policy language ("eligible dependents"); tests whether the agent avoids over-interpreting. |

### EVAL-014 — Sick Leave Medical Certificate Boundary

| Field | Value |
|---|---|
| **Question** | If I take 3 days of sick leave, do I need to provide a medical certificate? |
| **Category** | Leave |
| **Expected Answer** | The policy requires medical documentation for absences "longer than three consecutive working days" — meaning 4+ days. Exactly 3 days does not trigger the requirement. |
| **Source** | `leave-policy.md` — Sick Leave |
| **Expected Behavior** | Correctly interpret "longer than three" as 4+, note that exactly 3 does not meet the threshold. Cite leave-policy.md. |
| **Why Edge Case** | Boundary-condition test on precise wording ("longer than" vs "at least"). |

---

## Out-of-Scope / Knowledge-Gap Questions

These questions test the agent's ability to recognize when it lacks sufficient evidence and respond honestly rather than hallucinating.

### EVAL-011 — VPN Requirement (Knowledge Gap)

| Field | Value |
|---|---|
| **Question** | Does the company require employees to use a VPN when working remotely? |
| **Category** | VPN / Knowledge Gap |
| **Expected Answer** | *(No answer available in corpus)* |
| **Source** | None — no VPN-specific content exists in the pilot corpus |
| **Expected Behavior** | Clearly state insufficient information. Must NOT fabricate a VPN policy. |
| **Why Knowledge Gap** | Canonical gap case from the ingestion contract's pilot validation (Day 1 retrieval test). |

### EVAL-012 — Maternity / Paternity Leave

| Field | Value |
|---|---|
| **Question** | What is the company's policy on maternity or paternity leave? |
| **Category** | Leave / Knowledge Gap |
| **Expected Answer** | *(No answer available in corpus)* |
| **Source** | None — leave policy covers only annual, sick, and public holidays |
| **Expected Behavior** | Indicate that parental leave is not covered. May cite the general leave policy as partially related, but must clearly state the gap. |
| **Why Knowledge Gap** | Tests within-domain gap detection: the agent has leave knowledge but not for this subtopic. |

### EVAL-013 — Company Revenue

| Field | Value |
|---|---|
| **Question** | What is the company's annual revenue? |
| **Category** | General / Knowledge Gap |
| **Expected Answer** | *(No answer available in corpus)* |
| **Source** | None — entirely outside the HR/policy domain |
| **Expected Behavior** | Clearly state financial information is not in the knowledge base. Must NOT speculate. |
| **Why Knowledge Gap** | Completely off-domain. Tests broad out-of-scope detection. |

### EVAL-015 — Certification Course Reimbursement (Partial Gap)

| Field | Value |
|---|---|
| **Question** | Can the company reimburse me for a professional certification course? |
| **Category** | Employee Benefits / Partial Gap |
| **Expected Answer** | The Benefits Guide mentions reimbursement for approved certifications exists, but specific amounts, eligible certifications, and detailed procedures are not covered. |
| **Source** | `employee-benefits.md` — Learning and Development (partial) |
| **Expected Behavior** | Cite Learning & Development section but note the answer is high-level only — specific details are missing from the corpus. |
| **Why Knowledge Gap** | Partial knowledge scenario: the corpus confirms the benefit exists but lacks actionable detail. |

---

## Evaluation Criteria

When scoring agent responses against this evaluation set, assess the following dimensions:

| Dimension | Description |
|---|---|
| **Retrieval Accuracy** | Did the agent retrieve the correct source document and section? |
| **Answer Correctness** | Is the factual content of the answer correct relative to the policy? |
| **Citation Quality** | Does the agent provide verifiable citations (document ID, source file, chunk)? |
| **Knowledge-Gap Honesty** | Does the agent clearly state when it lacks information vs. hallucinating? |
| **Reasoning Quality** | For edge cases, does the agent apply correct boundary logic and convey nuance? |
| **Content Safety** | Does the response comply with content safety guidelines (see `content_safety.md`)? |
