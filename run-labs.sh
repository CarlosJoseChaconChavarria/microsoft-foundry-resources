#!/usr/bin/env bash
# Run a selected lab (01-04).
# Prerequisites: az login, and a .env file in each lab folder.

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv"

# ── colours ──────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; RED='\033[0;31m'; BOLD='\033[1m'; RESET='\033[0m'

pass() { echo -e "${GREEN}✓ $1${RESET}"; }
fail() { echo -e "${RED}✗ $1${RESET}"; exit 1; }
header() { echo -e "\n${BOLD}━━━ $1 ━━━${RESET}"; }

# ── pick a lab ───────────────────────────────────────────────────────────
echo -e "\n${BOLD}Which lab do you want to run?${RESET}"
echo "  1) Lab 01 · Basic Agent"
echo "  2) Lab 02 · MCP Tool Agent"
echo "  3) Lab 03 · Custom Function Tool"
echo "  4) Lab 04 · Tracing Agent"
echo ""
printf "Enter 1-4: "
read -r choice

case "$choice" in
    1) LAB_NUM="01"; LAB_DIR="01-basic-agent";                   LAB_SCRIPT="01-basic-agent.py" ;;
    2) LAB_NUM="02"; LAB_DIR="02-mcp-tool-agent";                LAB_SCRIPT="02-mcp-tool-agent.py" ;;
    3) LAB_NUM="03"; LAB_DIR="03-custom-function-tool-agent";    LAB_SCRIPT="03-custom-function-tool-agent.py" ;;
    4) LAB_NUM="04"; LAB_DIR="04-tracing-agent";                 LAB_SCRIPT="04-tracing-agent.py" ;;
    *) fail "Invalid choice '$choice'. Please enter a number between 1 and 4." ;;
esac

# ── check az login ────────────────────────────────────────────────────────
header "Checking prerequisites"
az account show --query name -o tsv > /dev/null 2>&1 || fail "Not signed in to Azure. Run: az login"
pass "Azure CLI signed in"

# ── check .env for selected lab ───────────────────────────────────────────
env_file="$ROOT/$LAB_DIR/.env"
if [ ! -f "$env_file" ]; then
    fail "Missing $LAB_DIR/.env — run: cp $LAB_DIR/.env.example $LAB_DIR/.env and fill in the values."
fi
if grep -q "<YOUR_" "$env_file"; then
    fail "$LAB_DIR/.env still has unfilled placeholders — open it and replace the <YOUR_...> values."
fi
pass ".env file ready"

# ── virtual environment ───────────────────────────────────────────────────
header "Setting up virtual environment"
if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
    pass "Created .venv"
else
    pass "Reusing existing .venv"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet \
    agent-framework \
    agent-framework-foundry \
    azure-monitor-opentelemetry \
    opentelemetry-sdk \
    python-dotenv
pass "Dependencies installed"

# ── run the selected lab ─────────────────────────────────────────────────
header "Lab $LAB_NUM"
cd "$ROOT/$LAB_DIR"
if python "$LAB_SCRIPT"; then
    pass "Lab $LAB_NUM completed successfully"
else
    fail "Lab $LAB_NUM failed — check output above"
fi
