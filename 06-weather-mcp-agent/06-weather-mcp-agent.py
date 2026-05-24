# Foundry agent → Azure Functions MCP server (workshop sample 06).
#
# Setup (one-time):
#   cd 06-weather-mcp-agent
#   cp .env.example .env                # then fill in the required values
#   python -m venv .venv && source .venv/bin/activate
#   pip install agent-framework azure-monitor-opentelemetry python-dotenv --pre
#   az login                            # FoundryChatClient uses your CLI creds
#
# Run:
#   python 06-weather-mcp-agent.py
#
# Auth modes (selected by WEATHER_MCP_AUTH):
#   - "key"   (iteration 1, default if WEATHER_MCP_AUDIENCE is unset):
#             pass the ``mcp_extension`` system key as ``x-functions-key``.
#             Works only while ``host.json`` keeps ``webhookAuthorizationLevel: "System"``
#             AND Easy Auth is OFF on the Function App.
#   - "entra" (iteration 2):
#             mint an Entra v2 token for ``api://<WEATHER_MCP_AUDIENCE>`` using
#             AzureCliCredential and pass it as ``Authorization: Bearer``.
#             Works when Easy Auth is ON and the caller's SP has been granted
#             the ``MCP.Invoke`` app role on the MCP audience. This mirrors the
#             exact flow Foundry's Agent Identity uses in production.

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential
from dotenv import load_dotenv

# Reuse the workshop's shared observability bootstrap (Application Insights
# wiring + GenAI content recording). Lives one directory up.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _observability import init_observability  # noqa: E402

load_dotenv(Path(__file__).resolve().parent / ".env")

PROJECT_ENDPOINT = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
MODEL = os.environ.get("FOUNDRY_MODEL", "gpt-4o")
MCP_ENDPOINT = os.environ["WEATHER_MCP_ENDPOINT"]

# Auth selection: default to "entra" when WEATHER_MCP_AUDIENCE is provided
# (iteration 2 deployment), otherwise fall back to "key" (iteration 1).
_AUDIENCE = os.environ.get("WEATHER_MCP_AUDIENCE", "").strip()
AUTH_MODE = os.environ.get(
    "WEATHER_MCP_AUTH",
    "entra" if _AUDIENCE else "key",
).strip().lower()

AGENT_NAME = "weather-mcp-agent"
AGENT_INSTRUCTIONS = (
    "You are a concise weather assistant. When the user asks about the weather, "
    "ALWAYS call the get_weather tool and base your answer on its result. "
    "If the tool returns an 'error' field, surface that error verbatim. "
    "Report temperature in both °F and °C and include the reported_at_utc timestamp."
)

USER_INPUTS = [
    "What's the current weather in Seattle, WA?",
    "And how about Paris?",
    "Compare the wind in Mumbai and Sydney right now.",
]


def _build_mcp_headers(credential: AzureCliCredential) -> dict[str, str]:
    """Returns the per-request headers for the configured auth mode.

    Entra mode resolves the bearer token in this priority:
      1. ``WEATHER_MCP_TOKEN`` env var (a pre-acquired JWT) — handy when the
         CLI user lacks a delegated OAuth2 scope on the MCP audience. In
         production, Foundry's Agent Identity supplies this token directly.
      2. ``AzureCliCredential.get_token("<audience>/.default")`` — requires
         the user to have been pre-consented to an OAuth2 scope on the MCP
         app reg (advanced; not the default Foundry setup).

    For ``key`` mode, ``WEATHER_MCP_KEY`` is sent as ``x-functions-key``.
    """
    if AUTH_MODE == "entra":
        pre_acquired = os.environ.get("WEATHER_MCP_TOKEN", "").strip()
        if pre_acquired:
            return {"Authorization": f"Bearer {pre_acquired}"}

        if not _AUDIENCE:
            raise RuntimeError(
                "WEATHER_MCP_AUTH=entra requires WEATHER_MCP_AUDIENCE "
                "(e.g. api://<mcp-app-id>) to mint a bearer token, or "
                "WEATHER_MCP_TOKEN to supply one directly."
            )
        scope = _AUDIENCE if _AUDIENCE.endswith("/.default") else f"{_AUDIENCE}/.default"
        token = credential.get_token(scope).token
        return {"Authorization": f"Bearer {token}"}

    # Fallback: iteration 1 function-key auth
    mcp_key = os.environ.get("WEATHER_MCP_KEY")
    if not mcp_key:
        raise RuntimeError(
            "WEATHER_MCP_AUTH=key requires WEATHER_MCP_KEY (the mcp_extension "
            "system key from the Function App)."
        )
    return {"x-functions-key": mcp_key}


async def main() -> None:
    init_observability("weather-mcp")

    credential = AzureCliCredential()

    client = FoundryChatClient(
        model=MODEL,
        project_endpoint=PROJECT_ENDPOINT,
        credential=credential,
    )

    print(f"[auth] WEATHER_MCP_AUTH={AUTH_MODE}", flush=True)
    mcp_headers = _build_mcp_headers(credential)

    # ``approval_mode="never_require"`` is safe here because get_weather is
    # read-only and idempotent. Use ``"always_require"`` (or per-tool dict)
    # for any MCP server with write/destructive tools.
    mcp_tool = client.get_mcp_tool(
        name="weather-mcp-azure-functions",
        url=MCP_ENDPOINT,
        approval_mode="never_require",
        headers=mcp_headers,
        allowed_tools=["get_weather"],
    )

    async with Agent(
        client=client,
        name=AGENT_NAME,
        instructions=AGENT_INSTRUCTIONS,
        tools=[mcp_tool],
    ) as agent:
        for user_input in USER_INPUTS:
            print(f"\n# User: {user_input!r}")
            result = await agent.run(user_input)
            print(f"# {AGENT_NAME}: {result}\n")

        print("\n--- All tasks completed successfully ---")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
    except Exception as exc:  # noqa: BLE001
        import traceback
        print(f"An unexpected error occurred: {exc}")
        traceback.print_exc()
    finally:
        print("Program finished.")
