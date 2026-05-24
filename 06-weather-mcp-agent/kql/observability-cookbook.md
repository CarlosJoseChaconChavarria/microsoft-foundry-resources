# KQL Observability Cookbook — sample 06

These queries prove the full chain in Application Insights:

```
user prompt → Foundry agent → MCP tool call → Azure Functions /runtime/webhooks/mcp
            → Open-Meteo dependency → tool result → tokens & cost
```

> **Important — correlation caveat.** The Foundry agent runs locally (this
> repo, exporting via `_observability.py`) and the Function App runs in Azure.
> Both export to the **same** Application Insights resource (that's what the
> Bicep / `.env` wiring guarantees). W3C `traceparent` may or may not be
> propagated all the way from the agent into the Function App's request span
> depending on Foundry Agent Service internals. So the cookbook includes
> **two correlation strategies**:
>
> 1. **Best-effort `operation_Id` join** — works if traceparent makes it
>    through (cleanest waterfall).
> 2. **Time-window + role-name + tool-arg join** — always works, used as the
>    fallback in the final consolidated query.

Run these in the same App Insights resource the workshop is wired to:
**Foundry portal → your project → Manage → Tracing → Open in Azure portal**.

---

## 1. Locate the most recent run of this sample

```kusto
union dependencies, traces, requests
| where timestamp > ago(15m)
| where cloud_RoleName == "foundry-workshop.weather-mcp"
   or operation_Name has "weather-mcp"
   or customDimensions.["gen_ai.system"] != ""
| summarize first=min(timestamp), last=max(timestamp), spans=count() by operation_Id
| order by first desc
| take 5
```

Pick the most recent `operation_Id`; use it as `<OP>` in queries below.

---

## 2. The user prompt

```kusto
traces
| where timestamp > ago(30m)
| where cloud_RoleName startswith "foundry-workshop.weather-mcp"
| where message has "gen_ai.user.message"
   or customDimensions.["gen_ai.event.name"] == "gen_ai.user.message"
| project timestamp, operation_Id, message, customDimensions
| order by timestamp asc
```

The user's literal prompt lives in `customDimensions["gen_ai.event.content"]`
(captured because `_observability.py` sets
`OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true`).

---

## 3. The model's decision to call `get_weather`

```kusto
dependencies
| where timestamp > ago(30m)
| where cloud_RoleName startswith "foundry-workshop.weather-mcp"
| where name has "tool" or name has "get_weather" or type =~ "GenAI"
| project timestamp, operation_Id, name, duration,
          tool_name = tostring(customDimensions.["gen_ai.tool.name"]),
          tool_args = tostring(customDimensions.["gen_ai.tool.call.arguments"])
| order by timestamp asc
```

You should see one span per tool invocation with `tool_name = "get_weather"`
and `tool_args` containing the `location` the model chose.

---

## 4. The MCP HTTP hop into the Function App

```kusto
requests
| where timestamp > ago(30m)
| where cloud_RoleName endswith "-func" or cloud_RoleName has "weather"
| where url has "/runtime/webhooks/mcp"
| project timestamp, operation_Id, cloud_RoleName, name, resultCode,
          duration, url, traceparent = tostring(customDimensions.["http.request.header.traceparent"])
| order by timestamp asc
```

Each `tools/call` from Foundry shows up as a 200 to `/runtime/webhooks/mcp`.
If the `traceparent` column is non-empty AND its trace-id matches the agent's
`operation_Id`, you can use **strategy 1** (best-effort join) below.

---

## 5. The actual `get_weather` invocation on the worker

```kusto
traces
| where timestamp > ago(30m)
| where cloud_RoleName endswith "-func" or cloud_RoleName has "weather"
| where message has "get_weather"
| project timestamp, operation_Id, severityLevel, message
| order by timestamp asc
```

These are the `logging.info(...)` lines emitted by `function_app.py` /
`weather_service.py` — useful for confirming the resolved location and
condition.

---

## 6. The Open-Meteo outbound dependency

```kusto
dependencies
| where timestamp > ago(30m)
| where cloud_RoleName endswith "-func" or cloud_RoleName has "weather"
| where target has "open-meteo.com"
| project timestamp, operation_Id, name, target, resultCode, duration, data
| order by timestamp asc
```

