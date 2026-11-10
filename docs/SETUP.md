# Maya setup

## Requirements
- Windows 10/11, Node.js LTS and npm
- Python 3.11 or later

## Development
Create the backend environment and install its dependencies:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
npm ci
npm run dev
```

The single `npm run dev` command starts Vite on a free loopback port, passes that exact URL to Electron, then launches the supervised FastAPI service. Electron generates a separate random backend port and token, waits for its authenticated health response after SQLite migrations, and only then opens the window. This avoids stale pages when another Vite process already owns port 5173. The renderer can request sanitized status through the narrow preload IPC bridge. The SQLite database and rotating redacted logs are stored under Electron's per-user `userData` directory.

## Credentials and live conversation
No keys are required in mock mode. To enable live conversation, set `GNANI_API_KEY` and `GEMINI_API_KEY` in `backend/.env`. `MAYA_LLM_PROVIDER` defaults to `auto` and prefers Gemini if its key is present; use `gemini` or `openai` to force a provider. `MAYA_LLM_MODEL` defaults to `gemini-2.5-flash`. An OpenAI key must be set as `OPENAI_API_KEY` and paired with `MAYA_LLM_PROVIDER=openai` (or used as the auto fallback when no Gemini key is present). A Gemini key must never be put under `OPENAI_API_KEY`. Keys stay in the backend and are never passed to Electron's renderer or logged. Missing providers leave that part of the app in clearly labeled mock mode; mock mode does not recognize audio or fabricate spoken output. Never commit `backend/.env`.

## What to configure later
For a packaged build, install Python separately and configure `MAYA_PYTHON` to its executable if it is not on PATH. The current installer script packages backend source, not a Python runtime or virtual environment. Gnani account entitlements, live latency, microphone permission and device selection, and Windows hotkey behavior need manual verification. Consult `LANGUAGES.md` for documented speech support and limits.
