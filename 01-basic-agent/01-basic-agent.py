"""Build a basic agent using Microsoft Agent Framework (sample 01).

Run this script
---------------
> python -m venv .venv
> source .venv/bin/activate            # macOS / Linux
> .venv\\Scripts\\activate              # Windows
> pip install agent-framework agent-framework-azure-ai python-dotenv --pre
> cp .env.example .env                 # then edit .env and fill in your values
> az login
> python 01-basic-agent.py
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from agent_framework import ChatAgent
from agent_framework_azure_ai import AzureAIAgentClient
from azure.identity.aio import DefaultAzureCredential

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
    async with (
        DefaultAzureCredential() as credential,
        ChatAgent(
            chat_client=AzureAIAgentClient(
                project_endpoint=ENDPOINT,
                model_deployment_name=MODEL_DEPLOYMENT_NAME,
                async_credential=credential,
                agent_name=AGENT_NAME,
                agent_id=None,  # Since no Agent ID is provided, the agent will be automatically created and deleted after getting response
            ),
            instructions=AGENT_INSTRUCTIONS,
            max_tokens=4096,
            tools=None,
        ) as agent
    ):
        # Create a new thread that will be reused
        thread = agent.get_new_thread()

        # Process user messages
        for user_input in USER_INPUTS:
            print(f"\n# User: '{user_input}'")
            async for chunk in agent.run_stream([user_input], thread=thread):
                if chunk.text:
                    print(chunk.text, end="")
                elif (
                    chunk.raw_representation
                    and chunk.raw_representation.raw_representation
                    and hasattr(chunk.raw_representation.raw_representation, "status")
                    and hasattr(chunk.raw_representation.raw_representation, "type")
                    and chunk.raw_representation.raw_representation.status == "completed"
                    and hasattr(chunk.raw_representation.raw_representation, "step_details")
                    and hasattr(chunk.raw_representation.raw_representation.step_details, "tool_calls")
                ):
                    print("")
                    print("Tool calls: ", chunk.raw_representation.raw_representation.step_details.tool_calls)
            print("")
        
        print("\n--- All tasks completed successfully ---")

    # Give additional time for all async cleanup to complete
    await asyncio.sleep(1.0)

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