You'll see two calls per tool invocation: one to
`geocoding-api.open-meteo.com` then one to `api.open-meteo.com`. These spans
are emitted because the Function App initializes
`URLLibInstrumentor().instrument()` at boot.

---

## 7. Tokens & cost

```kusto
dependencies
| where timestamp > ago(30m)
| where cloud_RoleName startswith "foundry-workshop.weather-mcp"
| where customDimensions.["gen_ai.system"] != ""
| extend input_tokens  = toint(customDimensions.["gen_ai.usage.input_tokens"])
| extend output_tokens = toint(customDimensions.["gen_ai.usage.output_tokens"])
| extend model         = tostring(customDimensions.["gen_ai.request.model"])
| project timestamp, operation_Id, model, input_tokens, output_tokens, duration
| summarize total_in=sum(input_tokens), total_out=sum(output_tokens) by operation_Id, model
```

---

## 8. The single-query waterfall

### Strategy 1 — operation_Id join (try first; for agent-only views)

> ⚠️ KQL gotchas worth knowing:
> 1. `$table` is **only** available inside each leg of a `union`, not after
>    `project`. Use `withsource=<col>` to materialize the table name as a
>    real column instead.
> 2. The natural column name `kind` collides with the `kind=outer` `union`
>    parameter and trips the parser (`SYN0002: Query could not be parsed at
>    'kind'`). Use any other name (e.g. `src_table`) — or skip `withsource`
>    entirely and rely on the built-in `itemType` column, which is always
>    one of `request | dependency | trace`.
> 3. For **hosted MCP tools** (the Foundry Agent Service calling your
>    Function App from Microsoft-managed compute), `operation_Id` does
>    **not** propagate across the boundary. Strategy 1 will only return
>    the **agent-side** spans for a given operation_Id. To see the
>    Function App + Open-Meteo side too, use strategy 2.

```kusto
union withsource=src_table requests, dependencies, traces
| where timestamp > ago(30m)
| where operation_Id == "<OP>"      // ← paste the value from query 1
| project timestamp, src_table, itemType, cloud_RoleName, name, target, duration,
          tool   = tostring(customDimensions.["gen_ai.tool.name"]),
          args   = tostring(customDimensions.["gen_ai.tool.call.arguments"]),
          model  = tostring(customDimensions.["gen_ai.request.model"]),
          in_tok = tostring(customDimensions.["gen_ai.usage.input_tokens"]),
          out_tok= tostring(customDimensions.["gen_ai.usage.output_tokens"]),
          msg    = message
| order by timestamp asc
```

### Strategy 2 — time-window cross-boundary waterfall (always works)

This is the **demo-time** query — paste it during a workshop and the audience
sees the entire chain in a single ordered table.

```kusto
let start = ago(30m);
let agent_spans =
    dependencies
    | where timestamp > start
    | where cloud_RoleName startswith "foundry-workshop.weather-mcp"
    | project timestamp, source="agent", cloud_RoleName, name,
              tool_name = tostring(customDimensions.["gen_ai.tool.name"]),
              tool_args = tostring(customDimensions.["gen_ai.tool.call.arguments"]),
              model     = tostring(customDimensions.["gen_ai.request.model"]),
              tokens    = strcat(
                  tostring(customDimensions.["gen_ai.usage.input_tokens"]), "/",
                  tostring(customDimensions.["gen_ai.usage.output_tokens"]));
let func_in =
    requests
    | where timestamp > start
    | where cloud_RoleName == "weather-mcp-demo-func"   // ← your Function App
    | where url has "/mcp"
    | project timestamp, source="function-app/in", cloud_RoleName,
              name = strcat("HTTP ", name),
              tool_name="", tool_args="", model="",
              tokens = strcat(toint(resultCode), " ",
                              iff(success == "True", "ok", "fail"));
let func_out =
    dependencies
    | where timestamp > start
    | where cloud_RoleName == "weather-mcp-demo-func"
    | where target has "open-meteo"
    | project timestamp, source="function-app/out", cloud_RoleName,
              name = strcat(type, " ", target),
              tool_name="", tool_args = tostring(data), model="",
              tokens = strcat(toint(resultCode), " ",
                              iff(success == "True", "ok", "fail"));
agent_spans
| union func_in
| union func_out
| order by timestamp asc
| project timestamp, source, cloud_RoleName, name, tool_name, tool_args, model, tokens
```

