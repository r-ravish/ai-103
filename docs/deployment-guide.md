# Comprehensive AI-103 Production Deployment Guide

This document provides an in-depth, technical breakdown of how the AI-103 Enterprise Knowledge Agent was deployed to Microsoft Azure. This guide is designed to explain *why* certain architectural choices were made and *how* the different components interact in a production environment.

---

## 1. Cloud Architecture Overview

The production architecture is completely serverless and utilizes Platform-as-a-Service (PaaS) offerings from Azure to ensure scalability, security, and minimal maintenance.

The architecture consists of four major cloud components:
1. **Frontend**: Next.js application hosted on **Azure Static Web Apps**.
2. **Backend**: FastAPI application hosted on **Azure Container Apps**.
3. **MCP Server**: FastMCP application hosted on a separate **Azure Container App**.
4. **Database**: **Azure Database for PostgreSQL Flexible Server**.
5. **AI Services**: **Azure AI Foundry** (for Agent routing, LLM processing) and **Azure AI Search** (for Vector Retrieval/RAG).

---

## 2. Database Provisioning & Seeding

**Service Used**: Azure Database for PostgreSQL Flexible Server

### Why PostgreSQL Flexible Server?
Unlike local SQLite, a cloud-hosted PostgreSQL database ensures that data is persistent, backed up, and scalable. It allows multiple container instances of the backend to connect simultaneously without database locking issues.

### Deployment Steps:
1. We provisioned a Postgres Flexible Server named `ai103-postgres`.
2. We configured firewall rules to allow Azure internal services (like Container Apps) to connect securely.
3. The connection string was formatted for both Async (`postgresql+asyncpg://...`) and Sync (`postgresql+psycopg2://...`) operations and passed to the backend as environment variables.
4. **Data Seeding**: Because the database was brand new, we securely executed a Python script directly inside the production backend container (`az containerapp exec`) to seed the initial `admin@company.com` and `employee@company.com` accounts into the `users` table.

---

## 3. Backend Deployment (FastAPI)

**Service Used**: Azure Container Apps (`ai103-backend`)

### Why Azure Container Apps?
Container Apps is a serverless container service built on top of Kubernetes. It allows us to run Python/FastAPI Docker containers without managing the underlying VMs or Kubernetes clusters. It automatically scales up based on HTTP traffic and scales down to zero when not in use.

### The Cross-Tenant Authorization Challenge
During deployment, we faced an issue where the backend was hosted in one Azure Tenant (e.g., Chitkara University), but the **Azure AI Foundry** workspace (which hosts the AI Agents) was in another tenant.

**The Solution:**
Instead of using standard Managed Identities (which cannot easily cross tenant boundaries), we created an **Azure Service Principal** (App Registration) in the Foundry tenant. We then securely injected its credentials into our Backend container using environment variables:
- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_CLIENT_SECRET`
This allows the FastAPI backend to programmatically authenticate as the Service Principal and interact with the AI Foundry project in the foreign tenant.

### Deployment Command:
We used the Azure CLI's "up" command, which builds the Dockerfile (`Dockerfile.backend`) in the cloud and deploys the container in one step:
```bash
az containerapp up \
  --name ai103-backend \
  --resource-group ai103-production \
  --source . \
  --env-vars "DATABASE_URL=..." "AZURE_CLIENT_ID=..." # (plus 15+ other variables)
```

---

## 4. MCP Server Deployment (Model Context Protocol)

**Service Used**: Azure Container Apps (`ai103-mcp`)

### Why a Separate Container for MCP?
The Model Context Protocol (MCP) server provides tools (like creating support tickets) to the AI Agent. We separated the MCP server from the main backend for two reasons:
1. **Security**: The AI Agent needs public network access to call the MCP tools. By isolating the MCP server, we only expose the specific tool endpoints (like `create_support_ticket`) to the AI, without exposing the rest of our backend API to the AI Foundry agent directly.
2. **Scalability**: If tool execution becomes resource-heavy, the MCP container can scale independently of the main API backend.

### Connecting the AI to the MCP Server
After deploying the MCP server via `Dockerfile.mcp`, we obtained its public HTTPS URL (e.g., `https://ai103-mcp...azurecontainerapps.io/sse`). 

