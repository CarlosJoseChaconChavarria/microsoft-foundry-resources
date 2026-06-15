"""Build a basic agent using Microsoft Agent Framework (sample 01).

Run this script
---------------
> python -m venv .venv
> source .venv/bin/activate            # macOS / Linux
> .venv\\Scripts\\activate              # Windows
> pip install agent-framework agent-framework-foundry python-dotenv
> cp .env.example .env                 # then edit .env and fill in your values
> az login
> python 01-basic-agent.py
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from agent_framework import Agent
from agent_framework_foundry import FoundryChatClient
from azure.identity import AzureCliCredential

# Load .env from this file's folder so both `python 01-basic-agent.py` and
# VS Code's ▶ Run button pick up the same configuration.
load_dotenv(Path(__file__).resolve().parent / ".env")

# Microsoft Foundry Agent Configuration (read from .env — see .env.example).
ENDPOINT = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")
MODEL_DEPLOYMENT_NAME = os.environ.get("FOUNDRY_MODEL", "gpt-4o")

if not ENDPOINT or "<YOUR_" in ENDPOINT:
    raise RuntimeError(
        "FOUNDRY_PROJECT_ENDPOINT is not configured. "
        "Copy .env.example to .env in this folder and fill in your Foundry "
        "project endpoint. See README.md → Prerequisites."
    )

AGENT_NAME = "ai-agent"
AGENT_INSTRUCTIONS = "You are a helpful AI assistant."

# User inputs for the conversation
USER_INPUTS = [
    "Can you tell me the gravity of Earth versus the gravity of Mars?",
]


async def main() -> None:
    # The Foundry chat client owns the HTTPS transport to your project.
    # FoundryChatClient also reads FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL
    # from the environment automatically; we pass them explicitly here so the
    # fail-fast check above runs first.
    client = FoundryChatClient(
        project_endpoint=ENDPOINT,
        model=MODEL_DEPLOYMENT_NAME,
        credential=AzureCliCredential(),
    )

    agent = Agent(
        client=client,
        name=AGENT_NAME,
        instructions=AGENT_INSTRUCTIONS,
    )

    # A session carries conversation history across multiple .run() calls so
    # the model can answer follow-ups in context.
    session = agent.create_session()

    for user_input in USER_INPUTS:
        print(f"\n# User: '{user_input}'")
        async for chunk in agent.run(user_input, session=session, stream=True):
            if chunk.text:
                print(chunk.text, end="", flush=True)
        print("")

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
