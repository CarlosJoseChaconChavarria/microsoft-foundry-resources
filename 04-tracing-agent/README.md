# Chapter 4 · Observing an Agent with OpenTelemetry and Application Insights

> **You have just finished sample 03**: an agent with one local function tool
> that fires on demand. The agent works — and you have *no idea* what's
> happening inside it. Was the tool actually called? How many tokens did the
> model consume? Which prompt produced which completion? If something
> regresses next week, how will you debug it?
>
> Welcome to the chapter that grows your eyes.

This chapter takes the *same* basic agent from sample 01 and adds **one new
import**, **one new function call**, and **one `with` block** — and in doing
so wires it into **Azure Monitor Application Insights** through the
**OpenTelemetry (OTel)** SDK. Every prompt, every completion, every model
call, and every token count becomes a queryable telemetry record.

By the time you finish this chapter you'll know:

- What OpenTelemetry is, why every cloud SDK now ships with it, and how the
  abstraction stack of **OTel API → OTel SDK → Azure Monitor exporter →
  Application Insights** works end to end.
- How `configure_azure_monitor()` is the *one line* that wires everything up.
- How the Agent Framework's GenAI-aware instrumentation populates
  semantic-conventions-compliant span attributes (`gen_ai.system`,
  `gen_ai.usage.input_tokens`, `gen_ai.prompt`, `gen_ai.completion`).
- How to write **Kusto Query Language (KQL)** queries against the
  `dependencies` and `traces` tables to reconstruct an agent run.
- The privacy switch that controls whether prompts/completions are recorded
  in your telemetry — and when to flip it on or off.

---

## Table of contents

