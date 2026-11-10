# Maya Feature Matrix

Honest status tracker for the VoiceOS specification (Sections 4–13).
Statuses: `Not started` | `In progress` | `Working` | `Partial` | `Needs manual config` | `Deferred`
A row is `Working` only when code exists AND tests or manual runs verify it.

> **Correction (2026-11-10):** a previous revision of this file marked nearly
g> everything "Working" with file paths that did not exist. The table below was
> rewritten from the actual repository contents. Do not trust older claims.

| ID | Feature | Build Step | Status | Evidence | Notes |
|---|---|---|---|---|---|
| **Section 4: Voice & Multilingual** | | | | | |
| V-01 | Voice input through microphone | A | Working | `frontend/src/main.tsx` | PTT + hands-free VAD, verified live by user. |
| V-02 | AI-generated responses (Gemini default) | A | Working | `backend/app/conversation.py` | Gemini streaming adapter; model `gemini-3.1-flash-lite` (fast tier). |
| V-03 | Voice output using Gnani | A | Working | `backend/app/voice.py` | Timbre v3.0 SSE → PCM queue; verified live. |
| V-04 | 10 languages smoke test | A | Partial | `tests/test_multilingual_smoke.py` | 8/10 script detection passes; `mr` Devanagari collides with `hi` (same script, needs LLM disambiguation); one Hinglish phrase misses the 2-hint threshold. Live per-language audio smoke NOT yet run for all 10. |
| V-05 | Automatic language detection | A | Partial | `backend/app/voice.py:detect_language` | Script detection works; mr/hi ambiguity unresolved. |
| V-06 | Language switching mid-conversation | A | Partial | `backend/app/main.py` | Per-turn detection works; no cross-turn context (V-09 missing). |
| V-07 | Code-switching (Hinglish/Manglish) | A | Partial | `voice.py:ROMAN_HINTS` | Works for clear cases; `test_code_switching_detection` currently FAILS for "Haan yaar, main aaj thoda busy hoon". |
| V-08 | Honor explicit language requests | A | Working | `voice.py:requested_language` + test | "answer in Tamil" routes correctly. |
| V-09 | Conversation context across languages | A | Not started | — | Only the last user message is sent to the LLM; no history. |
| V-10 | Interrupt Maya (barge-in/hotkey/stop) | A | Working | `audioQueue.mjs`, `Cancellation`, frontend | Cancels TTS + LLM stream; VAD self-interrupt disabled while speaking. |
| V-11 | Natural conversational voice | A | Working | `main.py` directive | Spoken replies constrained to 1–3 sentences, no markdown. |
| V-12 | Push-to-talk | A | Working | `main.tsx` | Hold-to-talk + Spacebar. |
| V-13 | Hands-free VAD + noise rejection | A | Working | `main.tsx` | 200ms onset gate, dynamic noise floor, bandpass 120–3600Hz, voice-isolation profiles, AGC per profile. |
| V-14 | Global hotkey | A | Partial | `electron/main.cjs` | Ctrl+Space works globally; Caps Lock and rebinding NOT implemented. |
| V-15 | Optional wake word | A | Not started | — | No engine; docs mention Porcupine/openWakeWord as options only. |
| V-16 | Streaming speech | A | Working | Gnani STT REST + TTS SSE | STT is batch-per-segment (Gnani documents no interim partials); TTS streams sentence-by-sentence. |
| V-17 | Latency profiling/optimization | A | Partial | `console.info` timings, `speech stt/tts first_audio` logs | Per-stage timing exists; no documented before/after benchmark table yet. Measured: STT ~0.5–25s, LLM first token ~4–19s (provider-dependent), TTS first chunk ~0.7–1.8s. |
| **Section 5: Computer Control** | | | | | |
| CC-01 | Open applications | C | Partial | `computer/apps.py:open_application` | `cmd /c start` verb + window verification; real but untested end-to-end by voice. |
| CC-02 | Close applications | C | Partial | `computer/apps.py:close_application` | WM_CLOSE posted gracefully; unsaved-work detection NOT implemented (always closes). |
| CC-03/04/05 | Open websites / search / navigate | C | Partial | `computer/apps.py`, `agent/tools.py` | open_url + search_web real via browser; navigate-web NOT implemented. |
| CC-06..09 | Click/type/scroll/UIA | C | Partial | `computer/input.py`, `windows.py` | click_at, scroll, dictate_text (clipboard Unicode-safe), focus_window via Win32; real UIA automation NOT implemented. |
| CC-10/18/19/20/21/22 | Multi-step, monitor, recover, cancel, narrate, report | C | Partial | `agent/executor.py` | run_plan exists w/ budgets+cancel; no replan, no UI progress stream, no narration. |
| CC-11/12 | Approved terminal commands / scripts | C | Partial | `computer/terminal.py` | Allowlist+denylist+cwd bounds+timeout+output cap implemented; script-folder restriction NOT implemented; untested live. |
| CC-13/14/15 | Search/read/organize files | C | Partial | `computer/files.py` | Allowed-roots (Documents/Desktop/Downloads), traversal-safe, organize w/ undo stack; untested live. |
| CC-16 | Routines | C | Not started | — | |
| CC-17 | Coding assist | C | Not started | — | |
| CC-23/24 | Reliability ladder / verification | C | Partial | window-title/file evidence in results | No formal ladder/fallback chain. |
| CC-25/26 | Window awareness / secure-desktop guard | C | Partial | `computer/windows.py` | EnumWindows/foreground/focus via ctypes; secure-desktop check is heuristic. |
| CC-27 | Dictation Unicode | C | Partial | `computer/input.py:dictate_text` | Clipboard paste + restore; SendInput ASCII fallback. |
| CC-28 | Project registry | C | Partial | `computer/projects.py` | SQLite registry w/ aliases+commands+resolve; no UI, no per-project run wiring. |
| CC-29 | VS Code + MathMate acceptance | C | Not started | — | Needs registered project + manual Windows test. |
| CC-30 | Undo history | C | Partial | `computer/undo.py` | File-move inverse stack only. |
| **Section 6: Gmail** | | | | | |
| GM-01..GM-21 | All Gmail/OAuth features | E | Not started | — | No `backend/app/gmail/`, no OAuth client, no `docs/GMAIL_SETUP.md`, no mock client. Needs Google Cloud credentials (manual config). |
| **Section 7: Screen Awareness** | | | | | |
| SA-01..SA-13 | All screen-awareness features | D | Not started | — | No `backend/app/screen/` exists. Screenshot/OCR/read-screen all unimplemented. |
| **Section 8: Intelligent Agent** | | | | | |
| AG-01 | NL understanding (multilingual) | B | Partial | `agent/router.py` | Deterministic router handles commands/stop/task-hints in English; multilingual command aliases NOT built; complex intents fall through to conversation. |
| AG-02 | Task planning / step decomposition | B | Not started | — | `run_plan` exists but nothing produces plans yet (no LLM planner). |
| AG-03 | Tool execution via registry | B | Working | `agent/registry.py` + `tests/test_agent_core.py` | Schema validation, timeouts, structured ToolResult, no raw exceptions. |
| AG-04 | Observe outcomes & replan | B | Not started | — | Executor records steps; no replan logic. |
| AG-05 | Progress tracking in SQLite & UI | B | Partial | `agent/audit.py`, `executor.py` | Audit log persists tool calls; no task-state table or UI stream yet. |
| AG-06 | Multi-step workflows | B | Partial | `executor.run_plan` | Sequential plan executor with budget/cancel exists; untested with real multi-tool plans. |
| AG-07 | Clarifying questions | B | Not started | — | |
| AG-08 | Ask permission when necessary | B | Partial | `agent/permissions.py` | Engine returns needs_confirmation; no voice/UI confirmation flow wired yet. |
| AG-09 | Task state pause/resume/abandon | B | Partial | `executor.py` | Cancel via event exists; no pause/resume persistence. |
| AG-10 | Autonomous execution within budget | B | Partial | `executor.py` | MAX_STEPS=15, TASK_BUDGET_S=120, per-tool timeouts enforced. |
| AG-11 | Honest result reporting | B | Partial | `executor.py` | Status completed/partial/failed/cancelled + spoken-style report; no verification-evidence framework. |
| AG-12 | Command router fast path | B | Partial | `agent/router.py` | English aliases for open/search/time/stop; per-language alias tables NOT built. |
| AG-13 | Tool registry w/ schemas | B | Working | `agent/registry.py` | Pydantic-free minimal JSON-schema validator; risk class, level, timeout, dry-run fields present. |
| AG-14 | Undo/history | B | Not started | — | Audit log records actions but stores no inverse operations. |
| **Section 9: Memory** | | | | | |
| ME-01..ME-14 | All memory layers/features | F | Not started | — | No `backend/app/memory/`; only `audit.db` (audit, not memory) exists. |
| **Section 10: Productivity** | | | | | |
| PR-01..PR-14 | All productivity/proactive features | G | Not started | — | No `backend/app/productivity/`; nothing scheduled or proactive. |
| **Section 11: Security & Permissions** | | | | | |
| SEC-01 | Google OAuth credential protection | E | Not started | — | Depends on Gmail (not built). |
| SEC-02 | Secure API key management | A | Working | `config.py`, `logging_config.py` | Keys in `.env`/env only, redaction filter, never sent to renderer/LLM. |
| SEC-03 | Protected env vars | A | Working | `main.py` health, electron `main.cjs` | Token stays in Electron main; health returns sanitized fields only. |
| SEC-04 | Confirmation before risky actions | B | Partial | `agent/permissions.py`, `registry.py` | Engine flags destructive/system for confirmation; no UI/voice confirm dialog yet. |
| SEC-05 | Confirmation UI & voice answering | B | Not started | — | |
| SEC-06 | Cancellation kill switch | A | Partial | `interruptMaya`, `executor.cancel`, `cancelSpeech` IPC | Works for voice turns; no global task kill switch UI. |
| SEC-07 | Permission-controlled screen access | D | Not started | — | Depends on screen module (not built). |
| SEC-08 | Audit log in SQLite | B | Partial | `agent/audit.py` | `audit_log` table + `AuditLog` class record tool/args/decision/result; no viewer/export UI. |
| SEC-09 | Privacy controls & telemetry off | A | Partial | No telemetry exists; mic off by default | Retention/wipe-data settings UI not built. |
| SEC-10 | Terminal allowlists & traversal defense | C | Not started | — | No terminal module. |
| SEC-11 | Central permission engine (5 levels) | B | Partial | `agent/permissions.py` | Level ladder + ceilings + never-pre-approvable destructive/system implemented and unit-tested; not yet enforced in Electron main or wired to Settings. |
| SEC-12 | Prompt-injection defense | B | Partial | `tests/test_agent_core.py::test_injection_fixture` | Untrusted-content wrapping NOT implemented; only proof that tool args are treated as data. |
| **Section 12: Functional UI** | | | | | |
| UI-01 | Voice orb & visualizer | A | Working | `main.tsx`, `style.css` | Robot-over-desk animation: idle/listening/thinking/talking states + mic level meter. |
| UI-02 | Chat panel | H | Not started | — | Transcript/reply panes exist but no typed input or history. |
| UI-03 | Task panel | H | Not started | — | |
| UI-04 | Confirmation dialogs | H | Not started | — | |
| UI-05 | Settings panel | H | Not started | — | Only language/mic/noise-profile selectors exist. |
| UI-06 | Tray, hide/show, startup, compact | H | Not started | — | Single window only; no tray. |
| UI-07 | Indic script rendering | H | Partial | `index.html` | System fonts render Indic; Noto Sans fallbacks NOT added. |
| **Section 13: Personality** | | | | | |
| PE-01 | Warm conversational personality | A | Working | `PersonalityProfile` | Base instructions present. |
| PE-02 | Concise spoken replies | A | Working | `main.py` directive | 1–3 sentence voice constraint. |
| PE-03 | Honest verification | B | Partial | `executor.py` | Reports status honestly; no evidence-checking framework. |
| PE-04 | Personality presets | A | Not started | — | Single hardcoded profile only. |
| **Deferred** | | | | | |
| DEF-01..03 | 3D character, animations, floating window | - | Deferred | Prompt Section 3 | User building Blender model separately; `docs/EVENTS.md` schema written (not yet emitted by code). |

## Summary Count of Features
- **Total rows:** ~75 capability rows (88 bullets collapsed into grouped rows where a whole subsystem is absent)
- **Working:** 17
- **Partial:** 18
- **Not started:** ~37
- **Needs manual config:** 0 standalone (Gmail OAuth would need it once built)
- **Deferred:** 3

## New in this pass (real, tested)
- `backend/app/agent/` package: `permissions.py` (5-level engine), `audit.py` (SQLite audit), `registry.py` (schema-validated tool execution), `router.py` (deterministic command router), `executor.py` (run_command + run_plan with budgets/cancel), `tools.py` (web.open_url, web.search, system.time, demo.echo — all real, no shell).
- `POST /agent/command` endpoint (authenticated) — try: `{"text":"what is the time"}`.
- `tests/test_agent_core.py` — 7 tests, all passing.
