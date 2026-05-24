# Sample 01 · Your first Microsoft Foundry agent

> **What this chapter teaches.** You will build the smallest possible
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
- [Prerequisites](#prerequisites)
- [The mental model](#the-mental-model)
- [Step-by-step code walkthrough](#step-by-step-code-walkthrough)
  - [Section 1 · Imports and `.env` loader (lines 17–26)](#section-1--imports-and-env-loader-lines-1726)
  - [Section 2 · Configuration constants and fail-fast check (lines 29–46)](#section-2--configuration-constants-and-fail-fast-check-lines-2946)
  - [Section 3 · The `main()` coroutine](#section-3--the-main-coroutine)
  - [Section 4 · The entry-point guard](#section-4--the-entry-point-guard)
- [Running the sample](#running-the-sample)
- [Expected output](#expected-output)
- [Troubleshooting](#troubleshooting)
- [Exercises — try these next](#exercises--try-these-next)
- [What you've learned](#what-youve-learned)
- [Where to go next](#where-to-go-next)

---

## What you will learn

By the end of this chapter you will be able to:

1. **Explain the four building blocks** of every Microsoft Foundry agent: a
   *credential*, a *client*, an *agent*, and a *thread*.
2. **Authenticate to Azure from Python code** using `DefaultAzureCredential`
   without ever embedding a secret in your source.
3. **Send a prompt and stream a response** from a Foundry-hosted gpt-4o
   model.
4. **Recognise the lifecycle pattern** (async context managers) that the
   Agent Framework uses to guarantee clean shutdown.

---

## Prerequisites

| Requirement                                                                                                        | Why                                                                                                                                                |
| ------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Python 3.10+**                                                                                                   | The Agent Framework uses modern `async` features.                                                                                                  |
| **A Microsoft Foundry project** with a **gpt-4o** model deployment                                                 | The agent's "brain". Create one at [ai.azure.com](https://ai.azure.com); see the [Foundry quickstart](https://learn.microsoft.com/azure/ai-foundry/quickstarts/get-started-code). |
| **Azure CLI** (`az`) signed in: `az login`                                                                         | `DefaultAzureCredential` picks up your CLI login as a credential source. No secrets in code.                                                       |
| **A configured `.env` file in this folder**                                                                        | Holds your project endpoint and model name. See [Step 1 below](#step-1--configure-your-env-file).                                                  |
| **VS Code** with the **Python** and **Azure Tools** extensions (recommended)                                       | You can click ▶ **Run Python File** in the editor and watch the streamed response in the integrated terminal. The Python extension auto-loads `.env`. |

### Step 1 — Configure your `.env` file

This sample reads its configuration from a `.env` file **in this folder**.
You'll do this exactly once per chapter; both VS Code's ▶ *Run Python File*
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
   │   │ DefaultAzureCredential │ ──── reads your `az login` token ──┐
   │   └────────────────────────┘     │                              │
   │             │                    │                              ▼
   │             ▼                    │             ┌────────────────────────┐
   │   ┌────────────────────────┐     │    HTTPS    │ Microsoft Entra ID     │
   │   │  AzureAIAgentClient    │ ────┼────────────►│ (mints access tokens)  │
   │   │  (HTTP transport)      │     │             └────────────────────────┘
   │   └────────────────────────┘     │                          │
   │             │                    │                          │
   │             ▼                    │             ┌────────────────────────┐
   │   ┌────────────────────────┐     │    HTTPS    │ Microsoft Foundry      │
   │   │  ChatAgent             │ ────┼────────────►│ project (gpt-4o)       │
   │   │   • instructions       │     │             │   • model deployment   │
   │   │   • max_tokens         │     │             │   • thread storage     │
   │   │   • tools=None         │     │             └────────────────────────┘
   │   └────────────────────────┘     │
   │             │                    │
   │             ▼                    │
   │   ┌────────────────────────┐     │
   │   │  agent.run_stream(...) │     │
   │   │  ◄── async iterator ──┘     │
   │   │  prints text as it          │
   │   │  arrives from the model     │
   │   └────────────────────────┘     │
   └──────────────────────────────────┘
```

**The four building blocks** highlighted above are the same four you'll see
in *every* Foundry agent you ever write, no matter how complex. Get
comfortable with them here and the rest of the workshop is a rearrangement.

| Building block            | Class / function           | Responsibility                                                                                       |
| ------------------------- | -------------------------- | ---------------------------------------------------------------------------------------------------- |
| **Credential**            | `DefaultAzureCredential()` | Talks to Microsoft Entra ID to get a fresh access token, transparently.                              |
| **Client**                | `AzureAIAgentClient(...)`  | Knows the HTTP wire protocol for the Foundry **Azure AI Agents** REST API.                            |
| **Agent**                 | `ChatAgent(...)`           | Composes the model, the instructions, the tools, and the per-call settings into one logical agent.   |
| **Thread**                | `agent.get_new_thread()`   | Holds the conversation history (messages) so the model can answer follow-ups in context.             |

---

## Step-by-step code walkthrough

Open [`01-basic-agent.py`](01-basic-agent.py) side-by-side with this guide.
We'll walk through every section.

### Section 1 · Imports and `.env` loader (lines 17–26)

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

**What each import is for:**

| Line | Import                                                | Purpose                                                                                                                                     |
| ---- | ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| 17   | `asyncio`                                             | The Agent Framework is async-first. We use `asyncio.run(main())` at the bottom of the file to launch the event loop.                        |
| 18   | `os`                                                  | Read configuration from environment variables.                                                                                              |
| 19   | `from pathlib import Path`                            | Build a robust filesystem path to `.env` next to *this* file (not the user's current working directory).                                     |
| 21   | `from dotenv import load_dotenv`                      | Read a `.env` file and inject its key=value pairs into `os.environ`. VS Code's Python extension does this automatically too, but `python-dotenv` makes the script work the same way from any terminal. |
| 23   | `from agent_framework import ChatAgent`               | `ChatAgent` is the Agent Framework's high-level abstraction over "an LLM with instructions and (optionally) tools". This is the *agent*.    |
| 24   | `from agent_framework_azure_ai import AzureAIAgentClient` | The transport. This is the bit that turns method calls into HTTPS requests against your Foundry project's **Azure AI Agents** endpoint. |
| 25   | `from azure.identity.aio import DefaultAzureCredential` | Azure Identity's async credential chain. It tries (in order) environment variables, managed identity, Azure CLI, and a few others until one returns a token. |
| 27   | `load_dotenv(Path(__file__).resolve().parent / ".env")` | Load `.env` from **the same folder as this `.py` file**, no matter where you ran Python from. This is the line that makes `cd anywhere; python /full/path/to/01-basic-agent.py` still work. |

> **Deep dive · Why two import packages for "the framework"?** The Agent
> Framework is built in *layers*. `agent_framework` is the **core** package
> (provider-agnostic abstractions like `ChatAgent`, `Agent`, `HostedMCPTool`).
> `agent_framework_azure_ai` is one of several **provider packages**
> (Azure AI Foundry, OpenAI, Anthropic, Ollama, …). Swapping providers is a
> one-line change at the client level — the `ChatAgent` above doesn't move.

### Section 2 · Configuration constants and fail-fast check (lines 29–46)

```python
ENDPOINT = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")
MODEL_DEPLOYMENT_NAME = os.environ.get("FOUNDRY_MODEL", "gpt-4o")

if not ENDPOINT or "<YOUR_" in ENDPOINT:
    raise RuntimeError(
        "FOUNDRY_PROJECT_ENDPOINT is not configured. "
        "Copy .env.example to .env in this folder and fill in your Foundry "
        "project endpoint. See README.md → Prerequisites."
    )

AGENT_NAME = "ai-agent"
AGENT_INSTRUCTIONS = "You are a helpful AI assistant."

USER_INPUTS = [
    "Can you tell me the gravity of Earth versus the gravity of Mars?",
]
```

| Constant                    | What goes here                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ENDPOINT`                  | The **project endpoint** of your Foundry project. Read from the `FOUNDRY_PROJECT_ENDPOINT` env var (which `load_dotenv` populated from `.env`). Format: `https://<RESOURCE>.services.ai.azure.com/api/projects/<PROJECT>`.                                                                                                                                                                                                                                                                                                  |
| `MODEL_DEPLOYMENT_NAME`     | The name of a model **deployment** inside your project. Note: the *deployment name* you gave it, not necessarily the model family (`gpt-4o`, `gpt-4o-mini`). Defaults to `"gpt-4o"` when `FOUNDRY_MODEL` isn't set in `.env`.                                                                                                                                                                                                                                                                                                |
| `AGENT_NAME`                | A label for the agent. Shows up in tracing and in the Foundry portal's Agents panel while the agent exists.                                                                                                                                                                                                                                                                                                                                                                                                              |
| `AGENT_INSTRUCTIONS`        | The **system prompt** — the only piece of writing you control that the model always sees. Spend time on it in production.                                                                                                                                                                                                                                                                                                                                                                                                  |
| `USER_INPUTS`               | A list of prompts to send sequentially. We use a list (not a single string) to make the loop further down trivially extensible — try adding a second prompt to see what happens.                                                                                                                                                                                                                                                                                                                                          |

> **Deep dive · The fail-fast check.** If `FOUNDRY_PROJECT_ENDPOINT` is
> unset *or* still contains the placeholder string `<YOUR_`, we raise a
> `RuntimeError` **before** opening any HTTP connection. This turns a
> confusing 404 into a one-line error that points you straight at the fix.
> The pattern is repeated in samples 03 and 04 — and is worth copying into
> any production script that depends on env vars.

### Section 3 · The `main()` coroutine

This is where the actual work happens. Let's break it into three logical parts.

#### Part 3a — Open two async context managers at once (lines 29–43)

```python
async def main() -> None:
    async with (
        DefaultAzureCredential() as credential,
        ChatAgent(
            chat_client=AzureAIAgentClient(
                project_endpoint=ENDPOINT,
                model_deployment_name=MODEL_DEPLOYMENT_NAME,
                async_credential=credential,
                agent_name=AGENT_NAME,
                agent_id=None,
            ),
            instructions=AGENT_INSTRUCTIONS,
            max_tokens=4096,
            tools=None,
        ) as agent
    ):
```

This single `async with` statement is doing **a lot**. Read it carefully:

1. **`DefaultAzureCredential() as credential`** — opens a credential object
   and binds it to the name `credential`. Behind the scenes, the credential
   has *not* yet acquired a token; it will lazily do so the first time the
   client asks for one. The `async with` ensures it gets closed at the end
   (releases caches, HTTP connections, etc.).

2. **`AzureAIAgentClient(...)`** — constructed inline. This is your HTTP
   transport. The interesting kwargs:

   | kwarg                     | Meaning                                                                                                                                                                                                                            |
   | ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
   | `project_endpoint`        | Where to send requests.                                                                                                                                                                                                            |
   | `model_deployment_name`   | Which deployment in the project to use as the LLM brain.                                                                                                                                                                           |
   | `async_credential`        | The credential we just opened. The client will call `credential.get_token(...)` on every HTTP request that needs auth.                                                                                                              |
   | `agent_name`              | Cosmetic label.                                                                                                                                                                                                                    |
   | `agent_id=None`           | **Key detail.** When `agent_id` is `None`, the client creates a *temporary* agent on the server side at the start of the run and **deletes it again when the context manager exits**. This is why you don't see leftover agents accumulating in the portal after each run. To re-use an existing portal-defined agent, you'd pass its ID here (that's sample 02b). |

3. **`ChatAgent(...)`** — wraps the client. Notice the agent is constructed
   *with* `chat_client=...` rather than inheriting from the client. The Agent
   Framework uses composition, not inheritance: any class implementing the
   `ChatClient` protocol can power any `ChatAgent`.

4. **`tools=None`** — explicit "this agent has no tools". The model can only
   *talk*; it cannot do anything. We'll add tools in samples 02 and 03.

5. The whole thing is bound to `agent` (the `as agent` at the end).

> **Deep dive · Why a context manager?** Both the credential and the agent
> own external resources — HTTP connection pools, possibly a server-side
> agent. Using `async with` guarantees Python runs `__aexit__` on both even
> if an exception is raised inside the block. **This is the recommended
> pattern for every Foundry agent you write.** Hand-managing `.close()` is
> a leak waiting to happen.

#### Part 3b — Create a thread and send each prompt (lines 45–64)

```python
        # Create a new thread that will be reused
        thread = agent.get_new_thread()

        # Process user messages
        for user_input in USER_INPUTS:
            print(f"\n# User: '{user_input}'")
            async for chunk in agent.run_stream([user_input], thread=thread):
                if chunk.text:
                    print(chunk.text, end="")
                elif (
                    chunk.raw_representation
                    and chunk.raw_representation.raw_representation
                    and hasattr(chunk.raw_representation.raw_representation, "status")
                    and hasattr(chunk.raw_representation.raw_representation, "type")
                    and chunk.raw_representation.raw_representation.status == "completed"
                    and hasattr(chunk.raw_representation.raw_representation, "step_details")
                    and hasattr(chunk.raw_representation.raw_representation.step_details, "tool_calls")
                ):
                    print("")
                    print("Tool calls: ", chunk.raw_representation.raw_representation.step_details.tool_calls)
            print("")
```

There are **three concepts** worth pausing on here.

**Concept 1 — Threads carry conversation memory.**
`agent.get_new_thread()` asks the server to allocate a *thread*: a server-side
container that stores every message in the conversation. We create it
**outside** the `for` loop so all prompts go into the same conversation. If
we created a fresh thread per prompt the model would forget prior turns —
useful for stateless QA, but not what we want here.

**Concept 2 — `run_stream(...)` returns an async iterator of *chunks*.**
The model streams its response token-by-token. Each `chunk` is a small
`AgentRunResponseUpdate` object. `chunk.text` holds the new text fragment
since the last chunk (often a single word or a fragment of one). We
`print(chunk.text, end="")` so it appears incrementally — that's the
familiar "typewriter" effect.

**Concept 3 — The big `elif` is a tool-call detector** (forward-looking).
This sample has no tools, so the `elif` branch never fires. But the same
code is reused in sample 03 — when the model decides to call a tool, the
Foundry server emits a special "step completed" chunk whose raw payload
includes the list of `tool_calls`. The code probes deep into the raw
representation defensively (lots of `hasattr` checks) because the shape of
this object can vary across API versions. Keeping this branch in your
own code is good practice — it costs nothing when there are no tools and
gives you free tool-call visibility once you add them.

> **Deep dive · The streaming vs the blocking API.** The Agent Framework
> offers two flavours of every call. `agent.run(prompt)` returns the full
> response once the model has finished. `agent.run_stream(prompt)` returns
> an async iterator that yields chunks as they arrive. **For interactive
> UIs prefer streaming** — first-token latency feels dramatically faster.
> For batch jobs the blocking API is simpler.

#### Part 3c — Print a completion banner and let async cleanup settle (lines 66–69)

```python
        print("\n--- All tasks completed successfully ---")

    # Give additional time for all async cleanup to complete
    await asyncio.sleep(1.0)
```

When control leaves the `async with` block at line 43, Python calls
`__aexit__` on the agent and the credential. That triggers an HTTP `DELETE`
on the temporary agent, closes the connection pool, and flushes any
in-flight telemetry. The one-second sleep on line 69 gives those background
tasks time to finish before the process exits. It's a *belt-and-braces*
move; in production you'd typically lean on whichever runtime (FastAPI,
asyncio.Runner, …) you're embedded in.

### Section 4 · The entry-point guard

```python
if __name__ == "__main__":
    try:
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

Standard Python defensive boilerplate. The interesting line is
`asyncio.run(main())`, which:

1. Creates a fresh event loop,
2. Runs `main()` to completion,
3. Closes the loop deterministically.

`asyncio.run` is the correct way to launch top-level async code in Python
3.7+. Don't reach for `loop = asyncio.get_event_loop()` patterns you might
have seen in older blog posts; those are deprecated.

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
   pip install agent-framework agent-framework-azure-ai python-dotenv --pre
   ```
4. **Sign in to Azure:**
   ```bash
   az login
   ```
   This populates the credential cache that `DefaultAzureCredential` reads.
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
appear one or two at a time, not all at once. That's `run_stream` doing its
job.

---

## Troubleshooting

| Symptom                                                                                                       | Cause                                                                                                                      | Fix                                                                                                                                                                       |
| ------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `RuntimeError: FOUNDRY_PROJECT_ENDPOINT is not configured`                                                    | You haven't created `.env`, or `.env` still contains the `<YOUR_…>` placeholder.                                            | Follow [Step 1 of the Prerequisites](#step-1--configure-your-env-file): `cp .env.example .env` and fill in the two values.                                                  |
| `azure.identity.exceptions.CredentialUnavailableError` or `DefaultAzureCredential failed to retrieve a token` | You haven't signed in to Azure CLI, or you're signed into the wrong tenant.                                                | Run `az login` (optionally `az login --tenant <YOUR_TENANT_ID>`). Verify with `az account show`.                                                                          |
| `ResourceNotFound` / `404` from the client                                                                    | `FOUNDRY_PROJECT_ENDPOINT` in `.env` is wrong (typo, wrong project, wrong resource).                                       | Open Foundry portal → **your project → Overview**, copy the endpoint URL, paste over the value in `.env`.                                                                  |
| `DeploymentNotFound` / `404` for the model                                                                    | `FOUNDRY_MODEL` doesn't match any deployment in your project.                                                              | In the Foundry portal → **your project → Models + Endpoints**, copy the exact deployment name into `.env`.                                                                  |
| Streamed output has no spaces or looks "wrong"                                                                | Some terminals buffer line-by-line. We use `print(..., end="")` which can interact with line buffering.                    | Set `PYTHONUNBUFFERED=1` before running, or pipe through `python -u 01-basic-agent.py`.                                                                                    |
| `ModuleNotFoundError: agent_framework_azure_ai` *or* `ModuleNotFoundError: dotenv`                            | The pre-release wheels (or `python-dotenv`) weren't installed in the active venv.                                          | `pip install agent-framework agent-framework-azure-ai python-dotenv --pre`                                                                                                  |

---

## Exercises — try these next

1. **Change the personality.** Edit `AGENT_INSTRUCTIONS` to say *"You are a
   pirate who answers in nautical slang."* Re-run. The same model, the same
   prompt, but a completely different style — your first hands-on lesson in
   how powerful the system prompt is.
2. **Add a second prompt to `USER_INPUTS`** that depends on the first
   (e.g., *"And what about the Moon?"*). Run it. Observe that the model
   answers correctly because both prompts share the same `thread` and it
   has the prior turn in context.
3. **Recreate the thread inside the `for` loop** by moving `thread =
   agent.get_new_thread()` *into* the loop. Re-run with the follow-up
   question above and see that the model *no longer knows what you're
   referring to*. That's the practical importance of threads in three lines
   of code.
4. **Switch from `run_stream` to `run`.** Replace the `async for chunk …`
   block with `result = await agent.run(user_input); print(result)`. You'll
   lose the typewriter effect but the code is dramatically simpler — and it
   still works.

---

## What you've learned

You can now describe a Foundry agent in four words: **credential, client,
agent, thread**. You've signed in to Azure without putting a secret in
your code. You've streamed tokens from gpt-4o. You've seen the lifecycle
pattern (`async with`) that every Foundry sample in this workshop uses.

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
