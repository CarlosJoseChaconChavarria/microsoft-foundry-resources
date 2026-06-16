#!/usr/bin/env sh
# Post-provision hook — derives the Foundry project endpoint and fills in all .env files.
# Runs automatically after `azd provision` / `azd up`.

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo ""
echo "=== Configuring .env files ==="

# ── Get values from azd environment ──────────────────────────────────────
RG=$(azd env get-value AZURE_RESOURCE_GROUP 2>/dev/null)
HUB=$(azd env get-value FOUNDRY_HUB_NAME 2>/dev/null)
PROJECT=$(azd env get-value FOUNDRY_PROJECT_NAME 2>/dev/null)
MODEL=$(azd env get-value FOUNDRY_MODEL 2>/dev/null)
AI_CONN=$(azd env get-value APPLICATIONINSIGHTS_CONNECTION_STRING 2>/dev/null)

# ── Derive the Foundry project endpoint from the AI Services account ──────
echo "  Getting Foundry project endpoint..."

AI_SERVICES_NAME=$(azd env get-value FOUNDRY_AI_SERVICES_NAME 2>/dev/null)

FOUNDRY_BASE=$(az cognitiveservices account show \
    --name "$AI_SERVICES_NAME" \
    --resource-group "$RG" \
    --query "properties.endpoints.\"AI Foundry API\"" -o tsv 2>/dev/null | sed 's|/$||')

ENDPOINT="${FOUNDRY_BASE}/api/projects/${PROJECT}"

echo "  Endpoint: $ENDPOINT"

# ── Fill in .env files ────────────────────────────────────────────────────
fill_env() {
    file="$1"
    [ -f "$file" ] || return

    sed -i "s|FOUNDRY_PROJECT_ENDPOINT=.*|FOUNDRY_PROJECT_ENDPOINT=${ENDPOINT}|" "$file"
    sed -i "s|FOUNDRY_MODEL=.*|FOUNDRY_MODEL=${MODEL}|" "$file"

    # Remove placeholder markers so run-labs.sh doesn't reject the file
    sed -i "s|<YOUR_FOUNDRY_RESOURCE>[^>]*||g" "$file"
    sed -i "s|<YOUR_PROJECT_NAME>[^>]*||g" "$file"
}

fill_env "$ROOT/01-basic-agent/.env"
fill_env "$ROOT/02-mcp-tool-agent/.env"
fill_env "$ROOT/03-custom-function-tool-agent/.env"
fill_env "$ROOT/04-tracing-agent/.env"

# App Insights connection string (labs 02 and 04)
for f in "$ROOT/02-mcp-tool-agent/.env" "$ROOT/04-tracing-agent/.env"; do
    [ -f "$f" ] || continue
    if grep -q "^APPLICATIONINSIGHTS_CONNECTION_STRING=" "$f"; then
        sed -i "s|APPLICATIONINSIGHTS_CONNECTION_STRING=.*|APPLICATIONINSIGHTS_CONNECTION_STRING=${AI_CONN}|" "$f"
    else
        echo "APPLICATIONINSIGHTS_CONNECTION_STRING=${AI_CONN}" >> "$f"
    fi
done

echo ""
echo "✓ All .env files configured."
echo ""
echo "  Run the labs with:  ./run-labs.sh"
echo "  Tear down with:     azd down"
echo ""
