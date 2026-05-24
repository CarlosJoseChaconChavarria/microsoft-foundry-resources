"""Shared observability setup for the workshop samples (patterns 02 / 02b / 02c).

What this does
--------------
Wires Microsoft Foundry tracing through OpenTelemetry into the project's
Application Insights resource. Spans for agent runs, model calls, and MCP tool
invocations all land in App Insights where you can query them via KQL.

How to enable
-------------
Set ``APPLICATIONINSIGHTS_CONNECTION_STRING`` (e.g. via a ``.env`` file next to
this module). To find the project's connection string:

  Microsoft Foundry portal → your project → Manage → Tracing
  → "Connect a new Application Insights resource" panel shows the value.

If the env var is unset, this module is a silent no-op and your script runs
without observability.

How to read it back (KQL)
-------------------------
Each call to ``init_observability(scenario)`` tags every span emitted by the
process with ``cloud_RoleName = "foundry-workshop.<scenario>"`` so you can
filter per pattern:

    dependencies
    | where timestamp > ago(15m)
    | where cloud_RoleName startswith "foundry-workshop."
    | project timestamp, cloud_RoleName, name, duration, customDimensions
    | order by timestamp desc
"""

from __future__ import annotations

import os
from pathlib import Path

TRACING_ENABLED: bool = False
SCENARIO: str | None = None


def init_observability(scenario: str) -> None:
    """Wire OTel → Azure Monitor and turn on agent-framework instrumentation.

    Args:
        scenario: a short tag — e.g. "pure-code", "portal-first", "hybrid".
            Stored as the OTel service name so KQL queries can filter by pattern.
    """
    global TRACING_ENABLED, SCENARIO

    # Load .env from the same folder as this file, if present.
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parent / ".env")
    except Exception:
        pass

    conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
    if not conn:
        print(
            "[observability] skipped — APPLICATIONINSIGHTS_CONNECTION_STRING is not set. "
            "Copy .env.example to .env and paste the project's Application Insights connection string."
        )
        return

    os.environ.setdefault("OTEL_SERVICE_NAME", f"foundry-workshop.{scenario}")
    os.environ.setdefault("OTEL_RESOURCE_ATTRIBUTES", f"workshop.scenario={scenario}")
    # Surface user/assistant message content + tool args/results in spans.
    # Without these, the OTel GenAI semconv only records metadata (token counts,
    # model name, etc.) — never the actual content. Useful for demos and KQL
    # of prompts/completions.
    os.environ.setdefault("AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED", "true")
    os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "true")

    from agent_framework.observability import enable_instrumentation
    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor(connection_string=conn)
    enable_instrumentation(enable_sensitive_data=True)

    TRACING_ENABLED = True
    SCENARIO = scenario
    print(f"[observability] ✓ enabled  scenario='{scenario}'  → Application Insights")
