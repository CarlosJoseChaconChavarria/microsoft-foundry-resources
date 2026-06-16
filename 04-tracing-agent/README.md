# Sample 04: Observing an Agent with OpenTelemetry and Application Insights

> **You have just finished sample 03**: an agent with one local function tool
> that fires on demand. The agent works, and you have *no idea* what's
> happening inside it. Was the tool actually called? How many tokens did the
> model consume? Which prompt produced which completion? When something
> regresses next week, how will you debug it?
>
> Welcome to the lab that grows your eyes.

This lab takes the *same* basic agent from sample 01 and adds **one new
import**, **one new function call**, and **one `with` block**. In doing
so it wires the agent into **Azure Monitor Application Insights** through
the **OpenTelemetry (OTel)** SDK. Every prompt, every completion, every
model call, and every token count becomes a queryable telemetry record.

By the time you finish this lab you'll know:

- What OpenTelemetry is, why every cloud SDK now ships with it, and how the
  abstraction stack of **OTel API, OTel SDK, Azure Monitor exporter,
  Application Insights** works end to end.
- How `configure_azure_monitor()` is the *one line* that wires everything up.
- How the Agent Framework's GenAI-aware instrumentation populates
  semantic-conventions-compliant span attributes (`gen_ai.system`,
  `gen_ai.usage.input_tokens`, `gen_ai.input.messages`,
  `gen_ai.output.messages`).
- How to write **Kusto Query Language (KQL)** queries against the
  `dependencies` and `traces` tables to reconstruct an agent run.
- The privacy switch that controls whether prompts and completions are recorded
  in your telemetry, and when to flip it on or off.

---

## Table of contents

