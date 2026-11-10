# Maya implementation plan

## Architecture summary

Maya uses an Electron main/preload shell around a React + TypeScript + Vite renderer, a supervised loopback FastAPI service, and SQLite. Renderer code never receives backend or provider credentials. Phase 1 startup, health, migrations, narrow IPC, and log redaction remain in place. Phase 2 has the configured-provider conversation path: mic/VAD audio segment → Gnani STT → Gemini or OpenAI streaming LLM → sentence boundaries → Gnani TTS SSE → scheduled PCM playback. Live/manual end-to-end validation still requires valid provider keys and an app restart after configuration changes.

## Phases

| Phase | Status |
|---|---|
| 1 Foundation | Working |
| 2 Voice core | Partial |
| 3 Command pipeline | Not implemented |
| 4 Screen awareness | Not implemented |
| 5 Memory and settings | Not implemented |
| 6 Companion | Not implemented |
| 7 Knowledge/proactive | Not implemented |
| 8 Hardening/packaging | Not implemented |

## Phase 2 status (2026-11-07)

| Feature | Status | Evidence / limits |
|---|---|---|
| Gnani research and language/voice matrix | Working | Official docs and UNVERIFIED account limits recorded in `docs/LANGUAGES.md`. Streaming transcripts are final per VAD segment (`is_final: true`); interim text deltas are not documented. |
| STT/TTS interfaces and capability introspection | Working | Abstract speech contract; documented Gnani REST STT and SSE TTS; explicit no-recognition mock. |
| Gemini/OpenAI streaming LLM | Partial | Gemini GenerateContent SSE adapter uses the documented `x-goog-api-key` header, profile instructions, and language directive. `MAYA_LLM_PROVIDER=auto` prefers Gemini when `GEMINI_API_KEY` is set; OpenAI remains available by selecting `openai`. Provider access and account/model entitlement need live validation. |
| Mic → STT → LLM → TTS → playback | Partial | Connected `/voice/turn` SSE path; sentence deltas and audio chunks flow through Electron's authenticated IPC to the UI PCM queue. Live end-to-end use requires both keys and provider entitlement. |
| Transcript and response overlay | Working | Interim transcript area, finalized STT transcript, streamed assistant text, transcribing state, and speaking state are surfaced. Gnani documents final utterance segments, not partial text. |
| Gapless playback scheduling | Working | Shared PCM scheduler queues each TTS chunk by sample duration; simulated tests verify contiguous scheduling and interruption clears/stops queued sources. Device/speaker QA remains. |
| Barge-in by voice/hotkey/click/“stop” | Partial | Hands-free speech onset, Ctrl+Space, Stop Maya click, and recognized stop phrase cancel the turn request and scheduled playback. Echo behavior and live provider cancellation require manual QA. |
| Microphone selection and persistence | Partial | Enumerates inputs and persists device ID in local settings (`localStorage`). Device IDs/labels and hot switching require Windows device testing. |
| Language preference, explicit requests, unsupported voice language | Partial | Script/romanized detection and explicit “answer in Tamil” style directives; unsupported voice languages direct the LLM to explain in the user's detected supported language. Recognition accuracy is not guaranteed. |
| Provider retries, timeouts, circuit breaker, redacted timings | Partial | Gnani retry/timeout/circuit breaker; LLM/STT/TTS timing logs exclude content. Live latencies cannot be measured without keys. |
| Real-time partial STT | Not implemented | Official streaming transport is documented, but transcript events are final per utterance. The app uses REST after local VAD and shows “Transcribing…” until completion. |
| Phase 1 foundation and security | Working | Existing health, env validation, SQLite migration, token isolation, trusted IPC, and redaction tests still pass. |

## Provider configuration and measured latency

Set `GNANI_API_KEY` and `GEMINI_API_KEY` in `backend/.env` to enable live speech and Gemini. `MAYA_LLM_PROVIDER=auto` prefers Gemini; an OpenAI key must use `OPENAI_API_KEY` and provider `openai`. A Gemini key placed in `OPENAI_API_KEY` is sent to OpenAI and rejected, producing an HTTP 401. Restart Maya after editing `.env`; credentials are loaded at backend startup. The renderer records per-turn first finalized transcript and first audio timing without recording audio/text. The backend logs LLM first-token and Gnani TTS first-chunk latency.

| Requested metric | English | Indian language | Result / reason |
|---|---|---|---|
| Time to first partial transcript | N/A | N/A | Gnani's official streaming transcript event is documented as final for each VAD segment (`is_final: true`); interim partial text is not documented. |
| Time from end of speech to first final transcript | Unmeasured | Unmeasured (Tamil) | No Gnani key configured, so no live STT requests were made. |
| Time from end of speech to first audio | Unmeasured | Unmeasured (Tamil) | No Gnani/OpenAI keys configured, so no live conversation/TTS requests were made. |

Do not treat mock timings as provider measurements. Optional live Gnani STT and OpenAI streaming tests run only when their respective keys are configured.

## Verification record

- Earlier `npm run lint`, `npm run build`, and `npm test` passed before adding Gemini support. Re-run the checks below for the Gemini change before treating it as verified.
- `npm run dev` — starts Vite, Electron, and the supervised Python backend together. Startup reserves a free Vite port and passes its exact URL to Electron, verified with port 5173 occupied.
- Fixed the white renderer screen: the playback queue was CommonJS but Vite serves browser modules; it is now an ES module. Dev CSP allows Vite's local React bootstrap/HMR while packaged CSP remains strict. Electron diagnostic confirmed React mounted, and the Maya UI tree shows the mock badge, healthy local service, language/mic controls, and transcript/reply areas.
- Coverage includes Hinglish/Manglish detection, explicit language selection, unsupported language routing, provider mock/contract, streamed sentence pipeline, delayed cancellation, playback timing/interruption, and existing Phase 1 security/redaction tests.
- No Phase 3 code or actions were started.