> 📎 **Known gap (iteration 1).** The Azure Functions Python worker on Flex
> Consumption auto-instruments inbound HTTP via the platform's built-in App
> Insights wiring, but it does **not** pick up our manual
> `URLLibInstrumentor().instrument()` call (the auto-wiring takes precedence
> at import time). So `func_out` rows for Open-Meteo will be empty until
> we either (a) replace the auto-wiring with manual `configure_azure_monitor`
> + `OTEL_PYTHON_DISABLE_INSTRUMENTATIONS` env, or (b) switch to the
> `requests` package and rely on the runtime's HTTP instrumentation. The
> waterfall is still complete for demo purposes — you can see every
> agent → function HTTP hop and every tool decision from the agent side.

### Strategy 3 — agent-only "prompt → tool call → tokens" (no Function App data needed)

The agent's `chat gpt-4o` span carries the entire conversation in custom
dimensions, so even without the function-side telemetry you can prove the
full GenAI loop:

```kusto
dependencies
| where timestamp > ago(30m)
| where cloud_RoleName startswith "foundry-workshop.weather-mcp"
| where name has "chat"
| project timestamp,
          user_input   = tostring(customDimensions.["gen_ai.input.messages"]),
          model_output = tostring(customDimensions.["gen_ai.output.messages"]),
          model        = tostring(customDimensions.["gen_ai.response.model"]),
          in_tokens    = toint(customDimensions.["gen_ai.usage.input_tokens"]),
          out_tokens   = toint(customDimensions.["gen_ai.usage.output_tokens"])
| order by timestamp asc
```

`model_output` will contain JSON with a `mcp_server_tool_call` part naming
`get_weather` and the arguments the model chose — this is the cleanest
single piece of evidence that the agent actually invoked the MCP tool.

---

## Recording your own results

Below is the **actual** output from a real run of `06-weather-mcp-agent.py`
against the deployed `weather-mcp-demo-func` Function App on 2026-05-24.

### Strategy 2 — cross-boundary waterfall (actual run)

```text
timestamp                     source           name                               tokens
----------------------------  ---------------  ---------------------------------  -------
2026-05-24T18:23:51.161270Z   agent            AIProjectClient.get_openai_client  /
2026-05-24T18:23:51.190107Z   agent            invoke_agent weather-mcp-agent     349/80     (gpt-4o)
2026-05-24T18:23:51.190292Z   agent            chat gpt-4o                        349/80
2026-05-24T18:23:58.885350Z   function-app/in  HTTP get_weather                   200 ok
2026-05-24T18:24:02.441220Z   agent            invoke_agent weather-mcp-agent     347/91
2026-05-24T18:24:02.441403Z   agent            chat gpt-4o                        347/91
2026-05-24T18:24:04.459062Z   function-app/in  HTTP get_weather                   200 ok
2026-05-24T18:24:06.590076Z   agent            invoke_agent weather-mcp-agent     462/114
2026-05-24T18:24:06.590481Z   agent            chat gpt-4o                        462/114
2026-05-24T18:24:15.153958Z   function-app/in  HTTP get_weather                   200 ok    (Mumbai)
2026-05-24T18:24:19.543241Z   function-app/in  HTTP get_weather                   200 ok    (Sydney)
```

You can clearly see three agent turns (each one a `chat gpt-4o` span with
input/output token counts) interleaved with `HTTP get_weather 200` requests
landing on the Function App. Turn 3 fires **two** function calls back to
back — that's the model deciding to call `get_weather` twice for the
"compare Mumbai and Sydney" prompt.

### Strategy 3 — agent-only chain (actual run)

This is the most compact, single-table view of the full GenAI loop —
prompt → tool call → tool result → final answer → tokens — all from one
row per turn:

