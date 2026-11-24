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
(cd protocol && uv sync --extra dev)
for s in hearing speech brain body; do
    echo "── $s"
    (cd "services/$s" && uv sync --extra dev)
done

echo ""
echo "Autostart on the Pi (units assume /home/pi/robot-tyapa, user pi — edit if different):"
echo "  sudo cp systemd/tyapa@.service systemd/tyapa.target /etc/systemd/system/"
echo "  sudo systemctl daemon-reload && sudo systemctl enable --now tyapa.target"
echo ""
echo "Done. Put LLM_PROVIDER / API key in services/brain/.env (never in git)."
echo "Run 'just' to see available commands."
