r"""Hybrid (agent-as-code) pattern for Microsoft Foundry (Agent Framework v1.6+ GA)

Companion to ``02-mcp-tool-agent.py`` (pure code) and ``02b-portal-agent.py`` (portal-first).

| Script                   | Where defined            | Persists in portal | Source of truth      |
|--------------------------|--------------------------|--------------------|----------------------|
| 02-mcp-tool-agent.py     | this Python file         | ❌ no              | the .py file         |
| 02b-portal-agent.py      | Microsoft Foundry portal | ✅ yes             | portal UI            |
| 02c-hybrid-agent.py      | this Python file         | ✅ yes             | the .py file (GitOps)|

The hybrid pattern:
  1. The full agent definition (instructions + tools + model) is declared in
     code so it can be version-controlled, code-reviewed, and deployed via CI.
  2. The first run creates the agent server-side via the Foundry REST API,
     making it visible in the portal — just like clicking "Create Agent" in
     the UI, but reproducibly from code.
  3. Subsequent runs reuse the existing server-side agent. Re-running after
     editing the AGENT_DEFINITION below adds a NEW VERSION (audit trail).
  4. The agent is invoked through ``FoundryAgent`` — same call site as a
     purely portal-defined agent.

Cleanup:
  This script does NOT delete the agent. To remove it after the demo:
      curl -X DELETE -H "Authorization: Bearer $(az account get-access-token \
        --resource https://ai.azure.com --query accessToken -o tsv)" \
        "<PROJECT_ENDPOINT>/agents/<AGENT_NAME>?api-version=2025-11-15-preview"

# Run this python script
> python -m venv demos
> source demos/bin/activate     # macOS / Linux
> demos\Scripts\activate        # Windows
> pip install agent-framework agent-framework-foundry httpx azure-monitor-opentelemetry python-dotenv
> az login
> python 02c-hybrid-agent.py
"""

import asyncio
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from agent_framework.foundry import FoundryAgent
from azure.identity import AzureCliCredential

from _observability import init_observability

# Microsoft Foundry project configuration.
# Set FOUNDRY_PROJECT_ENDPOINT in .env (see .env.example).
PROJECT_ENDPOINT = os.environ.get(
    "FOUNDRY_PROJECT_ENDPOINT",
    "https://<YOUR_FOUNDRY_RESOURCE>.services.ai.azure.com/api/projects/<YOUR_PROJECT_NAME>",
)
API_VERSION = "2025-11-15-preview"

AGENT_NAME = "mcp-learn-agent-hybrid"

# The agent definition lives HERE in code — git is your source of truth.
# Re-running this script after editing creates a new version in the portal.
AGENT_DEFINITION = {
    "kind": "prompt",
    "model": "gpt-4o",
    "instructions": (
        "You are a Microsoft Learn research assistant. "
        "Use the MicrosoftLearn MCP tool to answer questions about Azure and "
        "Microsoft technologies, citing the Microsoft Learn pages you used."
    ),
    "tools": [
        {
            "type": "mcp",
            "server_label": "MicrosoftLearn",
            "server_url": "https://learn.microsoft.com/api/mcp",
            "require_approval": "never",
        }
    ],
}

USER_INPUTS = [
    "Please summarize the Azure AI Agent documentation related to MCP tool calling?",
]


async def ensure_agent(token: str) -> str:
    """Create the agent if missing; otherwise reuse the latest version. Returns version."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    params = {"api-version": API_VERSION}
    base = f"{PROJECT_ENDPOINT}/agents"

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        # Check if it exists.
        get_resp = await client.get(f"{base}/{AGENT_NAME}", params=params)
        if get_resp.status_code == 200:
            version = get_resp.json()["versions"]["latest"]["version"]
            print(f"  ↳ found existing agent in portal, latest version = {version}")
            return version

        # Create it server-side from the in-code definition.
        print(f"  ↳ agent not found, creating from in-code definition...")
        create_resp = await client.post(
            base,
            params=params,
            json={"name": AGENT_NAME, "definition": AGENT_DEFINITION},
        )
        create_resp.raise_for_status()
        version = create_resp.json()["versions"]["latest"]["version"]
        print(f"  ↳ created agent '{AGENT_NAME}' version {version} in portal")
        return version


async def main() -> None:
    init_observability("hybrid")
    print(f"Hybrid pattern: code defines '{AGENT_NAME}', server hosts it.\n")

    credential = AzureCliCredential()
    token = credential.get_token("https://ai.azure.com/.default").token

    agent_version = await ensure_agent(token)
    print()

    agent = FoundryAgent(
        project_endpoint=PROJECT_ENDPOINT,
        agent_name=AGENT_NAME,
        agent_version=agent_version,
        credential=credential,
    )

    for user_input in USER_INPUTS:
        print(f"# User: {user_input}\n")
        result = await agent.run(user_input)
        print(f"# {AGENT_NAME}:\n{result}\n")

    print("--- All tasks completed successfully ---")
    print(f"View this agent in the portal at:\n  https://ai.azure.com  →  Agents  →  {AGENT_NAME}")


if __name__ == "__main__":
    asyncio.run(main())
    print("Program finished.")
