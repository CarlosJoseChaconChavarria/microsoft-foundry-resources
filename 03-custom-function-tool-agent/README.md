# Sample 03 · An agent that calls your own Python functions

> **What this lab teaches.** Sample 02 showed an agent calling a
> *remote* tool over MCP. Here you'll do the opposite extreme: give the
> agent a **plain Python function** living inside the same script. No
> server, no JSON-RPC, no network. The model decides when to call it, the
> framework wires up the arguments, and you write business logic the way
> you always have. By the end you'll understand exactly when to reach for
> a local function tool vs an MCP server.

**Time to complete:** 15 minutes
**Difficulty:** ⭐⭐ Intermediate. Assumes you've completed sample 01
**Lines of code:** 91

---

## Table of contents

- [What you will learn](#what-you-will-learn)
- [Prerequisites](#prerequisites)
- [Local function tools vs MCP: the trade-off](#local-function-tools-vs-mcp-the-trade-off)
- [How the framework discovers your function](#how-the-framework-discovers-your-function)
- [Step-by-step code walkthrough](#step-by-step-code-walkthrough)
  - [Section 1 · Imports and `.env` loader](#section-1--imports-and-env-loader)
  - [Section 2 · Configuration and fail-fast check](#section-2--configuration-and-fail-fast-check)
  - [Section 3 · The function tool](#section-3--the-function-tool)
  - [Section 4 · `main()`: wiring the function as a tool](#section-4--main-wiring-the-function-as-a-tool)
  - [Section 5 · The streaming loop with tool-call visibility](#section-5--the-streaming-loop-with-tool-call-visibility)
- [Running the sample](#running-the-sample)
- [Expected output](#expected-output)
- [Troubleshooting](#troubleshooting)
- [Exercises](#exercises)
- [What you've learned](#what-youve-learned)
- [Where to go next](#where-to-go-next)

---

## What you will learn

By the end of this lab you will be able to:

1. **Define a Python function as an agent tool**, and explain exactly how
   the model knows what arguments it takes.
2. **Choose between a local function and an MCP server** for a given task.
3. **See the tool-call event in the streaming response** and understand
   what's happening on the wire.
4. **Apply the docstring-as-schema convention** so the model's tool-call
   arguments are correctly typed.

---

## Exam AI-300 mapping

This lab covers objectives across two AI-300 skill areas.

[Exam AI-300: Operationalizing Machine Learning and Generative AI Solutions](https://learn.microsoft.com/credentials/certifications/resources/study-guides/ai-300)

| AI-300 skill area | Specific objective | What you do in this lab |
|---|---|---|
| **Design and implement a GenAIOps infrastructure (20–25%)** | *Create and configure Foundry resources and project environments* | You wire a Python function as an agent tool with one `tools=[get_time]` entry and work through the local-function vs MCP trade-off — a design decision AI-300 tests under "select appropriate deployment patterns". |
| **Design and implement a GenAIOps infrastructure (20–25%)** | *Deploy foundation models by using serverless API endpoints* | gpt-4o calls `get_time()` through the Foundry agents API. You observe the full tool-call cycle: model decision → framework execution → result injection → final answer. |
| **Implement generative AI quality assurance and observability (10–15%)** | *Configure detailed logging, tracing, and debugging capabilities* | The streaming loop exposes `function_call` and `function_result` chunk types — the raw events that OpenTelemetry spans (lab 04) are built from. Seeing them here makes lab 04's traces interpretable. |

> **Exam tip.** AI-300 may present a scenario where you must choose between a local function tool and an MCP server. The key discriminator: "does a second agent or team need the same capability?" If yes → MCP server. If the tool is internal to one agent's process and will never be reused → local function. The exam also tests that you know the docstring is the tool's contract with the model — a missing or vague docstring means the model will not call the tool.

---

## Prerequisites

| Requirement                                                       | Why                                                                                                           |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| **You've completed sample 01**                                    | The four building blocks (credential, client, agent, thread) are not re-explained here.                       |
| **Python 3.10+**                                                  | The framework uses modern `async` features.                                                                    |
| **A Microsoft Foundry project** with a **gpt-4o** deployment      | Same as samples 01 and 02.                                                                                     |
| **Azure CLI signed in** (`az login`)                              | `AzureCliCredential` reads your CLI login.                                                                     |
| **A configured `.env` file in this folder**                       | Holds your project endpoint and model name. See [Step 1 below](#step-1--configure-your-env-file).              |
| **VS Code with the Python extension** (recommended)               | Click ▶ to run. The Python extension auto-loads `.env`. Debug breakpoints work inside `get_time()` so you can step into the tool the moment it fires. |

### Step 1: Configure your `.env` file

This sample reads configuration from a `.env` file **in this folder**.

1. **Copy the example to a real `.env`:**
   ```bash
   cd 03-custom-function-tool-agent
   cp .env.example .env
   ```

2. **Open `.env` in VS Code** and fill in:

   | Variable                    | Where to find it                                                                                                                       |
   | --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
   | `FOUNDRY_PROJECT_ENDPOINT`  | Foundry portal → **your project → Overview**. Copy the **project endpoint URL** (ends in `/api/projects/<project-name>`).               |
   | `FOUNDRY_MODEL`             | The **deployment name** of a chat model in your project. Defaults to `gpt-4o`.                                                          |

If you already configured `.env` in sample 01, you can copy the same values
over. Both samples need the same two variables.

> **Security.** `.env` is **gitignored** at the repo root.
> **Fail-fast behaviour.** Run the script without a configured `.env` and
> you'll get a clear error pointing back here, not a confusing 404.

---

## Local function tools vs MCP: the trade-off

You now know two ways to give an agent capabilities. When do you reach for
each?

| Dimension                          | Local Python function (this sample)                                       | Remote MCP server (sample 02)                                                |
| ---------------------------------- | ------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| **Where the code runs**            | In your Python process                                                    | In an HTTP service somewhere                                                  |
| **Latency**                        | Microseconds                                                              | Tens to hundreds of milliseconds                                              |
| **Deployment**                     | Ship with your agent                                                      | Independent service, independent versioning                                   |
| **Sharing across teams / agents**  | Hard. Copy the function or extract a library                              | Trivial. Point another agent at the same URL                                  |
| **Auth / authorisation**           | Inherits the agent's process identity                                     | Each call can flow a separate token                                            |
| **Sandboxing**                     | Same process, bad function = bad agent                                     | Process isolated, can be hardened independently                                |
| **Discovery by other agents**      | None                                                                      | `tools/list` JSON-RPC, language-agnostic                                       |
| **Best for…**                      | Quick utilities, in-process calculations, talking to local files          | Anything shared across multiple agents, written by a different team, or that needs its own scaling story |

**Rule of thumb:** Start local. The moment a second agent in a different
codebase needs the same capability, **promote it to an MCP server**.

---

## How the framework discovers your function

The single most important thing to internalise about local function tools
is this:

> **The model sees your function's name, signature, type hints, and
> docstring, and that's it.** Everything else (your variable names,
> comments, internal logic) is invisible.

So when you write a function like:

```python
def get_time() -> str:
    """Get the current UTC time."""
    current_time = datetime.now(timezone.utc)
    return f"The current UTC time is {current_time.strftime('%Y-%m-%d %H:%M:%S')}."
```

…the model receives a tool spec roughly equivalent to:

```json
{
  "name": "get_time",
  "description": "Get the current UTC time.",
  "parameters": { "type": "object", "properties": {}, "required": [] },
  "returns": "string"
}
```

That JSON spec is the **only** thing the model uses to decide:
1. Whether to call `get_time` for a given user prompt.
2. What arguments to pass (none in this case).
3. How to interpret the returned string.

**Three concrete consequences:**

- A **bad docstring** = the model never calls your tool. Treat the
  docstring as critically as you treat the system prompt.
- **Type hints matter.** `def f(x)` gives the model nothing. `def f(x: int)`
  gives it a clear schema.
- **Argument names matter.** `def find_user(q: str)` vs
  `def find_user(email: str)` produces different tool-call behaviour. The
  model literally reads the names.

---

## Step-by-step code walkthrough

Open [`03-custom-function-tool-agent.py`](03-custom-function-tool-agent.py)
side-by-side with this guide.

### Section 1 · Imports and `.env` loader

```python
import asyncio
import os
# Used by get_time() — local function tools can use any Python library you
# can pip install; there is no restriction to framework-provided primitives.
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Load .env from this folder into os.environ *before* the framework imports,
# so any module-level os.environ.get() calls see the file's values.
# Same pattern as samples 01 and 02.
load_dotenv(Path(__file__).resolve().parent / ".env")

# Same Agent class as samples 01 and 02.
from agent_framework import Agent
# Foundry transport — lives in the separate agent-framework-foundry package.
from agent_framework.foundry import FoundryChatClient
# Sync credential that reads your `az login` token.
# Matches the sync Agent constructor used in this script.
from azure.identity import AzureCliCredential
```

> **Note.** `load_dotenv` is called **before** the framework imports so that
> any framework-level config that reads environment variables at import time
> sees the values from `.env`. Keep this order in your own scripts.

> **Mixing tools.** Want to add an MCP server alongside `get_time`? Import
> `client.get_mcp_tool(...)` (see sample 02) and pass it in the same `tools=[...]`
> list. The framework treats each entry by type.

### Section 2 · Configuration and fail-fast check

```python
ENDPOINT = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")
MODEL = os.environ.get("FOUNDRY_MODEL", "gpt-4o")

if not ENDPOINT or "<YOUR_" in ENDPOINT:
    raise RuntimeError(
        "FOUNDRY_PROJECT_ENDPOINT is not configured. "
        "Copy .env.example to .env in this folder and fill in your Foundry "
        "project endpoint. See README.md."
    )

AGENT_NAME = "time-agent"
AGENT_INSTRUCTIONS = (
    "You are a helpful assistant that can provide time information in UTC "
    "format. Always call the get_time tool when asked about the current time."
)

USER_INPUTS = [
    "What is the current time in UTC?",
]
```

Three things worth pointing out:

1. **`load_dotenv` populated `os.environ`.** When `python-dotenv` runs at
   import time (in Section 1), the values in `.env` are merged into the
   process environment. So `os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")`
   here returns whatever you wrote in `.env`. **Real environment variables
   set in the shell take precedence over `.env`**. Useful for CI / Docker.
2. **The fail-fast check** catches the most common workshop mistake (forgot
   to fill in `.env`) before any HTTP call. The error message tells you
   exactly what to do.
3. **`AGENT_INSTRUCTIONS` mentions UTC time explicitly.** This *nudges* the
   model to use the tool. Without that hint, gpt-4o might confidently
   make up a time. The system prompt and the available tools work together,
   change one, expect the other to behave differently.

### Section 3 · The function tool

```python
# The function signature is the tool's *contract* with the model.
# It takes no arguments and returns a string — the model sees this exact shape.
def get_time() -> str:
    # The docstring IS the tool's description sent to the model.
    # Be specific: "Get the current UTC time" vs "Get the time" are
    # very different signals. A vague docstring = the model never calls it.
    """Get the current UTC time."""
    # The body is pure Python logic — the model never sees this.
    # You can change the implementation freely without touching the tool spec.
    current_time = datetime.now(timezone.utc)
    return f"The current UTC time is {current_time.strftime('%Y-%m-%d %H:%M:%S')}."
```

> **Deep dive · Async vs sync tool functions.** This one is sync. The Agent
> Framework accepts both. Wrap blocking I/O in `async def` if you want to
> avoid stalling the event loop. For pure-compute calls like `datetime.now()`,
> sync is fine.

### Section 4 · `main()`: wiring the function as a tool

```python
async def main() -> None:
    # Standard Foundry client — same as samples 01 and 02.
    client = FoundryChatClient(
        model=MODEL,
        project_endpoint=ENDPOINT,
        credential=AzureCliCredential(),
    )

    async with Agent(
        client=client,
        name=AGENT_NAME,
        instructions=AGENT_INSTRUCTIONS,
        # Pass a *reference* to the function — not a call.
        # That single entry is the entire mechanic for registering a local
        # Python function as an agent tool. The framework inspects the
        # signature, type hints, and docstring at startup.
        tools=[get_time],
    ) as agent:
```

You can mix and match:

```python
tools=[get_time, mcp_search_tool, get_user_profile]
```

The framework introspects each entry. Plain function becomes a local
function tool. An MCP-tool object (from `client.get_mcp_tool(...)`) is
registered as an MCP tool. Same list, multiple kinds. The model sees a flat
menu.

### Section 5 · The streaming loop with tool-call visibility

```python
        for user_input in USER_INPUTS:
            print(f"\n# User: '{user_input}'")
            print(f"# {AGENT_NAME}: ", end="", flush=True)

            # stream=True returns an async iterator of AgentResponseUpdate objects.
            async for chunk in await agent.run(user_input, stream=True):
                # Each chunk's .contents list holds one or more typed Content objects.
                for content in chunk.contents:
                    # to_dict() yields a plain dict with a stable "type" discriminator.
                    data = content.to_dict()
                    ctype = data.get("type")

                    # "text" — the model is streaming its natural-language answer;
                    # print inline (no newline) so tokens flow together.
                    if ctype == "text" and data.get("text"):
                        print(data["text"], end="", flush=True)
                    # "function_call" — the model has decided to invoke a tool;
                    # carries the function name and JSON arguments.
                    # Prints: [tool call] get_time({})
                    elif ctype == "function_call":
                        print(
                            f"\n[tool call] {data.get('name')}"
                            f"({data.get('arguments', '{}')})",
                            flush=True,
                        )
                    # "function_result" — the framework executed the function and
                    # is feeding the return value back to the model.
                    # Prints: [tool result] The current UTC time is ...
                    elif ctype == "function_result":
                        print(
                            f"[tool result] {data.get('result')}\n# {AGENT_NAME}: ",
                            end="",
                            flush=True,
                        )
            print()
```

Each streaming chunk is an `AgentResponseUpdate` whose `.contents` list
carries one or more typed `Content` objects. Calling `.to_dict()` gives you
a plain dict with a stable `type` discriminator. The three types above cover
the full local-function-tool cycle: the model's decision to call, the
framework's execution, and the model's final text answer.

Walk through what happens on a single user prompt:

```
   ┌──────────────────────────────────────────────────────────────────────┐
   │  agent.run("What is the current time in UTC?", stream=True)          │
   │                                                                      │
   │   Chunk #1   contents=[function_call(name=get_time, args={})]        │
   │              prints: [tool call] get_time({})                        │
   │                                                                      │
   │   (framework invokes get_time(), captures the return value)          │
   │                                                                      │
   │   Chunk #2   contents=[function_result(result="The current UTC...")] │
   │              prints: [tool result] The current UTC time is ...       │
   │                                                                      │
   │   Chunk #3   contents=[text("The")]                                  │
   │   Chunk #4   contents=[text(" current")]                             │
   │   Chunk #5   contents=[text(" UTC")]                                 │
   │   ...        contents=[text(" time is 2026-06-15 04:59:20.")]        │
   └──────────────────────────────────────────────────────────────────────┘
```

The earlier API forced a deep `hasattr` probe into a nested
`raw_representation.raw_representation.step_details` chain. The current
framework normalises that into typed content parts, so the branching is a
plain `if ctype == ...` ladder. The `Content` objects also expose typed
attributes (`content.call_id`, `content.name`, `content.arguments`) so you
do not have to round-trip through `to_dict()` if you prefer.

---

## Running the sample

```bash
# 1. cd into this folder
cd 03-custom-function-tool-agent

# 2. Make a virtual environment and install the framework
python -m venv .venv
source .venv/bin/activate         # macOS / Linux
# OR on Windows:
.venv\Scripts\activate
pip install --upgrade pip
pip install agent-framework agent-framework-foundry python-dotenv

# 3. Sign in to Azure
az login

# 4. Configure .env (one-time)
cp .env.example .env
#    then open .env and fill in FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL
#    (see Prerequisites → "Step 1 · Configure your .env file")

# 5. Run
python 03-custom-function-tool-agent.py
```

Or in VS Code: open the file and click ▶ **Run Python File**. The Python
extension auto-loads `.env` from this folder.

---

## Expected output

```
# User: 'What is the current time in UTC?'
# time-agent: 
[tool call] get_time({})
[tool result] The current UTC time is 2026-06-15 04:59:20.
# time-agent: The current time in UTC is June 15, 2026, at 04:59:20.

--- All tasks completed successfully ---
Program finished.
```

You should see **three distinct things** in the output:

1. A `[tool call]` line, emitted when the model decides to call `get_time`.
   The arguments are `{}` because the function takes none.
2. A `[tool result]` line, emitted when the framework has executed the
   function and is feeding the return value back to the model.
3. The **final answer** that incorporates the tool's return value. The
   model doesn't just echo the tool result, it weaves it into a natural
   sentence. After the tool returns, the model gets another turn to compose
   the final user-facing reply.

If you see only the final answer with no `[tool call]` line, the model
chose not to call your tool. Tighten the system prompt, for example
*"Always use the get_time tool when asked about time"*, and try again.

---

## Troubleshooting

| Symptom                                                    | Cause                                                                                                | Fix                                                                                                                                                                |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `RuntimeError: FOUNDRY_PROJECT_ENDPOINT is not configured` | You haven't created `.env`, or `.env` still has the `<YOUR_…>` placeholder.                          | `cp .env.example .env` and fill in the two values. See [Prerequisites → Step 1](#step-1--configure-your-env-file).                                                  |
| `Tool calls:` line never appears                           | The model decided not to call the tool, usually because the docstring is too vague.                   | Make the docstring more specific. Add a sentence to `AGENT_INSTRUCTIONS` like *"Use the get_time tool for any question about the current time."*                    |
| `TypeError: get_time() takes 0 positional arguments but 1 was given` | You added an argument to `get_time` but didn't update the type hint, and the model passed an unexpected payload. | Add a typed argument: `def get_time(timezone: str = "UTC") -> str`, and update the docstring. The model's tool-call args will line up.                              |
| `CredentialUnavailableError`                                | Not signed in to Azure CLI.                                                                          | `az login` (optionally `az login --tenant <YOUR_TENANT_ID>`).                                                                                                       |
| `'Agent' object has no attribute 'run_stream'`               | Old API usage. The current `Agent` accepts streaming via `await agent.run(input, stream=True)`.       | Update the call site to `async for chunk in await agent.run(user_input, stream=True):`.                                                                              |
| `DeploymentNotFound` / `404`                                | `MODEL_DEPLOYMENT_NAME` is wrong.                                                                    | Check the Foundry portal → **Models + Endpoints** for the exact name.                                                                                                |
| Tool runs but the model ignores the result                  | The function returns something the model can't usefully interpret (e.g., a complex object).           | Return a **clear, human-readable string**. The model "sees" the return value as text. Avoid returning huge JSON blobs unless you also instruct the model how to parse them. |

---

## Exercises

1. **Add a `city` parameter** to `get_time(city: str = "UTC") -> str` and
   teach it to return the local time for that city (use `zoneinfo` from the
   standard library). Re-run with the prompt *"What time is it in Tokyo?"*
   and watch the model fill in the `city` argument from the prompt. No
   extra parsing on your side.
2. **Add a second tool** `get_date()` that returns today's date as a string.
   Put both in `tools=[get_time, get_date]`. Ask *"What's the date and time
   in UTC?"* and observe the model call **both** tools before composing the
   final answer.
3. **Mix local and MCP.** Add an MCP tool for `https://learn.microsoft.com/api/mcp`
   alongside `get_time` (use `client.get_mcp_tool(name="MicrosoftLearn", url=..., approval_mode="never_require")` from sample 02). Ask the model *"Look up the Foundry MCP docs and tell me what time it is in UTC."* The model picks one tool per claim, one for the lookup and one for the time.
4. **Return JSON instead of a sentence.** Change `get_time` to return
   `{"utc": "2025-05-24T22:50:08Z"}` (as a JSON string). The model usually
   still incorporates it correctly, *because* the JSON keys are
   self-describing. Confirm by inspecting the streamed response.
5. **Break the docstring on purpose.** Change `"""Get the current UTC time."""`
   to `"""Function."""`. Re-run. Most of the time, the model will refuse to
   call the tool. That's the practical importance of docstrings.

---

## What you've learned

You can now:

- **Wire a Python function as an agent tool** with one item in a `tools=[…]`
  list.
- **Predict whether the model will call your tool** by inspecting just the
  signature, type hints, and docstring.
- **Read tool-call events** in the streaming response so you can log them,
  meter them, or block them.
- **Decide on the right boundary** for a tool: local function for in-process
  utilities, MCP server for anything shared.

You've now seen the **two fundamental tool flavours** in the Agent
Framework. Everything else is variations on these themes. Built-in tools
(Bing search, code interpreter) are pre-defined hosted-tool classes.
OpenAPI tools auto-generate function tools from an OpenAPI spec. Custom
authentication on MCP is a wrapper around the MCP tool object returned by
`client.get_mcp_tool(...)`.

---

## Where to go next

| If you want to…                                                                          | Go to                                                                  |
| ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Add **OpenTelemetry tracing** so you can query tool-call latency and arguments in KQL    | [`04-tracing-agent.py`](../04-tracing-agent.py) at the repo root        |
| **Build your own MCP server** and have a Foundry agent call its tools                    | [Sample 06 · Weather MCP agent](../06-weather-mcp-agent/README.md)      |
| Give the agent **its own Entra identity** and call an authenticated downstream API       | [Sample 05 · End-to-end with Entra Agent ID](../05-end-to-end-agent/)   |
| See the **full workshop arc**                                                            | [Root README](../README.md#-hands-on-samples--the-learning-arc)          |
