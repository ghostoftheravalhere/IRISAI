#!/usr/bin/env bash
# setup.sh — Bootstrap the full dev environment (run once after cloning)
set -e

echo "==> Setting up IRIS AI backend..."
cd backend
python -m venv .venv
source .venv/Scripts/activate 2>/dev/null || source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp ../.env.example ../.env
echo "Backend ready."

echo "==> Setting up IRIS AI frontend..."
cd ../frontend
npm install
echo "Frontend ready."

echo ""
echo "Setup complete."
echo "  Start backend : cd backend && python main.py"
echo "  Start frontend: cd frontend && npm run dev"
