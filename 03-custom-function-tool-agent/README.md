# Sample 03 · An agent that calls your own Python functions

> **What this lab teaches.** Sample 02 showed an agent calling a
> *remote* tool over MCP. Here you'll do the opposite extreme: give the
> agent a **plain Python function** living inside the same script. No
> server, no JSON-RPC, no network. The model decides when to call it, the
> framework wires up the arguments, and you write business logic the way
> you always have. By the end you'll understand exactly when to reach for
> a local function tool vs an MCP server.

**Time to complete:** 15 minutes
**Difficulty:** ⭐⭐ Intermediate — assumes you've completed sample 01
**Lines of code:** 91

---

## Table of contents

- [What you will learn](#what-you-will-learn)
- [Prerequisites](#prerequisites)
- [Local function tools vs MCP — the trade-off](#local-function-tools-vs-mcp--the-trade-off)
- [How the framework discovers your function](#how-the-framework-discovers-your-function)
- [Step-by-step code walkthrough](#step-by-step-code-walkthrough)
  - [Section 1 · Imports and `.env` loader](#section-1--imports-and-env-loader)
  - [Section 2 · Configuration and fail-fast check](#section-2--configuration-and-fail-fast-check)
  - [Section 3 · The function tool](#section-3--the-function-tool)
  - [Section 4 · `main()` — wiring the function as a tool](#section-4--main--wiring-the-function-as-a-tool)
  - [Section 5 · The streaming loop with tool-call visibility (lines 55–76)](#section-5--the-streaming-loop-with-tool-call-visibility-lines-5576)
- [Running the sample](#running-the-sample)
- [Expected output](#expected-output)
- [Troubleshooting](#troubleshooting)
- [Exercises](#exercises)
- [What you've learned](#what-youve-learned)
- [Where to go next](#where-to-go-next)

---

## What you will learn

By the end of this lab you will be able to:

1. **Define a Python function as an agent tool** — and explain exactly how
   the model knows what arguments it takes.
2. **Choose between a local function and an MCP server** for a given task.
3. **See the tool-call event in the streaming response** and understand
   what's happening on the wire.
4. **Apply the docstring-as-schema convention** so the model's tool-call
   arguments are correctly typed.

---

## Prerequisites

| Requirement                                                       | Why                                                                                                           |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| **You've completed sample 01**                                    | The four building blocks (credential, client, agent, thread) are not re-explained here.                       |
| **Python 3.10+**                                                  | The framework uses modern `async` features.                                                                    |
| **A Microsoft Foundry project** with a **gpt-4o** deployment      | Same as samples 01 and 02.                                                                                     |
| **Azure CLI signed in** (`az login`)                              | `DefaultAzureCredential` reads your CLI login.                                                                 |
| **A configured `.env` file in this folder**                       | Holds your project endpoint and model name. See [Step 1 below](#step-1--configure-your-env-file).              |
| **VS Code with the Python extension** (recommended)               | Click ▶ to run; the Python extension auto-loads `.env`. Debug breakpoints work inside `get_time()` so you can step into the tool the moment it fires. |

### Step 1 — Configure your `.env` file

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
over — both samples need the same two variables.

> **Security.** `.env` is **gitignored** at the repo root.
> **Fail-fast behaviour.** Run the script without a configured `.env` and
> you'll get a clear error pointing back here, not a confusing 404.

---

## Local function tools vs MCP — the trade-off

You now know two ways to give an agent capabilities. When do you reach for
each?

| Dimension                          | Local Python function (this sample)                                       | Remote MCP server (sample 02)                                                |
| ---------------------------------- | ------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| **Where the code runs**            | In your Python process                                                    | In an HTTP service somewhere                                                  |
| **Latency**                        | Microseconds                                                              | Tens to hundreds of milliseconds                                              |
| **Deployment**                     | Ship with your agent                                                      | Independent service, independent versioning                                   |
| **Sharing across teams / agents**  | Hard — copy the function or extract a library                              | Trivial — point another agent at the same URL                                 |
| **Auth / authorisation**           | Inherits the agent's process identity                                     | Each call can flow a separate token                                            |
| **Sandboxing**                     | Same process — bad function = bad agent                                    | Process isolated; can be hardened independently                                |
| **Discovery by other agents**      | None                                                                      | `tools/list` JSON-RPC, language-agnostic                                       |
| **Best for…**                      | Quick utilities, in-process calculations, talking to local files          | Anything shared across multiple agents, written by a different team, or that needs its own scaling story |

**Rule of thumb:** Start local. The moment a second agent in a different
codebase needs the same capability, **promote it to an MCP server**.

---

## How the framework discovers your function

The single most important thing to internalise about local function tools
is this:

> **The model sees your function's name, signature, type hints, and
> docstring — and that's it.** Everything else (your variable names,
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
from pathlib import Path

from dotenv import load_dotenv

from agent_framework import ChatAgent
from agent_framework import HostedMCPTool
from agent_framework_azure_ai import AzureAIAgentClient
from azure.identity.aio import DefaultAzureCredential
from datetime import datetime, timezone

load_dotenv(Path(__file__).resolve().parent / ".env")
```

| Import                                              | Purpose                                                                                                                                                                                |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `asyncio`, `os`, `Path`, `load_dotenv`              | Read the `.env` file in this folder into `os.environ` so the rest of the script can `os.environ.get(...)`. Same pattern as sample 01.                                                  |
| `ChatAgent`                                         | Same class as samples 01 and 02.                                                                                                                                                       |
| `HostedMCPTool`                                     | Imported but **not used** in this script. Left in place to show you the alternative: had we wanted to add an MCP tool *in addition to* the local one, we'd import and instantiate it here. |
| `AzureAIAgentClient`                                | Same transport as previous samples.                                                                                                                                                    |
| `DefaultAzureCredential`                            | Same credential chain as previous samples.                                                                                                                                             |
| `from datetime import datetime, timezone`           | Used by our tool function. **This is the entire reason `get_time()` works** — and a reminder that local function tools can use *any* Python library you can `pip install`.             |

> **Deep dive · Why `HostedMCPTool` is imported but unused.** Leftover from
> the file's evolution as a tutorial — it's a hint to you that mixing local
> functions and MCP tools in one agent's `tools=[...]` list is a fully
> supported pattern. Try it as an exercise (see below).

### Section 2 · Configuration and fail-fast check

```python
ENDPOINT = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")
MODEL_DEPLOYMENT_NAME = os.environ.get("FOUNDRY_MODEL", "gpt-4o")

if not ENDPOINT or "<YOUR_" in ENDPOINT:
    raise RuntimeError(
        "FOUNDRY_PROJECT_ENDPOINT is not configured. "
        "Copy .env.example to .env in this folder and fill in your Foundry "
        "project endpoint. See README.md → Prerequisites."
    )

AGENT_NAME = "Agent"
AGENT_INSTRUCTIONS = "You are a helpful assistant that can provide time information in UTC format."

USER_INPUTS = [
    "What is the current time in UTC??",
]
```

Three things worth pointing out:

1. **`load_dotenv` populated `os.environ`.** When `python-dotenv` runs at
   import time (in Section 1), the values in `.env` are merged into the
   process environment. So `os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")`
   here returns whatever you wrote in `.env`. **Real environment variables
   set in the shell take precedence over `.env`** — useful for CI / Docker.
2. **The fail-fast check** catches the most common workshop mistake (forgot
   to fill in `.env`) before any HTTP call. The error message tells you
   exactly what to do.
3. **`AGENT_INSTRUCTIONS` mentions UTC time explicitly.** This *nudges* the
   model to use the tool — without that hint, gpt-4o might confidently
   make up a time. The system prompt and the available tools work together;
   change one, expect the other to behave differently.

### Section 3 · The function tool

```python
def get_time() -> str:
    """Get the current UTC time."""
    current_time = datetime.now(timezone.utc)
    return f"The current UTC time is {current_time.strftime('%Y-%m-%d %H:%M:%S')}."
```

Four lines that do **three jobs**:

1. **`def get_time() -> str:`** — the tool's *contract*: it takes no
   arguments and returns a string. The model sees this exact shape.
2. **`"""Get the current UTC time."""`** — the tool's *description* to the
   model. Be specific. "Get the time" vs "Get the current UTC time" are
   very different signals.
3. **Body** — actual logic. The model never sees this. You can change the
   implementation freely without re-introducing the tool.

> **Deep dive · Async vs sync tool functions.** This one is sync. The Agent
> Framework accepts both — wrap blocking I/O in `async def` if you want to
> avoid stalling the event loop. For pure-compute calls like `datetime.now()`,
> sync is fine.

### Section 4 · `main()` — wiring the function as a tool

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
            tools=[get_time],
        ) as agent
    ):
```

Same pattern as sample 01, but **`tools=[get_time]`**. That's the entire
mechanic for adding a Python function as a tool: **put a reference to it in
the `tools` list**.

You can mix and match:

```python
tools=[get_time, mcp_search_tool, get_user_profile]
```

The framework introspects each entry. Plain function → wraps it as a local
function tool. `HostedMCPTool` instance → registers it as an MCP tool. Same
list, multiple kinds — the model sees a flat menu.

### Section 5 · The streaming loop with tool-call visibility (lines 55–76)

```python
        thread = agent.get_new_thread()

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

The streaming loop is identical to sample 01, but now the **`elif` branch
actually fires**. Walk through what happens on a single user prompt:

```
   ┌──────────────────────────────────────────────────────────────────────┐
   │  agent.run_stream(["What is the current time in UTC??"])             │
   │                                                                      │
   │   Chunk #1   text=""        ← model decides to call get_time         │
   │   Chunk #2   raw={status:"completed", step_details:{tool_calls:[…]}} │
   │              ^── elif branch prints:                                 │
   │                 "Tool calls:  [<ToolCall name=get_time args={}>]"    │
   │                                                                      │
   │   (framework invokes get_time(), receives result, sends it back to   │
   │    the model — all transparently)                                    │
   │                                                                      │
   │   Chunk #3   text="The "                                             │
   │   Chunk #4   text="current "                                         │
   │   Chunk #5   text="UTC "                                             │
   │   …          text="time is 2025-05-24 22:50:08."                     │
   └──────────────────────────────────────────────────────────────────────┘
```

The `elif` is a **deep, defensive probe** into the chunk's raw payload —
seven `hasattr` checks before we touch the field. Why so cautious?

- Different streaming events carry different payloads. The "tool call
  completed" event is one specific shape; everything else (text chunks,
  status updates, role indicators, …) lacks one or more of these
  attributes.
- The chunk's raw API shape evolves across Foundry API versions. Probing
  before reading means the loop never crashes when fields move.

In practice, when *you* write production code you'd factor this into a
helper like `is_tool_call_event(chunk)`. The walrus operator (`:=`) makes
it readable.

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
pip install agent-framework agent-framework-azure-ai python-dotenv --pre

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
# User: 'What is the current time in UTC??'

Tool calls:  [{'id': 'call_abc123', 'type': 'function', 'function': {'name': 'get_time', 'arguments': '{}'}}]
The current UTC time is 2025-05-24 22:50:08.

--- All tasks completed successfully ---
Program finished.
```

You should see **two distinct things** in the output:

1. The **`Tool calls:`** line — printed by the `elif` branch when the model
   decides to call `get_time`. The arguments are `{}` (the function takes
   none).
2. The **final answer** that incorporates the tool's return value. Notice
   the model doesn't *just* echo the tool result — it weaves it into a
   natural sentence. That's because after the tool returns, the model gets
   another turn to compose the final user-facing reply.

If you see *only* the final answer with no `Tool calls:` line, the model
chose **not** to call your tool. Tighten the system prompt (e.g.,
*"Always use the get_time tool when asked about time"*) and try again.

---

## Troubleshooting

| Symptom                                                    | Cause                                                                                                | Fix                                                                                                                                                                |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `RuntimeError: FOUNDRY_PROJECT_ENDPOINT is not configured` | You haven't created `.env`, or `.env` still has the `<YOUR_…>` placeholder.                          | `cp .env.example .env` and fill in the two values. See [Prerequisites → Step 1](#step-1--configure-your-env-file).                                                  |
| `Tool calls:` line never appears                           | The model decided not to call the tool — usually because the docstring is too vague.                  | Make the docstring more specific. Add a sentence to `AGENT_INSTRUCTIONS` like *"Use the get_time tool for any question about the current time."*                    |
| `TypeError: get_time() takes 0 positional arguments but 1 was given` | You added an argument to `get_time` but didn't update the type hint, and the model passed an unexpected payload. | Add a typed argument: `def get_time(timezone: str = "UTC") -> str`, and update the docstring. The model's tool-call args will line up.                              |
| `CredentialUnavailableError`                                | Not signed in to Azure CLI.                                                                          | `az login` (optionally `az login --tenant <YOUR_TENANT_ID>`).                                                                                                       |
| `DeploymentNotFound` / `404`                                | `MODEL_DEPLOYMENT_NAME` is wrong.                                                                    | Check the Foundry portal → **Models + Endpoints** for the exact name.                                                                                                |
| Tool runs but the model ignores the result                  | The function returns something the model can't usefully interpret (e.g., a complex object).           | Return a **clear, human-readable string**. The model "sees" the return value as text. Avoid returning huge JSON blobs unless you also instruct the model how to parse them. |

---

## Exercises

1. **Add a `city` parameter** to `get_time(city: str = "UTC") -> str` and
   teach it to return the local time for that city (use `zoneinfo` from the
   standard library). Re-run with the prompt *"What time is it in Tokyo?"*
   and watch the model fill in the `city` argument from the prompt — no
   extra parsing on your side.
2. **Add a second tool** `get_date()` that returns today's date as a string.
   Put both in `tools=[get_time, get_date]`. Ask *"What's the date and time
   in UTC?"* and observe the model call **both** tools before composing the
   final answer.
3. **Mix local and MCP.** Add `HostedMCPTool` for `https://learn.microsoft.com/api/mcp`
   alongside `get_time`. Ask the model *"Look up the Foundry MCP docs and
   tell me what time it is in UTC."* The model picks one tool per claim —
   one for the lookup, one for the time.
4. **Return JSON instead of a sentence.** Change `get_time` to return
   `{"utc": "2025-05-24T22:50:08Z"}` (as a JSON string). The model usually
   still incorporates it correctly — *because* the JSON keys are
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
Framework. Everything else is variations on these themes: built-in tools
(Bing search, code interpreter) are pre-defined `HostedXTool` classes;
OpenAPI tools auto-generate function tools from an OpenAPI spec; custom
authentication on MCP is a wrapper around `HostedMCPTool`.

---

## Where to go next

| If you want to…                                                                          | Go to                                                                  |
| ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Add **OpenTelemetry tracing** so you can query tool-call latency and arguments in KQL    | [`04-tracing-agent.py`](../04-tracing-agent.py) at the repo root        |
| **Build your own MCP server** and have a Foundry agent call its tools                    | [Sample 06 · Weather MCP agent](../06-weather-mcp-agent/README.md)      |
| Give the agent **its own Entra identity** and call an authenticated downstream API       | [Sample 05 · End-to-end with Entra Agent ID](../05-end-to-end-agent/)   |
| See the **full workshop arc**                                                            | [Root README](../README.md#-hands-on-samples--the-learning-arc)          |
