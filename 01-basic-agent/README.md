# Sample 01 · Your first Microsoft Foundry agent

> **What this lab teaches.** You will build the smallest possible
> Microsoft Foundry agent — a single Python file that connects to your
> Foundry project, sends one prompt to **gpt-4o**, streams the response back
> to the terminal, and tears everything down cleanly. By the end you will
> understand the **four building blocks** that every Foundry agent has, and
> you will know exactly which line of code is responsible for each one.

**Time to complete:** 10 minutes (after prerequisites are met)
**Difficulty:** ⭐ Beginner — no prior agent experience required
**Lines of code:** 81

---

## Table of contents

- [What you will learn](#what-you-will-learn)
- [Exam AI-300 mapping](#exam-ai-300-mapping)
- [Prerequisites](#prerequisites)
- [The mental model](#the-mental-model)
- [Step-by-step code walkthrough](#step-by-step-code-walkthrough)
- [Running the sample](#running-the-sample)
- [Expected output](#expected-output)
- [Troubleshooting](#troubleshooting)
- [Exercises, try these next](#exercises-try-these-next)
- [What you've learned](#what-youve-learned)
- [Where to go next](#where-to-go-next)

---

## What you will learn

By the end of this lab you will be able to:

1. **Explain the four building blocks** of every Microsoft Foundry agent: a
   *credential*, a *client*, an *agent*, and a *session*.
2. **Authenticate to Azure from Python code** using `AzureCliCredential`
   without ever embedding a secret in your source.
3. **Send a prompt and stream a response** from a Foundry-hosted gpt-4o
   model.

---

## Exam AI-300 mapping

This lab gives you hands-on practice with objectives from **two** of the five
skill areas measured in
[Exam AI-300: Operationalizing Machine Learning and Generative AI Solutions](https://learn.microsoft.com/credentials/certifications/resources/study-guides/ai-300).

| AI-300 skill area | Specific objective | What you do in this lab |
|---|---|---|
| **Design and implement a GenAIOps infrastructure (20–25%)** | *Create and configure Foundry resources and project environments* | You connect to a live Foundry project via `FOUNDRY_PROJECT_ENDPOINT` and exercise the four building blocks (credential → client → agent → session) that every Foundry-hosted agent is built from. |
| **Design and implement a GenAIOps infrastructure (20–25%)** | *Configure identity and access management with managed identities and RBAC* | You authenticate with `AzureCliCredential` — the local equivalent of a managed identity. No API keys or connection strings touch the code. This is the same pattern the exam tests for production workloads that use system-assigned or user-assigned managed identities. |
| **Design and implement a GenAIOps infrastructure (20–25%)** | *Deploy foundation models by using serverless API endpoints* | The gpt-4o model is consumed through the Foundry agents API, a serverless endpoint. The lab shows exactly which constructor argument maps the client to that endpoint. |
| **Implement generative AI quality assurance and observability (10–15%)** | *Configure detailed logging, tracing, and debugging capabilities* | Streaming responses (`stream=True`) is the first step toward observability. Lab 04 extends this with Application Insights tracing built on top of the same `agent.run(...)` call you write here. |

> **Exam tip.** AI-300 tests you on *when* to use each auth method and
> *what resource type* backs a Foundry project. After this lab you should
> be able to explain: (1) why `AzureCliCredential` is the dev-time proxy
> for a managed identity, and (2) that a Foundry project is a
> `Microsoft.CognitiveServices/accounts/projects` child resource (not an
> Azure ML workspace) — the distinction the exam uses to test infrastructure
> knowledge.

---

## Prerequisites

| Requirement                                                                                                        | Why                                                                                                                                                |
| ------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Python 3.10+**                                                                                                   | The Agent Framework uses modern `async` features.                                                                                                  |
| **A Microsoft Foundry project** with a **gpt-4o** model deployment                                                 | The agent's "brain". Create one at [ai.azure.com](https://ai.azure.com); see the [Foundry quickstart](https://learn.microsoft.com/azure/ai-foundry/quickstarts/get-started-code). |
| **Azure CLI** (`az`) signed in: `az login`                                                                         | `AzureCliCredential` picks up your CLI login as a credential source. No secrets in code.                                                       |
| **A configured `.env` file in this folder**                                                                        | Holds your project endpoint and model name. See [Step 1 below](#step-1--configure-your-env-file).                                                  |
| **VS Code** with the **Python** and **Azure Tools** extensions (recommended)                                       | You can click ▶ **Run Python File** in the editor and watch the streamed response in the integrated terminal. The Python extension auto-loads `.env`. |

### Step 1 — Configure your `.env` file

This sample reads its configuration from a `.env` file **in this folder**.
You'll do this exactly once per lab; both VS Code's ▶ *Run Python File*
button and `python 01-basic-agent.py` from the terminal pick up the same
file automatically.

1. **Copy the example to a real `.env`:**
   ```bash
   cd 01-basic-agent
   cp .env.example .env
   ```

2. **Open `.env` in VS Code** and fill in two values:

   | Variable                    | Where to find it                                                                                                                       |
   | --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
   | `FOUNDRY_PROJECT_ENDPOINT`  | Foundry portal → **your project → Overview**. Copy the **project endpoint URL** (ends in `/api/projects/<project-name>`).               |
   | `FOUNDRY_MODEL`             | The **deployment name** (not the model family) of a chat model in your project. Defaults to `gpt-4o`. Find it under **Models + Endpoints**. |

> **Security.** `.env` is **gitignored** at the repo root — your endpoint
> won't be committed. Never put credentials, function keys, or connection
> strings in source-tracked files.

> **What if `.env` is missing or has placeholders?** The script **fails
> fast** with a clear error message pointing back here. You won't silently
> hit a confusing 404 against the wrong endpoint.

---

## The mental model

Before reading any code, picture the runtime:

```
   ┌──────────────────────────────────┐
   │  Your laptop (Python process)    │
   │                                  │
   │   ┌────────────────────────┐     │
   │   │  AzureCliCredential    │ ──── reads your `az login` token ──┐
   │   └────────────────────────┘     │                              │
   │             │                    │                              ▼
   │             ▼                    │             ┌────────────────────────┐
   │   ┌────────────────────────┐     │    HTTPS    │ Microsoft Entra ID     │
   │   │  FoundryChatClient     │ ────┼────────────►│ (mints access tokens)  │
   │   │  (HTTP transport)      │     │             └────────────────────────┘
   │   └────────────────────────┘     │                          │
   │             │                    │                          │
   │             ▼                    │             ┌────────────────────────┐
   │   ┌────────────────────────┐     │    HTTPS    │ Microsoft Foundry      │
   │   │  Agent                 │ ────┼────────────►│ project (gpt-4o)       │
   │   │   • instructions       │     │             │   • model deployment   │
   │   │   • tools=None         │     │             │   • session storage    │
   │   └────────────────────────┘     │             └────────────────────────┘
   │             │                    │
   │             ▼                    │
   │   ┌────────────────────────────┐ │
   │   │ agent.run(..., stream=True)│ │
   │   │  ◄── async iterator ──┘    │ │
   │   │  prints text as it         │ │
   │   │  arrives from the model    │ │
   │   └────────────────────────────┘ │
   └──────────────────────────────────┘
```

**The four building blocks** highlighted above are the same four you'll see
in *every* Foundry agent you ever write, no matter how complex. Get
comfortable with them here and the rest of the workshop is a rearrangement.

| Building block            | Class / function           | Responsibility                                                                                       |
| ------------------------- | -------------------------- | ---------------------------------------------------------------------------------------------------- |
| **Credential**            | `AzureCliCredential()`     | Talks to Microsoft Entra ID to get a fresh access token using your `az login` session.               |
| **Client**                | `FoundryChatClient(...)`   | Knows the HTTP wire protocol for the Microsoft Foundry project endpoint.                              |
| **Agent**                 | `Agent(...)`               | Composes the model, the instructions, the tools, and the per-call settings into one logical agent.   |
| **Session**               | `agent.create_session()`   | Holds the conversation history (messages) so the model can answer follow-ups in context.             |

---

## Step-by-step code walkthrough

Open [`01-basic-agent.py`](01-basic-agent.py) — the comments below are embedded
directly in each snippet so you can read code and explanation together.

### Section 1 — Imports and `.env` loader

```python
import asyncio          # Agent Framework is async-first; asyncio.run() launches the event loop.
import os               # Read FOUNDRY_* variables that load_dotenv injects into the environment.
from pathlib import Path  # Resolve .env relative to *this file*, not wherever you ran Python from.

from dotenv import load_dotenv  # Reads key=value pairs from .env into os.environ.
                                # The framework does NOT auto-load .env — this call is required.

# ── Building block 1 — CREDENTIAL ────────────────────────────────────────────
# Mints Entra ID tokens from your `az login` session. No API keys in source.
# AI-300: dev-time proxy for a system-assigned managed identity (same interface,
# different token source in production).
from azure.identity import AzureCliCredential

# ── Building block 3 — AGENT ─────────────────────────────────────────────────
# Provider-agnostic abstraction: instructions + tools + client.
# Knows nothing about Foundry specifically — any ChatClient implementation works.
from agent_framework import Agent

# ── Building block 2 — CLIENT ────────────────────────────────────────────────
# Foundry-specific HTTP transport. Translates Agent.run() calls into HTTPS
# requests against your project endpoint.
# AI-300 endpoint format: https://<account>.services.ai.azure.com/api/projects/<project>
# ARM resource type: Microsoft.CognitiveServices/accounts/projects
from agent_framework_foundry import FoundryChatClient

# Load .env from the same folder as this .py file — works regardless of cwd.
load_dotenv(Path(__file__).resolve().parent / ".env")
```

> **Why two framework packages?** `agent_framework` is the **core** (provider-agnostic
> abstractions). `agent_framework_foundry` is the **Foundry provider**. Swapping to
> OpenAI, Anthropic, or Ollama is a one-line change at the client level — `Agent` doesn't move.

### Section 2 — Configuration and fail-fast check

```python
# Read from .env (populated by load_dotenv above).
# Format: https://<resource>.services.ai.azure.com/api/projects/<project-name>
ENDPOINT = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")

# The deployment name you gave the model in Foundry, not the model family name.
MODEL_DEPLOYMENT_NAME = os.environ.get("FOUNDRY_MODEL", "gpt-4o")

# Raise before any HTTP call so you get a clear message instead of a confusing 404.
# Same pattern is used in labs 03 and 04 — worth copying to any env-var-driven script.
if not ENDPOINT or "<YOUR_" in ENDPOINT:
    raise RuntimeError(
        "FOUNDRY_PROJECT_ENDPOINT is not configured. "
        "Copy .env.example to .env in this folder and fill in your Foundry "
        "project endpoint. See README.md → Prerequisites."
    )

AGENT_NAME = "ai-agent"
AGENT_INSTRUCTIONS = "You are a helpful AI assistant."  # System prompt — always visible to the model.

# Add more strings to send multiple turns that share conversation memory (see session below).
USER_INPUTS = [
    "Can you tell me the gravity of Earth versus the gravity of Mars?",
]
```

### Section 3 — The `main()` coroutine

#### Part 3a — Assemble the four building blocks

```python
async def main() -> None:
    # ── CREDENTIAL → CLIENT → AGENT → SESSION ────────────────────────────────
    # These four objects appear in every Foundry agent, no matter how complex.

    # Building block 2 — CLIENT
    # project_endpoint: where to send requests (services.ai.azure.com/api/projects/…)
    # model:            which gpt-4o deployment to use
    # credential:       building block 1 — mints tokens lazily on first request
    client = FoundryChatClient(
        project_endpoint=ENDPOINT,
        model=MODEL_DEPLOYMENT_NAME,
        credential=AzureCliCredential(),    # Building block 1 — CREDENTIAL
    )

    # Building block 3 — AGENT
    # Wraps client with a system prompt. No tools= here → pure conversation.
    # Tools are added in labs 02 (MCP) and 03 (custom function).
    # Uses composition, not inheritance: any ChatClient protocol impl works here.
    agent = Agent(
        client=client,
        name=AGENT_NAME,
        instructions=AGENT_INSTRUCTIONS,
    )
```

#### Part 3b — Session and streaming loop

```python
    # Building block 4 — SESSION
    # Holds all messages in the conversation so the model can answer follow-ups.
    # Created OUTSIDE the loop → all prompts share memory.
    # Move it INSIDE the loop → each prompt is stateless (model forgets prior turns).
    session = agent.create_session()

    for user_input in USER_INPUTS:
        print(f"\n# User: '{user_input}'")

        # stream=True → returns an async iterator of incremental chunks (typewriter effect).
        # Each chunk.text is a small text fragment, often a single word.
        # Drop stream=True for a blocking single result: result = await agent.run(...)
        # Prefer streaming for interactive UIs (lower perceived latency);
        # blocking is simpler for batch jobs.
        async for chunk in agent.run(user_input, session=session, stream=True):
            if chunk.text:
                print(chunk.text, end="", flush=True)
        print("")

    print("\n--- All tasks completed successfully ---")
    # No async context manager needed here — FoundryChatClient and AzureCliCredential
    # hold no per-run server-side state. Hosted-agent sessions (lab 02b+) do need
    # `async with client:` to guarantee teardown.
```

#### Part 3c — Entry-point guard

```python
if __name__ == "__main__":
    try:
        # asyncio.run(): creates a fresh event loop, runs main(), closes it cleanly.
        # Prefer this over the deprecated `loop = asyncio.get_event_loop()` pattern.
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Program finished.")
```

---

## Running the sample

### Option A · From the VS Code integrated terminal (recommended)

1. **Open this folder in VS Code:**
   ```bash
   code 01-basic-agent
   ```
2. **Open a new terminal:** `Terminal → New Terminal` (or `` Ctrl+` `` / `` Cmd+` ``).
3. **Create a virtual environment and install the framework:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate          # macOS / Linux
   # OR on Windows:
   .venv\Scripts\activate
   pip install --upgrade pip
   pip install agent-framework agent-framework-foundry python-dotenv
   ```
4. **Sign in to Azure:**
   ```bash
   az login
   ```
   This populates the credential cache that `AzureCliCredential` reads.
5. **Confirm your `.env` is configured** (see [Step 1 of the Prerequisites](#step-1--configure-your-env-file)). The file lives in this folder and must have `FOUNDRY_PROJECT_ENDPOINT` filled in.
6. **Run it:**
   ```bash
   python 01-basic-agent.py
   ```

### Option B · One click in VS Code

With the venv selected as the Python interpreter (`Ctrl+Shift+P` → **Python:
Select Interpreter**), open `01-basic-agent.py` and click the ▶ **Run Python
File** button in the editor's top-right corner.

---

## Expected output

```
# User: 'Can you tell me the gravity of Earth versus the gravity of Mars?'
Sure! Here's a comparison of the gravitational acceleration on Earth and Mars:

- **Earth**: The standard gravitational acceleration is approximately **9.81 m/s²**.
- **Mars**: The gravitational acceleration is about **3.71 m/s²**.

In simpler terms, the gravity on Mars is about **38%** of that on Earth.
That's why objects (and people) would weigh much less on Mars compared to
Earth, and why future Mars explorers might experience that "bouncy" feeling
in lower gravity.

--- All tasks completed successfully ---
Program finished.
```

The text after `# User:` will stream in incrementally — you'll see words
appear one or two at a time, not all at once. That's `stream=True` doing its
job.

---

## Troubleshooting

| Symptom                                                                                                       | Cause                                                                                                                      | Fix                                                                                                                                                                       |
| ------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `RuntimeError: FOUNDRY_PROJECT_ENDPOINT is not configured`                                                    | You haven't created `.env`, or `.env` still contains the `<YOUR_…>` placeholder.                                            | Follow [Step 1 of the Prerequisites](#step-1--configure-your-env-file): `cp .env.example .env` and fill in the two values.                                                  |
| `azure.identity.exceptions.CredentialUnavailableError` or `AzureCliCredential failed to retrieve a token` | You haven't signed in to Azure CLI, or you're signed into the wrong tenant.                                                | Run `az login` (optionally `az login --tenant <YOUR_TENANT_ID>`). Verify with `az account show`.                                                                          |
| `ResourceNotFound` / `404` from the client                                                                    | `FOUNDRY_PROJECT_ENDPOINT` in `.env` is wrong (typo, wrong project, wrong resource).                                       | Open Foundry portal → **your project → Overview**, copy the endpoint URL, paste over the value in `.env`.                                                                  |
| `DeploymentNotFound` / `404` for the model                                                                    | `FOUNDRY_MODEL` doesn't match any deployment in your project.                                                              | In the Foundry portal → **your project → Models + Endpoints**, copy the exact deployment name into `.env`.                                                                  |
| Streamed output has no spaces or looks "wrong"                                                                | Some terminals buffer line-by-line. We use `print(..., end="")` which can interact with line buffering.                    | Set `PYTHONUNBUFFERED=1` before running, or pipe through `python -u 01-basic-agent.py`.                                                                                    |
| `ModuleNotFoundError: agent_framework_foundry` *or* `ModuleNotFoundError: dotenv`                            | Required packages weren't installed in the active venv.                                              | `pip install agent-framework agent-framework-foundry python-dotenv`                                                                                                  |

---

## Exercises — try these next

1. **Change the personality.** Edit `AGENT_INSTRUCTIONS` to say *"You are a
   pirate who answers in nautical slang."* Re-run. The same model, the same
   prompt, but a completely different style, your first hands-on lesson in
   how powerful the system prompt is.
2. **Add a second prompt to `USER_INPUTS`** that depends on the first
   (e.g., *"And what about the Moon?"*). Run it. Observe that the model
   answers correctly because both prompts share the same `session` and it
   has the prior turn in context.
3. **Recreate the session inside the `for` loop** by moving `session =
   agent.create_session()` *into* the loop. Re-run with the follow-up
   question above and see that the model *no longer knows what you're
   referring to*. That's the practical importance of sessions in three lines
   of code.
4. **Switch from streaming to blocking.** Replace the `async for chunk …`
   block with `result = await agent.run(user_input, session=session); print(result)`. You'll
   lose the typewriter effect but the code is dramatically simpler, and it
   still works.

---

## What you've learned

You can now describe a Foundry agent in four words: **credential, client,
agent, session**. You've signed in to Azure without putting a secret in
your code. You've streamed tokens from gpt-4o. You've seen the basic
pattern that every Foundry sample in this workshop uses.

Everything from here on is *additive*: tools (samples 02 and 03), tracing
(sample 04), per-agent identity and downstream API auth (sample 05), and
building your own MCP server (sample 06).

---

## Where to go next

| If you want to…                                                                                       | Go to                                                                                  |
| ----------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| Give the agent its first **tool** so it can do more than talk                                         | [Sample 02 · MCP tool agent](../02-mcp-tool-agent/README.md)                            |
| Define the same agent in the **Foundry portal** instead of in code                                    | [Sample 02b · Portal agent](../02-mcp-tool-agent/README.md#variant-b--02b-portal-agent-portal-first) |
| Use a **local Python function** as a tool (no MCP server needed)                                      | [Sample 03 · Custom function tool](../03-custom-function-tool-agent/README.md)          |
| Send all of this to **Application Insights** for queryable traces                                     | [`04-tracing-agent.py`](../04-tracing-agent.py) at the repo root                       |
| See the **full workshop arc**                                                                         | [Root README](../README.md#-hands-on-samples--the-learning-arc)                         |
