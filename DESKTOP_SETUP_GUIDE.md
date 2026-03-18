# Desktop Setup Guide (Beginner Friendly)

Use this guide if you want to run the app on your own computer.

---

## 1) Install Python (one-time)

- Go to: https://www.python.org/downloads/
- Download **Python 3.11+**
- During install, make sure **"Add Python to PATH"** is checked (Windows).

Verify install:

```bash
python3 --version
```

If that fails on Windows, try:

```bash
python --version
```

---

## 2) Open Terminal in project folder

After extracting/cloning the project, open Terminal in the folder where `app.py` exists.

You should see files like:
- `app.py`
- `requirements.txt`
- `pages/`
- `core/`

---

## 3) Run one-command setup

### Mac/Linux

```bash
chmod +x scripts/setup_desktop_env.sh
./scripts/setup_desktop_env.sh
```

### Windows (PowerShell)

Use these commands instead:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Then create `.env` file in project root with:

```env
GEMINI_API_KEY=
AIML_API_KEY=
```

---

## 4) Add API keys

Open `.env` and fill values:

```env
GEMINI_API_KEY=your_real_key_here
AIML_API_KEY=your_real_key_here
```

- `GEMINI_API_KEY` is needed for content + image generation.
- `AIML_API_KEY` is optional (needed for Veo video generation).

---

## 5) Start app

### Mac/Linux

```bash
source .venv/bin/activate
streamlit run app.py
```

### Windows PowerShell

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

---

## 6) Open in browser

Terminal will print a URL like:

- `http://localhost:8501`

Open it in browser.

---

## 7) Use the app

1. Open **Generate** page in sidebar.
2. Fill topic/platform/content type.
3. Click **Generate**.
4. Review ideas in tabs.

---

## Common issues

### A) `streamlit: command not found`
Run:

```bash
pip install streamlit
```

### B) Missing package error
Run:

```bash
pip install -r requirements.txt
```

### C) App runs but no generated media
- Check `.env` keys are correct.
- Static/video generation needs valid API keys.

