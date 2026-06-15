# The Sidecar Design Pattern

How the **Microsoft Entra Agent ID sidecar** lets an AI agent call downstream APIs with a secure, per-agent identity, without the agent code ever seeing a secret.

For runnable samples, see:
- [`foundry/`](foundry/README.md) is the **Microsoft Foundry** edition (the one in this repo).
- The local-LLM (**Ollama**) and **AWS Bedrock** (Claude) editions live in a separate, multi-cloud companion repo: [`razi-rais/3P-Agent-ID-Demo`](https://github.com/razi-rais/3P-Agent-ID-Demo).
- [`weather-api/`](weather-api/README.md) is the shared downstream API used by every edition.

For the PowerShell bootstrap that creates the Blueprint, Agent Identity, and Client SPA used by every edition (`Start-EntraAgentIDWorkflow`), see the [`razi-rais/3P-Agent-ID-Demo`](https://github.com/razi-rais/3P-Agent-ID-Demo) repo.

## The problem

Two common approaches to agent authentication both fall short:

1. **Hard-coded secrets in agent code.** Every agent image holds a copy of your app's `client_secret`. Any compromise, any log leak, any forgotten `.env` committed to Git is a full tenant breach.
2. **Delegated user tokens for everything.** The agent is reduced to acting only when a human is present, and you lose individual auditability — every call looks like the same service principal.

Entra Agent ID gives each agent its own identity. The sidecar pattern makes that identity easy to use.

## What the sidecar does

The **[Microsoft Entra SDK auth sidecar](https://mcr.microsoft.com/en-us/product/entra-sdk/auth-sidecar/about)** (`mcr.microsoft.com/entra-sdk/auth-sidecar`) runs as a second container next to your agent. It exposes a small HTTP API on the pod-local network and handles:

- Client-credentials exchange with `login.microsoftonline.com`
- Client-credentials or federated identity credential (FIC) token acquisition for the Agent Identity (autonomous flow)
- On-Behalf-Of (OBO) flows for user-context calls
- Token caching, refresh, and expiry
- Credential source abstraction — `ClientSecret` for dev, `SignedAssertionFromManagedIdentity` for Azure deployments, same API

Your agent asks the sidecar *"give me an authorization header for this API"* and gets back `Bearer eyJ…`. Credentials never live in agent memory.

| Agent (your code) | Sidecar (Microsoft Entra SDK) |
|---|---|
| Decide when to call the API | Acquire and cache the right token |
| Build the HTTP request | Perform client-credentials and OBO exchange |
| Pass through user token for OBO | Validate and forward user assertion |
| Handle business logic | Talk to `login.microsoftonline.com` |

The security boundary is explicit: the sidecar has no host port. Only services inside the same network (your agent, not your browser, not random processes on the host) can request tokens.

## The identity objects

| Object | Role | Where it lives |
|---|---|---|
| **Blueprint application** | Factory / template that issues Agent Identities. Holds the client credential (secret or federated). | Your Entra tenant |
| **Agent Identity** | The individual AI agent. Has its own app ID, its own permission grants (e.g. `User.Read.All`), its own audit trail. | Your Entra tenant |
| **Client SPA** (OBO only) | Web UI that signs the user in and exchanges the user's token into an Agent token on their behalf. | Your Entra tenant |
| **Sidecar container** | Runs client-credentials and OBO flows. Knows the Blueprint credential. | Next to your agent |
| **Agent container** | Your application code. Asks the sidecar for headers. | Your pod / compose / App Service |

Provisioning is covered in the multi-cloud companion repo [`razi-rais/3P-Agent-ID-Demo`](https://github.com/razi-rais/3P-Agent-ID-Demo). The `Start-EntraAgentIDWorkflow` PowerShell cmdlet creates all three Entra objects in one shot.

## What you'll learn by running the samples

- The difference between a Blueprint and an Agent Identity, and why agents need their own identity.
- How the sidecar exposes `/AuthorizationHeader` (get token) and `/DownstreamApi` (token + proxied call) endpoints.
- How to forward a signed-in user's token to the agent and have the Microsoft Entra SDK for Agent ID mint an agent-on-behalf-of-user token via OBO.
- How the downstream API validates agent tokens cryptographically — signature, issuer, `xms_par_app_azp`, audience.
- How to swap from `ClientSecret` (dev) to `SignedAssertionFromManagedIdentity` (Azure deployments) without changing a line of agent code.

## Next steps

| To... | Go to |
|---|---|
| Set up Blueprint + Agent Identity in your Entra tenant | [`razi-rais/3P-Agent-ID-Demo`](https://github.com/razi-rais/3P-Agent-ID-Demo) |
| Run the demo against **Microsoft Foundry** | [`foundry/README.md`](foundry/README.md) |
| Run the same demo against **AWS Bedrock** or **local Ollama** | [`razi-rais/3P-Agent-ID-Demo`](https://github.com/razi-rais/3P-Agent-ID-Demo) |

## Further reading

- [Microsoft Entra SDK for Agent Identities](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/microsoft-entra-sdk-for-agent-identities)
- [SDK endpoints reference](https://learn.microsoft.com/en-us/entra/msidweb/agent-id-sdk/endpoints)
- [Call a downstream API](https://learn.microsoft.com/en-us/entra/msidweb/agent-id-sdk/scenarios/call-downstream-api)
- [Python integration examples](https://learn.microsoft.com/en-us/entra/msidweb/agent-id-sdk/scenarios/using-from-python)