- [What you will build](#what-you-will-build)
- [Prerequisites](#prerequisites)
  - [Step 1 · Configure your `.env` file](#step-1--configure-your-env-file)
  - [Step 2 · Get an Application Insights connection string](#step-2--get-an-application-insights-connection-string)
- [Mental model — the telemetry pipeline](#mental-model--the-telemetry-pipeline)
- [Mental model — spans, traces, and the GenAI semantic conventions](#mental-model--spans-traces-and-the-genai-semantic-conventions)
- [Step-by-step code walkthrough](#step-by-step-code-walkthrough)
  - [Section 1 · Imports and `.env` loader](#section-1--imports-and-env-loader)
  - [Section 2 · Configuration and fail-fast checks](#section-2--configuration-and-fail-fast-checks)
  - [Section 3 · The single telemetry-toggle environment variable](#section-3--the-single-telemetry-toggle-environment-variable)
  - [Section 4 · Wiring Azure Monitor and getting a tracer](#section-4--wiring-azure-monitor-and-getting-a-tracer)
  - [Section 5 · The custom span around `main()`](#section-5--the-custom-span-around-main)
  - [Section 6 · Why `await asyncio.sleep(1.0)` at the end](#section-6--why-await-asynciosleep10-at-the-end)
- [Running the sample](#running-the-sample)
- [Expected output (console)](#expected-output-console)
- [Querying Application Insights with KQL](#querying-application-insights-with-kql)
- [Troubleshooting](#troubleshooting)
- [Exercises — try these next](#exercises--try-these-next)
- [What you've learned](#what-youve-learned)
- [Where to go next](#where-to-go-next)

---

## What you will build

A Python script that:

1. Loads Foundry endpoint, model name, and an **Application Insights
   connection string** from a `.env` file in this folder.
2. Calls `configure_azure_monitor(...)` once at import time — that single
   call installs the entire telemetry pipeline.
3. Opens a custom `example-tracing` span as the root.
4. Inside that span, runs a one-prompt conversation against a Foundry agent.
5. Behind the scenes, the Agent Framework's built-in OTel instrumentation
   emits **GenAI semantic-convention spans** for every model call.
6. All of those spans flow over HTTPS to Application Insights, where you
   can query them with KQL — the same query language used by Sentinel,
   Defender for Cloud, and most of Azure Monitor.

The code change relative to sample 01 is *tiny*. The capability you unlock
is enormous: you now have a queryable record of every model interaction,
which is the foundation of every production AI system.

---

## Prerequisites

| Requirement                                                                  | Why                                                                                                       |
| ---------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| **You've completed sample 01**                                               | We re-use the agent skeleton verbatim. The four building blocks are not re-explained.                      |
| **Python 3.10+**                                                             | Agent Framework uses modern `async` features.                                                              |
| **A Microsoft Foundry project** with a **gpt-4o** deployment                 | Same as previous chapters.                                                                                 |
| **An Application Insights resource** attached to your Foundry project        | The destination for our telemetry. See [Step 2 below](#step-2--get-an-application-insights-connection-string). |
| **Azure CLI signed in** (`az login`)                                         | `DefaultAzureCredential` picks up your CLI login.                                                          |
| **A configured `.env` file in this folder**                                  | Holds three values: project endpoint, model name, App Insights connection string.                         |
| **VS Code with the Python and Azure Tools extensions** (recommended)         | One click to run; you can also open the App Insights blade from inside VS Code's Azure side panel.         |

### Step 1 · Configure your `.env` file

1. **Copy the example:**
   ```bash
   cd 04-tracing-agent
   cp .env.example .env
   ```

2. **Open `.env`** and fill in three variables:

   | Variable                                  | Where to find it                                                                                                                                |
   | ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
   | `FOUNDRY_PROJECT_ENDPOINT`                | Foundry portal → **your project → Overview**. Ends in `/api/projects/<project-name>`.                                                            |
   | `FOUNDRY_MODEL`                           | The **deployment name** of your chat model. Defaults to `gpt-4o`.                                                                                |
   | `APPLICATIONINSIGHTS_CONNECTION_STRING`   | Foundry portal → **your project → Manage → Tracing**. Click **View Application Insights**, then **Properties**, then copy **Connection String**. |

> **Fail-fast behaviour.** This sample is specifically about tracing. If
> `APPLICATIONINSIGHTS_CONNECTION_STRING` is empty, the script raises a
> `RuntimeError` *before* opening any HTTP connection — running a
> "tracing" sample with no destination would be silently useless.

### Step 2 · Get an Application Insights connection string

You need an Application Insights resource (a special workspace inside
Log Analytics) to receive telemetry. The good news: **a Foundry project
already has one attached by default** for built-in tracing.

To grab the connection string from the portal:

1. Open the **Foundry portal** at [ai.azure.com](https://ai.azure.com).
2. Select your project, then **Manage → Tracing**.
3. Click **View Application Insights**. This opens the Azure portal blade
   for the resource.
4. In the App Insights blade's left rail, click **Configure → Properties**.
5. Copy the **Connection String** (a single line beginning with
   `InstrumentationKey=...`, also containing `IngestionEndpoint=` and
   `ApplicationId=`).
6. Paste it into `.env` as `APPLICATIONINSIGHTS_CONNECTION_STRING=...`.

> **No Application Insights resource attached?** Create one from
> *Azure portal → Create a resource → Application Insights*, choose
> **Workspace-based**, attach it to any Log Analytics workspace in your
> subscription, and then optionally wire it back to the Foundry project
> under **Manage → Tracing → Enable tracing**. For this lab you only need
> the connection string — the resource can be standalone.

---

## Mental model — the telemetry pipeline

When you call `configure_azure_monitor(...)`, you assemble this pipeline in
memory inside your Python process:

```
┌─────────────────────────────────────────────────────────────────────┐
│  YOUR CODE                                                          │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │ tracer.start_as_current_span("example-tracing")            │     │
│  │   └─ ChatAgent.run_stream(...)                             │     │
│  │      └─ AzureAIAgentClient → HTTPS POST to Foundry         │     │
│  │         (Agent Framework auto-instruments this call)       │     │
│  └────────────────────────────────────────────────────────────┘     │
│                            │                                        │
│                            ▼                                        │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  OpenTelemetry API   (vendor-neutral; opentelemetry-api)   │     │
│  │  • Span objects, Context propagation                        │    │
│  └────────────────────────────────────────────────────────────┘     │
│                            │                                        │
│                            ▼                                        │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  OpenTelemetry SDK   (opentelemetry-sdk)                   │     │
│  │  • TracerProvider, BatchSpanProcessor                       │    │
│  └────────────────────────────────────────────────────────────┘     │
│                            │                                        │
│                            ▼                                        │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  Azure Monitor exporter   (azure-monitor-opentelemetry)    │     │
│  │  • Converts OTel spans → App Insights envelopes             │    │
│  └────────────────────────────────────────────────────────────┘     │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ HTTPS (≈ every 5 s)
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  AZURE                                                              │
│  Application Insights ingestion endpoint                            │
│      └─ Log Analytics workspace tables:                             │
│         • dependencies  ← outgoing HTTP, model calls, tool calls    │
│         • traces        ← log lines, custom messages                │
│         • requests      ← incoming HTTP (none in this sample)       │
│         • exceptions    ← Python tracebacks                         │
└─────────────────────────────────────────────────────────────────────┘
```

Two ideas that this picture makes concrete:

1. **You write to a vendor-neutral API.** Your code only ever touches
   `opentelemetry.trace`. If a future you wants to switch from Application
   Insights to Jaeger, Honeycomb, or a self-hosted Tempo, you swap *only*
   the exporter — your spans and your queries-against-spans rationale
   carry over.
2. **The Agent Framework is already instrumented.** You don't have to call
   `tracer.start_span("model_call")` around every model call. The
   framework's HTTP client emits a span automatically for every outbound
   request to Foundry, *and* enriches it with GenAI semantic conventions.
   You only need a custom span if you want to **group related work**
   (which is exactly what our `example-tracing` span does).

> **Deep dive · Why batching matters.** The exporter doesn't ship every
> span over the wire immediately — it buffers them in a `BatchSpanProcessor`
> and flushes every few seconds (or when the buffer fills). That's why a
> short script that exits in 3 seconds may emit *no telemetry at all* unless
> you give it time to drain. See [Section 6](#section-6--why-await-asynciosleep10-at-the-end).

---

## Mental model — spans, traces, and the GenAI semantic conventions

Three OTel concepts are enough to read every dashboard you'll ever see:

| Concept     | One-line definition                                                                                                          |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **Span**    | A timed operation: it has a name, a start time, an end time, attributes (key-value pairs), and optional events.               |
| **Trace**   | A tree of spans tied together by a shared `trace_id`. A parent span's `span_id` becomes a child span's `parent_span_id`.      |
| **Context** | Thread-local (or async-task-local) state that carries the *current* span so child operations attach themselves automatically. |

When you write:

```python
with tracer.start_as_current_span("example-tracing"):
    ...  # any spans created here will be children of "example-tracing"
```

…the `with` block sets the context. Anything that creates a span inside —
the Agent Framework's HTTP client included — produces a child. After the
block exits, the context is restored.

For agent workloads, the [GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
define *which attributes a model-call span should carry*. The Agent
Framework follows them. Concretely, when you run this sample you will see
spans in App Insights with attributes like:

| Attribute name                       | Example value                                              | What it means                                   |
| ------------------------------------ | ---------------------------------------------------------- | ----------------------------------------------- |
| `gen_ai.system`                      | `az.ai.agents`                                             | Which provider was called.                      |
| `gen_ai.operation.name`              | `chat`                                                     | The kind of model interaction.                  |
| `gen_ai.request.model`               | `gpt-4o`                                                   | The deployment that handled this request.       |
| `gen_ai.usage.input_tokens`          | `87`                                                       | Prompt tokens billed.                           |
| `gen_ai.usage.output_tokens`         | `124`                                                      | Completion tokens billed.                       |
| `gen_ai.prompt`                      | `"Can you tell me the gravity of Earth versus Mars?"`      | Recorded **only** when content recording is on. |
| `gen_ai.completion`                  | `"Sure! On Earth gravity is approximately 9.81 m/s² ..."`  | Recorded **only** when content recording is on. |

These attributes are *exactly* what the KQL queries at the end of this
chapter rely on.

---

## Step-by-step code walkthrough

Open `04-tracing-agent.py` in VS Code. The full file is 125 lines. We'll
read it in six sections, top to bottom.

### Section 1 · Imports and `.env` loader

```python
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from agent_framework import ChatAgent
from agent_framework_azure_ai import AzureAIAgentClient
from azure.identity.aio import DefaultAzureCredential

load_dotenv(Path(__file__).resolve().parent / ".env")
```

Identical to samples 01 and 03 — we load `.env` from this folder so the
script behaves the same whether you launch it from VS Code's ▶ button or
from a terminal in any directory.

### Section 2 · Configuration and fail-fast checks

```python
ENDPOINT = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")
MODEL_DEPLOYMENT_NAME = os.environ.get("FOUNDRY_MODEL", "gpt-4o")
APPINSIGHTS_CONN = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()

if not ENDPOINT or "<YOUR_" in ENDPOINT:
    raise RuntimeError(
        "FOUNDRY_PROJECT_ENDPOINT is not configured. "
        "Copy .env.example to .env in this folder and fill in your Foundry "
        "project endpoint. See README.md → Prerequisites."
    )

if not APPINSIGHTS_CONN:
    raise RuntimeError(
        "APPLICATIONINSIGHTS_CONNECTION_STRING is not configured. "
        "This sample is specifically about tracing — without an App Insights "
        "connection string no telemetry is exported. Get it from the Foundry "
        "portal → your project → Manage → Tracing. See README.md → Prerequisites."
    )
```

Two fail-fast checks — one more than sample 01.

- The first repeats the sample-01 pattern: if you forgot to fill in the
  endpoint, fail before any HTTP call.
- The second is **new for sample 04**: if `APPLICATIONINSIGHTS_CONNECTION_STRING`
  is empty, fail immediately. Without it, `configure_azure_monitor` would
  initialize, the script would run, and you'd see no telemetry at all in
  App Insights — confusing silent failure that costs hours to debug.

> **Deep dive · The latent bug this guards against.** The Azure Monitor
> exporter accepts an empty connection string at initialization time and
> silently disables telemetry export. Before this guard existed, running
> the sample produced normal console output and *zero* App Insights data —
> the same symptoms as a working configuration with a query typo. The
> guard turns "silent and confusing" into "loud and obvious".

### Section 3 · The single telemetry-toggle environment variable

```python
os.environ["AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED"] = "true"
```

This is one of those one-line settings that hides an enormous policy
decision behind a boolean.

When this variable is **`false`** (the default), the Agent Framework
emits GenAI spans with *structural* attributes only: token counts, model
name, latency, success/failure. It does **not** record the actual prompt
text or completion text. This is the safe default for production systems
that may handle regulated data (PII, PHI, financial records, …).

When this variable is **`true`**, every prompt and completion is captured
as the `gen_ai.prompt` and `gen_ai.completion` attributes on the model
span. This is *vital* for debugging — the moment a user reports "the agent
said something weird", you need to know *exactly* what it said.

> **Deep dive · Why we flip it on here.** This is a learning sample. The
> ability to KQL-query the literal prompt and completion makes the
> mental connection between code and telemetry immediate. **In a real
> production deployment, default to `false`** and only enable it for
> short-lived diagnostic sessions, scoped to non-prod environments, or
> with a downstream redaction step.

### Section 4 · Wiring Azure Monitor and getting a tracer

```python
from azure.monitor.opentelemetry import configure_azure_monitor

configure_azure_monitor(connection_string=APPINSIGHTS_CONN)

from opentelemetry import trace
tracer = trace.get_tracer(__name__)
```

This is **the** four-line block that turns an uninstrumented Python script
into a fully observable one. Read it carefully — you will copy it into
dozens of future projects.

1. **`configure_azure_monitor(connection_string=...)`** does *all* of:
   - Installs an OTel `TracerProvider` (the factory for tracers) globally.
   - Attaches a `BatchSpanProcessor` to it.
   - Attaches the **Azure Monitor exporter** to that processor with the
     parsed instrumentation key and ingestion endpoint from your
     connection string.
   - Wires up the OTel `LoggerProvider` so Python `logging` calls flow to
     App Insights' `traces` table.
   - Auto-detects and enables several built-in instrumentations (HTTP
     clients, database drivers) so you don't have to wire them up
     individually.

2. **`trace.get_tracer(__name__)`** asks the global provider for a tracer
   named after this module. Tracers are cheap; the framework uses many of
   them internally. The `__name__` shows up in dashboards under "library"
   attribution, which helps when you want to know *which Python file*
   created a span.

> **Deep dive · Why imports come after `os.environ[...] = "true"`.** The
> Agent Framework reads `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED`
> at *import time* to decide whether to enable content recording. Setting
> the variable after importing the framework is too late — the framework
> has already made the decision. Hence Section 3 runs before Section 4.
> This is a common gotcha; **always set OTel-related env vars before
> importing the libraries that read them**.

### Section 5 · The custom span around `main()`

```python
async def main() -> None:
    with tracer.start_as_current_span("example-tracing"):
        async with (
            DefaultAzureCredential() as credential,
            ChatAgent(
                chat_client=AzureAIAgentClient(...),
                instructions=AGENT_INSTRUCTIONS,
                ...
            ) as agent
        ):
            thread = agent.get_new_thread()
            for user_input in USER_INPUTS:
                async for chunk in agent.run_stream([user_input], thread=thread):
                    ...
```

The single addition versus sample 01: `tracer.start_as_current_span("example-tracing")`.

This creates one **custom parent span** for the entire run. Why bother?

- **Grouping.** Every model-call span emitted by the framework underneath
  gets `example-tracing` as its parent. In KQL, you can find this trace
  by name (`name == "example-tracing"`) and then enumerate all children.
- **Custom attributes.** You can attach business-meaningful attributes —
  user ID, request ID, A/B-test bucket — to this parent span, and they'll
  be present in queries for the whole run.
- **Latency budget.** The span's start-to-end duration tells you the
  end-to-end time for the request as the user experienced it. The
  framework's child spans tell you *where* inside that budget the time
  went (Foundry HTTPS latency? model inference? local processing?).

You'll see this `example-tracing` span at the **top** of the trace tree in
the App Insights Transaction Search blade.

### Section 6 · Why `await asyncio.sleep(1.0)` at the end

```python
print("\n--- All tasks completed successfully ---")

# Give additional time for all async cleanup to complete
await asyncio.sleep(1.0)
```

This is **not arbitrary**. As mentioned in the mental model: the OTel
SDK's `BatchSpanProcessor` *buffers* spans and flushes them periodically.
If your Python process exits the moment `main()` returns, **the buffer
contents are lost**.

The official cure is `tracer_provider.shutdown()`, which forces a flush.
`asyncio.sleep(1.0)` is a simpler approximation that gives the batcher
about one tick to send what it has. For a workshop sample it's fine. In
production code, call `shutdown()` in a `finally:` block.

> **Deep dive · What you'd do in production.** Register a process-exit
> handler that flushes the provider:
>
> ```python
> import atexit
> from opentelemetry import trace
> atexit.register(lambda: trace.get_tracer_provider().shutdown())
> ```
>
> This guarantees the buffer drains on every clean exit, including those
> caused by `SystemExit` or `KeyboardInterrupt`.

---

## Running the sample

```bash
# 1. cd into this folder
cd 04-tracing-agent

# 2. Make a virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate          # macOS / Linux
# OR on Windows:
.venv\Scripts\activate
pip install --upgrade pip
pip install agent-framework agent-framework-azure-ai \
    azure-monitor-opentelemetry opentelemetry-sdk python-dotenv --pre

# 3. Sign in to Azure
az login

# 4. Configure .env (one-time)
cp .env.example .env
#    then open .env and fill in all three values
#    (see Prerequisites → Step 1)

# 5. Run
python 04-tracing-agent.py
```

Or, in VS Code: open `04-tracing-agent.py` and click ▶ **Run Python File**.

> **VS Code shortcut.** With the **Azure Tools** extension, the
> Application Insights resource attached to your Foundry project appears
> in the Azure side panel. After running the script, expand it, click
> **Live Metrics** or **Transaction Search** to verify spans are arriving.

---

## Expected output (console)

```
# User: 'Can you tell me the gravity of Earth versus the gravity of Mars?'
Sure! Here's a comparison of the gravitational acceleration on Earth and Mars:

- **Earth**: The standard gravitational acceleration is approximately **9.81 m/s²**.
- **Mars**: The gravitational acceleration is about **3.71 m/s²**.

In simpler terms, the gravity on Mars is about **38%** of that on Earth.

--- All tasks completed successfully ---
Program finished.
```

That's the *same* output you saw in sample 01. The interesting part is what
happens **in App Insights** — keep reading.

---

## Querying Application Insights with KQL

Application Insights stores OTel telemetry across a small set of Log
Analytics tables. The two that matter for this sample:

| Table          | What it contains                                                          |
| -------------- | ------------------------------------------------------------------------- |
| `dependencies` | **Outgoing** operations: HTTP requests, model calls, tool calls, spans you create manually. Every OTel span lands here. |
| `traces`       | Python `logging` lines and OTel log records.                              |

Open the App Insights blade → **Logs**. Paste each query and click **Run**.

### Query 1 — Find the run

```kql
dependencies
| where timestamp > ago(1h)
| where name == "example-tracing"
| project timestamp, name, duration, operation_Id
| top 5 by timestamp desc
```

You should see one row per execution of this script in the last hour.
**Save `operation_Id` from the most recent row** — it's the trace ID we'll
use to drill down.

### Query 2 — The whole trace, in order

```kql
let opId = "<paste operation_Id from Query 1>";
dependencies
| where operation_Id == opId
| order by timestamp asc
| project timestamp, name, duration, type
```

This reproduces the entire trace tree, top to bottom. You should see the
parent `example-tracing` span followed by one or more framework-emitted
GenAI spans (typical names: `chat`, `chat gpt-4o`, or similar).

### Query 3 — Token usage

```kql
dependencies
| where timestamp > ago(1h)
| where customDimensions has "gen_ai.usage.input_tokens"
| extend
    input_tokens = toint(customDimensions["gen_ai.usage.input_tokens"]),
    output_tokens = toint(customDimensions["gen_ai.usage.output_tokens"]),
    model = tostring(customDimensions["gen_ai.request.model"])
| project timestamp, model, input_tokens, output_tokens, duration
| order by timestamp desc
```

Now you can answer questions like *"how many tokens did my agent spend
yesterday?"* with a one-line aggregation — `summarize sum(input_tokens),
sum(output_tokens) by bin(timestamp, 1h)`.

### Query 4 — Prompt and completion text

```kql
dependencies
| where timestamp > ago(1h)
| where customDimensions has "gen_ai.prompt"
| extend
    prompt = tostring(customDimensions["gen_ai.prompt"]),
    completion = tostring(customDimensions["gen_ai.completion"])
| project timestamp, prompt, completion
| top 10 by timestamp desc
```

This is the magic of `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED=true`.
You can read every prompt and every completion as a row in a table.

> **Deep dive · `customDimensions` vs flat columns.** App Insights stores
> OTel span attributes in a dynamic JSON column called `customDimensions`.
> Use `customDimensions["key"]` to read them, and `tostring(...)` /
> `toint(...)` to convert them out of the dynamic type. Save your favourite
> queries — KQL syntax is dense at first but pays off enormously.

---

## Troubleshooting

| Symptom                                                                                  | Cause                                                                                                                | Fix                                                                                                                                                                                       |
| ---------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `RuntimeError: APPLICATIONINSIGHTS_CONNECTION_STRING is not configured`                  | `.env` is missing the connection string.                                                                             | Follow [Prerequisites → Step 2](#step-2--get-an-application-insights-connection-string) and paste the full connection string into `.env`.                                                  |
| `RuntimeError: FOUNDRY_PROJECT_ENDPOINT is not configured`                               | `.env` is missing or still has the `<YOUR_…>` placeholder.                                                            | `cp .env.example .env` and fill in all three values. See [Prerequisites → Step 1](#step-1--configure-your-env-file).                                                                       |
| Script runs but no telemetry appears in App Insights after a few minutes                 | Most common: process exited before the batcher flushed. Less common: wrong connection string (different resource).   | Verify the `asyncio.sleep(1.0)` line at the end is in place. Double-check the connection string in `.env` exactly matches the App Insights resource you're querying.                       |
| `ModuleNotFoundError: azure.monitor.opentelemetry`                                       | The Azure Monitor exporter wheel wasn't installed.                                                                   | `pip install azure-monitor-opentelemetry opentelemetry-sdk`                                                                                                                                |
| `gen_ai.prompt` and `gen_ai.completion` columns are empty in App Insights                | `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED` is not `"true"`, or it was set *after* importing the framework.     | Confirm the line `os.environ["AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED"] = "true"` is **before** `from azure.monitor.opentelemetry import configure_azure_monitor`.                  |
| Spans land in App Insights but `operation_Id` differs per child span (no shared trace)   | The `with tracer.start_as_current_span(...)` block isn't covering the model call.                                    | Make sure the framework calls happen *inside* the `with` block. Check that no exception bypassed the block before `agent.run_stream` ran.                                                  |
| `customDimensions has "gen_ai.usage.input_tokens"` returns zero rows                     | The query was run against the wrong App Insights resource, or telemetry hasn't ingested yet (ingestion lag ≈ 1–3 min). | Verify the App Insights resource ID matches the connection string in `.env`. Wait 3 minutes and re-run.                                                                                    |

---

## Exercises — try these next

1. **Disable content recording and re-run.** Change
   `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED = "false"` and run the
   script again. Re-run **Query 4**. Note: the `gen_ai.prompt` column is
   empty but token counts (**Query 3**) are still present. Now you've felt
   the production privacy/observability trade-off firsthand.
2. **Attach a custom attribute** to the parent span. Replace the `with`
   line with:
   ```python
   with tracer.start_as_current_span("example-tracing") as span:
       span.set_attribute("workshop.user", "razi")
       span.set_attribute("workshop.iteration", 4)
   ```
   Then query: `where customDimensions has "workshop.user"`. You've just
   added a queryable tag to every run.
3. **Force a failure** in `AGENT_INSTRUCTIONS` (e.g., point at a
   non-existent model) and observe the resulting `exceptions` table rows.
   Notice how the parent span's `success` field flips to `false`.
4. **Replace `asyncio.sleep(1.0)`** with the production-grade pattern:
   ```python
   from opentelemetry import trace
   try:
       asyncio.run(main())
   finally:
       trace.get_tracer_provider().shutdown()
   ```
   Verify telemetry still arrives. This is the recipe to use in real apps.

---

## What you've learned

- The four-line snippet that turns any Python script into an
  OpenTelemetry-instrumented one: `configure_azure_monitor`,
  `get_tracer`, `start_as_current_span`, plus a graceful shutdown.
- The conceptual stack from OTel API to the Azure Monitor exporter to
  the Log Analytics tables in your subscription.
- The GenAI semantic conventions and why following them means your
  dashboards work against any framework that emits them — not just the
  Microsoft Agent Framework.
- How to drive App Insights with KQL: four queries that you'll re-use
  on every agent project you build from now on.
- The one privacy-policy switch that controls whether prompts and
  completions are persisted with your telemetry.

---

## Where to go next

You now have **eyes on every agent run**. The remaining chapters take that
visibility into more sophisticated territory:

| Next chapter                                                                                                                          | Why                                                                                                                                                                 |
| ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`05-end-to-end-agent/`](../05-end-to-end-agent/)                                                                                     | An agent that calls a JWT-protected weather API as a Python function tool — the same observability lessons apply to outgoing HTTP from your tool functions.          |
| [`06-weather-mcp-agent/`](../06-weather-mcp-agent/)                                                                                   | A weather agent backed by a **custom MCP server on Azure Functions**, with an entire KQL cookbook (`06-weather-mcp-agent/kql/observability-cookbook.md`) showing how to correlate spans across the network boundary. |
| [`azure_ai_with_observability/`](../azure_ai_with_observability/) (external)                                                          | A focused tracing sample that uses the framework with explicit `setup_observability(...)` and exporter overrides — useful if you want to send to multiple destinations. |

Onward.
