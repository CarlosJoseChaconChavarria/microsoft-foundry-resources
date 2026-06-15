#!/usr/bin/env python3
"""Run a battery of KQL queries against the project's Application Insights
to verify observability for the three workshop patterns (02 / 02b / 02c).

Usage
-----
After running any of 02-/02b-/02c-*.py with .env set, wait ~60s for ingestion
then run this script. It prints span counts, token usage, cost, prompt content,
and tool-call types per scenario — proving the OTel wiring works end-to-end.

Run via the same container helper:
    docker run --rm -v "$PWD":/work -w /work -e HOME=/work/.dockerhome \\
        --env-file .env mcr.microsoft.com/azure-cli:latest \\
        bash -c 'az extension add -n application-insights --only-show-errors 2>/dev/null;
                 python3 verify_observability.py'

Required environment variables (set in .env — see .env.example)
---------------------------------------------------------------
    APPLICATIONINSIGHTS_SUBSCRIPTION_ID  — Azure subscription containing the App Insights
    APPLICATIONINSIGHTS_RESOURCE_GROUP   — Resource group of the App Insights resource
    APPLICATIONINSIGHTS_RESOURCE_NAME    — Name of the App Insights resource
    LOOKBACK_MINUTES                     — optional, default 1440 (24h)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

SUB = os.environ.get("APPLICATIONINSIGHTS_SUBSCRIPTION_ID")
RG = os.environ.get("APPLICATIONINSIGHTS_RESOURCE_GROUP")
APP = os.environ.get("APPLICATIONINSIGHTS_RESOURCE_NAME")
LOOKBACK = os.environ.get("LOOKBACK_MINUTES", "1440")

if not (SUB and RG and APP):
    sys.exit(
        "ERROR: set APPLICATIONINSIGHTS_SUBSCRIPTION_ID, "
        "APPLICATIONINSIGHTS_RESOURCE_GROUP, and APPLICATIONINSIGHTS_RESOURCE_NAME "
        "in your .env file (see .env.example)."
    )


def kql(query: str, title: str) -> None:
    print(f"\n━━━━━━━━━━━━━━━━━━━━ {title} ━━━━━━━━━━━━━━━━━━━━")
    result = subprocess.run(
        [
            "az", "monitor", "app-insights", "query",
            "--subscription", SUB, "-g", RG, "--app", APP,
            "--analytics-query", query, "-o", "json",
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  az error: {result.stderr.strip()[:300]}")
        return
    try:
        data = json.loads(result.stdout)
        table = data["tables"][0]
        cols = [c["name"] for c in table["columns"]]
        rows = table["rows"]
    except Exception as exc:  # pragma: no cover
        print(f"  parse error: {exc}\n{result.stdout[:300]}")
        return
    if not rows:
        print("  (no rows in the last "+LOOKBACK+" minutes — run a sample first, wait ~60s, retry)")
        return
    widths = [
        min(max(len(c), max((len(str(r[i])[:90]) for r in rows), default=0)), 90)
        for i, c in enumerate(cols)
    ]
    print("  " + " │ ".join(f"{c:<{w}}" for c, w in zip(cols, widths)))
    print("  " + " │ ".join("─" * w for w in widths))
    for row in rows:
        print("  " + " │ ".join(f"{str(v or '')[:w]:<{w}}" for v, w in zip(row, widths)))


def main() -> int:
    print(f"Querying App Insights '{APP}' in '{RG}' (last {LOOKBACK} min)")

    kql(f"""
let target_tbl = dependencies
    | where timestamp > ago({LOOKBACK}m)
    | where cloud_RoleName startswith "foundry-workshop."
    | where name startswith "invoke_agent"
    | where isnotempty(tostring(customDimensions["gen_ai.input.messages"]))
    | top 1 by timestamp desc
    | project operation_Id;
let span = dependencies
    | where timestamp > ago({LOOKBACK}m)
    | where operation_Id in (target_tbl)
    | where name startswith "invoke_agent";
