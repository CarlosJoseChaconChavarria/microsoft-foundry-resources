# Sample 02 · An agent that calls tools (Model Context Protocol)

> **What this lab teaches.** In sample 01 you built an agent that could
> only *talk*. Here you'll give an agent its first **tool** so it can
> actually *do* something — specifically, search the Microsoft Learn
> documentation library through the **Model Context Protocol (MCP)**.
> Along the way you'll learn three different patterns for *defining* an
> agent: **pure-code**, **portal-first**, and **hybrid (GitOps)** — and
> when to use each.

**Time to complete:** 25 minutes (10 min for variant A, +5 min each for B and C)
**Difficulty:** ⭐⭐ Intermediate — assumes you've completed sample 01
**Files in this folder:** 3 runnable Python files + 2 helper modules

---

## Table of contents

- [What you will learn](#what-you-will-learn)
- [Prerequisites](#prerequisites)
- [Three patterns at a glance](#three-patterns-at-a-glance)
- [What is the Model Context Protocol?](#what-is-the-model-context-protocol)
- [Variant A · `02-mcp-tool-agent.py` (pure code)](#variant-a--02-mcp-tool-agentpy-pure-code)
  - [Code walkthrough](#code-walkthrough)
  - [Running it](#running-it)
  - [Expected output](#expected-output)
- [Variant B · `02b-portal-agent.py` (portal-first)](#variant-b--02b-portal-agentpy-portal-first)
  - [How to build the portal agent](#how-to-build-the-portal-agent)
  - [Code walkthrough](#code-walkthrough-1)
  - [Running it](#running-it-1)
- [Variant C · `02c-hybrid-agent.py` (hybrid / GitOps)](#variant-c--02c-hybrid-agentpy-hybrid--gitops)
  - [Code walkthrough](#code-walkthrough-2)
  - [Running it](#running-it-2)
  - [Cleaning up the portal agent](#cleaning-up-the-portal-agent)
- [Observability — `_observability.py` explained](#observability--_observabilitypy-explained)
- [The shared `.env` file](#the-shared-env-file)
- [Verifying traces with `verify_observability.py`](#verifying-traces-with-verify_observabilitypy)
- [Troubleshooting](#troubleshooting)
- [Exercises](#exercises)
- [What you've learned](#what-youve-learned)
- [Where to go next](#where-to-go-next)

---

## What you will learn

By the end of this lab you will be able to:

1. **Explain MCP** — what it is, what problem it solves, and how it differs
   from "the agent calls a Python function".
2. **Attach a remote MCP server** as a tool to a Foundry agent in three lines.
3. **Choose the right pattern** (code vs portal vs hybrid) for defining
   agents in production.
4. **Read a `FoundryChatClient` vs `AzureAIAgentClient`** — and explain why
   they coexist.
5. **Light up Application Insights tracing** so every prompt, completion,
   and tool call becomes a queryable span.

---

## Prerequisites

| Requirement                                                          | Why                                                                                                                                                |
| -------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| **You've completed sample 01**                                       | The four building blocks (credential, client, agent, thread) are not re-explained here.                                                            |
| **Python 3.10+**                                                     | Required by the framework.                                                                                                                          |
| **A Microsoft Foundry project** with a **gpt-4o** deployment         | Same as sample 01.                                                                                                                                  |
| **Azure CLI signed in** (`az login`)                                 | All three variants use `AzureCliCredential` so the CLI session is the auth source.                                                                  |
| **An Application Insights resource attached to your Foundry project** | For tracing. Find it via **Foundry portal → your project → Manage → Tracing**. Optional — the samples run without it but emit no telemetry.         |
| **VS Code with the Python and Azure Tools extensions** (recommended) | The integrated terminal hosts every command in this lab.                                                                                            |

> **Note.** All three variants in this folder share one `.env` file. Copy
> `.env.example` to `.env` once and you're set for the whole lab.

---

## Three patterns at a glance

Picture this folder as **three solutions to the same problem**: *"I want
an agent that can search Microsoft Learn."* All three end up calling the
same MCP server (`https://learn.microsoft.com/api/mcp`) — they just disagree
on **where the agent definition lives**.

```
                           Where does the agent definition live?

                  ┌────────────────────────────────────────────────────────────┐
                  │                                                            │
                  │   Pure code (02)         Portal (02b)        Hybrid (02c)  │
                  │   ────────────────       ─────────────       ────────────  │
                  │                                                            │
   Source of      │   the .py file ✓         the portal UI ✓      the .py file ✓
   truth          │                                                            │
                  │                                                            │
   Visible in     │   ✗ (ephemeral)          ✓ (you built it)     ✓ (auto-     │
   portal?        │                                              │     created) │
                  │                                                            │
   Persists       │   ✗ deleted on exit      ✓ stays forever     ✓ stays      │
   between runs?  │                                              │  forever     │
                  │                                                            │
   Audit trail?   │   ✗                      portal only          ✓ git diff +  │
                  │                                              │  portal      │
                  │                                              │  versioning  │
                  │                                                            │
   Best for       │   demos, scripts,        agent built by a    real teams    │
                  │   getting started        non-developer        shipping code │
                  │                                                            │
                  └────────────────────────────────────────────────────────────┘
```

**Rule of thumb for production:**
- **02 (pure code)** when the agent is short-lived (a CI job, a test, a one-off batch).
- **02b (portal-first)** when a non-developer (a domain expert) writes prompts and tools.
- **02c (hybrid)** when an engineering team owns the agent and wants the portal as a *read-only mirror* of git.

---

## What is the Model Context Protocol?

**MCP is a JSON-RPC protocol** that lets a language model discover and call
*tools* hosted on a server, without the model — or the agent code —
needing per-tool client code.

```
   ┌──────────────────┐        JSON-RPC 2.0 over HTTPS         ┌────────────────────┐
   │  Foundry agent   │                                         │   MCP server       │
   │  (gpt-4o brain)  │ ─── tools/list ───────────────────────► │   (Microsoft Learn)│
   │                  │ ◄────────── tool schemas ──────────── ──│                    │
   │                  │                                         │   exposes:         │
   │                  │ ─── tools/call ──── { name, args } ────►│   • search_docs    │
   │                  │ ◄────────── tool result ──────────── ──│   • fetch_page     │
   │                  │                                         │   • …              │
   └──────────────────┘                                         └────────────────────┘

   The model never sees JSON-RPC. It just sees "you have these tools".
   The agent never sees per-tool code. It just sees "the model wants me to call X."
```

**Why this matters for you as a Foundry user:**

1. **One protocol, every tool.** Once the agent speaks MCP, you can attach
   *any* MCP server (Microsoft Learn, GitHub, Slack, your own) with a single
   line of configuration. No client SDK per tool.
2. **Discovery at runtime.** The agent asks the server "what tools do you
   have?" and the model sees those tools' descriptions on the very next
   turn. You can ship new tools without changing client code.
3. **Standardisation.** Anthropic, OpenAI, and Microsoft all support MCP.
   The MCP server you build today is portable.

> **Curious about a deeper dive?** Sample 06 in this repo (`06-weather-mcp-agent/`)
> walks you through **building your own MCP server** on Azure Functions.
> This sample just *consumes* one.

---

## Variant A · `02-mcp-tool-agent.py` (pure code)

The agent's entire definition lives in the file. When you run the script,
the agent is constructed in memory, sent to the LLM for one or more turns,
and discarded.

### Code walkthrough

Open [`02-mcp-tool-agent.py`](02-mcp-tool-agent.py) side-by-side.

#### Imports (lines 12–19)

```python
import asyncio
import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential

from _observability import init_observability
```

| Line | Import                                                  | What it does                                                                                                                                                                                                                                                                                                          |
| ---- | ------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 15   | `from agent_framework import Agent`                     | A simpler `Agent` class (vs sample 01's `ChatAgent`). Same idea, slightly different API surface — the `Agent` class is the path you'll see in newer Agent Framework docs.                                                                                                                                                |
| 16   | `from agent_framework.foundry import FoundryChatClient` | **A different client than sample 01 used.** This one talks to the newer **Foundry Inference** endpoint rather than the legacy **Azure AI Agents** endpoint. `FoundryChatClient` is what unlocks `get_mcp_tool()` (see line 51).                                                                                       |
| 17   | `from azure.identity import AzureCliCredential`         | Synchronous CLI credential. We use the sync one (not `.aio`) because `FoundryChatClient` accepts both — and the sync one removes the need for `async with` ceremony on the credential.                                                                                                                                |
| 19   | `from _observability import init_observability`         | The shared observability module — see [its dedicated section below](#observability--_observabilitypy-explained).                                                                                                                                                                                                       |

> **Deep dive · Why two different clients in the same framework?** Microsoft
> Foundry is in active evolution. The **`AzureAIAgentClient`** (sample 01)
> talks to the **Azure AI Agents** REST surface — stable, deployed-agent
> oriented, MCP-aware in preview. The **`FoundryChatClient`** talks to the
> **Foundry Inference** REST surface — newer, stateless, **MCP-first**, and
> the path the platform is converging on. Both are supported. Use
> `FoundryChatClient` when you need `get_mcp_tool()` (today, in GA).

#### Configuration (lines 21–36)

```python
PROJECT_ENDPOINT = os.environ.get(
    "FOUNDRY_PROJECT_ENDPOINT",
    "https://<YOUR_FOUNDRY_RESOURCE>.services.ai.azure.com/api/projects/<YOUR_PROJECT_NAME>",
)
MODEL = os.environ.get("FOUNDRY_MODEL", "gpt-4o")

AGENT_NAME = "mcp-learn-agent-codefirst"
AGENT_INSTRUCTIONS = "You answer questions by searching Microsoft Learn content only."

USER_INPUTS = [
    "Please summarize the Azure AI Agent documentation related to MCP tool calling?",
]
```

Note the **`os.environ.get`** pattern with a fallback. The fallback is the
placeholder URL; the real value comes from `.env`. This is the right
production pattern: code is environment-agnostic, configuration is
environment-specific.

#### Initialise observability (line 40)

```python
async def main() -> None:
    init_observability("pure-code")
```

One line and every span this process emits goes to Application Insights,
tagged with `cloud_RoleName = "foundry-workshop.pure-code"`. The full
mechanics are explained [further down](#observability--_observabilitypy-explained).

#### Create the client (lines 42–46)

```python
    client = FoundryChatClient(
        model=MODEL,
        project_endpoint=PROJECT_ENDPOINT,
        credential=AzureCliCredential(),
    )
```

No `async with` this time, because the client doesn't own enough resources
to justify it. (We'll still tear down the *agent* with an async context
manager on line 57.)

#### Define the MCP tool (lines 51–55)

```python
    mcp_tool = client.get_mcp_tool(
        name="Microsoft Learn MCP",
        url="https://learn.microsoft.com/api/mcp",
        approval_mode="never_require",
    )
```

This is the heart of the sample. Three arguments:

| Argument         | What it does                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`           | Cosmetic label that appears in traces and the portal's tool view.                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `url`            | The MCP endpoint. **No authentication is needed** for the Microsoft Learn MCP — it's a public read-only service. Your own MCP servers (like sample 06's `get_weather`) will require an Authorization header; that's covered in sample 06's lab.                                                                                                                                                                                                                                       |
| `approval_mode`  | The most important argument. Three values: <br>• `"never_require"` — auto-approve every tool call. Safe for **read-only public** tools like Microsoft Learn search.<br>• `"always_require"` — every tool call pauses for explicit human approval. Use for any tool that **writes** or **costs money**.<br>• A `dict` mapping tool name → mode for per-tool granularity.                                                                                                                |

> **Deep dive · The single most important security question for tools is:
> "what happens if the model calls this with bad arguments?"** Use
> `approval_mode="never_require"` *only* when the answer is "nothing bad,
> ever". Search is fine. `delete_user(id)` is not.

#### Wire up the agent (lines 57–66)

```python
    async with Agent(
        client=client,
        name=AGENT_NAME,
        instructions=AGENT_INSTRUCTIONS,
        tools=[mcp_tool],
    ) as agent:
        for user_input in USER_INPUTS:
            print(f"\n# User: '{user_input}'")
            result = await agent.run(user_input)
            print(f"# {AGENT_NAME}: {result}\n")
```

Two things to notice:

1. **`tools=[mcp_tool]`** — the *only* difference from sample 01 in
   structural terms. Adding a tool is genuinely one line.
2. **`await agent.run(user_input)`** — we used `run_stream` in sample 01;
   here we use the blocking `run()` to keep the loop body to two lines. For
   tool calls especially, `run()` returns *after* every back-and-forth with
   the model and the tool server has settled — you get the final answer.

### Running it

```bash
# 1. From this folder:
cd 02-mcp-tool-agent

# 2. Activate a venv and install
python -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install agent-framework agent-framework-azure-ai azure-monitor-opentelemetry python-dotenv --pre

# 3. Configure .env (one-time)
cp .env.example .env
# Now open .env in VS Code and fill in:
#   FOUNDRY_PROJECT_ENDPOINT
#   APPLICATIONINSIGHTS_CONNECTION_STRING (optional but recommended)
#   AZURE_TENANT_ID

# 4. Sign in to Azure
az login --tenant <YOUR_TENANT_ID>

# 5. Run
python 02-mcp-tool-agent.py
```

### Expected output

```
[observability] ✓ enabled  scenario='pure-code'  → Application Insights

# User: 'Please summarize the Azure AI Agent documentation related to MCP tool calling?'
# mcp-learn-agent-codefirst: The Azure AI Agent documentation describes Model
Context Protocol (MCP) tool calling as follows:

1. **MCP Overview** — MCP is an open standard that lets agents discover and
   invoke tools hosted on external servers without per-tool client code…

2. **Configuration** — You attach an MCP server to an agent by providing its
   URL and an approval policy (`require_approval`)…

3. **Authentication** — MCP servers can be public (like Microsoft Learn) or
   protected. For protected servers, configure custom headers or use
   Microsoft Entra…

(continues with cited Microsoft Learn pages…)

--- All tasks completed successfully ---
Program finished.
```

The model produces text *and* you can see in the Application Insights logs
(or in the Foundry portal's Tracing tab) that one `agent.run` produced two
HTTP dependencies: one to gpt-4o and one to `https://learn.microsoft.com/api/mcp`.

---

## Variant B · `02b-portal-agent.py` (portal-first)

In this variant, **the agent definition lives entirely in the Foundry
portal UI**. The Python code only knows the agent's *name* and *version*.

This is the pattern to use when a non-developer (a product manager, a
domain expert) writes the prompt and chooses the tools, and a developer
just needs to invoke it from code.

### How to build the portal agent

Before running `02b-portal-agent.py`, **create the agent in the portal**:

1. Open [https://ai.azure.com](https://ai.azure.com) and select your project.
2. Click **Agents** in the left rail → **+ Create**.
3. Fill in:
   - **Name:** `mcp-learn-agent-portal` (or whatever you prefer)
   - **Model:** `gpt-4o`
   - **Instructions:** *"You are a Microsoft Learn research assistant. Cite the pages you used."*
4. Click **+ Add tool** → **MCP server**, and configure:
   - **Server label:** `MicrosoftLearn`
   - **Server URL:** `https://learn.microsoft.com/api/mcp`
   - **Require approval:** Never
5. Click **Create**. The portal shows your agent with version **1**.

### Code walkthrough

Open [`02b-portal-agent.py`](02b-portal-agent.py).

#### Imports (lines 24–30)

```python
import asyncio
import os

from agent_framework.foundry import FoundryAgent
from azure.identity import AzureCliCredential

from _observability import init_observability
```

The headline change: **`FoundryAgent`** instead of the `Agent + Client +
get_mcp_tool` trio. `FoundryAgent` is purpose-built for "load an existing
portal agent by name and version".

#### Configuration (lines 32–46)

```python
PROJECT_ENDPOINT = os.environ.get(
    "FOUNDRY_PROJECT_ENDPOINT",
    "https://<YOUR_FOUNDRY_RESOURCE>.services.ai.azure.com/api/projects/<YOUR_PROJECT_NAME>",
)

AGENT_NAME = os.environ.get("PORTAL_AGENT_NAME", "<YOUR_PORTAL_AGENT_NAME>")
AGENT_VERSION = os.environ.get("PORTAL_AGENT_VERSION", "1")

USER_INPUTS = [
    "In one short sentence, tell me what kinds of questions you are designed to answer.",
]
```

Notice the **complete absence of instructions, tools, or model**. The whole
agent definition is on the server side. The script knows only the agent's
*identity*: `(name, version)`.

#### The runtime (lines 49–65)

```python
async def main() -> None:
    init_observability("portal-first")
    print(f"Connecting to portal agent: {AGENT_NAME} (version {AGENT_VERSION})\n")

    agent = FoundryAgent(
        project_endpoint=PROJECT_ENDPOINT,
        agent_name=AGENT_NAME,
        agent_version=AGENT_VERSION,
        credential=AzureCliCredential(),
    )

    for user_input in USER_INPUTS:
        print(f"# User: {user_input}\n")
        result = await agent.run(user_input)
        print(f"# {AGENT_NAME}:\n{result}\n")
```

The `FoundryAgent` constructor takes four arguments and *that's it*. The
project endpoint tells it where the agent lives; `agent_name` + `agent_version`
identify which one to load; `credential` is your CLI session.

> **Deep dive · Versions are immutable.** Each time you edit and save the
> agent in the portal, the portal creates a **new version**. You pin your
> code to `agent_version="1"` (or `"2"`, …) so a portal edit never silently
> changes your script's behaviour. To pick up the latest version, bump the
> env var or write `agent_version="latest"` (the framework resolves it for
> you on each call).

### Running it

```bash
# In the same folder as variant A; the same venv works.
# Add PORTAL_AGENT_NAME=<your agent name> to .env, then:
python 02b-portal-agent.py
```

**Expected output:**

```
[observability] ✓ enabled  scenario='portal-first'  → Application Insights
Connecting to portal agent: mcp-learn-agent-portal (version 1)

# User: In one short sentence, tell me what kinds of questions you are designed to answer.

# mcp-learn-agent-portal:
I'm designed to answer questions about Microsoft technologies (Azure, .NET, M365,
etc.) by searching the official Microsoft Learn documentation library.

--- All tasks completed successfully ---
Program finished.
```

Now go back to the portal, edit the agent's instructions to say *"…in
pirate slang…"*, save (creates version 2), bump
`PORTAL_AGENT_VERSION=2` in `.env`, and re-run. Same code, completely new
personality. **That's the value of portal-first.**

---

## Variant C · `02c-hybrid-agent.py` (hybrid / GitOps)

This is the **production pattern**. The agent definition is **in your
git-tracked Python file**, but it's *also* registered server-side so the
portal can show it, audit it, and let you query its versions.

The first run of the script creates the agent in the portal. Subsequent
runs reuse it. Editing the in-file `AGENT_DEFINITION` and re-running adds
a new server-side version — the portal becomes a *mirror* of git, not the
source of truth.

### Code walkthrough

Open [`02c-hybrid-agent.py`](02c-hybrid-agent.py).

#### The agent definition in code (lines 59–75)

```python
AGENT_DEFINITION = {
    "kind": "prompt",
    "model": "gpt-4o",
    "instructions": (
        "You are a Microsoft Learn research assistant. "
        "Use the MicrosoftLearn MCP tool to answer questions about Azure and "
        "Microsoft technologies, citing the Microsoft Learn pages you used."
    ),
    "tools": [
        {
            "type": "mcp",
            "server_label": "MicrosoftLearn",
            "server_url": "https://learn.microsoft.com/api/mcp",
            "require_approval": "never",
        }
    ],
}
```

This dict is the JSON body the Foundry **agents REST API** expects. Notice
it captures everything: model, system prompt, every tool, the approval
policy. Anything you can build in the portal UI you can express here.

> **Deep dive · Why a literal dict instead of an SDK object?** The Agent
> Framework intentionally keeps this raw — the schema is governed by the
> Foundry REST API version (`2025-11-15-preview` on line 53), and exposing
> a typed wrapper would slow down new feature adoption. Trade-off: a typo
> in a key gives you an HTTP 400 instead of a Python error. Pin your
> `API_VERSION` and stick to documented field names.

#### Idempotent server-side registration (lines 82–106)

```python
async def ensure_agent(token: str) -> str:
    """Create the agent if missing; otherwise reuse the latest version."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    params = {"api-version": API_VERSION}
    base = f"{PROJECT_ENDPOINT}/agents"

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        # Check if it exists.
        get_resp = await client.get(f"{base}/{AGENT_NAME}", params=params)
        if get_resp.status_code == 200:
            version = get_resp.json()["versions"]["latest"]["version"]
            print(f"  ↳ found existing agent in portal, latest version = {version}")
            return version

        # Create it server-side from the in-code definition.
        print(f"  ↳ agent not found, creating from in-code definition...")
        create_resp = await client.post(
            base,
            params=params,
            json={"name": AGENT_NAME, "definition": AGENT_DEFINITION},
        )
        create_resp.raise_for_status()
        version = create_resp.json()["versions"]["latest"]["version"]
        print(f"  ↳ created agent '{AGENT_NAME}' version {version} in portal")
        return version
```

This helper implements the classic **CRUD-as-Code** pattern:

1. **GET** the agent by name. If it returns 200, the agent already exists —
   read out the latest version and return it.
2. **POST** otherwise. The body has `{name, definition}`; the server
   creates the agent and returns version `"1"`.

> **Deep dive · Why hand-roll `httpx` instead of the SDK?** The SDK does
> not yet expose a `create_agent_from_definition` helper at the
> `2025-11-15-preview` API version. So we drop down one layer. This is
> *normal*. Every Azure SDK has features the underlying REST API ships
> first; until they're wrapped, REST calls are a fine workaround — and a
> good way to learn the shape of the platform.

#### The main flow (lines 109–132)

```python
async def main() -> None:
    init_observability("hybrid")
    print(f"Hybrid pattern: code defines '{AGENT_NAME}', server hosts it.\n")

    credential = AzureCliCredential()
    token = credential.get_token("https://ai.azure.com/.default").token

    agent_version = await ensure_agent(token)
    print()

    agent = FoundryAgent(
        project_endpoint=PROJECT_ENDPOINT,
        agent_name=AGENT_NAME,
        agent_version=agent_version,
        credential=credential,
    )

    for user_input in USER_INPUTS:
        print(f"# User: {user_input}\n")
        result = await agent.run(user_input)
        print(f"# {AGENT_NAME}:\n{result}\n")
```

Sequence:

1. Get an Azure token with audience `https://ai.azure.com/.default`. This
   is the right audience for the **agents REST API**.
2. Call `ensure_agent()` which either reuses or creates the server-side
   record and returns the latest version string.
3. Use the same `FoundryAgent` invocation pattern as variant B to run a
   prompt.

### Running it

```bash
# Same venv as A and B; just install the one extra dep:
pip install httpx
python 02c-hybrid-agent.py
```

**First run output:**

```
[observability] ✓ enabled  scenario='hybrid'  → Application Insights
Hybrid pattern: code defines 'mcp-learn-agent-hybrid', server hosts it.

  ↳ agent not found, creating from in-code definition...
  ↳ created agent 'mcp-learn-agent-hybrid' version 1 in portal

# User: Please summarize the Azure AI Agent documentation related to MCP tool calling?

# mcp-learn-agent-hybrid:
The Azure AI Agent documentation describes MCP (Model Context Protocol)
tool calling as follows…
```

**Second run** (no code change):

```
  ↳ found existing agent in portal, latest version = 1
```

**Third run**, after editing `AGENT_DEFINITION["instructions"]`:

```
  ↳ found existing agent in portal, latest version = 1
```

*Wait — why didn't the version bump?* Because the current `ensure_agent`
helper does **read-or-create**, not **upsert with new version**. To trigger
a new version, you'd add a `PUT` branch when the local definition hash
differs from the server's. That's a great exercise — see [Exercises](#exercises).

### Cleaning up the portal agent

The agent created by 02c **persists in your portal** until you delete it.
That's intentional (audit trail). To remove it:

```bash
TOKEN=$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv)
curl -X DELETE \
  -H "Authorization: Bearer $TOKEN" \
  "$FOUNDRY_PROJECT_ENDPOINT/agents/mcp-learn-agent-hybrid?api-version=2025-11-15-preview"
```

Same goes for the agent you built by hand in variant B — delete it from
the portal's Agents panel when you're done with the workshop.

---

## Observability — `_observability.py` explained

All three variants begin with `init_observability("<scenario>")`. That
single call configures **OpenTelemetry** for the whole process so every
HTTP call, every agent run, every model call, and every MCP tool
invocation emits a queryable span to Application Insights.

Open [`_observability.py`](_observability.py) and walk through it:

### Step 1 — Read `.env` (lines 52–57)

```python
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:
    pass
```

`load_dotenv` reads `.env` from the *same folder as this file* (not the
current working directory). That's why moving the script into this folder
required no path-handling — the `.env` you put alongside `_observability.py`
is the one that gets loaded.

### Step 2 — Bail out if the connection string is missing (lines 59–65)

```python
conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
if not conn:
    print("[observability] skipped — APPLICATIONINSIGHTS_CONNECTION_STRING is not set. …")
    return
```

**Silent-noop pattern.** If you didn't set the connection string, the
samples still run; they just don't emit traces. That keeps the *first*
experience low-friction.

### Step 3 — Tag every span with a scenario label (lines 67–74)

```python
os.environ.setdefault("OTEL_SERVICE_NAME", f"foundry-workshop.{scenario}")
os.environ.setdefault("OTEL_RESOURCE_ATTRIBUTES", f"workshop.scenario={scenario}")
os.environ.setdefault("AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED", "true")
os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "true")
```

| Env var                                                  | What it does                                                                                                                                                                              |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `OTEL_SERVICE_NAME`                                      | Maps to the **`cloud_RoleName`** column in Application Insights. You filter by this in KQL.                                                                                                |
| `OTEL_RESOURCE_ATTRIBUTES`                               | Free-form resource tags. Surfaces as `customDimensions` in App Insights.                                                                                                                  |
| `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED=true`    | **Captures prompt and completion content** in spans. Off by default for privacy reasons. *Turn it on for workshops; turn it off for any data with regulated PII.*                          |
| `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` | The OTel GenAI semconv equivalent of the same setting — present so OTel-aware tools (not just App Insights) see the content too.                                                          |

> **Deep dive · Setting via `os.environ.setdefault`.** This means *"only set
> if not already set"*. So if a user puts these in `.env` with different
> values, those win. The module is good behaviour: opinionated defaults,
> user values respected.

### Step 4 — Wire OTel to Azure Monitor (lines 76–80)

```python
from agent_framework.observability import enable_instrumentation
from azure.monitor.opentelemetry import configure_azure_monitor

configure_azure_monitor(connection_string=conn)
enable_instrumentation(enable_sensitive_data=True)
```

Two libraries collaborate:

- **`configure_azure_monitor`** wires the global OTel SDK to the Azure
  Monitor exporter. After this call, every span emitted by *anything* in
  the process — your code, urllib, HTTPX, the Agent Framework, the OpenAI
  SDK — is exported to App Insights.
- **`enable_instrumentation`** is the Agent Framework's own hook that turns
  on **GenAI-specific** semantic attributes (token counts, model name,
  tool-call name and arguments). Without it you'd see HTTP spans but no
  GenAI-flavoured spans.

### The KQL view

Once traces are flowing, this is the canonical *"show me every workshop
run, by scenario"* query. Run it in the **Foundry portal → Tracing →
KQL** tab, or in your Application Insights resource directly:

```kql
dependencies
| where timestamp > ago(15m)
| where cloud_RoleName startswith "foundry-workshop."
| project timestamp, scenario=tostring(customDimensions["workshop.scenario"]),
          name, duration, customDimensions
| order by timestamp desc
```

You'll see one row per HTTP dependency, tagged with which variant
(`pure-code`, `portal-first`, `hybrid`) emitted it.

---

## The shared `.env` file

[`.env.example`](.env.example) lists every variable used by the variants
and the helpers in this folder. Copy it to `.env` and fill in your values.

| Variable                                       | Used by             | What to put                                                                                                  |
| ---------------------------------------------- | ------------------- | ------------------------------------------------------------------------------------------------------------ |
| `FOUNDRY_PROJECT_ENDPOINT`                     | A, B, C             | Your Foundry project endpoint URL.                                                                            |
| `FOUNDRY_MODEL`                                | A                   | The deployment name for gpt-4o.                                                                              |
| `AZURE_TENANT_ID`                              | (your shell)        | For `az login --tenant <id>` to avoid signing into the wrong directory.                                       |
| `PORTAL_AGENT_NAME`                            | B                   | Name of the agent you built in the portal.                                                                    |
| `PORTAL_AGENT_VERSION`                         | B                   | Usually `1` on first creation.                                                                                |
| `APPLICATIONINSIGHTS_CONNECTION_STRING`        | A, B, C             | Optional. Without it, scripts run but emit no traces.                                                         |
| `APPLICATIONINSIGHTS_SUBSCRIPTION_ID/RG/NAME`  | `verify_observability.py` | Needed by the verification helper (next section).                                                       |

`.env` is **gitignored** (the repo's `.gitignore` covers it). Treat it like
a secret file.

---

## Verifying traces with `verify_observability.py`

The repo ships a smoke-test script that runs a KQL query against your
Application Insights and confirms it sees at least one span from each
scenario:

```bash
python verify_observability.py
```

It needs the three `APPLICATIONINSIGHTS_*` variables from `.env` to know
which resource to query. Useful as a CI step or right after first setup.

---

## Troubleshooting

| Symptom                                                                                                | Cause                                                                                          | Fix                                                                                                                                                                                              |
| ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `AADSTS65001: The user or administrator has not consented to use the application` from `AzureCliCredential` | The Foundry-bound app needs consent in your tenant.                                              | Run `az login --tenant <YOUR_TENANT_ID>` once. If problems persist, ask a tenant admin to grant consent (rare for first-party apps).                                                              |
| `[observability] skipped …`                                                                            | `APPLICATIONINSIGHTS_CONNECTION_STRING` is empty in `.env`.                                    | Get it from the Foundry portal → Project → Manage → Tracing → "Connect a new Application Insights resource".                                                                                      |
| `404` from `tools/list` on MCP                                                                         | Network egress is blocked or `learn.microsoft.com` is blocked by a proxy.                       | Try `curl -i https://learn.microsoft.com/api/mcp` first. If that fails, fix proxy/firewall.                                                                                                       |
| Portal agent (02b) returns generic answers, doesn't search Learn                                       | You forgot to attach the MCP tool when creating the portal agent.                              | Re-edit the agent in the portal and add the tool (see [How to build the portal agent](#how-to-build-the-portal-agent)). The portal's "Test" pane is a fast way to verify.                          |
| 02c creates the agent the first time, then errors with `403 Forbidden`                                 | Your Foundry user isn't an **AI Project Owner** on the project.                                | Have an owner grant you the role.                                                                                                                                                                |
| Spans don't appear in App Insights for 5+ minutes                                                      | OTel batches exports every ~30 s; first export after process exit can take a minute extra.    | Wait. If still missing, run `verify_observability.py` — it returns a clear pass/fail.                                                                                                             |

---

## Exercises

1. **Add Microsoft GitHub MCP.** The Microsoft GitHub MCP server lives at
   `https://api.githubcopilot.com/mcp/`. Add a second `client.get_mcp_tool(...)`
   call to `02-mcp-tool-agent.py` and watch the model decide *which* tool to
   use for a question like *"Find issues in microsoft/azure-cli labelled bug
   from last week."*
2. **Switch to `always_require` approval.** Change `approval_mode` in 02 to
   `"always_require"`. Run again. The agent should pause; observe the
   `tool_calls` you'd need to approve in your own UI.
3. **Make 02c upsert on change.** Hash `AGENT_DEFINITION` in code and the
   server-side definition; when they differ, issue a `PUT` to create a new
   version. (Hint: the REST endpoint is `PUT $base/$name/versions`.) This is
   how a CI pipeline would deploy agent updates.
4. **Run the KQL query above** in your App Insights and tell apart the
   three scenarios by `cloud_RoleName`.

---

## What you've learned

You can now:

- **Attach an MCP server as a tool to a Foundry agent** with three lines of
  configuration.
- **Pick the right deployment pattern** for your team's workflow: pure code,
  portal-first, or hybrid.
- **Read traces** from Application Insights, tagged per scenario, with
  prompt and completion content visible.
- **Distinguish `FoundryChatClient` from `AzureAIAgentClient`** and know
  which to use when.

These three patterns plus tracing are the foundation of every production
Foundry agent. Sample 03 narrows scope back to a single concept (custom
*local* functions as tools) and is shorter; sample 05 widens it to full
production identity and audit.

---

## Where to go next

| If you want to…                                                                | Go to                                                                |
| ------------------------------------------------------------------------------ | -------------------------------------------------------------------- |
| Use a **local Python function** as a tool (no MCP needed)                      | [Sample 03 · Custom function tool](../03-custom-function-tool-agent/README.md) |
| Add **lightweight** OTel tracing inline (no shared module)                     | [`04-tracing-agent.py`](../04-tracing-agent.py) at the repo root      |
| **Build your own MCP server** on Azure Functions and consume it from Foundry  | [Sample 06 · Weather MCP agent](../06-weather-mcp-agent/README.md)    |
| Add **per-agent Entra identity** to authenticate the agent against an API     | [Sample 05 · End-to-end with Entra Agent ID](../05-end-to-end-agent/) |