```text
# Turn 1  ts=2026-05-24T18:23:51Z  model=gpt-4o-2024-11-20  tokens=349/80
  user: "What's the current weather in Seattle, WA?"
  assistant tool_call: args={"location":"Seattle, WA"}
  assistant mcp_server_tool_result: {"location":"Seattle, Washington, United States",
                                     "condition":"Partly cloudy", ...}
  assistant text: "The current weather in Seattle, WA, is partly cloudy with a
                   temperature of 57°F (14°C). The humidity is 78%, and there's a
                   light wind blowing at 2 km/h from the south..."

# Turn 2  ts=2026-05-24T18:24:02Z  model=gpt-4o-2024-11-20  tokens=347/91
  user: "And how about Paris?"
  assistant tool_call: args={"location":"Paris"}
  assistant mcp_server_tool_result: {"location":"Paris, Île-de-France Region, France",
                                     "condition":"Clear sky", ...}
  assistant text: "The current weather in Paris, ..., is clear skies with a
                   temperature of 30°C (87°F). Humidity is at 40%, ..."

# Turn 3  ts=2026-05-24T18:24:06Z  model=gpt-4o-2024-11-20  tokens=462/114
  user: "Compare the wind in Mumbai and Sydney right now."
  assistant tool_call: args={"location":"Mumbai"}   ← first MCP call
  assistant mcp_server_tool_result: {"location":"Mumbai, Maharashtra, India", ...}
  assistant tool_call: args={"location":"Sydney"}   ← second MCP call in same turn
  assistant mcp_server_tool_result: {"location":"Sydney, New South Wales, Australia", ...}
  assistant text: "In Mumbai, the wind is blowing at 4 km/h from the west-northwest,
                   with a current condition of thunderstorms. In Sydney, the wind
                   speed is slightly higher at 7 km/h from the west, under light
                   rain conditions."
```

Notice turn 3 has **two** `tool_call` / `mcp_server_tool_result` pairs — the
model decided to call `get_weather` twice in a single chat turn, then
synthesized the comparison. Cross-reference with strategy 2 above: those
two calls show up as the two `HTTP get_weather` rows at 18:24:15 and
18:24:19, ~4 seconds apart, both 200.

---

## 9. Iteration 2 — who called the MCP server? (Easy Auth claims)

When Easy Auth is enabled (iteration 2), every authenticated request reaches
the function with the **caller's identity** baked into HTTP headers. The
`/api/whoami` route in `function_app.py` decodes them into a structured log
line that KQL can query:

```kusto
traces
| where timestamp > ago(1h)
| where cloud_RoleName == "weather-mcp-demo-func"
| where message startswith "[whoami]"
| project timestamp, message
| order by timestamp desc
```

Sample row:

```text
[whoami] oid=<agent-identity-object-id>
         name=None idp=aad roles=['MCP.Invoke']
```

`oid` is the Entra `objectId` of the caller's service principal — for a
Foundry Agent Identity SP named like `<your-resource>-<your-project>-<agent-name>-AgentIdentity`
this is the value you'll see here. The `roles` claim proves the caller had `MCP.Invoke`
when the token was issued (i.e. the role grant in §I.2 of the README took
effect). If a request reaches the function with no roles, Easy Auth let it
through but our authorization policy isn't being enforced — investigate.

### Stitch identity onto every MCP call (best-effort, time + role join)

The MCP webhook (`/runtime/webhooks/mcp`) is invoked by the Functions
runtime as a request, but the request span itself doesn't include the
decoded claims (Easy Auth doesn't write to App Insights). To prove **which
agent** invoked a given `get_weather` call, query both: most recent
`[whoami]` claim with the same client IP / role-name within a short window
of the MCP request span. In practice for a single-agent demo it's enough to
note "all `HTTP get_weather` rows during run X correspond to the agent
identity logged in `[whoami]` rows in the same minute".

For multi-agent setups, the function code can be extended to log the
claims at the start of every `get_weather` invocation by passing
`req: func.HttpRequest` into the MCP tool — but that requires SDK support
that isn't yet stable, so we surface identity via the side-channel above.
