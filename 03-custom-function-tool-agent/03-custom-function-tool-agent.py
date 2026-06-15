"""Build an agent with a custom Python function tool (sample 03).

Run this script
---------------
> python -m venv .venv
> source .venv/bin/activate            # macOS / Linux
> .venv\\Scripts\\activate              # Windows
> pip install agent-framework agent-framework-foundry python-dotenv
> cp .env.example .env                 # then edit .env and fill in your values
> az login
> python 03-custom-function-tool-agent.py
"""

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Load .env from this file's folder so both `python 03-...py` and VS Code's
# Run button pick up the same configuration.
load_dotenv(Path(__file__).resolve().parent / ".env")

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential

# Microsoft Foundry Agent Configuration (read from .env, see .env.example).
ENDPOINT = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")
MODEL = os.environ.get("FOUNDRY_MODEL", "gpt-4o")

if not ENDPOINT or "<YOUR_" in ENDPOINT:
    raise RuntimeError(
        "FOUNDRY_PROJECT_ENDPOINT is not configured. "
        "Copy .env.example to .env in this folder and fill in your Foundry "
        "project endpoint. See README.md."
    )

AGENT_NAME = "time-agent"
AGENT_INSTRUCTIONS = (
    "You are a helpful assistant that can provide time information in UTC "
    "format. Always call the get_time tool when asked about the current time."
)

USER_INPUTS = [
    "What is the current time in UTC?",
]


def get_time() -> str:
    """Get the current UTC time."""
    current_time = datetime.now(timezone.utc)
    return f"The current UTC time is {current_time.strftime('%Y-%m-%d %H:%M:%S')}."


async def main() -> None:
    client = FoundryChatClient(
        model=MODEL,
        project_endpoint=ENDPOINT,
        credential=AzureCliCredential(),
    )

    async with Agent(
        client=client,
        name=AGENT_NAME,
        instructions=AGENT_INSTRUCTIONS,
        tools=[get_time],
    ) as agent:
        for user_input in USER_INPUTS:
            print(f"\n# User: '{user_input}'")
            print(f"# {AGENT_NAME}: ", end="", flush=True)

            async for chunk in await agent.run(user_input, stream=True):
                for content in chunk.contents:
                    data = content.to_dict()
                    ctype = data.get("type")

                    if ctype == "text" and data.get("text"):
                        print(data["text"], end="", flush=True)
                    elif ctype == "function_call":
                        print(
                            f"\n[tool call] {data.get('name')}"
                            f"({data.get('arguments', '{}')})",
                            flush=True,
                        )
                    elif ctype == "function_result":
                        print(
                            f"[tool result] {data.get('result')}\n# {AGENT_NAME}: ",
                            end="",
                            flush=True,
                        )
            print()

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
