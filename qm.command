#!/usr/bin/env bash
# ============================================================================
#  LCHQMDriver launcher (macOS / Linux)
#  Usage:  ./qm.command start   -> launch the QUAlibrate server (default)
#          ./qm.command setup   -> run the interactive QUAlibrate configuration
#          double-click         -> same as "start"  (macOS Finder)
#
#  First-time setup:  chmod +x qm.command
# ============================================================================

# --- Edit this to target a different conda environment ----------------------
ENV_NAME="LCHQM"
# ----------------------------------------------------------------------------

# Default action is "start" when no argument / double-clicked
CMD="${1:-start}"

pause() {
    # Keep a double-clicked Terminal window from vanishing before output is read
    echo
    read -n 1 -s -r -p "Press any key to close..."
    echo
}

# Run from the folder this script lives in (so relative config paths resolve)
cd "$(dirname "$0")" || exit 1

# Locate the conda installation base
CONDA_BASE=""
if command -v conda >/dev/null 2>&1; then
    CONDA_BASE="$(conda info --base 2>/dev/null)"
else
    for d in "$HOME/miniconda3" "$HOME/anaconda3" "$HOME/miniforge3" \
             "/opt/miniconda3" "/opt/anaconda3" \
             "/opt/homebrew/Caskroom/miniconda/base"; do
        if [ -x "$d/bin/conda" ]; then
            CONDA_BASE="$d"
            break
        fi
    done
fi

if [ -z "$CONDA_BASE" ] || [ ! -f "$CONDA_BASE/etc/profile.d/conda.sh" ]; then
    echo "[ERROR] Could not find a conda installation."
    echo "        Install conda, or edit CONDA_BASE detection in this script."
    pause
    exit 1
fi

# Native activation (so the interactive 'setup-qualibrate-config' prompts work)
# shellcheck disable=SC1091
source "$CONDA_BASE/etc/profile.d/conda.sh"
if ! conda activate "$ENV_NAME"; then
    echo "[ERROR] Could not activate conda environment \"$ENV_NAME\"."
    echo "        Check the ENV_NAME variable at the top of this script."
    pause
    exit 1
fi

echo "Activated conda environment \"$ENV_NAME\"."

case "$CMD" in
    setup)
        setup-qualibrate-config
        pause
        ;;
    start)
        qualibrate start
        ;;
    *)
        echo "[ERROR] Unknown command \"$CMD\"."
        echo "Usage: ./qm.command [start|setup]"
        pause
        exit 1
        ;;
esac
