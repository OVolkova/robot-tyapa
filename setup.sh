#!/usr/bin/env bash
set -euo pipefail

# ── uv ────────────────────────────────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # add to current session if installer didn't
    export PATH="$HOME/.local/bin:$PATH"
else
    echo "uv $(uv --version) already installed"
fi

# ── just ──────────────────────────────────────────────────────────────────────
if ! command -v just &>/dev/null; then
    echo "Installing just..."
    curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh \
        | bash -s -- --to "$HOME/.local/bin"
    export PATH="$HOME/.local/bin:$PATH"
else
    echo "just $(just --version) already installed"
fi

# ── project deps ──────────────────────────────────────────────────────────────
echo "Installing project dependencies..."
uv sync --extra dev

echo ""
echo "Done. Run 'just' to see available commands."
