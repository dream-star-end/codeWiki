#!/usr/bin/env bash
set -euo pipefail

echo "Creating venv..."
python3 -m venv .venv

echo "Activating venv..."
source .venv/bin/activate

echo "Installing dependencies..."
python -m pip install -r backend/requirements.txt

echo "Starting server..."
python -m uvicorn app.main:app --reload --app-dir backend