- [What you will build](#what-you-will-build)
- [Exam AI-300 mapping](#exam-ai-300-mapping)
- [Prerequisites](#prerequisites)
  - [Step 1 · Configure your `.env` file](#step-1--configure-your-env-file)
  - [Step 2 · Get an Application Insights connection string](#step-2--get-an-application-insights-connection-string)
- [Mental model: the telemetry pipeline](#mental-model-the-telemetry-pipeline)
- [Mental model: spans, traces, and the GenAI semantic conventions](#mental-model-spans-traces-and-the-genai-semantic-conventions)
- [Step-by-step code walkthrough](#step-by-step-code-walkthrough)
  - [Section 1: Imports and `.env` loader](#section-1-imports-and-env-loader)
  - [Section 2: Configuration and fail-fast checks](#section-2-configuration-and-fail-fast-checks)
  - [Section 3: The content-recording environment variables](#section-3-the-content-recording-environment-variables)
  - [Section 4: Wiring Azure Monitor and getting a tracer](#section-4-wiring-azure-monitor-and-getting-a-tracer)
  - [Section 5: The custom span around `main()`](#section-5-the-custom-span-around-main)
  - [Section 6: Why `await asyncio.sleep(2.0)` at the end](#section-6-why-await-asynciosleep20-at-the-end)
- [Running the sample](#running-the-sample)
- [Expected output (console)](#expected-output-console)
- [Querying Application Insights with KQL](#querying-application-insights-with-kql)
- [Troubleshooting](#troubleshooting)
- [Exercises, try these next](#exercises-try-these-next)
- [What you've learned](#what-youve-learned)
- [Where to go next](#where-to-go-next)

---

## What you will build

A Python script that:

1. Loads Foundry endpoint, model name, and an **Application Insights
   connection string** from a `.env` file in this folder.
2. Calls `configure_azure_monitor(...)` once at import time. That single
   call installs the entire telemetry pipeline.
3. Opens a custom `example-tracing` span as the root.
4. Inside that span, runs a one-prompt conversation against a Foundry agent.
5. Behind the scenes, the Agent Framework's built-in OTel instrumentation
   emits **GenAI semantic-convention spans** for every model call.
6. All of those spans flow over HTTPS to Application Insights, where you
   can query them with KQL. That is the same query language used by Sentinel,
   Defender for Cloud, and most of Azure Monitor.

The code change relative to sample 01 is *tiny*. The capability you unlock
is enormous: you now have a queryable record of every model interaction,
which is the foundation of every production AI system.

---

## Exam AI-300 mapping

This lab is the most directly exam-relevant lab in the workshop — observability accounts for **10–15%** of AI-300.

[Exam AI-300: Operationalizing Machine Learning and Generative AI Solutions](https://learn.microsoft.com/credentials/certifications/resources/study-guides/ai-300)

| AI-300 skill area | Specific objective | What you do in this lab |
|---|---|---|
| **Implement generative AI quality assurance and observability (10–15%)** | *Configure detailed logging, tracing, and debugging capabilities for production troubleshooting* | You add `configure_azure_monitor()` — the single line that wires every prompt, completion, and token count into Application Insights via OpenTelemetry. |
| **Implement generative AI quality assurance and observability (10–15%)** | *Monitor performance metrics, including latency, throughput, and response times* | The KQL queries in this lab reconstruct per-run latency from `dependencies` table timestamps and measure call counts across agent runs. |
| **Implement generative AI quality assurance and observability (10–15%)** | *Track and optimize cost metrics, including token consumption and resource usage* | `gen_ai.usage.input_tokens` and `gen_ai.usage.output_tokens` are OTel semantic-convention attributes the Agent Framework auto-populates. The lab shows how to query them in KQL. |
| **Implement generative AI quality assurance and observability (10–15%)** | *Examine continuous monitoring in Foundry* | Application Insights is the backend for Foundry's continuous monitoring integration — the telemetry you ship here is what the Foundry portal's monitoring dashboards consume. |

> **Exam tip.** AI-300 tests you on the OTel abstraction stack: OTel API → OTel SDK → Azure Monitor exporter → Application Insights. Know that `configure_azure_monitor(connection_string=...)` is the single call that wires all four layers, and that `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED=true` is the environment variable that controls whether prompt and completion text is included in spans (off by default for privacy).

---

## Prerequisites

| Requirement                                                                  | Why                                                                                                       |
| ---------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| **You've completed sample 01**                                               | We re-use the agent skeleton verbatim. The four building blocks are not re-explained.                      |
| **Python 3.10+**                                                             | Agent Framework uses modern `async` features.                                                              |
| **A Microsoft Foundry project** with a **gpt-4o** deployment                 | Same as previous labs.                                                                                     |
| **An Application Insights resource** attached to your Foundry project        | The destination for our telemetry. See [Step 2 below](#step-2--get-an-application-insights-connection-string). |
| **Azure CLI signed in** (`az login`)                                         | `AzureCliCredential` picks up your CLI login.                                                              |
| **A configured `.env` file in this folder**                                  | Holds three values: project endpoint, model name, App Insights connection string.                         |
| **VS Code with the Python and Azure Tools extensions** (recommended)         | One click to run. You can also open the App Insights blade from inside VS Code's Azure side panel.         |

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

> **Fail-fast behaviour.** This sample is specifically about tracing. When
> `APPLICATIONINSIGHTS_CONNECTION_STRING` is empty, the script raises a
> `RuntimeError` *before* opening any HTTP connection. Running a
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
> *Azure portal, Create a resource, Application Insights*, choose
> **Workspace-based**, attach it to any Log Analytics workspace in your
> subscription, and then optionally wire it back to the Foundry project
> under **Manage, Tracing, Enable tracing**. For this lab you only need
> the connection string. The resource can be standalone.

---

## Mental model: the telemetry pipeline

When you call `configure_azure_monitor(...)`, you assemble this pipeline in
memory inside your Python process:

```
┌──────────────────────────────────────────────────────────────────────┐
│  YOUR CODE                                                          │
│  ┌─────────────────────────────────────────────────────────────┐     │
│  │ tracer.start_as_current_span("example-tracing")            │     │
│  │   └─ Agent.run(input, stream=True)                          │     │
│  │      └─ FoundryChatClient HTTPS POST to Foundry              │     │
│  │         (Agent Framework auto-instruments this call)       │     │
│  └────────────────────────────────────────────────────────────┘     │
│                            │                                        │
│                            ▼                                        │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  OpenTelemetry API   (vendor-neutral, opentelemetry-api)   │     │
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
   the exporter. Your spans and your queries-against-spans rationale
   carry over.
2. **The Agent Framework is already instrumented.** You don't have to call
   `tracer.start_span("model_call")` around every model call. The
   framework's HTTP client emits a span automatically for every outbound
   request to Foundry, *and* enriches it with GenAI semantic conventions.
   You only need a custom span if you want to **group related work**
   (which is exactly what our `example-tracing` span does).

> **Deep dive · Why batching matters.** The exporter doesn't ship every
> span over the wire immediately. It buffers them in a `BatchSpanProcessor`
> and flushes every few seconds (or when the buffer fills). That's why a
> short script that exits in 3 seconds may emit *no telemetry at all* unless
> you give it time to drain. See [Section 6](#section-6--why-await-asynciosleep10-at-the-end).

---

## Mental model: spans, traces, and the GenAI semantic conventions

Three OTel concepts are enough to read every dashboard you'll ever see:

| Concept     | One-line definition                                                                                                          |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **Span**    | A timed operation. It has a name, a start time, an end time, attributes (key-value pairs), and optional events.               |
| **Trace**   | A tree of spans tied together by a shared `trace_id`. A parent span's `span_id` becomes a child span's `parent_span_id`.      |
| **Context** | Thread-local (or async-task-local) state that carries the *current* span so child operations attach themselves automatically. |

When you write:

```python
with tracer.start_as_current_span("example-tracing"):
    ...  # any spans created here will be children of "example-tracing"
```

the `with` block sets the context. Anything that creates a span inside,
the Agent Framework's HTTP client included, produces a child. After the
block exits, the context is restored.

For agent workloads, the [GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
define *which attributes a model-call span should carry*. The Agent
Framework follows them. Concretely, when you run this sample you will see
spans in App Insights with attributes like:

| Attribute name                       | Example value                                              | What it means                                   |
| ------------------------------------ | ---------------------------------------------------------- | ----------------------------------------------- |
| `gen_ai.provider.name`               | `azure.ai.foundry`                                         | Which provider was called.                      |
| `gen_ai.operation.name`              | `chat`                                                     | The kind of model interaction.                  |
| `gen_ai.request.model`               | `gpt-4o`                                                   | The deployment that handled this request.       |
| `gen_ai.usage.input_tokens`          | `87`                                                       | Prompt tokens billed.                           |
| `gen_ai.usage.output_tokens`         | `124`                                                      | Completion tokens billed.                       |
| `gen_ai.input.messages`              | `[{"role":"user","parts":[{"type":"text","content":"Can you tell me the gravity of Earth versus Mars?"}]}]` | JSON array of conversation messages sent to the model. Recorded **only** when content recording is on. |
| `gen_ai.output.messages`             | `[{"role":"assistant","parts":[{"type":"text","content":"Sure! On Earth gravity is approximately 9.81 m/s² ..."}]}]` | JSON array of messages produced by the model. Recorded **only** when content recording is on. |

These attributes are *exactly* what the KQL queries at the end of this
lab rely on.

---

## Step-by-step code walkthrough

Open `04-tracing-agent.py` in VS Code and read along.

### Section 1: Imports and `.env` loader

```python
import asyncio          # agent.run() is an async generator — we need asyncio.run()
import os               # os.environ reads env vars; also used to set content-recording flags
from pathlib import Path  # makes __file__-relative path construction cross-platform

from dotenv import load_dotenv  # reads .env into os.environ before anything else touches it

# Load .env from THIS folder, not the cwd — so the script works from any terminal directory.
# Framework imports (Section 4) come AFTER we set content-recording env vars in Section 3,
# because the framework reads those flags at import time.
load_dotenv(Path(__file__).resolve().parent / ".env")
```

### Section 2: Configuration and fail-fast checks

```python
ENDPOINT = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")         # Foundry project endpoint URL
MODEL    = os.environ.get("FOUNDRY_MODEL", "gpt-4o")              # deployment name; defaults to gpt-4o
APPINSIGHTS_CONN = os.environ.get(
    "APPLICATIONINSIGHTS_CONNECTION_STRING", ""
).strip()  # .strip() removes accidental whitespace from the .env value

# Fail-fast #1 (same as sample 01): catch a missing or unfilled endpoint
# before any HTTP connection is attempted.
if not ENDPOINT or "<YOUR_" in ENDPOINT:
    raise RuntimeError(
        "FOUNDRY_PROJECT_ENDPOINT is not configured. "
        "Copy .env.example to .env in this folder and fill in your Foundry "
        "project endpoint. See README.md."
    )

# Fail-fast #2 (new in sample 04): the Azure Monitor exporter silently
# disables export when given an empty connection string — producing a working
# script with zero telemetry. Loud failure here is far easier to diagnose.
if not APPINSIGHTS_CONN:
    raise RuntimeError(
        "APPLICATIONINSIGHTS_CONNECTION_STRING is not configured. "
        "This sample is specifically about tracing. Without an App Insights "
        "connection string no telemetry is exported. Get it from the Foundry "
        "portal under your project, Manage, Tracing. See README.md."
    )
```

> **Deep dive on the latent bug this guards against.** The Azure Monitor
> exporter accepts an empty connection string at initialization time and
> silently disables telemetry export. Before this guard existed, running
> the sample produced normal console output and *zero* App Insights data,
> the same symptoms as a working configuration with a query typo. The
> guard turns "silent and confusing" into "loud and obvious".

### Section 3: The content-recording environment variables

```python
os.environ["AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED"] = "true"
os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"
```

Two one-line settings that together hide an enormous policy decision
behind a pair of booleans. Both must be `true` for the agent-framework
GenAI instrumentation to write the actual prompt and completion text
into spans.

When these variables are **`false`** (the default), the framework emits
GenAI spans with *structural* attributes only: token counts, model name,
latency, success or failure. It does **not** record the actual prompt
text or completion text. This is the safe default for production systems
that may handle regulated data (PII, PHI, financial records, and so on).

When both are **`true`**, every prompt and completion is captured as the
`gen_ai.input.messages` and `gen_ai.output.messages` attributes on the
model span (each is a JSON array of role/parts objects). This is *vital*
for debugging. The moment a user reports "the agent said something
weird," you need to know *exactly* what it said.

> **Deep dive on why we flip them on here.** This is a learning sample. The
> ability to KQL-query the literal prompt and completion makes the mental
> connection between code and telemetry immediate. **In a real production
> deployment, default to `false`** and only enable for short-lived
> diagnostic sessions, scoped to non-prod environments, or with a
> downstream redaction step.

### Section 4: Wiring Azure Monitor and getting a tracer

```python
# These imports come AFTER the content-recording os.environ lines in Section 3.
# The framework reads those flags at import time — setting them later is too late.
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework.observability import enable_instrumentation  # GenAI span emitter
from azure.identity import AzureCliCredential
from azure.monitor.opentelemetry import configure_azure_monitor   # the one-call setup
from opentelemetry import trace                                   # vendor-neutral OTel API

# Single call that assembles the entire pipeline in memory:
#   TracerProvider → BatchSpanProcessor → Azure Monitor exporter → App Insights
# Also wires OTel LoggerProvider so Python logging goes to App Insights 'traces' table,
# and auto-instruments HTTP clients and database drivers.
configure_azure_monitor(connection_string=APPINSIGHTS_CONN)

# Activates agent-framework GenAI instrumentation, which emits 'invoke_agent'
# and 'chat <model>' spans with all gen_ai.* semantic-convention attributes.
# Without this call the pipeline is wired but the framework emits nothing useful.
enable_instrumentation(enable_sensitive_data=True)

# Ask the global TracerProvider for a tracer named after this module.
# __name__ shows up in App Insights under "library" attribution so you can
# tell which Python file created a span when multiple files share a trace.
tracer = trace.get_tracer(__name__)
```

> **Deep dive on why imports come after `os.environ[...] = "true"`.** The
> Agent Framework reads `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED`
> and `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` at *import
> time* to decide whether to enable content recording. Setting either
> variable after importing the framework is too late, the framework has
> already made the decision. Hence Section 3 runs before Section 4. This
> is a common gotcha. **Always set OTel-related env vars before importing
> the libraries that read them.**

### Section 5: The custom span around `main()`

```python
async def main() -> None:
    # Open a custom ROOT span for the entire run.
    # Every framework-emitted span (invoke_agent, chat gpt-4o, …) created
    # inside this block becomes a CHILD, sharing the same operation_Id.
    # In KQL you can find this run with: name == "example-tracing"
    # and then list all children via operation_Id.
    #
    # You can also attach business attributes to this span (see Exercise 2):
    #   span.set_attribute("workshop.user", "razi")
    # Those attributes appear on every child in App Insights queries.
    with tracer.start_as_current_span("example-tracing"):
        client = FoundryChatClient(   # same as sample 01 — Foundry endpoint + credential
            model=MODEL,
            project_endpoint=ENDPOINT,
            credential=AzureCliCredential(),
        )

        async with Agent(             # context-manager creates the agent and cleans up
            client=client,
            name=AGENT_NAME,
            instructions=AGENT_INSTRUCTIONS,
        ) as agent:
            for user_input in USER_INPUTS:
                # stream=True lets us print tokens as they arrive;
                # the framework emits its GenAI spans when the stream closes.
                async for chunk in await agent.run(user_input, stream=True):
                    ...
```

You'll see this `example-tracing` span at the **top** of the trace tree in
the App Insights Transaction Search blade. Its start-to-end duration is the
end-to-end latency as the user experienced it; the framework's child spans
show you *where* inside that budget the time went.

### Section 6: Why `await asyncio.sleep(2.0)` at the end

```python
print("\n--- All tasks completed successfully ---")

# Give the BatchSpanProcessor a tick to flush before the process exits.
await asyncio.sleep(2.0)
```

This is **not arbitrary**. As mentioned in the mental model, the OTel
SDK's `BatchSpanProcessor` *buffers* spans and flushes them periodically.
When your Python process exits the moment `main()` returns, **the buffer
contents are lost**.

The official cure is `tracer_provider.shutdown()`, which forces a flush.
`asyncio.sleep(2.0)` is a simpler approximation that gives the batcher
about one tick to send what it has. For a workshop sample it's fine. In
production code, call `shutdown()` in a `finally:` block.

> **Deep dive on what you'd do in production.** Register a process-exit
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
pip install agent-framework agent-framework-foundry \
    azure-monitor-opentelemetry opentelemetry-sdk python-dotenv

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
happens **in App Insights**. Keep reading.

---

## Querying Application Insights with KQL

Application Insights stores OTel telemetry across a small set of Log
Analytics tables. The two that matter for this sample:

| Table          | What it contains                                                          |
| -------------- | ------------------------------------------------------------------------- |
| `dependencies` | **Outgoing** operations: HTTP requests, model calls, tool calls, spans you create manually. Every OTel span lands here. |
| `traces`       | Python `logging` lines and OTel log records.                              |

Open the App Insights blade → **Logs**. Paste each query and click **Run**.

### Query 1: Find the run

```kql
dependencies
| where timestamp > ago(1h)
| where name == "example-tracing"
| project timestamp, name, duration, operation_Id
| top 5 by timestamp desc
```

You should see one row per execution of this script in the last hour.
**Save `operation_Id` from the most recent row.** It's the trace ID we'll
use to drill down.

### Query 2: The whole trace, in order

Azure portal Logs (multi-statement `let`):

```kql
let opId = "<paste operation_Id from Query 1>";
dependencies
| where operation_Id == opId
| order by timestamp asc
| project timestamp, name, duration, type
```

Foundry portal Tracing KQL pane (single statement, uses `toscalar` to pin
the latest run):

```kql
dependencies
| where timestamp > ago(1h)
| where operation_Id == toscalar(
    dependencies
    | where timestamp > ago(1h)
    | where name == "example-tracing"
    | top 1 by timestamp desc
    | project operation_Id)
| order by timestamp asc
| project timestamp, name, duration, type
```

This reproduces the entire trace tree, top to bottom. You should see the
parent `example-tracing` span followed by one or more framework-emitted
GenAI spans (typical names: `chat`, `chat gpt-4o`, or similar).

### Query 3: Token usage

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
yesterday?"* with a one-line aggregation. `summarize sum(input_tokens),
sum(output_tokens) by bin(timestamp, 1h)`.

### Query 4: Prompt and completion text

The current agent-framework writes prompts and completions using the OTel
GenAI semantic-convention attributes `gen_ai.input.messages` and
`gen_ai.output.messages`. Both are **JSON strings** holding an array of
`{role, parts: [{type, content}]}` objects, not flat text.

```kql
dependencies
| where timestamp > ago(1h)
| where name startswith "chat "
| where customDimensions has "gen_ai.input.messages"
| extend
    input_messages  = todynamic(tostring(customDimensions["gen_ai.input.messages"])),
    output_messages = todynamic(tostring(customDimensions["gen_ai.output.messages"]))
| extend
    user_prompt = tostring(input_messages[array_length(input_messages) - 1].parts[0].content),
    assistant_reply = tostring(output_messages[0].parts[0].content)
| project timestamp, user_prompt, assistant_reply
| top 10 by timestamp desc
```

A few notes:

- Filter on `name startswith "chat "` (the model-call span) to avoid the
  parent `invoke_agent` span, which carries the same content and would
  double the rows.
- `gen_ai.input.messages` contains the **whole conversation history** sent
  to the model. The example pulls the last message (the user turn). Drop
  the last-index expression to see the full array.
- When you want the raw JSON instead of a parsed field, just
  `project timestamp, input=tostring(customDimensions["gen_ai.input.messages"]),
  output=tostring(customDimensions["gen_ai.output.messages"])`.

> **Why not `gen_ai.prompt` / `gen_ai.completion`?** Older versions of the
> OTel GenAI conventions used those flat-string attributes. The current
> spec, which agent-framework follows, replaced them with structured
> `gen_ai.input.messages` / `gen_ai.output.messages` arrays so multi-turn
> conversations, tool calls, and multi-modal content can all be captured
> losslessly.

> **Deep dive on `customDimensions` vs flat columns.** App Insights stores
> OTel span attributes in a dynamic JSON column called `customDimensions`.
> Use `customDimensions["key"]` to read them, and `tostring(...)`,
> `toint(...)`, or `todynamic(...)` to convert them out of the dynamic
> type. Save your favourite queries. KQL syntax is dense at first but
> pays off enormously.

---

## Troubleshooting

| Symptom                                                                                  | Cause                                                                                                                | Fix                                                                                                                                                                                       |
| ---------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `RuntimeError: APPLICATIONINSIGHTS_CONNECTION_STRING is not configured`                  | `.env` is missing the connection string.                                                                             | Follow [Prerequisites → Step 2](#step-2--get-an-application-insights-connection-string) and paste the full connection string into `.env`.                                                  |
| `RuntimeError: FOUNDRY_PROJECT_ENDPOINT is not configured`                               | `.env` is missing or still has the `<YOUR_…>` placeholder.                                                            | `cp .env.example .env` and fill in all three values. See [Prerequisites → Step 1](#step-1--configure-your-env-file).                                                                       |
| Script runs but no telemetry appears in App Insights after a few minutes                 | Most common: process exited before the batcher flushed. Less common: wrong connection string (different resource).   | Verify the `asyncio.sleep(2.0)` line at the end is in place. Double-check the connection string in `.env` exactly matches the App Insights resource you're querying.                       |
| `ModuleNotFoundError: azure.monitor.opentelemetry`                                       | The Azure Monitor exporter wheel wasn't installed.                                                                   | `pip install azure-monitor-opentelemetry opentelemetry-sdk`                                                                                                                                |
| `gen_ai.input.messages` and `gen_ai.output.messages` columns are empty in App Insights                | Either `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED` or `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` is not `"true"`, or one was set *after* importing the framework.     | Confirm both `os.environ["AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED"] = "true"` and `os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"` run **before** `from agent_framework import Agent` and `from azure.monitor.opentelemetry import configure_azure_monitor`. Also verify `enable_instrumentation(enable_sensitive_data=True)` was called. |
| Spans land in App Insights but `operation_Id` differs per child span (no shared trace)   | The `with tracer.start_as_current_span(...)` block isn't covering the model call.                                    | Make sure the framework calls happen *inside* the `with` block. Check that no exception bypassed the block before `await agent.run(..., stream=True)` ran.                                                  |
| `customDimensions has "gen_ai.usage.input_tokens"` returns zero rows                     | The query was run against the wrong App Insights resource, or telemetry hasn't ingested yet (ingestion lag is roughly 1 to 3 min). | Verify the App Insights resource ID matches the connection string in `.env`. Wait 3 minutes and re-run.                                                                                    |

---

## Exercises, try these next

1. **Disable content recording and re-run.** Change
   `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED = "false"` and run the
   script again. Re-run **Query 4**. Note: the `gen_ai.input.messages`
   column is empty but token counts (**Query 3**) are still present. Now
   you've felt the production privacy and observability trade-off firsthand.
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
  dashboards work against any framework that emits them, not just the
  Microsoft Agent Framework.
- How to drive App Insights with KQL: four queries that you'll re-use
  on every agent project you build from now on.
- The one privacy-policy switch that controls whether prompts and
  completions are persisted with your telemetry.

---

## Where to go next

You now have **eyes on every agent run**. The remaining labs take that
visibility into more sophisticated territory:

| Next lab                                                                                                                              | Why                                                                                                                                                                 |
| ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`05-end-to-end-agent/`](../05-end-to-end-agent/)                                                                                     | An agent that calls a JWT-protected weather API as a Python function tool. The same observability lessons apply to outgoing HTTP from your tool functions.          |
| [`06-weather-mcp-agent/`](../06-weather-mcp-agent/)                                                                                   | A weather agent backed by a **custom MCP server on Azure Functions**, with an entire KQL cookbook (`06-weather-mcp-agent/kql/observability-cookbook.md`) showing how to correlate spans across the network boundary. |
| [`azure_ai_with_observability/`](../azure_ai_with_observability/) (external)                                                          | A focused tracing sample that uses the framework with explicit `setup_observability(...)` and exporter overrides. Useful when you want to send to multiple destinations. |

Onward.
