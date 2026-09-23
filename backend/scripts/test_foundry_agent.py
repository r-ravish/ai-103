"""
backend/scripts/test_foundry_agent.py
--------------------------------------
Smoke-test: verify the Python backend can reach the Microsoft Foundry project,
find the persisted agent, and receive a real response.

Usage (from backend/ with .venv active):
    python scripts/test_foundry_agent.py

Requires in backend/.env:
    FOUNDRY_PROJECT_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>
    FOUNDRY_AGENT_NAME=enterprise-knowledge-agent

Authentication:
    Uses DefaultAzureCredential -- picks up the active `az login` session
    automatically on a developer machine.
"""
from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

# Load .env from the backend directory so the script works whether it is run
# from `backend/` or from the repository root.
_script_dir = os.path.dirname(os.path.abspath(__file__))
_env_path = os.path.join(_script_dir, "..", ".env")
load_dotenv(_env_path)

PROJECT_ENDPOINT: str | None = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
AGENT_NAME: str | None = os.getenv("FOUNDRY_AGENT_NAME")

TEST_QUERY = "What is the work-from-home policy?"


def _check_env() -> bool:
    """Return False and print an error if a required env var is missing."""
    ok = True
    if not PROJECT_ENDPOINT or "<" in PROJECT_ENDPOINT:
        print(
            "ERROR: FOUNDRY_PROJECT_ENDPOINT is missing or still contains a placeholder.\n"
            "       Edit backend/.env and set the real Foundry project URL."
        )
        ok = False
    if not AGENT_NAME:
        print("ERROR: FOUNDRY_AGENT_NAME is missing from .env")
        ok = False
    return ok


def main() -> int:
    if not _check_env():
        return 1

    print("=" * 60)
    print("Foundry agent connectivity test")
    print("=" * 60)
    print(f"  Project endpoint : {PROJECT_ENDPOINT}")
    print(f"  Agent name       : {AGENT_NAME}")
    print(f"  Test query       : {TEST_QUERY!r}")
    print()

    # -- Step 1: Connect to the Foundry project --------------------------------
    print("[1/4] Connecting to Foundry project ...")
    try:
        project = AIProjectClient(
            endpoint=PROJECT_ENDPOINT,
            credential=DefaultAzureCredential(),
            allow_preview=True,  # required for agent_name routing in get_openai_client
        )
    except Exception as exc:
        print(f"      FAILED to create AIProjectClient: {type(exc).__name__}: {exc}")
        return 1
    print("      OK - client created")

    try:
        # -- Step 2: Verify the agent exists and is enabled --------------------
        print(f"\n[2/4] Looking up agent '{AGENT_NAME}' ...")
        try:
            agent_details = project.agents.get(AGENT_NAME)
        except Exception as exc:
            print(f"      FAILED to retrieve agent: {type(exc).__name__}: {exc}")
            return 1

        print(f"      Found  : {agent_details.name}")
        print(f"      State  : {agent_details.state}")

        # surface the latest deployed version identifier for diagnostics
        latest_version = agent_details.versions.latest
        version_id: str = latest_version.version if latest_version else "unknown"
        print(f"      Version: {version_id}")

        state_value = getattr(agent_details.state, "value", str(agent_details.state))

        if str(state_value).lower() != "enabled":
            print(
                f"\n  WARNING: Agent state is '{agent_details.state}'. "
                "It may reject requests."
            )

        # -- Step 3: Get an OpenAI client scoped to the agent endpoint ---------
        print(f"\n[3/4] Acquiring OpenAI client scoped to agent ...")
        try:
            openai_client = project.get_openai_client(agent_name=AGENT_NAME)
        except Exception as exc:
            print(f"      FAILED: {type(exc).__name__}: {exc}")
            return 1
        print(f"      OK - base_url: {openai_client.base_url}")

        # -- Step 4: Send a test query via the Responses API -------------------
        print(f"\n[4/4] Sending query to agent ...")
        print(f"      Query: {TEST_QUERY!r}")
        try:
            response = openai_client.responses.create(
                input=TEST_QUERY,
            )
        except Exception as exc:
            print(f"\n      FAILED to get a response: {type(exc).__name__}: {exc}")
            return 1

        # -- Print results -----------------------------------------------------
        print("\n" + "=" * 60)
        print("AGENT RESPONSE")
        print("=" * 60)
        print(response.output_text)

        print("\n" + "=" * 60)
        print("RESPONSE METADATA")
        print("=" * 60)
        print(f"  Response ID : {response.id}")
        model_attr = getattr(response, "model", None)
        if model_attr:
            print(f"  Model       : {model_attr}")
        usage = getattr(response, "usage", None)
        if usage:
            print(f"  Usage       : {usage}")

        print("\n" + "=" * 60)
        print("RAW RESPONSE (JSON)")
        print("=" * 60)
        try:
            print(json.dumps(response.model_dump(), indent=2, default=str))
        except Exception:
            print(repr(response))

    finally:
        project.close()

    print("\nTest completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
