import asyncio

from mcp import Client


MCP_URL = "http://127.0.0.1:8001/mcp"


async def main():
    print(f"Connecting to {MCP_URL}...")

    async with Client(MCP_URL) as client:

        print("\nConnected to MCP server.")
        print(f"Server info: {client.server_info}")
        print(f"Protocol: {client.protocol_version}")

        # ---------------------------------------------------------
        # 1. Discover tools
        # ---------------------------------------------------------

        tools_result = await client.list_tools()

        print("\nAvailable tools:")

        for tool in tools_result.tools:
            print(f"  - {tool.name}")
            print(f"    {tool.description}")

        # ---------------------------------------------------------
        # 2. Create a ticket through MCP
        # ---------------------------------------------------------

        print("\nCalling create_support_ticket...")

        result = await client.call_tool(
            "create_support_ticket",
            {
                "title": "MCP Day 3 Test",
                "description": (
                    "Testing MCP to FastAPI ticket creation "
                    "for the AI-103 project."
                ),
                "priority": "medium",
            },
        )

        print("\ncreate_support_ticket result:")

        for item in result.content:
            if hasattr(item, "text"):
                print(item.text)

        # ---------------------------------------------------------
        # 3. Extract ticket ID
        # ---------------------------------------------------------

        ticket_id = None

        for item in result.content:
            if hasattr(item, "text"):
                for line in item.text.splitlines():
                    if line.startswith("ID:"):
                        ticket_id = line.split(":", 1)[1].strip()
                        break

        # ---------------------------------------------------------
        # 4. Get ticket through MCP
        # ---------------------------------------------------------

        if ticket_id:

            print(
                f"\nCalling get_support_ticket "
                f"for {ticket_id}..."
            )

            get_result = await client.call_tool(
                "get_support_ticket",
                {
                    "ticket_id": ticket_id,
                },
            )

            print("\nget_support_ticket result:")

            for item in get_result.content:
                if hasattr(item, "text"):
                    print(item.text)

        else:

            print(
                "\nCould not extract ticket ID "
                "from create_support_ticket result."
            )


if __name__ == "__main__":
    asyncio.run(main())