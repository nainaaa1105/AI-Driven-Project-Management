#!/usr/bin/env bash
# ============================================================
# setup.sh — Virtual Environment Bootstrap for Risk Engine
# ============================================================

set -e  # exit immediately on any error

VENV_DIR="venv"

echo ">>> Creating virtual environment in './${VENV_DIR}' ..."
python -m venv "${VENV_DIR}"

echo ">>> Activating virtual environment ..."
# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate"

echo ">>> Upgrading pip ..."
pip install --upgrade pip

echo ">>> Installing project dependencies from requirements.txt ..."
pip install -r requirements.txt

echo ""
echo "============================================================"
echo " Setup complete!"
echo " Run: source ${VENV_DIR}/bin/activate"
echo " Then: python risk_model.py"
echo "============================================================"
