from __future__ import annotations

import json
import os

import httpx
from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

load_dotenv()

BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
MCP_HOST: str = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT: int = int(os.getenv("MCP_PORT", "8001"))

MCP_PUBLIC_HOST: str = os.getenv("MCP_PUBLIC_HOST", "")
if MCP_PUBLIC_HOST == "*":
    MCP_PUBLIC_HOST = ""
MCP_PUBLIC_ORIGIN: str = f"https://{MCP_PUBLIC_HOST}" if MCP_PUBLIC_HOST else ""

transport_security = TransportSecuritySettings(
    allowed_hosts=[
        *([MCP_PUBLIC_HOST, f"{MCP_PUBLIC_HOST}:*"] if MCP_PUBLIC_HOST else []),
        "ai103-mcp.graysand-0fffbacf.koreacentral.azurecontainerapps.io",
        "undisputed-zitimobile.ngrok-free.dev",
        "undocked-ditzy-mobile.ngrok-free.dev",
        "127.0.0.1",
        "127.0.0.1:*",
        "localhost",
        "localhost:*",
    ],
    allowed_origins=[
        *([MCP_PUBLIC_ORIGIN] if MCP_PUBLIC_ORIGIN else []),
        "http://127.0.0.1:8001",
        "http://localhost:8001",
    ],
)

mcp = MCPServer("enterprise-knowledge-agent")


async def _request(method: str, path: str, **kwargs) -> httpx.Response:
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=60.0) as client:
        return await client.request(method, path, **kwargs)


def _detail(response: httpx.Response) -> str:
    try:
        body = response.json()
        if isinstance(body, dict):
            return body.get("detail") or json.dumps(body)
        return json.dumps(body)
    except Exception:
        return response.text


@mcp.tool()
async def create_support_ticket(title: str, description: str, priority: str = "medium") -> str:
    """Create an internal support ticket when the knowledge base cannot help
    or the user needs a support issue reported. Returns the ticket ID."""
    title = title.strip()
    description = description.strip()
    priority = priority.strip().lower()

    if not title:
        return "Error: title is required."
    if not description:
        return "Error: description is required."
    if priority not in {"low", "medium", "high"}:
        priority = "medium"

    try:
        response = await _request(
            "POST",
            "/internal/tickets",
            json={"title": title, "description": description, "priority": priority},
        )
        response.raise_for_status()
        ticket = response.json()
        return (
            "Ticket created successfully.\n"
            f"ID: {ticket['ticket_id']}\n"
            f"Title: {ticket['title']}\n"
            f"Priority: {ticket['priority']}\n"
            f"Status: {ticket['status']}\n"
            f"Created: {ticket['created_at']}"
        )
    except httpx.HTTPStatusError as exc:
        return f"Backend error {exc.response.status_code}: {_detail(exc.response)}"
    except httpx.RequestError as exc:
        return f"Cannot reach backend at {BACKEND_URL}: {exc}"
    except (KeyError, ValueError) as exc:
        return f"Invalid backend response: {exc}"


@mcp.tool()
async def get_support_ticket(ticket_id: str) -> str:
    """Look up a support ticket by ID, for example TKT-A1B2C3D4."""
    ticket_id = ticket_id.strip()
    if not ticket_id:
        return "Error: ticket_id is required."

    try:
        response = await _request("GET", f"/internal/tickets/{ticket_id}")

        if response.status_code == 404:
            return f"Ticket {ticket_id!r} not found."

        response.raise_for_status()
        data = response.json()
        ticket = data.get("ticket", {}) if isinstance(data, dict) else {}

        if not ticket:
            return f"Ticket {ticket_id!r} was not found."

        admin_resp_str = ""
        admin_resp = ticket.get('admin_response')
        if admin_resp:
            admin_resp_str = f"\nAdmin Response: {admin_resp}"

        return (
            "Ticket found.\n"
            f"ID: {ticket.get('ticket_id')}\n"
            f"Title: {ticket.get('title')}\n"
            f"Description: {ticket.get('description')}\n"
            f"Priority: {ticket.get('priority')}\n"
            f"Status: {ticket.get('status')}"
            f"{admin_resp_str}\n"
            f"Created: {ticket.get('created_at')}"
        )
    except httpx.HTTPStatusError as exc:
        return f"Backend error {exc.response.status_code}: {_detail(exc.response)}"
    except httpx.RequestError as exc:
        return f"Cannot reach backend at {BACKEND_URL}: {exc}"


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host=MCP_HOST,
        port=MCP_PORT,
        streamable_http_path="/mcp",
        transport_security=transport_security,
    )
