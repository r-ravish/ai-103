# Enterprise Knowledge Agent

## Problem Statement & Solution Overview
In modern enterprises, employees waste hours searching for HR and IT policies across siloed systems or waiting days for simple IT support requests to be resolved. This fragmented knowledge and slow helpdesk workflow cause massive losses in productivity.

Our solution, the **Enterprise Knowledge Agent**, is an internal HR and IT policy Q&A system powered by Agentic AI. Employees can ask questions in natural language, and the agent retrieves grounded answers with citations directly from the policy knowledge base. When an issue requires human intervention (e.g., a broken laptop), the agent securely interfaces with our backend systems via the Model Context Protocol (MCP) to automatically raise a support ticket.

## Team Members
| Role | Person | Focus Area |
|---|---|---|
| Lead / RAG foundation | Ravish | Backend, Data Ingestion, MCP, Bot Framework |
| Frontend | Radhika | Next.js Employee Chat Interface |
| Evaluation | Aditya | Automated Evaluation and Tracing |
| Dashboard | Disha | Streamlit Metrics Dashboard |
| Onboarding module | Rakshit | Document Ingestion Module, Admin Portal, Database |

---

## Solution Architecture & Data Flow

1. **Document Ingestion**: Administrators upload HR/IT policy documents (PDF/MD) via the Admin Portal. A FastAPI backend chunks the text using `tiktoken` and embeds it using Azure OpenAI (`text-embedding-3-small`). The vectors are securely stored in Azure AI Search.
2. **Employee Query**: Employees interact with the agent via a Next.js Chat UI or directly through Microsoft Teams (via Bot Framework).
3. **Grounded Retrieval (RAG)**: The Azure AI Foundry Agent intercepts the query, retrieves the most relevant policy chunks from Azure AI Search, and synthesises a grounded response with accurate citations.
4. **Taking Action (MCP)**: If the employee requests a support action (e.g., "raise a ticket"), the Agent invokes the MCP tool. The request is securely routed to the FastAPI backend, which creates a ticket in a PostgreSQL database and returns the Ticket ID to the employee.

---

## Technology Stack & AI Services

- **AI & ML Services**: 
  - Azure AI Foundry (Agent Orchestration)
  - Azure OpenAI (`text-embedding-3-small` and `gpt-4o-mini` models)
  - Azure AI Search (Vector Database)
  - Azure AI Content Safety (Input/Output moderation)
- **Backend**: Python, FastAPI, PostgreSQL, SQLAlchemy, Alembic
- **Frontend**: Next.js, React, Tailwind CSS
- **Dashboard**: Python, Streamlit
- **Integrations**: Model Context Protocol (MCP), Microsoft Bot Framework, Microsoft Teams

---

## Setup Instructions

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd ai-103

# 2. Create and activate a Python virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install backend dependencies
pip install -r backend/requirements.txt

# 4. Configure environment variables
cp backend/.env.example backend/.env
# Open backend/.env and fill in all values (see .env.example for instructions)

# 5. Run the backend
cd backend
uvicorn app.main:app --reload

# 6. Run the MCP Server (In a new terminal)
cd backend
python3 mcp_server.py
# Expose using ngrok: ngrok http 8001 (Then update Azure Foundry Agent with the ngrok URL)
```

### Frontend & Dashboard

```bash
# Frontend
cd frontend
npm install
npm run dev   # → http://localhost:3000

# Streamlit Dashboard
cd dashboard
streamlit run app.py # → http://localhost:8501
```

---

## Testing and Results

The evaluation system (`evaluation/run_eval.py`) tests 22 questions across 7 categories to ensure the agent performs accurately and safely:

| Category | Questions | What is evaluated |
|---|---|---|
| answerable | 8 | RAG retrieval quality, fact accuracy, citation correctness |
| edge_case | 4 | Boundary condition reasoning, no hallucination |
| knowledge_gap | 2 | Escalation triggered, no fabricated policy |
| out_of_scope | 1 | Escalation triggered, no speculation |
| tool_action | 2 | `create_support_ticket` called, TKT ID returned |
| no_tool | 2 | Tool NOT called for policy questions |
| escalation | 3 | Out-of-corpus scenarios escalate correctly |

Escalation is verified using structured response fields, not text matching. Results are written to `evaluation/results/day3-results.json` for dashboard consumption. The agent successfully achieves high retrieval quality without hallucinating out-of-scope policies.

### Responsible AI Practices
- **Grounded Retrieval**: The agent does not answer from general knowledge alone.
- **Citation Display**: Structured citation metadata ensures transparency.
- **Content Safety Screening**: Azure AI Content Safety screens all inputs and outputs (severity threshold: Low).
- **Human Oversight**: Out-of-scope queries automatically trigger an MCP tool to escalate to human reviewers.

---

## Known Limitations and Future Improvements

### Known Limitations
- **Pilot corpus only:** Results may not generalise to a full production document set.
- **Heuristic gap detection:** Knowledge gap detection uses marker phrases. Subtle hallucinations that do not trigger these markers may not be detected.
- **English only:** Multilingual behaviour has not been evaluated.
- **Automated-heuristic correctness scoring:** Uses keyword matching, not semantic similarity. Manual review of edge-case results is recommended.

### Future Improvements
- **Semantic Scoring:** Implement LLM-as-a-judge or semantic similarity for automated evaluation scoring.
- **Multilingual Support:** Localise the agent prompts and test on non-English policy documents.
- **External Integrations:** Integrate the MCP tool with enterprise tools like ServiceNow or Jira instead of a local PostgreSQL DB.
- **Confidence Calibration:** Use calibrated probabilities to drive knowledge gap detection instead of heuristic marker phrases.

---

## Acknowledgments

- **Third-Party Libraries**: Built using powerful open-source libraries including [FastAPI](https://fastapi.tiangolo.com/), [Next.js](https://nextjs.org/), [Streamlit](https://streamlit.io/), [SQLAlchemy](https://www.sqlalchemy.org/), and `tiktoken`.
- **Azure SDKs**: Extensively utilises the Azure AI Projects SDK and Azure Identity for secure, role-based access.
- **Datasets**: Uses synthetic HR/IT Policy documents created specifically for this pilot to ensure privacy and safety.
- **Protocols**: Uses the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) to securely expose backend functionality to the agent.
