r"""Build an MCP-enabled Agent using Microsoft Agent Framework v1.6+ (GA)

# Run this python script
> python -m venv demos
> source demos/bin/activate     # macOS / Linux
> demos\Scripts\activate        # Windows
> pip install agent-framework agent-framework-foundry azure-monitor-opentelemetry python-dotenv
> az login                      # FoundryChatClient uses your Azure CLI credentials
> python 02-mcp-tool-agent.py
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential

from _observability import init_observability

# Microsoft Foundry project configuration.
# Set FOUNDRY_PROJECT_ENDPOINT in .env (see .env.example).
# Format: https://<resource>.services.ai.azure.com/api/projects/<project-name>
PROJECT_ENDPOINT = os.environ.get(
    "FOUNDRY_PROJECT_ENDPOINT",
    "https://<YOUR_FOUNDRY_RESOURCE>.services.ai.azure.com/api/projects/<YOUR_PROJECT_NAME>",
)
MODEL = os.environ.get("FOUNDRY_MODEL", "gpt-4o")

AGENT_NAME = "mcp-learn-agent-codefirst"
AGENT_INSTRUCTIONS = "You answer questions by searching Microsoft Learn content only."

# User inputs for the conversation
USER_INPUTS = [
    "Please summarize the Azure AI Agent documentation related to MCP tool calling?",
]


async def main() -> None:
    init_observability("pure-code")

    client = FoundryChatClient(
        model=MODEL,
        project_endpoint=PROJECT_ENDPOINT,
        credential=AzureCliCredential(),
    )

    # Microsoft Learn MCP is read-only public docs search, so auto-approving
    # every tool call is safe. For any MCP server with write/destructive
    # tools, use approval_mode="always_require" (or a per-tool dict).
    mcp_tool = client.get_mcp_tool(
        name="MicrosoftLearn",
        url="https://learn.microsoft.com/api/mcp",
        approval_mode="never_require",
    )

    async with Agent(
        client=client,
        name=AGENT_NAME,
        instructions=AGENT_INSTRUCTIONS,
        tools=[mcp_tool],
    ) as agent:
        for user_input in USER_INPUTS:
            print(f"\n# User: '{user_input}'")
            result = await agent.run(user_input)
            print(f"# {AGENT_NAME}: {result}\n")

        print("\n--- All tasks completed successfully ---")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Program finished.")
