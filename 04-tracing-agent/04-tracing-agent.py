"""Build an agent wired up with OpenTelemetry tracing (sample 04).

Run this script
---------------
> python -m venv .venv
> source .venv/bin/activate            # macOS / Linux
> .venv\\Scripts\\activate              # Windows
> pip install agent-framework agent-framework-foundry \\
>   azure-monitor-opentelemetry opentelemetry-sdk python-dotenv
> cp .env.example .env                 # then edit .env and fill in your values
> az login
> python 04-tracing-agent.py
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from this file's folder so both `python 04-tracing-agent.py` and
# VS Code's Run button pick up the same configuration.
load_dotenv(Path(__file__).resolve().parent / ".env")

# Microsoft Foundry Agent Configuration (read from .env, see .env.example).
ENDPOINT = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")
MODEL = os.environ.get("FOUNDRY_MODEL", "gpt-4o")
APPINSIGHTS_CONN = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()

if not ENDPOINT or "<YOUR_" in ENDPOINT:
    raise RuntimeError(
        "FOUNDRY_PROJECT_ENDPOINT is not configured. "
        "Copy .env.example to .env in this folder and fill in your Foundry "
        "project endpoint. See README.md."
    )

if not APPINSIGHTS_CONN:
    raise RuntimeError(
        "APPLICATIONINSIGHTS_CONNECTION_STRING is not configured. "
        "This sample is specifically about tracing. Without an App Insights "
        "connection string no telemetry is exported. Get it from the Foundry "
        "portal under your project, Manage, Tracing. See README.md."
    )

# Capture prompt and completion content in OTel spans. False by default for
# privacy reasons. Turn it on for workshops and demos, leave it off for any
# data with regulated PII. Both env vars must be set BEFORE the framework
# imports below so they take effect at instrumentation-setup time.
os.environ["AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED"] = "true"
os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework.observability import enable_instrumentation
from azure.identity import AzureCliCredential
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace

# One-line install of the entire telemetry pipeline.
configure_azure_monitor(connection_string=APPINSIGHTS_CONN)

# Turn on the agent-framework GenAI instrumentation so model, tool, and
# agent-run spans are emitted with the GenAI semantic conventions.
enable_instrumentation(enable_sensitive_data=True)

tracer = trace.get_tracer(__name__)

AGENT_NAME = "ai-agent"
AGENT_INSTRUCTIONS = "You are a helpful AI assistant."

USER_INPUTS = [
    "Can you tell me the gravity of Earth versus the gravity of Mars?",
]


async def main() -> None:
    with tracer.start_as_current_span("example-tracing"):
        client = FoundryChatClient(
            model=MODEL,
            project_endpoint=ENDPOINT,
            credential=AzureCliCredential(),
        )

        async with Agent(
            client=client,
            name=AGENT_NAME,
            instructions=AGENT_INSTRUCTIONS,
        ) as agent:
            for user_input in USER_INPUTS:
                print(f"\n# User: '{user_input}'")
                print(f"# {AGENT_NAME}: ", end="", flush=True)

                async for chunk in await agent.run(user_input, stream=True):
                    for content in chunk.contents:
                        data = content.to_dict()
                        if data.get("type") == "text" and data.get("text"):
                            print(data["text"], end="", flush=True)
                print()

            print("\n--- All tasks completed successfully ---")

    # Give the BatchSpanProcessor a tick to flush before the process exits.
    # In production code, prefer trace.get_tracer_provider().shutdown() in a
    # finally block.
    await asyncio.sleep(2.0)


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
