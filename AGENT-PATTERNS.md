# Three patterns for building agents in Microsoft Foundry

> **What this doc is.** A workshop-friendly walk-through of the three distinct
> ways to build an agent on Microsoft Foundry. Each pattern is illustrated with
> a diagram, a runnable sample in this folder, and a plain-English explanation of
> when to use it and what trade-offs you accept.
>
> **Companion doc:** [`OBSERVABILITY.md`](./OBSERVABILITY.md) shows how to verify
> all three patterns are emitting traces, with copy-pasteable KQL queries and
> sample output.

---

## Table of contents

1. [TL;DR](#tldr)
2. [The big picture](#the-big-picture)
3. [Pattern 1 — Pure code](#pattern-1--pure-code)
4. [Pattern 2 — Portal-first](#pattern-2--portal-first)
5. [Pattern 3 — Hybrid (code-as-spec, server-as-runtime)](#pattern-3--hybrid-code-as-spec-server-as-runtime)
6. [Side-by-side comparison](#side-by-side-comparison)
7. [Choosing the right pattern](#choosing-the-right-pattern)
8. [Running the samples](#running-the-samples)

---

## TL;DR

| Pattern | Sample | One-line summary |
|---|---|---|
| **Pure code** | `02-mcp-tool-agent.py` | Agent lives entirely in your Python process. Nothing is registered on Foundry. |
| **Portal-first** | `02b-portal-agent.py` | A human builds the agent in the Foundry web UI. Your code only invokes it by name. |
| **Hybrid** | `02c-hybrid-agent.py` | Your code is the source of truth, but it pushes the definition to Foundry so the agent exists server-side. |

**Rule of thumb**
- *Throwaway script or in-app embedded agent?* → **Pure code**
- *Built by a non-developer SME, used by Logic Apps / Copilot Studio?* → **Portal-first**
- *Production-grade, multi-team, git-reviewed, governed?* → **Hybrid**

---

## The big picture

```
                                ┌────────────────────────────────────┐
                                │           Microsoft Foundry         │
                                │  (https://<resource>.ai.azure.com)  │
                                │                                    │
                                │   ┌───────────────────────────┐    │
   ┌──────────────────┐         │   │  Model deployments        │    │
   │ 02 Pure code     │ ───────►│   │   • gpt-4o                │    │
   │ Agent +          │  chat   │   │   • gpt-4o-mini           │    │
   │ FoundryChatClient│         │   └───────────────────────────┘    │
   └──────────────────┘         │                                    │
                                │   ┌───────────────────────────┐    │
                                │   │  Agents (server-side)     │    │
   ┌──────────────────┐         │   │   • Agent01  (portal-made)│    │
   │ 02b Portal-first │ ───────►│   │   • Agent02  (portal-made)│    │
   │ FoundryAgent     │ invoke  │   │   • mcp-learn-agent-hybrid│    │
   └──────────────────┘         │   │       (REST-made)         │    │
                                │   └───────────────────────────┘    │
   ┌──────────────────┐  create │            ▲                       │
   │ 02c Hybrid       │ REST PUT│            │                       │
   │ in-code defn +   │ ────────┼────────────┘                       │
   │ FoundryAgent     │ invoke  │                                    │
   └──────────────────┘ ────────┘                                    │
                                └────────────────────────────────────┘
```

The thing that varies across the three patterns is **where the agent
definition (model + instructions + tools) lives**:

- in your Python process (`02`),
- in Foundry's database, edited by a human in the web UI (`02b`),
- in Foundry's database, pushed there by your code (`02c`).

Everything else — auth, the LLM call, telemetry — is just consequences of that
choice.

---

## Pattern 1 — Pure code

**Sample:** [`02-mcp-tool-agent.py`](./02-mcp-tool-agent.py)
**Agent name in the sample:** `mcp-learn-agent-codefirst` (a Python label only — not registered on Foundry)

### What's happening

You build the agent in Python using the `Agent` class. The `FoundryChatClient`
just gives you authenticated access to a **model deployment** (Chat Completions
API). Foundry doesn't know an "agent" exists — from its point of view, your
script is just calling a model.

```
   YOUR PROCESS                                FOUNDRY
   ┌──────────────────────────┐                ┌──────────────┐
   │  agent = Agent(           │   POST /chat  │              │
   │    name="…codefirst",     │ ────────────► │   gpt-4o     │
   │    instructions="…",      │ ◄──────────── │  deployment  │
   │    tools=[mcp_tool],      │   completion  │              │
   │    chat_client=…ChatClient│                └──────────────┘
   │  )                        │
   │  await agent.run(prompt)  │
   └──────────────────────────┘
        (nothing persisted server-side)
```

### Plain-English description

- Definition is **ephemeral** — it dies when your Python process ends.
- The "agent" is just a Python object in memory.
- The only thing Foundry sees is each individual chat-completion call.
- You provide the MCP / function tools as Python objects.

### When to use it

- Fast prototyping at your laptop.
- Embedding an agent inside a larger Python app where the agent is just
  another module.
- Educational demos.

### When to avoid it

- You need governance, audit trails, or sharing across teams.
- You want the agent invokable from .NET, Java, Logic Apps, Copilot Studio, etc.
- You want the rich agent-level traces in the Foundry portal's
  **Operate → Traces** tab. (You only get model-level call spans.)

---

## Pattern 2 — Portal-first

**Sample:** [`02b-portal-agent.py`](./02b-portal-agent.py)
**Agent loaded:** `Agent02` version `4` (created via the portal UI by a human)

### What's happening

A human opens https://ai.azure.com → your project → **Agents → + New** and
builds the agent in a form. The definition lives in Foundry's database. Your
script only references it **by name + version**.

```
                       ┌─────────────────────────┐
   HUMAN BUILDS IT     │  Foundry web UI         │
   ────────────────►   │  Agents → + New Agent    │
                       │   name: Agent02          │
                       │   model: gpt-4o          │
                       │   tools: [MCP, …]        │
                       │   instructions: …        │
                       └─────────────┬───────────┘
                                     │ saved
                                     ▼
                       ┌─────────────────────────┐
   YOUR PROCESS        │  Foundry Agents service │
   ┌────────────────┐  │   ┌─────────────────┐   │
   │ FoundryAgent(  │─►│   │ Agent02 v4      │   │
   │  name="Agent02",│  │  │  (config + run) │   │
   │  version="4")  │  │   └─────────────────┘   │
   │ agent.run(...) │  │                          │
   └────────────────┘  └─────────────────────────┘
       (just invokes — never authors)
```

### Plain-English description

- Definition is **server-side and persistent**.
- The agent has an ID, a version, an audit history, a permissions model.
- Your code is dumb — it just says "run Agent02 v4 with this input".
- Teams can edit the agent without touching code.

### When to use it

- A subject-matter expert / business analyst owns the agent.
- The same agent is consumed from multiple languages, Logic Apps, or Power Platform.
- You want point-and-click guardrails, evaluations, and version pinning.

### When to avoid it

- Your agent definition needs to be reviewed in pull requests.
- You want reproducible "infrastructure-as-code" deployments.
- You're worried about portal config drift across environments (dev/test/prod).

---

## Pattern 3 — Hybrid (code-as-spec, server-as-runtime)

**Sample:** [`02c-hybrid-agent.py`](./02c-hybrid-agent.py)
**Agent created:** `mcp-learn-agent-hybrid` (created by the script via REST, then invoked)

### What's happening

The agent definition is written in Python (or YAML/JSON — same idea). The
script **upserts** it to Foundry via REST (idempotent: create if new, version-up
if changed), then invokes it. Think **Terraform/Bicep for agents**, not for
infrastructure.

```
        SOURCE OF TRUTH                   APPLY                 RUNTIME
   ┌────────────────────────┐         ┌──────────────┐     ┌──────────────┐
   │ AGENT_DEFINITION = {   │ POST    │ Foundry      │     │ Foundry      │
   │  "model": "gpt-4o",    │ /agents │ Agents API   │     │ Agents API   │
   │  "instructions": "…",  │ ──────► │              │     │              │
   │  "tools": [{           │         │  upsert      │     │              │
   │    "type":"mcp",       │         │  mcp-learn-  │     │  ┌────────┐  │
   │    "require_approval": │         │  agent-hybrid│     │  │ v1     │  │
   │      "never"           │         │              │     │  └────────┘  │
   │  }]}                   │         └──────────────┘     └──────┬───────┘
   │                        │                                     │
   │ FoundryAgent(          │ ───────────────────────────────────►│
   │   name="…hybrid")      │                  invoke             │
   │ .run(prompt)           │ ◄───────────────────────────────────│
   └────────────────────────┘
        (git-committed)
```

### Plain-English description

- **Code wins.** If somebody hand-edits the agent in the portal, the next run
  of the script will overwrite their change (or bump to a new version).
- The agent **exists server-side** — same permissions, traces, audit log,
  evaluations, and reach as portal-first.
- Your repo can `diff`, `review`, `revert`, and `roll forward` the agent the
  same way you do code.

### When to use it

- Production deployments with CI/CD.
- Multi-environment (dev/staging/prod) where each env should match git exactly.
- Teams who want both git history *and* portal-level features.

### When to avoid it

- Just exploring on a laptop — pure-code is faster.
- The agent is owned by a non-coder who needs to edit it in the UI.

---

## Side-by-side comparison

### 🔧 Definition & lifecycle

|                                    | Pure code                       | Portal-first       | Hybrid                             |
|------------------------------------|---------------------------------|--------------------|------------------------------------|
| SDK class                          | `Agent` + `FoundryChatClient`   | `FoundryAgent`     | REST upsert → `FoundryAgent`       |
| Foundry API used                   | Chat Completions                | Agents             | Agents (create + invoke)           |
| Where it lives                     | client memory                   | server             | server                             |
| Object ID / version                | ❌                              | ✅                 | ✅                                 |
| Shows in portal                    | ❌                              | ✅                 | ✅                                 |
| Persistent across runs             | ❌                              | ✅                 | ✅                                 |
| Source of truth                    | `.py` file                      | portal             | `.py` file (in git)                |

### 💬 Messages, threads & state

|                                    | Pure code              | Portal-first         | Hybrid               |
|------------------------------------|------------------------|----------------------|----------------------|
| Message history                    | client-side list       | server thread        | server thread        |
| Thread / session ID                | local SDK object       | persistent resource  | persistent resource  |
| Resume after process restart       | ❌ (manual persist)    | ✅ load thread by ID | ✅ load thread by ID |
| Multi-user concurrent sessions     | manual                 | ✅ thread-per-user   | ✅ thread-per-user   |
| Streaming                          | ✅                     | ✅                   | ✅                   |

### 🧠 Memory & knowledge

|                                    | Pure code              | Portal-first         | Hybrid               |
|------------------------------------|------------------------|----------------------|----------------------|
| Short-term (within thread)         | manual                 | ✅ automatic         | ✅ automatic         |
| Long-term / cross-thread memory    | BYO (vector DB)        | ✅ Foundry memory    | ✅ Foundry memory    |
| Knowledge base attachable          | ❌                     | ✅                   | ✅                   |
| Vector store                       | BYO                    | ✅ Foundry-managed   | ✅ Foundry-managed   |
| RAG                                | BYO retrieval code     | ✅ built-in `file_search` | ✅                |

### 🛠️ Tools

|                                    | Pure code                | Portal-first         | Hybrid               |
|------------------------------------|--------------------------|----------------------|----------------------|
| Local Python functions as tools    | ✅ pass callables        | ❌ (server-side)     | ❌ (server-side)     |
| Hosted MCP tool                    | ✅ `client.get_mcp_tool` | ✅ portal config     | ✅ in-code definition|
| Code interpreter                   | ✅ via `HostedCodeInterpreterTool` | ✅ portal      | ✅                   |
| File search                        | ✅                       | ✅                   | ✅                   |
| OpenAPI tools                      | via function shim        | ✅ first-class       | ✅                   |
| Tool spec lives where              | code                     | portal config        | code → portal config |

### 👁️ Observability & tracing

|                                    | Pure code                | Portal-first         | Hybrid               |
|------------------------------------|--------------------------|----------------------|----------------------|
| Client-side OTel spans (App Insights) | ✅ `invoke_agent`+`chat` | ⚠ warm-up only       | ✅ `invoke_agent`+`chat` |
| Server-side Foundry agent trace    | ❌ (no server agent)     | ✅ portal Traces tab | ✅ portal Traces tab |
| Token usage queryable in KQL       | ✅                       | ❌ (server-side only)| ✅                   |
| Run inspector UI in portal         | ❌                       | ✅                   | ✅                   |

> The "thinner" client-side telemetry for portal-first agents is a side-effect
> of which transport protocol the portal uses when it creates them. See
> [`OBSERVABILITY.md → Per-pattern differences`](./OBSERVABILITY.md#per-pattern-observability-differences)
> for the full explanation.

### 📊 Evaluations & quality

|                                    | Pure code  | Portal-first         | Hybrid               |
|------------------------------------|------------|----------------------|----------------------|
| Built-in evaluations               | ❌ BYO     | ✅ Foundry Evaluations | ✅                 |
| Continuous eval pipeline           | BYO        | ✅                   | ✅                   |
| A/B versioning                     | ❌         | ✅ versioned agents  | ✅ each re-run = new version |

### 🛡️ Safety, security & governance

|                                    | Pure code            | Portal-first         | Hybrid               |
|------------------------------------|----------------------|----------------------|----------------------|
| Default content filter             | ✅                   | ✅                   | ✅                   |
| Agent-level Guardrails (PII, jailbreak…) | ❌             | ✅ portal config     | ✅ portal config     |
| Entra Agent Identity issued        | ❌                   | ✅                   | ✅                   |
| Agent blueprints / policies        | ❌                   | ✅                   | ✅                   |
| OBO (act-as-user) flow             | ❌                   | ✅ (`05-end-to-end-agent`) | ✅              |
| Conditional Access / ID Governance | ❌                   | ✅                   | ✅                   |
| Audit log entry per run            | ❌                   | ✅                   | ✅                   |

### 🔌 Integration reach

|                                    | Pure code     | Portal-first         | Hybrid               |
|------------------------------------|---------------|----------------------|----------------------|
| Invokable from .NET / Java / REST  | ❌ rewrite    | ✅ by name           | ✅ by name           |
| Logic Apps / Power Automate        | ❌            | ✅                   | ✅                   |
| Copilot Studio                     | ❌            | ✅                   | ✅                   |
| Teams / Outlook agents catalog     | ❌            | ✅                   | ✅                   |
| Embeddable into your app           | ✅ trivially  | ✅ via SDK call      | ✅                   |

### 💸 Operations

|                                    | Pure code             | Portal-first         | Hybrid               |
|------------------------------------|-----------------------|----------------------|----------------------|
| Cost driver                        | model tokens only     | tokens + small mgmt overhead | same         |
| Cold start                         | none                  | first call resolves agent | same           |
| Versioning & rollback              | git only              | ✅ portal versioning | ✅ both              |
| Disaster recovery                  | re-deploy code        | export config        | re-run script        |

### 🎭 Personas & fit

|                                    | Pure code             | Portal-first         | Hybrid               |
|------------------------------------|-----------------------|----------------------|----------------------|
| Persona                            | App developer         | Ops / SME / business | Platform / DevOps    |
| Analogy                            | inline `system_prompt`| OpenAI playground Assistant | Terraform / Bicep for agents |
| Best for                           | prototypes, in-process agents | non-coders, demos | production teams, governed CI/CD |
| Anti-pattern                       | sharing across teams/languages | "treat portal as source of truth" without export | letting someone hand-edit in portal — next deploy wipes it |

---

## Choosing the right pattern

```
                ┌─────────────────────────────────────────┐
                │  Is the agent definition in git?         │
                └──────────────────┬──────────────────────┘
                          NO       │       YES
              ┌───────────────────┘ └────────────────────┐
              ▼                                          ▼
   ┌───────────────────────┐               ┌──────────────────────────┐
   │ Portal-first          │               │ Does it need to exist     │
   │ (a human owns it)     │               │ on Foundry server-side?   │
   └───────────────────────┘               └────────────┬─────────────┘
                                                  NO   │   YES
                                          ┌────────────┘ └──────────┐
                                          ▼                         ▼
                                ┌──────────────────┐     ┌──────────────────┐
                                │ Pure code        │     │ Hybrid           │
                                │ (script-only)    │     │ (REST upsert)    │
                                └──────────────────┘     └──────────────────┘
```

---

## Running the samples

All three use the same containerized runner (no local Python install needed).
First, copy `.env.example` to `.env` and fill in your Foundry endpoint, tenant
ID, App Insights connection string, etc. Then:

```bash
cd $(git rev-parse --show-toplevel)

docker run --rm -it \
  -v "$PWD":/work -w /work -e HOME=/work/.dockerhome \
  --env-file .env \
  mcr.microsoft.com/azure-cli:latest \
  bash -c '
    python3 -m ensurepip --upgrade >/dev/null 2>&1
    python3 -m pip install --quiet --pre \
        agent-framework httpx python-dotenv \
        azure-monitor-opentelemetry
    az account show >/dev/null 2>&1 || az login --use-device-code \
        --tenant "$AZURE_TENANT_ID"
    python3 02-mcp-tool-agent.py   # or 02b-portal-agent.py, or 02c-hybrid-agent.py
  '
```

> **Find your tenant ID** with `az account show --query tenantId -o tsv`, then
> paste it into `.env` as `AZURE_TENANT_ID=<YOUR_TENANT_ID>`.

After running, check both:

1. **Foundry portal → Operate → Traces** — server-side view (best for 02b/02c)
2. **App Insights → Logs** — client-side view (best for 02 / 02c)

For the App Insights side with copy-pasteable KQL, see
[`OBSERVABILITY.md`](./OBSERVABILITY.md).
