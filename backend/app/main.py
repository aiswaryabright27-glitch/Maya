from __future__ import annotations

import hmac
import base64
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Body
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import Settings
from app.database import migrate_database
from app.logging_config import configure_logging
from app.voice import GnaniProvider, LANGUAGES, MockSpeechProvider, detect_language, route_language, requested_language, is_stop_phrase
from app.conversation import Cancellation, GeminiProvider, MockLLMProvider, OpenAIResponsesProvider, PersonalityProfile, stream_sentences
from app.agent.audit import AuditLog
from app.agent.executor import AgentExecutor
from app.agent.permissions import Level, PermissionEngine
from app.agent.registry import ToolRegistry
from app.agent.router import route
from app.agent.tools import register_builtin_tools
from app.computer.computer_tools import register_computer_tools


logger = logging.getLogger("maya")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_environment()
    gemini_model = settings.llm_model if settings.llm_model.startswith(("gemini-", "gemma-")) else "gemini-3.1-flash-lite"

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        applied = migrate_database(settings.database_path)
        application.state.database_ready = True
        if settings.mode == "mock":
            logger.warning("MAYA MOCK MODE: speech providers and desktop actions are disabled")
        logger.info("Maya backend ready; database migrations applied: %d", len(applied))
        yield
        application.state.database_ready = False

    application = FastAPI(title="Maya Local API", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None)
    application.state.database_ready = False
    application.state.speech = GnaniProvider(settings.gnani_api_key.get_secret_value()) if settings.gnani_api_key else MockSpeechProvider()
    if settings.llm_provider == "gemini" and settings.gemini_api_key:
        application.state.llm = GeminiProvider(settings.gemini_api_key.get_secret_value(), gemini_model)
    elif settings.llm_provider == "openai" and settings.openai_api_key:
        application.state.llm = OpenAIResponsesProvider(settings.openai_api_key.get_secret_value(), settings.llm_model)
    elif settings.llm_provider == "auto" and settings.gemini_api_key:
        application.state.llm = GeminiProvider(settings.gemini_api_key.get_secret_value(), gemini_model)
    elif settings.llm_provider == "auto" and settings.openai_api_key:
        application.state.llm = OpenAIResponsesProvider(settings.openai_api_key.get_secret_value(), settings.llm_model)
    else:
        application.state.llm = MockLLMProvider()

    @application.middleware("http")
    async def require_local_token(request: Request, call_next):
        provided = request.headers.get("authorization", "")
        expected = f"Bearer {settings.backend_token.get_secret_value()}"
        if not hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8")):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        return await call_next(request)

    audit_log = AuditLog(settings.data_dir / "audit.db")
    agent_registry = ToolRegistry(PermissionEngine(default_ceiling=Level.MODIFY), audit_log)
    register_builtin_tools(agent_registry)
    register_computer_tools(agent_registry, data_dir=settings.data_dir)
    application.state.agent_executor = AgentExecutor(agent_registry)

    @application.get("/healthz")
    async def health():
        return {
            "ok": True,
            "mode": settings.mode,
            "database_ready": application.state.database_ready,
            "capabilities": (["speech.stt", "speech.tts"] if settings.gnani_api_key else ["speech.mock"]) + (["llm.stream"] if not isinstance(application.state.llm, MockLLMProvider) else ["llm.mock"]),
        }

    @application.get("/voice/capabilities")
    async def voice_capabilities():
        return application.state.speech.capabilities().__dict__

    @application.post("/voice/transcribe")
    async def transcribe(payload: dict = Body(...)):
        encoded = payload.get("audio_base64")
        language = payload.get("language", "en")
        audio_format = payload.get("format", "wav")
        if not isinstance(encoded, str) or len(encoded) > 12_000_000:
            return JSONResponse(status_code=400, content={"error": "Invalid or oversized audio payload."})
        if language not in {*LANGUAGES, "auto"}:
            return JSONResponse(status_code=400, content={"error": "Unsupported language selection."})
        import base64
        try:
            audio = base64.b64decode(encoded, validate=True)
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "Invalid audio encoding."})
        if not settings.gnani_api_key:
            result = await application.state.speech.transcribe(audio, language, audio_format)
            return {"text": result.text, "language": result.language, "latency_ms": result.latency_ms, "mock": True}
        result = await application.state.speech.transcribe(audio, language, audio_format)
        return {"text": result.text, "language": result.language, "latency_ms": result.latency_ms, "mock": False}

    @application.post("/voice/turn")
    async def voice_turn(request: Request, payload: dict = Body(...)):
        encoded = payload.get("audio_base64")
        preferred = payload.get("language", "en")
        if not isinstance(encoded, str) or len(encoded) > 12_000_000 or preferred not in {*LANGUAGES, "auto"}:
            return JSONResponse(status_code=400, content={"error": "Invalid audio or language selection."})
        try:
            audio = base64.b64decode(encoded, validate=True)
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "Invalid audio encoding."})

        async def events():
            def send(kind: str, **fields) -> str:
                return f"data: {json.dumps({'type': kind, **fields}, ensure_ascii=False)}\n\n"

            cancellation = Cancellation()
            generated = sentence_stream = guarded = pending_tts = None
            try:
                yield send("status", value="transcribing")
                if not settings.gnani_api_key:
                    yield send("mock", message="Mock speech mode: no speech recognition is configured.")
                    yield send("done")
                    return
                transcript = await application.state.speech.transcribe(audio, preferred, "wav")
                # Text-based detection is authoritative: Indic script -> that language,
                # Latin text -> romanized hints -> 'en'. The provider's detected
                # language_code mislabels short commands, so it is not trusted here.
                detected, _ = detect_language(transcript.text, "en")
                base_language = preferred if preferred in LANGUAGES else detected
                if not transcript.text.strip():
                    fallback_msg = "Sorry, I didn't catch that. Please try again."
                    yield send("status", value=fallback_msg)
                    yield send("assistant_final", text=fallback_msg)
                    pending_tts = application.state.speech.synthesize(fallback_msg, base_language)
                    async for chunk in pending_tts:
                        if cancellation.cancelled:
                            return
                        yield send("audio", pcm_base64=base64.b64encode(chunk).decode("ascii"), sample_rate=24000)
                    yield send("done")
                    return
                output_language = requested_language(transcript.text) or base_language
                yield send("transcript", text=transcript.text, language=detected)
                if output_language == detected and is_stop_phrase(transcript.text):
                    yield send("done")
                    return
                routed = route(transcript.text)
                logger.info("voice route kind=%s tool=%s", routed.kind, routed.tool)
                if routed.kind == "stop":
                    yield send("done")
                    return
                if routed.kind == "tool" and routed.tool:
                    yield send("status", value=f"Running: {routed.summary}")
                    task = await application.state.agent_executor.run_command(routed, provenance="voice")
                    reply_text = task.report
                    yield send("assistant_final", text=reply_text)
                    pending_tts = application.state.speech.synthesize(reply_text, output_language)
                    async for chunk in pending_tts:
                        if cancellation.cancelled:
                            return
                        yield send("audio", pcm_base64=base64.b64encode(chunk).decode("ascii"), sample_rate=24000)
                    yield send("done")
                    return
                _, unsupported = route_language("", "fixed", output_language)
                if unsupported:
                    output_language = base_language
                if isinstance(application.state.llm, MockLLMProvider):
                    answer = "Mock mode: no language model is configured, so I cannot answer yet."
                    yield send("assistant_final", text=answer)
                    pending_tts = application.state.speech.synthesize(answer, output_language)
                    async for chunk in pending_tts:
                        if cancellation.cancelled:
                            return
                        yield send("audio", pcm_base64=base64.b64encode(chunk).decode("ascii"), sample_rate=24000)
                else:
                    if unsupported:
                        directive = f"Reply only in {LANGUAGES[detected]} ({detected}). The user's requested voice language ({output_language}) is unsupported by the configured speech model. Explain this briefly and politely in {LANGUAGES[detected]}, then continue in {LANGUAGES[detected]}. Keep your answer short, conversational, and direct for voice output; avoid markdown formatting, asterisks, bullet points, or lists."
                    else:
                        directive = f"Respond only in {output_language} ({LANGUAGES[output_language]}). The user's language preference is {LANGUAGES[base_language]}; honor their explicit supported language request. Keep your answer short, conversational, and direct for voice output (1-3 sentences); avoid markdown formatting, asterisks, bullet points, or lists."
                    profile = PersonalityProfile(instructions=f"{PersonalityProfile.instructions} {directive}")
                    generated = application.state.llm.stream([{"role": "user", "content": transcript.text}], profile)
                    sentence_stream = stream_sentences(generated)
                    guarded = cancellation.guard(sentence_stream)
                    answer = ""
                    async for kind, content in guarded:
                        if kind == "delta":
                            answer += content
                            yield send("assistant_delta", text=content)
                        else:
                            yield send("sentence", text=content)
                            pending_tts = application.state.speech.synthesize(content, output_language)
                            async for chunk in pending_tts:
                                if cancellation.cancelled:
                                    return
                                yield send("audio", pcm_base64=base64.b64encode(chunk).decode("ascii"), sample_rate=24000)
                if answer:
                    yield send("assistant_final", text=answer)
                yield send("done")
            except Exception as error:
                logger.warning("voice turn failed: %s", type(error).__name__)
                message = str(error)
                if message.startswith(("Gemini rejected the request", "Gemini request failed", "LLM request failed", "Gnani")):
                    safe_message = message
                else:
                    safe_message = "The voice request failed. Check provider configuration and try again."
                yield send("error", message=safe_message)
                try:
                    pending_tts = application.state.speech.synthesize("Sorry, something went wrong. Please try again.", "en")
                    async for chunk in pending_tts:
                        if cancellation.cancelled:
                            break
                        yield send("audio", pcm_base64=base64.b64encode(chunk).decode("ascii"), sample_rate=24000)
                except Exception as fallback_error:
                    logger.warning("voice turn fallback speech failed: %s", type(fallback_error).__name__)
            finally:
                cancellation.cancel()
                for gen in (guarded, sentence_stream, generated, pending_tts):
                    if gen is not None:
                        try:
                            await gen.aclose()
                        except Exception:
                            pass

        return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @application.post("/agent/command")
    async def agent_command(payload: dict = Body(...)):
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            return JSONResponse(status_code=400, content={"error": "Invalid command text."})
        command = route(text)
        if command.kind == "stop":
            return {"intent": "stop", "result": {"ok": True, "report": "Stopped."}}
        if command.kind in {"conversation", "task"} or not command.tool:
            return {"intent": command.kind, "result": {"ok": True,
                    "report": "Conversation handled by the voice pipeline."}}
        task = await application.state.agent_executor.run_command(
            command, provenance="text", confirmed=bool(payload.get("confirmed")))
        return {"intent": "tool", "tool": command.tool, "taskId": task.task_id,
                "status": task.status, "report": task.report,
                "needs_confirmation": task.needs_confirmation,
                "steps": [{"tool": s.tool, "ok": s.ok, "detail": s.detail} for s in task.steps]}

    return application


settings = Settings.from_environment()
configure_logging(settings.data_dir / "logs")
app = create_app(settings)
