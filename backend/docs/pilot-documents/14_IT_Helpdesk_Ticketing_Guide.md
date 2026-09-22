# IT Helpdesk / Ticketing Guide — NovaWorks Technologies

## Document Info
- **Document ID:** POL-IT-003
- **Owner:** IT Support
- **Last Reviewed:** September 2026
- **Applies to:** All employees

## 1. How to Raise a Ticket
1. Go to **NovaWorks Desk — IT Module** (also accessible via Slack: `/it-ticket`).
2. Select a category: Hardware, Software/Access, Network/VPN, Security Incident, or Other.
3. Provide a clear title, description, and priority (see Section 2 for priority guidance).
4. Attach screenshots/error messages if applicable — this significantly speeds up resolution.
5. You'll receive a ticket number and automatic status updates by email/Slack.

## 2. Priority Levels & SLAs

| Priority | Definition | Examples | First Response SLA | Resolution SLA |
|---|---|---|---|---|
| P1 – Critical | Full work stoppage, security breach, company-wide outage | Ransomware, VPN down for entire office, production outage | 15 minutes | 4 hours |
| P2 – High | Individual unable to work | Laptop won't boot, cannot log in, VPN not connecting | 1 hour | 1 business day |
| P3 – Medium | Partial impact, workaround exists | Slow laptop, software glitch, printer issue | 4 business hours | 3 business days |
| P4 – Low | Minor request, no urgency | New software request, equipment upgrade request | 1 business day | 5 business days |

Priority is initially set by the requester but may be adjusted by the IT team based on actual impact assessment.

## 3. Escalation Matrix

| Step | Trigger | Escalates To |
|---|---|---|
| 1 | Ticket unresolved past SLA | Automatic escalation to IT Team Lead |
| 2 | Unresolved 24 hours past SLA (P1/P2) | IT Manager |
| 3 | Unresolved 48 hours past SLA, or business-critical impact | Director of IT / CTO's office |
| 4 | Security incidents specifically | Always routes directly to IT Security team regardless of stated priority |

Employees can manually escalate by replying "escalate" on the ticket thread or contacting their IT Business Partner if a P1/P2 SLA is missed.

## 4. Common Troubleshooting FAQs
- **"My VPN won't connect."** → Check you're on a stable internet connection, restart the VPN client, and confirm your password hasn't expired. If it persists, raise a P2 Network/VPN ticket.
- **"I can't log into my email."** → Try a password reset via the self-service portal first (link on the login page). If MFA is the issue, raise a P2 ticket — do not share your password with anyone, including IT staff, to "help" troubleshoot.
- **"My laptop is running slow."** → Restart it, close unused applications, and check available disk space. If unresolved, raise a P3 Hardware ticket.
- **"I need software installed."** → Check the IT-approved software catalog first; if it's listed, self-install. If not listed, raise a P4 Software/Access ticket with business justification.
- **"How do I get a new laptop/monitor?"** → Raise a P4 "Equipment Request" ticket; approval depends on role eligibility and budget cycle.
- **"I locked myself out after too many failed logins."** → Use the self-service unlock via the password manager, or raise a P2 ticket if self-service isn't available.

## 5. What NOT to Do
- Do not share your password with anyone, including IT support — legitimate IT staff will never ask for it.
- Do not bypass a ticket by messaging an individual IT staff member directly for non-emergencies; this breaks SLA tracking and reporting.
- For genuine security incidents, use the "Report Security Incident" flow (see Information Security & Data Protection Policy), not a general ticket, to ensure the correct fast-path response.

## Common Questions
- **"How do I raise an IT ticket?"** → Via NovaWorks Desk — IT Module or Slack `/it-ticket`; see Section 1.
- **"How long will my ticket take?"** → Depends on priority; see the SLA table in Section 2.
- **"My ticket has been open too long, what do I do?"** → Reply "escalate" on the ticket thread, or it auto-escalates per the matrix in Section 3.

*This document should ground ticket process, SLA, and general troubleshooting questions. It pairs naturally with a live "raise a ticket" MCP tool action rather than only being used for retrieval.*
