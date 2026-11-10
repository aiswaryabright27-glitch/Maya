# Maya Handoff — VoiceOS build state

## Reality check
Antigravity's run wrote docs claiming ~85 features "Working" — **false**; the matrix has been rewritten honestly. Current real state: voice loop works end-to-end; agent core + computer-control layer now exist as real (partially tested) code.

## What works now (code exists; see matrix for verification level)
- Voice: mic → Gnani STT → Gemini `gemini-3.1-flash-lite` → Gnani TTS → playback; barge-in, PTT, hands-free VAD w/ noise gate; 10-lang routing (mr/hi ambiguity + 1 Hinglish case still fail tests).
- `/voice/turn` now routes transcripts through `agent/router.py`: stop/open-app/open-url/search/time/file/terminal/dictate commands execute via `agent_executor` and the report is spoken via TTS. Everything else falls through to the LLM.
- `POST /agent/command {"text": ...}` — same router for typed commands.
- `backend/app/agent/`: permissions (5 levels), audit (SQLite), registry (schema validation), router, executor (budgets/cancel), builtin tools.
- `backend/app/computer/`: windows (EnumWindows/focus/secure-desktop heuristic), apps (start-verb launch, WM_CLOSE), files (allowed-roots search/read/organize+undo), terminal (allowlist, no shell, cwd bounds, timeouts), projects (SQLite registry+aliases), undo stack, input (dictate/click/scroll via Win32+clipboard).
- Frontend robot-over-desk animation + voice isolation profiles.

## Test state
`cd backend && .venv/Scripts/python.exe -m pytest ../tests -q` → **29 passed, 2 failed** (pre-existing `test_multilingual_smoke.py`: mr-vs-hi Devanagari ambiguity; one Hinglish phrase), 1 skipped. New: `tests/test_agent_core.py` 7/7.

## Remaining, priority order
1. **Verify computer control live on Windows** — modules are written but NOT exercised end-to-end (open app, search file, run allowlisted command, dictate). Add `tests/test_computer.py` with sandboxed cases; then the MathMate/VS Code acceptance example.
2. **UIA layer** — real control of buttons/fields needs `comtypes`/`pywinauto` (new dep) or PowerShell UIAutomation; current input.py is coordinate/clipboard level only.
3. **Voice confirmations** — `needs_confirmation` results currently just speak the report; needs a pending-confirmation state + "yes/no" handling in `/voice/turn`.
4. **Agent events → frontend** — `docs/EVENTS.md` schema exists; executor emits via `on_event` callback but nothing streams it to the renderer; add SSE/IPC + task panel.
5. **Step D screen** — `backend/app/screen/`: PIL ImageGrab capture (pillow installed), Windows OCR (needs `winsdk` or Tesseract — manual config), consent flags.
6. **Step E Gmail** — full `backend/app/gmail/` + `docs/GMAIL_SETUP.md`; user must create Google Cloud OAuth Desktop client.
7. **Step F memory** — `backend/app/memory/`: SQLite conversations/FTS5/long-term approvals/preferences.
8. **Step G productivity** — reminders/tasks/notifications/scheduler.
9. **Step H UI** — chat panel, task panel, confirmation dialogs, settings, tray, Noto Indic fonts; security pass; packaging (`MAYA_PYTHON`, Python runtime not bundled).
10. Fix 2 failing smoke tests honestly; wake word; Caps Lock hotkey+rebinding; conversation history (V-09); per-language command aliases; LLM task planner → `run_plan`.

## Key files
- Voice: `backend/app/main.py` (`/voice/turn`), `voice.py`, `conversation.py`
- Agent: `backend/app/agent/*.py`; Computer: `backend/app/computer/*.py`
- Frontend: `frontend/src/{main.tsx,audioQueue.mjs,style.css}`; Electron: `electron/main.cjs`
- Env: `backend/.env` — GNANI_API_KEY, GEMINI_API_KEY, MAYA_LLM_MODEL=gemini-3.1-flash-lite
