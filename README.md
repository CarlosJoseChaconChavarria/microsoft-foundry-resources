# Hands-on Microsoft Foundry: Session Takeaways  
* by Razi Rais*  
- **⬇️ [Download Presentation (PDF)](https://github.com/razi-rais/microsoft-foundry-resources/raw/main/Hands-on%20Microsoft%20Foundry.pdf)**

---

## 📚 Microsoft Learn – Validated Documentation Links

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

### FAQ and extra
- [Microsoft Foundry FAQ](https://learn.microsoft.com/azure/ai-foundry/faq)

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
| File | Description |
|------|-------------|
| [`azure_ai_basic.py`](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai_agent/azure_ai_basic.py) | The simplest way to create an agent using `ChatAgent` with `AzureAIAgentClient`. It automatically handles all configuration using environment variables. |
| [`azure_ai_with_bing_custom_search.py`](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai_agent/azure_ai_with_bing_custom_search.py) | Shows how to use Bing Custom Search with Azure AI agents to find real-time information from the web using custom search configurations. Demonstrates how to set up and use HostedWebSearchTool with custom search instances. |
| [`azure_ai_with_bing_grounding.py`](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai_agent/azure_ai_with_bing_grounding.py) | Shows how to use Bing Grounding search with Azure AI agents to find real-time information from the web. Demonstrates web search capabilities with proper source citations and comprehensive error handling. |
| [`azure_ai_with_code_interpreter.py`](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai_agent/azure_ai_with_code_interpreter.py) | Shows how to use the HostedCodeInterpreterTool with Azure AI agents to write and execute Python code. Includes helper methods for accessing code interpreter data from response chunks. |
| [`azure_ai_with_existing_agent.py`](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai_agent/azure_ai_with_existing_agent.py) | Shows how to work with a pre-existing agent by providing the agent ID to the Azure AI chat client. This example also demonstrates proper cleanup of manually created agents. |
| [`azure_ai_with_existing_thread.py`](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai_agent/azure_ai_with_existing_thread.py) | Shows how to work with a pre-existing thread by providing the thread ID to the Azure AI chat client. This example also demonstrates proper cleanup of manually created threads. |
| [`azure_ai_with_explicit_settings.py`](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai_agent/azure_ai_with_explicit_settings.py) | Shows how to create an agent with explicitly configured `AzureAIAgentClient` settings, including project endpoint, model deployment, credentials, and agent name. |
| [`azure_ai_with_azure_ai_search.py`](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai_agent/azure_ai_with_azure_ai_search.py) | Demonstrates how to use Azure AI Search with Azure AI agents to search through indexed data. Shows how to configure search parameters, query types, and integrate with existing search indexes. |
| [`azure_ai_with_file_search.py`](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai_agent/azure_ai_with_file_search.py) | Demonstrates how to use the HostedFileSearchTool with Azure AI agents to search through uploaded documents. Shows file upload, vector store creation, and querying document content. Includes both streaming and non-streaming examples. |
| [`azure_ai_with_function_tools.py`](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai_agent/azure_ai_with_function_tools.py) | Demonstrates how to use function tools with agents. Shows both agent-level tools (defined when creating the agent) and query-level tools (provided with specific queries). |
| [`azure_ai_with_hosted_mcp.py`](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai_agent/azure_ai_with_hosted_mcp.py) | Shows how to integrate Azure AI agents with hosted Model Context Protocol (MCP) servers for enhanced functionality and tool integration. Demonstrates remote MCP server connections and tool discovery. |
| [`azure_ai_with_local_mcp.py`](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai_agent/azure_ai_with_local_mcp.py) | Shows how to integrate Azure AI agents with local Model Context Protocol (MCP) servers for enhanced functionality and tool integration. Demonstrates both agent-level and run-level tool configuration. |
| [`azure_ai_with_multiple_tools.py`](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai_agent/azure_ai_with_multiple_tools.py) | Demonstrates how to use multiple tools together with Azure AI agents, including web search, MCP servers, and function tools. Shows coordinated multi-tool interactions and approval workflows. |
| [`azure_ai_with_openapi_tools.py`](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai_agent/azure_ai_with_openapi_tools.py) | Demonstrates how to use OpenAPI tools with Azure AI agents to integrate external REST APIs. Shows OpenAPI specification loading, anonymous authentication, thread context management, and coordinated multi-API conversations using weather and countries APIs. |
| [`azure_ai_with_thread.py`](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai_agent/azure_ai_with_thread.py) | Demonstrates thread management with Azure AI agents, including automatic thread creation for stateless conversations and explicit thread management for maintaining conversation context across multiple interactions. |

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