let user_step = span
    | extend msgs = parse_json(tostring(customDimensions["gen_ai.input.messages"]))
    | mv-expand m = msgs
    | mv-expand p = m.parts
    | where tostring(m.role) == "user"
    | project ord=0, step="(1) USER", who="human", detail=tostring(p.content);
let agent_steps = span
    | extend msgs = parse_json(tostring(customDimensions["gen_ai.output.messages"]))
    | mv-expand m = msgs
    | mv-expand p = m.parts
    | extend ptype = tostring(p.type)
    | extend ord  = case(ptype == "mcp_server_tool_call", 1,
                         ptype == "mcp_server_tool_result", 2,
                         ptype == "text", 3, 9)
    | extend step = case(ptype == "mcp_server_tool_call",   "(2) TOOL CALL",
                         ptype == "mcp_server_tool_result", "(3) TOOL RESULT",
                         ptype == "text",                   "(4) ANSWER",
                                                            ptype)
    | extend who  = case(ptype == "mcp_server_tool_call",
                            strcat(tostring(p.server_name), ".", tostring(p.tool_name)),
                         ptype == "mcp_server_tool_result", "mcp-server",
                         ptype == "text", "assistant", "")
    | extend raw  = case(ptype == "mcp_server_tool_call",   tostring(p.arguments),
                         ptype == "mcp_server_tool_result", tostring(p.output),
                         ptype == "text",                   tostring(p.content), "")
    | extend detail = iif(strlen(raw) > 120, strcat(substring(raw, 0, 120), " ..."), raw)
    | project ord, step, who, detail;
union user_step, agent_steps
| order by ord asc
| project step, who, detail
""", "Q0 (HEADLINE) - Full chat-turn waterfall: USER -> TOOL -> RESULT -> ANSWER")

    kql(f"""
union dependencies, traces
| where timestamp > ago({LOOKBACK}m)
| where cloud_RoleName startswith "foundry-workshop."
| summarize spans=count() by scenario=cloud_RoleName, itemType
| order by scenario, itemType
""", "Q1 — Span counts per scenario")

    kql(f"""
dependencies
| where timestamp > ago({LOOKBACK}m)
| where cloud_RoleName startswith "foundry-workshop."
| extend in_tok=toint(customDimensions["gen_ai.usage.input_tokens"]),
         out_tok=toint(customDimensions["gen_ai.usage.output_tokens"])
| where isnotnull(in_tok)
| summarize input_tok=sum(in_tok), output_tok=sum(out_tok), calls=count() by scenario=cloud_RoleName
| extend cost_usd=round(input_tok*2.5/1000000 + output_tok*10.0/1000000, 6)
""", "Q2 — Tokens + cost per scenario (gpt-4o list price)")

    kql(f"""
dependencies
| where timestamp > ago({LOOKBACK}m)
| where cloud_RoleName startswith "foundry-workshop."
| where name startswith "invoke_agent"
| extend msgs=parse_json(tostring(customDimensions["gen_ai.input.messages"]))
| extend prompt=tostring(msgs[0].parts[0].content)
| where isnotempty(prompt)
| project ts=format_datetime(timestamp, "HH:mm:ss"),
          scenario=cloud_RoleName,
          agent=tostring(customDimensions["gen_ai.agent.name"]),
          prompt=substring(prompt, 0, 60)
| order by ts asc
""", "Q3 — User prompts captured per scenario")

    kql(f"""
dependencies
| where timestamp > ago({LOOKBACK}m)
| where cloud_RoleName startswith "foundry-workshop."
| where name startswith "invoke_agent"
| extend kinds=strcat_array(extract_all(@'"type"\\s*:\\s*"([^"]+)"',
            tostring(customDimensions["gen_ai.output.messages"])), ",")
| project ts=format_datetime(timestamp, "HH:mm:ss"),
          scenario=cloud_RoleName, tool_call_types=kinds
| order by ts asc
""", "Q4 — Output content types (text vs mcp_server_tool_call)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
