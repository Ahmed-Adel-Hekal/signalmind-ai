#!/usr/bin/env bash
set -euo pipefail

echo "==> AI Content Factory desktop setup starting..."

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is not installed."
  exit 1
fi

if [ ! -f "requirements.txt" ]; then
  echo "ERROR: run this script from project root (where requirements.txt exists)."
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "==> Creating virtual environment (.venv)"
  python3 -m venv .venv
fi

echo "==> Activating virtual environment"
source .venv/bin/activate

echo "==> Upgrading pip"
python -m pip install --upgrade pip

echo "==> Installing requirements"
pip install -r requirements.txt

if [ ! -f ".env" ]; then
  echo "==> Creating .env template"
  cat > .env <<'EOF'
GEMINI_API_KEY=
AIML_API_KEY=
OPENROUTER_API_KEY=
EOF
  echo "NOTE: .env created. Add your API keys before full generation."
fi

echo
echo "✅ Setup complete."
echo "Next steps:"
echo "1) source .venv/bin/activate"
echo "2) edit .env and add GEMINI_API_KEY or OPENROUTER_API_KEY (AIML_API_KEY for video)"
echo "3) streamlit run app.py"
