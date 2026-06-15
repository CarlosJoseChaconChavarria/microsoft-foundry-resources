r"""Invoke a portal-defined agent from Microsoft Foundry (Agent Framework v1.6+ GA)

Companion to ``02-mcp-tool-agent.py``.

| Script                  | Where the agent is defined | What's in the code              |
|-------------------------|----------------------------|---------------------------------|
| 02-mcp-tool-agent.py    | this Python file           | instructions + tools + name     |
| 02b-portal-agent.py     | Microsoft Foundry portal   | only the agent name + version   |

This script does NOT build an agent — it loads one you've already configured in
the Foundry portal (https://ai.azure.com) and runs it. Update the agent's
instructions or tools in the portal, re-run the script, and you'll see the new
behavior immediately. No code change needed.

# Run this python script
> python -m venv demos
> source demos/bin/activate     # macOS / Linux
> demos\Scripts\activate        # Windows
> pip install agent-framework agent-framework-foundry azure-monitor-opentelemetry python-dotenv
> az login                      # FoundryAgent uses your Azure CLI credentials
> python 02b-portal-agent.py
"""

import asyncio
import os
from pathlib import Path

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

# Pick one of the agents you can see in the Foundry portal.
# The version number is shown next to each agent in the portal listing.
AGENT_NAME = os.environ.get("PORTAL_AGENT_NAME", "<YOUR_PORTAL_AGENT_NAME>")
AGENT_VERSION = os.environ.get("PORTAL_AGENT_VERSION", "1")

USER_INPUTS = [
    "In one short sentence, tell me what kinds of questions you are designed to answer.",
]


async def main() -> None:
    init_observability("portal-first")
    print(f"Connecting to portal agent: {AGENT_NAME} (version {AGENT_VERSION})\n")

    agent = FoundryAgent(
        project_endpoint=PROJECT_ENDPOINT,
        agent_name=AGENT_NAME,
        agent_version=AGENT_VERSION,
        credential=AzureCliCredential(),
    )

    for user_input in USER_INPUTS:
        print(f"# User: {user_input}\n")
        result = await agent.run(user_input)
        print(f"# {AGENT_NAME}:\n{result}\n")

    print("--- All tasks completed successfully ---")


if __name__ == "__main__":
    asyncio.run(main())
    print("Program finished.")
