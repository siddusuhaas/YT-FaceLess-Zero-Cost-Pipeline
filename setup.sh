#!/usr/bin/env bash
# ============================================================
# YouTube Shorts Automation Pipeline - Environment Setup
# Apple M4 Mac | Python 3.10 venv
# ============================================================

set -e  # Exit immediately on any error

PYTHON="/opt/homebrew/bin/python3.10"
VENV_DIR="./venv"
OLLAMA_MODEL="llama3.2:3b"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   YouTube Shorts Pipeline — Environment Bootstrap    ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Step 1: System Dependencies ──────────────────────────────
echo "▶ [1/5] Installing system dependencies via Homebrew..."
brew install ffmpeg ollama
echo "   ✅ ffmpeg and ollama installed."

# ── Step 2: Python Virtual Environment ───────────────────────
echo ""
echo "▶ [2/5] Creating Python 3.10 virtual environment at ${VENV_DIR}..."
if [ -d "$VENV_DIR" ]; then
    echo "   ⚠️  venv already exists — skipping creation."
else
    "$PYTHON" -m venv "$VENV_DIR"
    echo "   ✅ venv created."
fi

# ── Step 3: Activate venv and install packages ────────────────
echo ""
echo "▶ [3/5] Installing Python packages inside venv..."
source "${VENV_DIR}/bin/activate"
pip install --upgrade pip --quiet
pip install -r requirements.txt
echo "   ✅ All Python packages installed."

# ── Step 4: Pull Ollama LLM Model ────────────────────────────
echo ""
echo "▶ [4/5] Pulling Ollama model: ${OLLAMA_MODEL}..."
echo "   (This may take a few minutes on first run — ~2GB download)"
# Start ollama serve in background if not already running
if ! pgrep -x "ollama" > /dev/null; then
    ollama serve &>/dev/null &
    OLLAMA_PID=$!
    sleep 3
    echo "   ℹ️  Started ollama server (PID: ${OLLAMA_PID})"
fi
ollama pull "$OLLAMA_MODEL"
echo "   ✅ Model ${OLLAMA_MODEL} ready."

# ── Step 5: Create output directory ──────────────────────────
echo ""
echo "▶ [5/5] Creating output directory..."
mkdir -p output
echo "   ✅ ./output/ directory ready."

deactivate

# ── Done ─────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   ✅ Setup Complete!                                  ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║   To generate a video, run:                          ║"
echo "║                                                      ║"
echo "║   source venv/bin/activate                           ║"
echo "║   python main.py \"Bhagavad Gita Chapter 2, Verse 47\"║"
echo "║                                                      ║"
echo "║   ⚠️  Make sure Draw Things app is running before    ║"
echo "║   generating images (it serves on localhost:7888)    ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
