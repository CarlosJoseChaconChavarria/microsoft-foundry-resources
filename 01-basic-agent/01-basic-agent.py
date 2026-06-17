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

AI-300 skills covered
---------------------
• Create and configure Foundry resources and project environments (GenAIOps)
• Configure identity and access management — keyless auth via AzureCliCredential
  is the local equivalent of a managed identity (same pattern the exam tests).
• Deploy foundation models via serverless API endpoints (gpt-4o through Foundry).
"""

# ── Standard library ─────────────────────────────────────────────────────────
import asyncio          # Agent Framework is async-first; asyncio.run() launches the loop.
import os               # Read FOUNDRY_* variables that load_dotenv injects into the env.
import sys              # sys.stdout.write for the spinner (avoids print's newline).
from pathlib import Path  # Build a path to .env relative to *this file*, not the cwd.

# ── Third-party ──────────────────────────────────────────────────────────────
from dotenv import load_dotenv  # Reads key=value pairs from .env into os.environ.
                                # The framework does NOT auto-load .env, so we do it here.

# ── Building block 1 of 4 — CREDENTIAL ───────────────────────────────────────
# AzureCliCredential mints Entra ID tokens from your `az login` session.
# No API keys or connection strings ever touch the source code.
# In production this swaps to DefaultAzureCredential / ManagedIdentityCredential
# without changing any other line — same interface, different token source.
# AI-300: this is the dev-time proxy for a system-assigned managed identity.
from azure.identity import AzureCliCredential

# ── Building block 3 of 4 — AGENT ────────────────────────────────────────────
# Agent is the provider-agnostic abstraction: instructions + tools + client.
# It does NOT know about Foundry specifically; any ChatClient implementation works.
from agent_framework import Agent

# ── Building block 2 of 4 — CLIENT ───────────────────────────────────────────
# FoundryChatClient is the HTTP transport layer for Microsoft Foundry.
# It translates Agent.run() calls into HTTPS requests against your project endpoint.
# AI-300: the endpoint format is
#   https://<account>.services.ai.azure.com/api/projects/<project>
# This maps to a Microsoft.CognitiveServices/accounts/projects ARM resource.
from agent_framework_foundry import FoundryChatClient

# Load .env from this file's folder so both `python 01-basic-agent.py` and
# VS Code's ▶ Run button pick up the same configuration regardless of cwd.
load_dotenv(Path(__file__).resolve().parent / ".env")

# ── Configuration ─────────────────────────────────────────────────────────────
ENDPOINT = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")
MODEL_DEPLOYMENT_NAME = os.environ.get("FOUNDRY_MODEL", "gpt-4o")

# Fail fast with a clear message rather than a confusing 404 from the API.
if not ENDPOINT or "<YOUR_" in ENDPOINT:
    raise RuntimeError(
        "FOUNDRY_PROJECT_ENDPOINT is not configured. "
        "Copy .env.example to .env in this folder and fill in your Foundry "
        "project endpoint. See README.md → Prerequisites."
    )

async def _thinking_spinner(stop: asyncio.Event) -> None:
    """Animate a spinner until stop is set, then erase it.

    Runs as a background task while waiting for the model's first token.
    The perceived wait feels shorter because something is visibly happening.
    """
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    i = 0
    while not stop.is_set():
        sys.stdout.write(f"\r  {frames[i % len(frames)]} thinking...")
        sys.stdout.flush()
        i += 1
        await asyncio.sleep(0.1)
    sys.stdout.write("\r" + " " * 20 + "\r")   # erase the spinner line
    sys.stdout.flush()


AGENT_NAME = "ai-agent"
AGENT_INSTRUCTIONS = "You are a helpful AI assistant."  # System prompt — what the model always sees.

# Add more strings to send multiple turns in the same session (shares memory).
USER_INPUTS = [
    "Can you tell me the gravity of Earth versus the gravity of Mars?",
    "And what about the Moon?",
]


async def main() -> None:
    # ── Assemble the four building blocks ────────────────────────────────────
    #
    #   CREDENTIAL → CLIENT → AGENT → SESSION
    #
    # These four objects appear in every Foundry agent, no matter how complex.

    # Building block 2 — CLIENT
    # Owns the HTTPS connection to your Foundry project.
    # We pass ENDPOINT and MODEL explicitly so the fail-fast check above runs first.
    client = FoundryChatClient(
        project_endpoint=ENDPOINT,          # Where: services.ai.azure.com/api/projects/...
        model=MODEL_DEPLOYMENT_NAME,        # Which deployment: "gpt-4o"
        credential=AzureCliCredential(),    # Building block 1 — CREDENTIAL (token source)
    )

    # Building block 3 — AGENT
    # Wraps the client with a system prompt and (optionally) tools.
    # No tools here → pure conversation. Tools are added in labs 02 and 03.
    agent = Agent(
        client=client,
        name=AGENT_NAME,
        instructions=AGENT_INSTRUCTIONS,
    )

    # Building block 4 — SESSION
    # Holds the conversation history (all messages so far).
    # Create it OUTSIDE the loop so every prompt shares the same memory.
    # Move it INSIDE the loop to make each turn stateless (model forgets prior turns).
    session = agent.create_session()

    for user_input in USER_INPUTS:
        print(f"\n# User: '{user_input}'")

        # Show a spinner while waiting for the model's first token, then erase it.
        # asyncio.Event lets the spinner task know the moment a chunk arrives.
        stop_spinner = asyncio.Event()
        spinner = asyncio.create_task(_thinking_spinner(stop_spinner))

        first_chunk = True
        async for chunk in agent.run(user_input, session=session, stream=True):
            if chunk.text:
                if first_chunk:
                    stop_spinner.set()      # signal the spinner to stop
                    await spinner           # wait for it to erase itself
                    first_chunk = False
                print(chunk.text, end="", flush=True)

        if first_chunk:                     # model returned nothing — still stop spinner
            stop_spinner.set()
            await spinner
        print("")

    print("\n--- All tasks completed successfully ---")


if __name__ == "__main__":
    try:
        # asyncio.run() creates a fresh event loop, runs main(), then closes it.
        # Prefer this over the deprecated loop = asyncio.get_event_loop() pattern.
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Program finished.")
