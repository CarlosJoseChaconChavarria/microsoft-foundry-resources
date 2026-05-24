# Observability for the three agent patterns

> **What this doc is.** A complete, copy-pasteable walk-through of how we make
> the three Foundry-agent patterns (pure-code / portal-first / hybrid)
> **observable**, and how to **prove it works** using KQL queries against
> Azure Application Insights.
>
> **Companion doc:** [`AGENT-PATTERNS.md`](./AGENT-PATTERNS.md) explains the
> three patterns themselves.
>
> **⚠ Note on the sample output.** Real outputs captured from the workshop runs
> are shown below. **Anything that could plausibly identify a user has been
> redacted** (replaced with `<REDACTED>`). The token counts, timestamps, span
> names, and tool-call types are real; the user-prompt text in Q3 has been
> trimmed and tagged.

---

## Table of contents

1. [Why observability for agents is hard](#why-observability-for-agents-is-hard)
2. [Architecture — how telemetry flows](#architecture--how-telemetry-flows)
3. [What gets captured (attribute glossary)](#what-gets-captured-attribute-glossary)
4. [Setup — turning it on](#setup--turning-it-on)
5. [KQL queries — copy, paste, run](#kql-queries--copy-paste-run)
   - [⭐ Q0 — Full chat-turn waterfall (the headline query)](#-q0--full-chat-turn-waterfall-the-headline-query)
   - [Q1 — Are all three patterns sending telemetry?](#q1--are-all-three-patterns-sending-telemetry)
   - [Q2 — How many tokens / dollars did each scenario burn?](#q2--how-many-tokens--dollars-did-each-scenario-burn)
   - [Q3 — What did users actually ask?](#q3--what-did-users-actually-ask)
   - [Q4 — Did the MCP tool actually fire?](#q4--did-the-mcp-tool-actually-fire)
6. [Per-pattern observability differences](#per-pattern-observability-differences)
7. [Running the verification script](#running-the-verification-script)
8. [Troubleshooting](#troubleshooting)

---

## Why observability for agents is hard

A traditional API call is one HTTP request → one response → one log line.

An agent is **not** that. A single `agent.run("…")` call can fan out into:

- N model calls (the agent loops until it's done),
- M tool calls (MCP server, code interpreter, file search, …),
- a thread of intermediate "thoughts",
- and finally, the user-facing answer.

If your logs only show you the final answer, you can't debug latency, you
can't prove the right tool was used, and you can't tell why the bill is high.

**The fix:** emit OpenTelemetry spans for every step, all the way through, and
ship them to Application Insights, where you can query them with KQL.

That's what this folder does — for all three agent patterns — in **one shared
helper**, [`_observability.py`](./_observability.py).

---

## Architecture — how telemetry flows

```
   YOUR PYTHON PROCESS                  AZURE                  YOU
   ┌───────────────────────┐         ┌────────────────┐    ┌──────────┐
   │  02 / 02b / 02c       │         │  Application   │    │  KQL     │
   │                       │         │  Insights      │    │  query   │
   │  init_observability(  │         │  "foundry-     │    │  (this   │
   │      scenario=…)      │         │   insights"    │    │   doc)   │
   │           │           │         │                │    │          │
   │           ▼           │         │  Workspace     │    │          │
   │  ┌───────────────────┐│         │  ┌────────────┐│    │          │
   │  │ OpenTelemetry SDK ││  HTTPS  │  │dependencies││    │          │
   │  │  + agent_framework││ ──────► │  ├────────────┤│ ─► │          │
   │  │  instrumentation  ││  OTLP   │  │traces       ││    │          │
   │  │                   ││         │  ├────────────┤│    │          │
   │  │ tag every span:   ││         │  │customEvents││    │          │
   │  │  cloud_RoleName = ││         │  └────────────┘│    │          │
   │  │  "foundry-        ││         │                │    │          │
   │  │   workshop.<scen>"││         │                │    │          │
   │  └───────────────────┘│         │                │    │          │
   └───────────────────────┘         └────────────────┘    └──────────┘
```

**Key idea: the `cloud_RoleName` tag.** Each of the three samples sets
`OTEL_SERVICE_NAME` to a different value:

| Sample                  | `cloud_RoleName` in App Insights |
|-------------------------|----------------------------------|
| `02-mcp-tool-agent.py`  | `foundry-workshop.pure-code`     |
| `02b-portal-agent.py`   | `foundry-workshop.portal-first`  |
| `02c-hybrid-agent.py`   | `foundry-workshop.hybrid`        |

This is the magic that lets a single KQL query slice across all three
scenarios. Everything else is just OpenTelemetry doing its thing.

---

## What gets captured (attribute glossary)

Every `invoke_agent` and `chat` span carries these standard
[OpenTelemetry GenAI semantic-convention](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
attributes. In App Insights they all live inside the `customDimensions`
property bag on `dependencies` rows.

| Attribute                                  | What it means                                                  |
|--------------------------------------------|----------------------------------------------------------------|
| `gen_ai.agent.name`                        | Which agent ran (e.g. `mcp-learn-agent-codefirst`).            |
| `gen_ai.agent.id`                          | Server-side agent ID (portal-first / hybrid only).             |
| `gen_ai.request.model`                     | Model deployment hit (e.g. `gpt-4o`).                          |
| `gen_ai.input.messages`                    | Full user prompt(s), as JSON. **Contains user PII.**           |
| `gen_ai.output.messages`                   | Full assistant response + tool calls, as JSON.                 |
| `gen_ai.usage.input_tokens`                | Prompt tokens billed.                                          |
| `gen_ai.usage.output_tokens`               | Completion tokens billed.                                      |
| `gen_ai.provider.name`                     | Always `microsoft.agent_framework`.                            |
| `microsoft.gen_ai.main_agent.name`         | Microsoft-specific shadow of `gen_ai.agent.name`.              |
| `_MS.GenAIContentId`                       | Foundry portal correlation key — opens the run in the UI.      |

> **PII warning.** `gen_ai.input.messages` and `gen_ai.output.messages` contain
> the **raw user text**. Recording them is gated by the env var
> `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED=true`, which our helper sets
> automatically for the workshop so the KQL examples below have something to
> show. **Turn it off in production** if your users send personal data.

---

## Setup — turning it on

### One-time

1. Copy the template env file:

   ```bash
   cp .env.example .env
   ```

2. In the Foundry portal, go to **Manage → Tracing** and click **Show
   connection string**. Paste it into `.env`:

   ```
   APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=<GUID>;IngestionEndpoint=https://…
   ```

   `.env` is in `.gitignore` — it won't be committed.

### Every run

Pass the env file into the container:

```bash
docker run --rm -it \
  -v "$PWD":/work -w /work -e HOME=/work/.dockerhome \
  --env-file .env \
  mcr.microsoft.com/azure-cli:latest \
  bash -c 'python3 02c-hybrid-agent.py'
```

When the helper boots correctly you'll see this line near the top of the
output:

```
[observability] ✓ enabled  scenario='hybrid'  → Application Insights
```

If `APPLICATIONINSIGHTS_CONNECTION_STRING` isn't set, the helper prints a
warning and **the script still runs without telemetry** — no silent failures,
no crashes.

### What the helper actually does

The 30-line file [`_observability.py`](./_observability.py) does five things
when you call `init_observability("<scenario>")`:

1. Loads `.env` if present.
2. Sets `OTEL_SERVICE_NAME=foundry-workshop.<scenario>` → becomes
   `cloud_RoleName` in App Insights.
3. Sets `OTEL_RESOURCE_ATTRIBUTES=workshop.scenario=<scenario>` as a backup
   tag.
4. Sets `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED=true` and
   `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` so prompts and
   responses are captured.
5. Calls `configure_azure_monitor(...)` + `enable_instrumentation(...)` to
   start the exporter.

---

## KQL queries — copy, paste, run

You can run these in any of these places:

- **Foundry portal → Operate → Tracing → Open in Logs** (recommended — pre-scoped to this project).
- **Azure portal → Application Insights `<YOUR_APP_INSIGHTS_RESOURCE_NAME>` → Logs**.
- **`verify_observability.py`** — runs all queries in one shot. See below.

> **Heads-up: ingestion lag.** It takes Application Insights about 60–120
> seconds to make a new span queryable. If you just ran a script and see
> nothing, wait two minutes and retry.

---

### ⭐ Q0 — Full chat-turn waterfall (the headline query)

**Question this answers.** *"For one agent run, show me everything that
happened, in order, as a timeline: what the user asked, what tool the agent
called and with what arguments, what the tool returned, and the final answer."*

This is the **single most useful query** for debugging or demoing agents.

#### How the data is laid out (important context)

A hosted-MCP agent run produces **one `invoke_agent` span** in App Insights.
That span carries:

- **`gen_ai.input.messages`** — a JSON array with the user's turn (`role: user`,
  `parts: [{type:"text", content:"…"}]`).
- **`gen_ai.output.messages`** — a JSON array with the assistant's turn, whose
  `parts` is a sequence of:
  - `{type: "mcp_server_tool_call", tool_name, server_name, arguments}` — the model decided to call a tool
  - `{type: "mcp_server_tool_result", output: [...]}` — what the tool returned
  - `{type: "text", content: "…"}` — the assistant's final natural-language answer

So the full flow is **already inside one row** — we just have to *unfold* the
two JSON arrays with `mv-expand` and label each piece.

#### The query

```kql
// === ⭐ Full chat-turn waterfall — USER → TOOL CALL → TOOL RESULT → ANSWER ===
//
// Pick the most recent agent run that captured content.
// To pin a specific scenario, change `startswith "foundry-workshop."`
// to e.g. `== "foundry-workshop.hybrid"` or `== "foundry-workshop.pure-code"`.
let target_tbl = dependencies
    | where timestamp > ago(24h)
    | where cloud_RoleName startswith "foundry-workshop."
    | where name startswith "invoke_agent"
    | where isnotempty(tostring(customDimensions["gen_ai.input.messages"]))
    | top 1 by timestamp desc
    | project operation_Id;
let span = dependencies
    | where timestamp > ago(24h)
    | where operation_Id in (target_tbl)
    | where name startswith "invoke_agent";
// --- USER turn: pull out role=user parts from gen_ai.input.messages ---
let user_step = span
    | extend msgs = parse_json(tostring(customDimensions["gen_ai.input.messages"]))
    | mv-expand m = msgs
    | mv-expand p = m.parts
    | where tostring(m.role) == "user"
    | project ord = 0,
              step   = "① USER",
              who    = "human",
              detail = tostring(p.content);
// --- ASSISTANT turn: unfold every part of gen_ai.output.messages ---
let agent_steps = span
    | extend msgs = parse_json(tostring(customDimensions["gen_ai.output.messages"]))
    | mv-expand m = msgs
    | mv-expand p = m.parts
    | extend ptype = tostring(p.type)
    | extend ord  = case(ptype == "mcp_server_tool_call",   1,
                         ptype == "mcp_server_tool_result", 2,
                         ptype == "text",                   3, 9)
    | extend step = case(ptype == "mcp_server_tool_call",   "② TOOL CALL",
                         ptype == "mcp_server_tool_result", "③ TOOL RESULT",
                         ptype == "text",                   "④ AGENT ANSWER",
                                                            ptype)
    | extend who  = case(ptype == "mcp_server_tool_call",
                            strcat(tostring(p.server_name), ".", tostring(p.tool_name)),
                         ptype == "mcp_server_tool_result", "mcp-server",
                         ptype == "text",                   "assistant",
                         "")
    | extend raw  = case(ptype == "mcp_server_tool_call",   tostring(p.arguments),
                         ptype == "mcp_server_tool_result", tostring(p.output),
                         ptype == "text",                   tostring(p.content),
                         "")
    | extend detail = iif(strlen(raw) > 200, strcat(substring(raw, 0, 200), " …"), raw)
    | project ord, step, who, detail;
union user_step, agent_steps
| order by ord asc
| project step, who, detail
```

#### How to read it line-by-line

| Block | Plain English |
|-------|---------------|
| `let target_tbl = …` | Find the most recent agent run that actually captured prompt/response content. Returns a one-row, one-column table containing its `operation_Id`. |
| `where operation_Id in (target_tbl)` | Keep only spans belonging to that one run. (We use `in (table)` instead of `== toscalar(…)` because some App Insights workspaces silently fail on the latter.) |
| `parse_json(tostring(...))` | The `gen_ai.input.messages` / `gen_ai.output.messages` come out of `customDimensions` as JSON-encoded strings; we re-parse them into structured data. |
| `mv-expand m = msgs \| mv-expand p = m.parts` | Each message is `{role, parts: [...]}`. Two `mv-expand`s flatten that into one row per part. |
| `case(ptype == "mcp_server_tool_call", …)` | Label each part: tool call / tool result / text answer. |
| `extend ord = …` | Give each part a sort key so the timeline displays in the natural order (user first, then tool call, then tool result, then answer). |
| `iif(strlen(raw) > 200, …)` | Trim long bodies so the table stays readable. Remove this clause to see full content. |
| `union user_step, agent_steps \| order by ord asc` | Stitch the two flat tables together into the final timeline. |

#### Sample output — `foundry-workshop.hybrid`

> *User prompt below was the workshop demo text (about Microsoft Learn public
> docs, no PII). In production the `① USER` row could contain user PII —
> `<REDACTED>` shows where redaction would go.*

```
STEP             │ WHO                                       │ DETAIL
─────────────────│───────────────────────────────────────────│─────────────────────────────────────────────────
① USER           │ human                                     │ <REDACTED — user question about Azure AI Agent docs>
② TOOL CALL      │ MicrosoftLearn.microsoft_docs_search      │ {"query":"Azure AI Agent documentation about MCP tool calling"}
③ TOOL RESULT    │ mcp-server                                │ [{"type":"text","text":"{\"results\":[{\"title\":\"How to use the Mode …
④ AGENT ANSWER   │ assistant                                 │ The Azure AI Agent documentation related to MCP (Model Context Protoco …
```

#### Sample output — `foundry-workshop.pure-code`

```
STEP             │ WHO                                       │ DETAIL
─────────────────│───────────────────────────────────────────│─────────────────────────────────────────────────
① USER           │ human                                     │ <REDACTED — user question about Azure AI Agent docs>
② TOOL CALL      │ Microsoft_Learn_MCP.microsoft_docs_search │ {"query":"Azure AI Agent MCP tool calling documentation"}
③ TOOL RESULT    │ mcp-server                                │ [{"type":"text","text":"{\"results\":[{\"title\":\"How to use the Mode …
④ AGENT ANSWER   │ assistant                                 │ Here is a summarized overview of Azure AI Agent documentation related …
```

#### Sample output — `foundry-workshop.portal-first`

```
(0 rows)
```

**Why portal-first returns nothing here — and where to find the equivalent.**

The portal-first sample (`02b-portal-agent.py`) invokes `Agent02`, which was
created in the Foundry portal UI. Portal-created agents default to the legacy
Assistants transport (`protocols: null`), and the agent-framework SDK does NOT
emit `invoke_agent` + content spans for that transport client-side. The full
execution **does happen** — it just isn't visible from this App Insights
query.

To see the same waterfall for portal-first agents, use:

1. **Foundry portal → Operate → Tracing**
2. Filter by your agent name (`Agent02`)
3. Open the most recent run → expand the tree

That view is rendered from Foundry's server-side OpenTelemetry instrumentation
and includes the same USER → TOOL CALL → TOOL RESULT → ANSWER breakdown.

**Take-away.** This is *the* reason the workshop recommends the **hybrid**
pattern for production: it gives you the rich client-side waterfall (above)
*and* the server-side portal view, for the price of a one-line REST upsert.

---

### Supplementary queries (drill-downs into the same data)

The waterfall is the headline. Q1–Q4 below answer narrower questions —
useful for monitoring dashboards rather than per-request debugging.

---

### Q1 — Are all three patterns sending telemetry?

**Question this answers.** *"After I ran the three samples, did any spans
actually reach App Insights? How many per pattern, and what kind?"*

**The query**

```kql
union dependencies, traces
| where timestamp > ago(15m)
| where cloud_RoleName startswith "foundry-workshop."
| summarize spans=count() by scenario=cloud_RoleName, itemType
| order by scenario, itemType
```

**How to read it line-by-line**

| Line | Plain English |
|------|---------------|
| `union dependencies, traces` | Look in two tables at once — `dependencies` (HTTP/RPC spans, which is where agent and chat spans land) and `traces` (informational log lines). |
| `where timestamp > ago(15m)` | Only the last 15 minutes. |
| `where cloud_RoleName startswith "foundry-workshop."` | Only rows tagged by our three samples — ignore everything else in this App Insights resource. |
| `summarize spans=count() by …` | Group and count. |

**Sample output** (real, no PII in this one)

```
scenario                       itemType    spans
─────────────────────────────  ──────────  ─────
foundry-workshop.pure-code     trace       4
foundry-workshop.pure-code     dependency  2
foundry-workshop.portal-first  trace       3
foundry-workshop.portal-first  dependency  2
foundry-workshop.hybrid        trace       2
foundry-workshop.hybrid        dependency  6
```

**What this tells us.** All three scenarios show up — observability is wired
end-to-end. Note that *hybrid* emits more `dependency` rows (one per
internal model + tool call) because it ran the full MCP loop; *portal-first*
emits fewer because the agent's run happens server-side (see
[Per-pattern observability differences](#per-pattern-observability-differences)).

---

### Q2 — How many tokens / dollars did each scenario burn?

**Question this answers.** *"What did this experiment cost me?"*

**The query**

```kql
dependencies
| where timestamp > ago(15m)
| where cloud_RoleName startswith "foundry-workshop."
| extend in_tok  = toint(customDimensions["gen_ai.usage.input_tokens"]),
         out_tok = toint(customDimensions["gen_ai.usage.output_tokens"])
| where isnotnull(in_tok)
| summarize input_tok  = sum(in_tok),
            output_tok = sum(out_tok),
            calls      = count()
            by scenario = cloud_RoleName
| extend cost_usd = round(input_tok  * 2.5  / 1000000
                       +  output_tok * 10.0 / 1000000, 6)
```

**How to read it line-by-line**

| Line | Plain English |
|------|---------------|
| `dependencies` | Only the structured span rows. |
| `extend in_tok=…, out_tok=…` | Pull `gen_ai.usage.input_tokens` and `gen_ai.usage.output_tokens` out of the `customDimensions` JSON bag and convert them to integers. |
| `where isnotnull(in_tok)` | Drop spans that don't have token data (e.g. setup spans). |
| `summarize …` | Total tokens and call counts per scenario. |
| `extend cost_usd = …` | Apply gpt-4o list pricing: $2.50 / million input tokens, $10.00 / million output tokens. Adjust if you use a different model. |

**Sample output**

```
scenario                    input_tok  output_tok  calls  cost_usd
─────────────────────────   ─────────  ──────────  ─────  ────────
foundry-workshop.hybrid     42876      2080        3      0.12799
foundry-workshop.pure-code  29652      1442        2      0.08855
```

**What this tells us.** Three runs of the hybrid agent cost ~13¢; two runs of
pure-code cost ~9¢. **Portal-first doesn't appear here** because its token
accounting happens server-side and isn't visible on the client-side
`dependencies` table (see the per-pattern note below).

---

### Q3 — What did users actually ask?

**Question this answers.** *"Show me the actual prompts that hit each agent —
so I can build evaluations from real usage."*

**The query**

```kql
dependencies
| where timestamp > ago(15m)
| where cloud_RoleName startswith "foundry-workshop."
| where name startswith "invoke_agent"
| extend msgs   = parse_json(tostring(customDimensions["gen_ai.input.messages"]))
| extend prompt = tostring(msgs[0].parts[0].content)
| where isnotempty(prompt)
| project ts       = format_datetime(timestamp, "HH:mm:ss"),
          scenario = cloud_RoleName,
          agent    = tostring(customDimensions["gen_ai.agent.name"]),
          prompt   = substring(prompt, 0, 60)
| order by ts asc
```

**How to read it line-by-line**

| Line | Plain English |
|------|---------------|
| `where name startswith "invoke_agent"` | Only top-level "agent run" spans (not the inner model calls). |
| `extend msgs = parse_json(…)` | The input messages are stored as a JSON string; parse them into structured form. |
| `extend prompt = tostring(msgs[0].parts[0].content)` | Pull the first user message's first text part. |
| `substring(prompt, 0, 60)` | Trim to 60 chars for display. Remove this in production if you actually want the full prompt. |

**Sample output** *(real prompts captured during the workshop; the workshop
prompt happens to be about public documentation but in production this column
would contain user PII — `<REDACTED>` shown to illustrate the redaction pattern
for the doc)*

```
ts        scenario                    agent                       prompt
────────  ──────────────────────────  ─────────────────────────   ────────────────────────────────────
16:56:06  foundry-workshop.hybrid     mcp-learn-agent-hybrid      <REDACTED — user query about MS Learn>
16:59:45  foundry-workshop.pure-code  mcp-learn-agent-codefirst   <REDACTED — user query about MS Learn>
```

**What this tells us.** The exact prompt text is in App Insights for every
run, attributed to the right agent and scenario. This is the raw material for
offline evaluations.

> ⚠ For production: this is PII territory. Two options:
> 1. Disable content capture (`AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED=false`), or
> 2. Apply a [Log Ingestion-time transformation](https://learn.microsoft.com/azure/azure-monitor/essentials/data-collection-transformations) that hashes / redacts the field.

---

### Q4 — Did the MCP tool actually fire?

**Question this answers.** *"My agent has an MCP tool wired up. Did the model
actually call it on this run, or did it just hallucinate an answer?"*

**The query**

```kql
dependencies
| where timestamp > ago(15m)
| where cloud_RoleName startswith "foundry-workshop."
| where name startswith "invoke_agent"
| extend kinds = strcat_array(
    extract_all(@'"type"\s*:\s*"([^"]+)"',
                tostring(customDimensions["gen_ai.output.messages"])),
    ",")
| project ts              = format_datetime(timestamp, "HH:mm:ss"),
          scenario        = cloud_RoleName,
          tool_call_types = kinds
| order by ts asc
```

**How to read it line-by-line**

| Line | Plain English |
|------|---------------|
| `extract_all(@'"type"\s*:\s*"([^"]+)"', …)` | Regex-pull every `"type":"…"` value out of the output messages JSON. Each piece of the agent's response (text answer, tool call, tool result, image, …) has one. |
| `strcat_array(…, ",")` | Join them into a comma-separated list for readability. |

**Sample output**

```
ts        scenario                    tool_call_types
────────  ──────────────────────────  ─────────────────────────────────────────────────────
16:56:06  foundry-workshop.hybrid     mcp_server_tool_call,mcp_server_tool_result,text,text
16:59:45  foundry-workshop.pure-code  mcp_server_tool_call,mcp_server_tool_result,text,text
```

**What this tells us.** **Yes** — for both the `hybrid` and `pure-code`
scenarios, the agent's output stream contains:

- `mcp_server_tool_call` → the model asked the MCP server to do something,
- `mcp_server_tool_result` → the MCP server replied,
- two `text` chunks → the model's reasoning + final answer.

So we have **proof** that the MCP tool was actually exercised, not
hallucinated. If this column were just `text`, that would be a red flag —
the agent skipped the tool.

---

## Per-pattern observability differences

A common workshop question: "Why does portal-first show less data than the
other two in Q2 / Q3 / Q4?"

|                                            | Pure code | Portal-first | Hybrid |
|--------------------------------------------|-----------|--------------|--------|
| Client-side `invoke_agent` + `chat` spans  | ✅         | ⚠ warm-up only | ✅      |
| Server-side Foundry agent trace            | ❌ (no agent on the server) | ✅ in portal Traces tab | ✅ in portal Traces tab |
| Token usage in App Insights / KQL          | ✅         | ❌ (server-side only) | ✅     |

**Why portal-first shows less, client-side.** Agents created in the **portal
UI** default to a transport (`protocols: null` / legacy Assistants) that the
agent-framework SDK doesn't trace as `invoke_agent`. Agents created via the
**REST** path (hybrid) default to `protocols: ["responses"]`, which the SDK
*does* fully trace. The full execution **is still recorded** — it just shows
up in the **Foundry portal Traces tab**, not in App Insights via OTel.

**What this means for production.** You typically want **both layers**:

- **Client-side OTel** (what hybrid + pure-code give you) for end-to-end
  latency, retries, queue time — everything *you* control.
- **Server-side Foundry traces** (what portal-first + hybrid give you) for
  what happens *inside* Foundry: the model loop, tool execution, content
  filtering.

The **hybrid pattern is the only one that gives you both for free** — which
is one more reason it's the production-recommended pattern.

---

## Running the verification script

The repo ships [`verify_observability.py`](./verify_observability.py), which
runs all four queries above in one shot and prints them as tables:

```bash
docker run --rm \
  -v "$PWD":/work -w /work -e HOME=/work/.dockerhome \
  --env-file .env \
  mcr.microsoft.com/azure-cli:latest \
  bash -c '
    az extension add -n application-insights --only-show-errors 2>/dev/null
    python3 verify_observability.py
  '
```

Use it as a smoke test after every run. If Q1 returns no rows, something is
wrong; run through the troubleshooting section below.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `init_observability` prints a `⚠` warning at startup | `APPLICATIONINSIGHTS_CONNECTION_STRING` not set | Put it in `.env`; pass `--env-file .env` to docker |
| Script runs fine but Q1 returns no rows | Ingestion lag, or you queried the wrong App Insights resource | Wait 2 min and retry; double-check the resource name in `verify_observability.py` |
| Q3 returns rows but `prompt` column is empty | `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED` not set | Helper sets it automatically — make sure you didn't override it elsewhere |
| Q4 shows only `text`, no `mcp_server_tool_*` | The MCP tool didn't fire. Two common causes: missing `require_approval: "never"` on the MCP tool config (server-side agents); or the prompt didn't actually need the tool | Inspect the agent's tool config; rephrase the prompt to one that requires the tool |
| `portal-first` (`02b-portal-agent.py`) shows no token rows in Q2 | Expected — see [per-pattern differences](#per-pattern-observability-differences) | Use the Foundry portal Traces tab for the server-side view |
