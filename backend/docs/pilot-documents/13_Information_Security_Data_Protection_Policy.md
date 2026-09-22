# Information Security & Data Protection Policy — NovaWorks Technologies

## Document Info
- **Document ID:** POL-IT-002
- **Owner:** IT Security / Compliance
- **Last Reviewed:** September 2026
- **Applies to:** All employees, contractors, and systems handling company data

## 1. Password & Authentication Rules
- Minimum 12 characters, combining uppercase, lowercase, numbers, and symbols.
- Multi-Factor Authentication (MFA) is mandatory on all company accounts (email, VPN, HR portal, code repos).
- Passwords must be changed every 180 days, or immediately if a breach is suspected.
- Password reuse across the last 5 passwords is blocked by the system.
- Use of the company-approved password manager is required; passwords must never be stored in plain text files, spreadsheets, or sticky notes.

## 2. Data Classification

| Level | Examples | Handling Requirement |
|---|---|---|
| **Public** | Marketing content, published blog posts | No restriction |
| **Internal** | Internal wikis, org charts, general policies | Company employees only; not for external sharing |
| **Confidential** | Financial reports, HR records, source code | Access on a need-to-know basis; encryption required at rest and in transit |
| **Restricted** | Customer PII, payment data, security credentials | Strict access control, logged access, encryption mandatory, subject to regulatory compliance (GDPR/DPDP Act) |

Every document and dataset should be tagged with its classification level at creation; the knowledge assistant must only surface **Public** and **Internal** content by default, and **Confidential/Restricted** content only to permission-verified users via Entra ID group filtering.

## 3. VPN Access
- **Standard access:** All employees get VPN access provisioned automatically on Day 1, required for accessing internal systems (HR portal, internal wikis, code repos) from outside the office network.
- **VPN Exception Request** (e.g., needing access from a personal device, or a region-restricted access exception): Submit via NovaWorks Desk — IT Module → "VPN Exception Request," including business justification and duration needed. Requires manager approval; Security reviews requests longer than 30 days.
- **Split-tunneling and personal device VPN use** are disabled by default; enabling either requires a documented, time-bound exception approved by IT Security.
- VPN sessions auto-disconnect after 12 hours and require re-authentication.

## 4. Data Handling Rules
- Confidential/Restricted data must not be stored on personal devices, personal cloud storage (personal Google Drive/Dropbox), or emailed to personal accounts.
- Customer data (Restricted) must only be accessed through approved, audited systems — never exported to local spreadsheets for ad-hoc analysis without a documented business case and Security sign-off.
- Data retention: customer data is retained per contractual terms and deleted upon contract termination unless legally required otherwise; internal HR records are retained for 7 years per statutory requirements.

## 5. Incident Reporting
- **Suspected security incident** (phishing click, lost device, suspicious account activity, data exposure): report **immediately** via the "Report Security Incident" option in NovaWorks Desk — IT Module, or email security-incident@novaworks-example.com.
- **Response SLA:** Security acknowledges within 30 minutes for critical incidents (active breach, ransomware), and within 4 hours for lower-severity reports.
- Do not attempt to "fix" a suspected breach yourself (e.g., don't delete logs, don't try to patch it) — preserve evidence and let the Security team investigate.
- All incidents are logged, and significant incidents trigger a post-incident review shared with affected teams.

## 6. Third-Party & Vendor Access
Any vendor requiring access to company systems must go through IT Security review and sign a Data Processing Agreement before access is provisioned; access is time-bound and reviewed quarterly.

## Common Questions
- **"How do I request a VPN exception?"** → Submit a "VPN Exception Request" ticket in NovaWorks Desk — IT Module with business justification; requires manager approval.
- **"What counts as confidential data?"** → See the classification table in Section 2 — financial reports, HR records, and source code are Confidential; customer PII is Restricted.
- **"I think I clicked a phishing link, what do I do?"** → Report immediately via "Report Security Incident" in NovaWorks Desk — do not wait or try to fix it yourself.
- **"How often do I need to change my password?"** → Every 180 days, or immediately if a breach is suspected.

*This is the authoritative source for password rules, data classification, VPN access, and incident reporting. Restricted-data details in specific incidents are never surfaced through the general knowledge assistant.*