We then updated the main Backend's configuration (via the `MCP_PUBLIC_HOST` environment variable). Now, when a user asks the AI a question, the Backend tells the Azure AI Foundry Agent: *"If you need to create a ticket, call this live MCP server URL."*

---

## 5. Frontend Deployment (Next.js)

**Service Used**: Azure Static Web Apps (`ai103-frontend`)

### Why Azure Static Web Apps?
Our frontend is a Next.js application that uses hybrid rendering (both static pages and server-side logic). Azure Static Web Apps natively understands Next.js, automatically building and hosting the static assets globally on a CDN while deploying the server-side API routes to managed Azure Functions.

### Continuous Deployment (CI/CD) with GitHub Actions
Unlike the backend (which we deployed manually), the frontend is configured with a fully automated CI/CD pipeline.

**How it works:**
1. We created a workflow file at `.github/workflows/deploy-frontend.yml`.
2. We stored the deployment token in GitHub Secrets (`AZURE_STATIC_WEB_APPS_API_TOKEN`) to securely authorize GitHub to push to Azure.
3. We stored the `BACKEND_URL` in GitHub variables. During the build phase, this URL is baked into the Next.js frontend so it knows where to send API requests.
4. **The Pipeline**: Whenever a developer pushes code to the `main` branch, GitHub Actions provisions an Ubuntu runner, checks out the code, installs Node.js, builds the Next.js application (using the Microsoft Oryx build system), and pushes the compiled artifacts to Azure.

---

## 6. Available API Endpoints

The backend (`ai103-backend`) exposes the following REST API endpoints:

### Core & Chat
- `GET /health`: Liveness probe (returns 200 OK and content safety status).
- `POST /chat`: The primary endpoint where the Next.js frontend sends employee questions to the Azure AI Foundry agent. Handles LLM RAG, citations, and conversation state.

### Authentication (`/api/auth`)
- `POST /api/auth/login`: Accepts credentials and returns a JWT access token.
- `POST /api/auth/logout`: Invalidates the current session.
- `GET /api/auth/me`: Returns the currently authenticated user's profile and role.

### Support Tickets (`/api/tickets` & `/api/admin/tickets`)
- `GET /api/tickets`: Lists tickets created by the authenticated employee.
- `GET /api/admin/tickets`: (Admin only) Lists all tickets across the enterprise.
- `PATCH /api/admin/tickets/{ticket_id}`: (Admin only) Resolves or updates a ticket.
- *(Note: Tickets are generally created automatically via the MCP Server during a `/chat` escalation, but a `POST` endpoint also exists).*

### Conversations & Feedback (`/api/conversations` & `/api/feedback`)
- `GET /api/conversations`: Lists previous chat sessions for the user.
- `GET /api/conversations/{conversation_id}`: Retrieves the full message history of a specific chat.
- `POST /api/feedback`: Submits user feedback (thumbs up/down) on a specific agent response.

### Bot Channels (`/api/bot`)
- `POST /api/bot/api/messages`: Endpoint for Microsoft Bot Framework integrations (e.g., MS Teams).

---

## 7. Summary of Future Updates

If asked how to update the system in the future:
- **Updating the UI**: Simply push code to the `main` branch on GitHub. The GitHub Action will automatically build and deploy the new frontend in about 3 minutes.
- **Updating the Backend API or Database Schema**: A developer must run `az containerapp up` from the CLI, passing the updated source code. If database changes are made, Alembic migrations must be run against the production database.
- **Updating AI Tools**: Modify the tools in `mcp_server.py`, then deploy specifically to the `ai103-mcp` container app.
