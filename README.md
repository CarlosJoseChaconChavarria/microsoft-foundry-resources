# Hands-on Microsoft Foundry: Session Takeaways  
*[by Razi Rais](https://linkedin.com/in/razirais)*

**⬇️ [Download Presentation (PDF)](https://github.com/razi-rais/microsoft-foundry-resources/raw/main/Hands-on%20Microsoft%20Foundry.pdf)**

---

## 🧑‍💻 Hands-on samples — the learning arc

This repository ships **nine runnable samples** that build on each other.
Each one adds exactly one new concept on top of the previous, so you can
either follow the arc start-to-finish or jump straight to the one that
matches what you want to learn.

### The arc at a glance

```
   01  →  02  →  02b  →  02c  →  03  →  04  →  05  →  06  →  07
   │     │     │      │      │     │     │     │     │
   │     │     │      │      │     │     │     │     └─ AI red-teaming:
   │     │     │      │      │     │     │     │        local PyRIT (07a) and
   │     │     │      │      │     │     │     │        cloud Foundry RT agent
   │     │     │      │      │     │     │     │        (07b) against the same
   │     │     │      │      │     │     │     │        AcmeBot target
   │     │     │      │      │     │     │     └─ Build your own MCP server
   │     │     │      │      │     │     │        on Azure Functions
   │     │     │      │      │     │     │        + Entra hardening + KQL
   │     │     │      │      │     │     └─ Per-agent identity (Entra
   │     │     │      │      │     │        Agent ID), sidecar pattern,
   │     │     │      │      │     │        OBO, JWT-protected downstream
   │     │     │      │      │     └─ OpenTelemetry tracing → App Insights
   │     │     │      │      └─ Custom Python function tool
   │     │     │      └─ Hybrid: code is source of truth, persists in portal
   │     │     └─ Portal-defined agent, loaded by ID from code
   │     └─ HostedMCPTool — call a remote MCP server (Microsoft Learn MCP)
   └─ Minimal agent: model + system prompt + one user turn

   ──── full lab folders ───────────────────────────────────────────────────
```

> **Every numbered sample (01–07) has its own folder with a book-style
> chapter README** that walks through the code line-by-line, with
> architecture diagrams, expected output, troubleshooting, and exercises.
> Click any *"Open it from"* link below to jump into a chapter.

### Samples in detail

| #      | Sample                                                              | What it adds (the one new concept)                                                                                                                                                                                                                                       | Open it from                                                                                                                                                                                                                                                                                                          |
| ------ | ------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **01** | **[`01-basic-agent/`](01-basic-agent/)**                            | The minimum: model + system prompt + one user turn. No tools.                                                                                                                                                                                                            | **[`01-basic-agent/README.md`](01-basic-agent/README.md)** — chapter introduces the four building blocks of every Foundry agent.                                                                                                                                                                                       |
| **02** | **[`02-mcp-tool-agent/`](02-mcp-tool-agent/)**                      | Adds a **remote MCP tool**. Three variants in the same folder: **02** (pure code), **02b** (portal-defined agent, loaded by ID), **02c** (hybrid / GitOps). Shared observability via `_observability.py` lights up Application Insights for all three.                    | **[`02-mcp-tool-agent/README.md`](02-mcp-tool-agent/README.md)** — covers all three variants in detail, plus the `_observability.py` walkthrough and the KQL verification step.                                                                                                                                         |
| **03** | **[`03-custom-function-tool-agent/`](03-custom-function-tool-agent/)** | Adds a **local Python function** as a tool — the model decides when to call it.                                                                                                                                                                                          | **[`03-custom-function-tool-agent/README.md`](03-custom-function-tool-agent/README.md)** — explains how the framework turns a function signature + docstring into a tool spec the model can reason about.                                                                                                                |
| **04** | **[`04-tracing-agent/`](04-tracing-agent/)**                        | Adds **OpenTelemetry tracing** into Application Insights — every prompt, completion, latency, and token count becomes a queryable span. Covers the GenAI semantic conventions and ships a four-query KQL cookbook.                                                          | **[`04-tracing-agent/README.md`](04-tracing-agent/README.md)** — chapter walks through `configure_azure_monitor`, the parent span pattern, and how to read App Insights with KQL.                                                                                                                                       |
| **05** | **[`05-end-to-end-agent/`](05-end-to-end-agent/)**                  | **Microsoft Entra Agent ID** end-to-end: LangGraph ReAct agent + the official **Microsoft Entra SDK auth sidecar** + JWT-protected downstream Weather API + autonomous *and* OBO flows.                                                                                  | **Start here →** [`05-end-to-end-agent/sidecar/foundry/README.md`](05-end-to-end-agent/sidecar/foundry/README.md) for the runnable lab. The conceptual deep dive on the sidecar pattern lives in [`05-end-to-end-agent/sidecar/README.md`](05-end-to-end-agent/sidecar/README.md). |
| **06** | **[`06-weather-mcp-agent/`](06-weather-mcp-agent/)**                | **Build your own MCP server.** `azd`-deployable `get_weather` tool on Azure Functions, consumed by a Foundry agent. Two iterations: (1) function-key auth, (2) Microsoft Entra hardening (Easy Auth + `MCP.Invoke` app role). Includes a complete KQL observability cookbook. | **Start here →** [`06-weather-mcp-agent/README.md`](06-weather-mcp-agent/README.md) — Part 0 is full VS Code setup, Parts 1–9 are the book-style lab. The MCP server itself has its own README: [`06-weather-mcp-agent/mcp-server/README.md`](06-weather-mcp-agent/mcp-server/README.md). |
| **07** | **[`07-red-teaming/`](07-red-teaming/)**                            | **AI red-teaming.** Two side-by-side labs that attack the same deliberately-permissive "AcmeBot" target: **07a** uses the open-source **PyRIT** library locally so you see every converter, scorer, and ASR calculation by hand; **07b** uses Foundry's **AI Red Teaming Agent** so you get a hosted simulator + judge + scorecard that lands in the portal Evaluations tab. End-to-end teaches the Map / Measure / Manage loop and the standard harm taxonomy (Violence, Hate, Sexual, Self-harm). | **Start here →** [`07-red-teaming/README.md`](07-red-teaming/README.md) — chapter intro with side-by-side comparison, then dive into [`07a-local-pyrit/README.md`](07-red-teaming/07a-local-pyrit/README.md) or [`07b-cloud-foundry/README.md`](07-red-teaming/07b-cloud-foundry/README.md). |

### Four suggested paths

- 🥚 **"I want the 30-minute tour."** Run `01` → `02` → `04`. You'll see a
  plain chat agent, then a tool-calling agent, then traces light up live in
  Application Insights.
- 🚀 **"I want to ship a custom MCP server on Azure."** Jump to sample
  **`06`**. The README is a complete book-style lab; first deploy is ~15 min.
- 🔐 **"I want production-grade identity."** Sample **`05`** is the deep
  dive — per-agent identity, on-behalf-of, sidecar pattern, JWT validation,
  cross-cloud portability.
- 🛡️ **"I need to ship safely — how do I prove my agent is hard to break?"**
  Sample **`07`**. Run 07a to learn the moving parts of an adversarial scan,
  then run 07b to see what your release pipeline will actually use.

> [!TIP]
> **VS Code is the recommended IDE for every sample.** Sample 06's README has
> a full **Part 0** with extension recommendations, integrated-terminal
> shortcuts, and one-click Azure deploys — most of it applies to the other
> samples too. Each folder's `README.md` is best viewed with `Ctrl+Shift+V`
> (preview pane) so you can read the chapter and run the code side-by-side.

---

## 📚 Reference links

The links below are the "what to read next" companion to the session. They
point at official Microsoft Learn docs; the samples above are the runnable
counterparts.

### Microsoft Foundry (platform, models, architecture)
- [Microsoft Foundry documentation home](https://learn.microsoft.com/azure/ai-foundry/)  
- [What is Microsoft Foundry?](https://learn.microsoft.com/azure/ai-foundry/what-is-azure-ai-foundry)  
- [Explore Microsoft Foundry models](https://learn.microsoft.com/azure/ai-foundry/concepts/foundry-models-overview)  
- [Microsoft Foundry architecture](https://learn.microsoft.com/azure/ai-foundry/concepts/architecture)  
- [SDKs and endpoints overview](https://learn.microsoft.com/azure/ai-foundry/how-to/develop/sdk-overview)  

### Agents & tools
- [Overview of Foundry Agent Service](https://learn.microsoft.com/azure/ai-foundry/agents/overview)  
- [Quickstart: Create a Foundry agent project](https://learn.microsoft.com/azure/ai-foundry/agents/quickstart)  
- [Discover and manage tools in Foundry (tool catalog)](https://learn.microsoft.com/azure/ai-foundry/agents/concepts/tool-catalog)  
- [Tools governance with AI Gateway](https://learn.microsoft.com/azure/ai-foundry/agents/how-to/tools/governance)  

### RAG (Retrieval Augmented Generation) & Knowledge
- [Retrieval augmented generation and indexes in Foundry](https://learn.microsoft.com/azure/ai-foundry/concepts/retrieval-augmented-generation)  
- [Retrieval Augmented Generation with Azure AI Search](https://learn.microsoft.com/azure/search/retrieval-augmented-generation-overview)  
- [Training module: Develop a RAG-based solution with Microsoft Foundry](https://learn.microsoft.com/training/modules/build-copilot-ai-studio/)  
- [Connect agents to Foundry IQ knowledge bases](https://learn.microsoft.com/azure/ai-foundry/agents/how-to/tools/knowledge-retrieval)  

### Model Context Protocol (MCP)
- [Connect to Model Context Protocol servers (preview)](https://learn.microsoft.com/azure/ai-foundry/agents/how-to/tools/model-context-protocol)  
- [Code samples for MCP tool integration](https://learn.microsoft.com/azure/ai-foundry/agents/how-to/tools/model-context-protocol-samples)  
- [Build and register your own MCP server](https://learn.microsoft.com/azure/ai-foundry/mcp/build-your-own-mcp-server)  
- [Get started with Foundry MCP Server using VS Code](https://learn.microsoft.com/azure/ai-foundry/mcp/get-started)  
- [Deploy a self-hosted Azure MCP Server and connect via Foundry](https://learn.microsoft.com/azure/developer/azure-mcp-server/how-to/deploy-remote-mcp-server-microsoft-foundry)  

### Observability, monitoring & tracing
- [Monitor your generative AI applications in Foundry](https://learn.microsoft.com/azure/ai-foundry/how-to/monitor-applications)  
- [Continuously evaluate your AI agents](https://learn.microsoft.com/azure/ai-foundry/how-to/continuous-evaluation-agents)  
- [Application Insights overview (observability)](https://learn.microsoft.com/azure/azure-monitor/app/app-insights-overview)  
- [AI agents view in Application Insights](https://learn.microsoft.com/azure/azure-monitor/app/agents-view)  

### Safety, evaluation & red-teaming
- [AI Red Teaming Agent (concept)](https://learn.microsoft.com/azure/ai-foundry/concepts/ai-red-teaming-agent)  
- [Run automated red-teaming scans on your AI app](https://learn.microsoft.com/azure/ai-foundry/how-to/develop/run-scans-ai-red-teaming-agent)  
- [PyRIT — Python Risk Identification Toolkit (GitHub)](https://github.com/Azure/PyRIT)  
- [Azure AI Content Safety overview](https://learn.microsoft.com/azure/ai-services/content-safety/overview)  
- [Microsoft AI Red Team — official blog](https://www.microsoft.com/security/blog/topic/ai-red-team/)  

### FAQ and extra
- [Microsoft Foundry FAQ](https://learn.microsoft.com/azure/ai-foundry/faq)

---

## 🧑‍💻 Hands-on Sample Code

→ See the **[Hands-on samples — the learning arc](#-hands-on-samples--the-learning-arc)**
section at the top of this README for the full sample list, suggested learning
paths, and links into each sample's own README.

---

## 1. What is Microsoft Foundry?

Microsoft Foundry is a unified, enterprise-ready Azure platform that brings models, tools, frameworks, and governance together into a single runtime for building and running intelligent AI agents.

**Key points:**
- Access to 1900+ models (foundation, reasoning, multimodal, domain-specific).  
- Microsoft-hosted models with enterprise SLAs and responsible AI review.  
- Partner and community models for specialized capabilities.  
- Organizational data is never used for model training.

---

## 2. Learning Objectives

- Understand Microsoft Foundry’s model catalog, agent runtime, and tools.  
- Learn how to build/run agents, including system prompts and tool integration.  
- Explore RAG, custom functions, and MCP.  
- Gain awareness of observability for monitoring and tracing.

---

## 3. Prerequisites

- No prior Foundry experience required.  
- Helpful: Azure familiarity, Python or C#.  
- Session is broad, not a deep dive into every feature.

---

## 4. Foundry Setup Options

### Basic Setup
- Quickest to provision.  
- Uses platform-managed storage for agent state.

### Standard Setup
- Uses your own Azure resources for full data ownership.  
- Files, threads, and vector stores are stored in your subscriptions.

### Standard Setup + BYO Virtual Network
- Runs entirely inside your own VNet.  
- Helps prevent data exfiltration and gives strict control over data movement.

---

## 5. Retrieval Augmented Generation (RAG)

### Why RAG?
- Base LLMs don’t know your internal product/catalog data.  
- RAG grounds responses using your organizational content for factual, up-to-date answers.

### How it works (with Azure AI Search)
- Create an index/vector index.  
- Store metadata such as:
  - Index location  
  - Search modes (keyword, vector, hybrid)  
  - Vector support  
  - Embedding model used  
- At runtime, relevant chunks are retrieved and passed into the model for generation.

---

## 6. Microsoft Foundry Agents

### Agent Components
- **Instructions** – system prompt and behavior guidelines.  
- **Tools** – external capabilities the agent can call.  
- **Model** – LLM selected from the Foundry model catalog.

### Runtime Workflow
1. Create an agent.  
2. Optionally create a conversation thread.  
3. Send messages and generate responses.  
4. Monitor run status (especially with tools / streaming).  
5. Retrieve and display agent responses.

### Core Concepts
- **Threads** – conversation sessions.  
- **Messages** – user/agent text or files held within a thread.  
- **Runs** – executions where the agent processes thread messages, calls tools, and appends new messages.


### AI Agent Examples

The **runnable samples in this repository** (01–06) are listed in the
[Hands-on samples — the learning arc](#-hands-on-samples--the-learning-arc)
section at the top. They progress from a minimal chat agent to a full
Entra-secured MCP server.

For a much larger catalog of **Azure AI / Foundry agent patterns** — Bing
grounding, code interpreter, file search, OpenAPI tools, multi-tool
orchestration, thread management, and more — see the upstream **Agent
Framework getting-started gallery**:

→ [microsoft/agent-framework · python/samples/getting_started/agents/azure_ai_agent](https://github.com/microsoft/agent-framework/tree/main/python/samples/getting_started/agents/azure_ai_agent)

A few standouts worth bookmarking:

| Pattern                            | Sample                                                                                                                                                                       |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Simplest Azure AI agent            | [`azure_ai_basic.py`](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai_agent/azure_ai_basic.py)                          |
| Bing grounding (web search)        | [`azure_ai_with_bing_grounding.py`](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai_agent/azure_ai_with_bing_grounding.py) |
| Code Interpreter                   | [`azure_ai_with_code_interpreter.py`](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai_agent/azure_ai_with_code_interpreter.py) |
| File search (vector store)         | [`azure_ai_with_file_search.py`](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai_agent/azure_ai_with_file_search.py)     |
| Custom Python function tools       | [`azure_ai_with_function_tools.py`](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai_agent/azure_ai_with_function_tools.py) |
| Hosted MCP server                  | [`azure_ai_with_hosted_mcp.py`](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai_agent/azure_ai_with_hosted_mcp.py)       |
| Local MCP server                   | [`azure_ai_with_local_mcp.py`](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai_agent/azure_ai_with_local_mcp.py)         |
| Multi-tool orchestration           | [`azure_ai_with_multiple_tools.py`](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai_agent/azure_ai_with_multiple_tools.py) |
| OpenAPI 3.0 tools                  | [`azure_ai_with_openapi_tools.py`](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai_agent/azure_ai_with_openapi_tools.py) |
| Azure AI Search (RAG)              | [`azure_ai_with_azure_ai_search.py`](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai_agent/azure_ai_with_azure_ai_search.py) |
| Thread management                  | [`azure_ai_with_thread.py`](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai_agent/azure_ai_with_thread.py)               |

---

## 7. Foundry Tools

### Purpose
- Allow agents to access external data and perform real-world actions.  
- Invoked automatically based on model reasoning and tool descriptions.

### Built-in tool examples
- Azure AI Search  
- Azure Functions  
- Browser Automation  
- Code Interpreter  
- Deep Research (preview)  
- File Search  
- Function Calling  
- Grounding with Bing Search / Bing Custom Search  
- Model Context Protocol (MCP)  
- Microsoft Fabric (preview)  
- OpenAPI 3.0–specified tools

### Third-party tools (examples)
- Auquan (finance workflows)  
- Celonis (process intelligence)  
- InsureMO (insurance quotations)  
- LexisNexis, Morningstar, Tripadvisor, Trademo, etc.

---

## 8. Model Context Protocol (MCP)

### What MCP Provides
- A standard protocol for AI agents to access tools, data sources, and systems securely and consistently.  
- Acts as a universal bridge between agents and external applications, APIs, files, and databases.

### Key terminology
- **Host** – the LLM application that starts connections to MCP servers.  
- **Client** – component in the host that manages one-to-one connections to servers.  
- **Server** – exposes tools, resources, and prompts.

### Capabilities & benefits
- Dynamic discovery of tools exposed by MCP servers.  
- Interoperability across different LLMs.  
- Easier integration of existing APIs and internal systems as tools.

---

## 9. Observability in Foundry

### Monitoring
- Built-in integration with **Application Insights** for:
  - Token and cost tracking  
  - Latency and throughput  
  - Prompt/response behavior  
  - Error rates

### Tracing with OpenTelemetry
- End-to-end traces of each agent run:
  - Messages and intermediate steps  
  - Tool calls and responses  
  - Helps pinpoint where failures or unexpected behavior occur.

---

## 10. Final Takeaways

- Microsoft Foundry unifies models, RAG, tools, MCP, and observability into an enterprise-ready platform for building AI agents.  
- Tools extend agents beyond “just chat” into real workflows and systems.  
- RAG and Azure AI Search close the knowledge gap with your own data.  
- Observability (Application Insights + OpenTelemetry) is essential to safely operate agents in production.  
- Keep learning via Microsoft Learn docs, official training modules, and community resources.

