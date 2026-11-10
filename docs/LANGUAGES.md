# Gnani speech and language support

Research checked: 2026-11-07 against Gnani's current official developer documentation. These are published capabilities; access and quotas still depend on the Maya account. Maya must not treat documentation coverage as proof of account entitlement.

## Models, authentication, and endpoints (verified)

| Service | Documented model(s) | Endpoint and authentication |
|---|---|---|
| STT REST | Prisma v2.5 (default when omitted), Prisma v3.0 | `POST https://api.vachana.ai/stt/v3`, multipart `audio_file`, `model`, `language_code`; `X-API-Key-ID` header |
| STT WebSocket | Prisma v3.0 in documented streaming example | `wss://api.vachana.ai/stt/v3/stream`; `x-api-key-id`, `language_code`, `model` headers |
| TTS REST | Timbre v2.5 and v3.0 | `POST https://api.vachana.ai/api/v1/tts/inference`; `X-API-Key-ID` header |
| TTS SSE | Timbre v2.5 and v3.0 | `POST https://api.vachana.ai/api/v1/tts/sse`; `X-API-Key-ID` header |

The auth value is an API key in the `X-API-Key-ID` header. Never send it to the renderer or log it. The HTTP API uses the `api.vachana.ai` base URL. Only these documented routes are implemented. STT REST accepts WAV, MP3, OGG, FLAC, AAC and M4A, up to 30 seconds. STT WebSocket accepts raw mono signed 16-bit little-endian PCM at documented rates including 16 kHz (the documented frame example is 1024 bytes / 32 ms at 16 kHz). Streaming STT returns transcript events and, with Prisma v3, `detected_language_code`. The docs specify `is_final: true` for transcript events: real-time audio streaming is supported, but incremental interim transcript text is not documented. Maya therefore shows “Transcribing…” until a segment transcript arrives. The docs describe a 15-minute session maximum and 60-second default idle timeout. Streaming STT has server VAD; this does not replace Maya's local adjustable VAD.

TTS request fields documented by the API are `text`, `voice`, `model`, `language`, `speed`, and `audio_config`. TTS audio is mono, 16-bit PCM; documented sample rates are 8, 16, 22.05, 24, 44.1 and 48 kHz, with WAV default and raw PCM, MP3, OGG, mu-law and A-law options. Timbre SSE returns ordered base64 audio chunks and a completion event. OGG is not streamed chunk-by-chunk. SSE documentation specifies one active request per organization and possible HTTP 429. Supported speed range is 0.85–1.15.

## Language coverage

| Language | Locale | Prisma v2.5/v3.0 STT | Timbre v2.5 TTS sample voices | Timbre v3.0 TTS |
|---|---|---|---|---|
| English | `en-IN` | Documented | Kaveri, Trupti, Devika, Pranav, Shlok, Girish | All 13 v3 voices |
| Hindi | `hi-IN` | Documented | Nalini, Bhavna, Yashvi, Urmila, Jwala, Chitra, Ambuja, Deepak, Roopesh, Vikrant, Hemraj, Jalaj, Omkar | All 13 v3 voices |
| Malayalam | `ml-IN` | Documented | Reshma, Riyaan | All 13 v3 voices |
| Kannada | `kn-IN` | Documented | Saanvi, Kavin | All 13 v3 voices |
| Tamil | `ta-IN` | Documented | Asmita, Trisha, Brinda, Vedika, Noopur | All 13 v3 voices |
| Telugu | `te-IN` | Documented | Suhana, Lehara, Lavanya, Yukti, Varuni | All 13 v3 voices |
| Bengali | `bn-IN` | Documented | Kirra, Dhruva | All 13 v3 voices |
| Marathi | `mr-IN` | Documented | Zahira, Ishaan | All 13 v3 voices |
| Gujarati | `gu-IN` | Documented | Falak, Veera | All 13 v3 voices |
| Punjabi | `pa-IN` | Documented | Mehuli, Zayan | All 13 v3 voices |

Timbre v2.5 includes the `hi-en` Hinglish locale and Poorvi voice. Timbre v3 documents 13 multilingual voices (Avinash, Shivani, Lakshmi, Kalpana, Chetana, Vasudha, Riyaa, Tarika, Shubham, Prakash, Devansh, Yashraj, Harshad), each covering the ten listed languages. Its `auto` mode is documented as script-based; it is not evidence of romanized-language detection. Prisma v3 documents code-mix (`codemix`) and transliteration output options and up to four locale hints; Maya's romanized-language recognizer is a local heuristic, not a claim about Gnani.

## Limits and UNVERIFIED items

- STT REST's 30-second cap, WebSocket session/idle limits, TTS SSE one-request concurrency, and documented TTS speed/sample-rate bounds are above.
- Exact organization concurrency beyond the TTS SSE statement, monthly quota, pricing, per-key rate limits, and numeric TTS text-size maximum: **UNVERIFIED** in the reviewed public API pages. A 429 response is possible.
- Account entitlement, availability by API key, and observed quality/latency: **UNVERIFIED** until configured and live-tested.
- Streaming transport is documented for STT WebSocket and TTS SSE/WebSocket. Gnani's STT `transcript` event is documented with `is_final: true` for each completed VAD segment; no interim partial text event is documented. Maya uses the verified STT REST endpoint and therefore displays “Transcribing…” until the final segment response. TTS uses the documented SSE endpoint.
- Response details not explicitly relied upon by Maya are not assumed. Live tests are skipped unless `GNANI_API_KEY` is configured.

## Official sources

- [Gnani API introduction](https://docs.gnani.ai/api/introduction/introduction)
- [STT speech-to-text](https://docs.gnani.ai/api/STT/speech-to-text)
- [STT WebSocket streaming](https://docs.gnani.ai/api/STT/stt-websocket)
- [TTS inference](https://docs.gnani.ai/api/TTS/tts-inference)
- [TTS SSE streaming](https://docs.gnani.ai/api/TTS/tts-sse)
- [TTS WebSocket streaming](https://docs.gnani.ai/api/TTS/tts-websocket)
- [Prisma v3 product page](https://www.gnani.ai/resources/prisma-v3)
- [OpenAI Responses API streaming guide](https://platform.openai.com/docs/guides/streaming-responses)

## Maya integration status

Gnani and OpenAI providers are feature-gated and selected only when their corresponding backend keys are configured. The mock provider is explicitly labeled and never represents recognition or synthesis. Verify configured API keys and account entitlements before live use. No API key is committed or passed into renderer code.
