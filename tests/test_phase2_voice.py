from __future__ import annotations

import asyncio
import io
import os
import wave
import base64
import json

from app.conversation import Cancellation, GeminiProvider, MockLLMProvider, OpenAIResponsesProvider, PersonalityProfile, VoiceActivityDetector, sentence_chunks, stream_sentences
from app.voice import LANGUAGES, MockSpeechProvider, detect_language, requested_language, is_stop_phrase, route_language
from app.voice import GnaniProvider
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.voice import Transcript


def test_detects_hinglish_and_manglish_romanized_samples() -> None:
    assert detect_language("Yaar, kya karna hai?", "en")[0] == "hi"
    assert detect_language("Njan ivide aanu, sugam alle?", "en")[0] == "ml"


def test_script_detection_and_unsupported_language_are_honest() -> None:
    assert detect_language("नमस्ते दोस्त", "en")[0] == "hi"
    language, message = route_language("ನಮಸ್ಕಾರ", supported=("en", "hi"))
    assert language is None
    assert "not available" in message


def test_language_preferences_and_capability_matrix() -> None:
    assert set(LANGUAGES) == {"en", "hi", "ml", "kn", "ta", "te", "bn", "mr", "gu", "pa"}
    assert route_language("ನಮಸ್ಕಾರ", "fixed", "en")[0] == "en"
    assert MockSpeechProvider().capabilities().name.startswith("MOCK")
    assert requested_language("Please answer in Tamil") == "ta"
    assert requested_language("Now reply in Spanish") == "es"
    assert route_language("", "fixed", requested_language("Now reply in Spanish"))[0] is None
    assert is_stop_phrase("Stop!") and is_stop_phrase("stop maya") and not is_stop_phrase("don't stop")


def test_mock_provider_discloses_it_does_not_recognize_audio() -> None:
    async def run() -> None:
        result = await MockSpeechProvider().transcribe(b"arbitrary bytes", "en")
        assert "does not recognize" in result.text
        assert [chunk async for chunk in MockSpeechProvider().synthesize("hello", "en")] == []
    asyncio.run(run())


def test_gnani_capabilities_and_voice_routing_use_documented_models() -> None:
    v3 = GnaniProvider("unit-test-key", "prisma-v3.0", "timbre-v3.0").capabilities()
    v25 = GnaniProvider("unit-test-key", "prisma-v2.5", "timbre-v2.5").capabilities()
    assert v3.streaming and len(v3.voices) == 13
    assert "Reshma" in v25.voices


def test_vad_threshold_and_silence_hangover() -> None:
    vad = VoiceActivityDetector(threshold=0.04, silence_ms=300)
    assert vad.process(0.01, 100) == "silence"
    assert vad.process(0.06, 100) == "speech"
    assert vad.process(0.01, 100) == "silence"
    assert vad.process(0.01, 100) == "silence"
    assert vad.process(0.01, 100) == "end"


def test_cancellation_and_sentence_chunking() -> None:
    async def scenario() -> None:
        provider = MockLLMProvider()
        stream = provider.stream([{"role": "user", "content": "hello"}], PersonalityProfile())
        cancel = Cancellation()
        emitted = []
        async for token in cancel.guard(stream):
            emitted.append(token)
            cancel.cancel()
        assert len(emitted) == 1

        async def words():
            yield "Hello. Next"
            yield " sentence! Done"

        assert [chunk async for chunk in sentence_chunks(words())] == ["Hello.", "Next sentence!", "Done"]
    asyncio.run(scenario())


def test_cancellation_interrupts_a_delayed_stream_immediately() -> None:
    async def scenario() -> None:
        cancellation = Cancellation()
        emitted: list[str] = []

        async def slow_stream():
            await asyncio.sleep(2)
            yield "late token"

        async def consume():
            async for item in cancellation.guard(slow_stream()):
                emitted.append(item)

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.02)
        cancellation.cancel()
        await asyncio.wait_for(task, timeout=0.2)
        assert emitted == []
    asyncio.run(scenario())


def test_stream_sentence_pipeline_emits_deltas_then_sentences() -> None:
    async def scenario() -> None:
        async def words():
            yield "First. "
            yield "Second"
        assert [item async for item in stream_sentences(words())] == [
            ("delta", "First. "), ("sentence", "First."), ("delta", "Second"), ("sentence", "Second")
        ]
    asyncio.run(scenario())


def test_openai_responses_sse_adapter_streams_and_sends_personality(monkeypatch) -> None:
    from app import conversation
    captured = {}

    class FakeResponse:
        def raise_for_status(self): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *_args): pass
        async def aiter_lines(self):
            yield 'data: {"type":"response.output_text.delta","delta":"Hello"}'
            yield 'data: {"type":"response.completed"}'

    class FakeClient:
        def __init__(self, **_kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *_args): pass
        def stream(self, _method, _url, **kwargs):
            captured.update(kwargs)
            return FakeResponse()

    monkeypatch.setattr(conversation.httpx, "AsyncClient", FakeClient)
    async def scenario():
        provider = OpenAIResponsesProvider("test-api-key")
        profile = PersonalityProfile(instructions="Answer only in Tamil.")
        return [delta async for delta in provider.stream([{"role": "user", "content": "hello"}], profile)]
    assert asyncio.run(scenario()) == ["Hello"]
    assert captured["headers"]["Authorization"] == "Bearer test-api-key"
    assert captured["json"]["instructions"] == "You are Maya. Answer only in Tamil."
    assert captured["json"]["stream"] is True and captured["json"]["store"] is False


def test_gemini_stream_adapter_uses_documented_auth_and_system_instruction(monkeypatch) -> None:
    from app import conversation
    captured = {}

    class FakeResponse:
        def raise_for_status(self): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *_args): pass
        async def aiter_lines(self):
            yield 'data: {"candidates":[{"content":{"parts":[{"text":"Hello from Gemini."}]}}]}'

    class FakeClient:
        def __init__(self, **_kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *_args): pass
        def stream(self, method, url, **kwargs):
            captured.update(method=method, url=url, **kwargs)
            return FakeResponse()

    monkeypatch.setattr(conversation.httpx, "AsyncClient", FakeClient)
    async def scenario():
        provider = GeminiProvider("test-gemini-key")
        profile = PersonalityProfile(instructions="Respond only in Tamil.")
        return [part async for part in provider.stream([{"role": "user", "content": "hello"}], profile)]

    assert asyncio.run(scenario()) == ["Hello from Gemini."]
    assert captured["method"] == "POST"
    assert captured["url"] == GeminiProvider.URL.format(model="gemini-2.5-flash")
    assert captured["headers"] == {"x-goog-api-key": "test-gemini-key"}
    assert captured["json"]["systemInstruction"]["parts"][0]["text"].endswith("Respond only in Tamil.")
    assert captured["json"]["contents"][0]["parts"][0]["text"] == "hello"


def test_conversation_stream_routes_requested_language_and_tts_audio(tmp_path) -> None:
    class FakeSpeech:
        synthesized: list[tuple[str, str]] = []
        async def transcribe(self, audio, language, audio_format="wav"):
            del audio, audio_format
            return Transcript("Please answer in Tamil", "en-IN", 5.0)
        async def synthesize(self, text, language, voice=None):
            del voice
            self.synthesized.append((text, language))
            yield b"\x01\x00\x02\x00"

    class FakeLLM:
        profile = None
        def stream(self, messages, profile):
            self.profile = profile
            async def tokens():
                assert messages[-1]["content"] == "Please answer in Tamil"
                yield "வணக்கம். "
                yield "நன்றி!"
            return tokens()

    settings = Settings(
        host="127.0.0.1", port=9876, backend_token="unit-test-token-value-000000000000000000000000",
        mode="mock", data_dir=tmp_path, gnani_api_key="fake-key", openai_api_key="fake-key",
    )
    application = create_app(settings)
    speech, llm = FakeSpeech(), FakeLLM()
    application.state.speech, application.state.llm = speech, llm
    with TestClient(application) as client:
        response = client.post("/voice/turn", headers={"Authorization": f"Bearer {settings.backend_token.get_secret_value()}"}, json={"audio_base64": base64.b64encode(b"audio").decode(), "language": "en"})
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    assert response.status_code == 200
    assert next(event for event in events if event["type"] == "transcript")["text"] == "Please answer in Tamil"
    assert any(event["type"] == "audio" for event in events)
    assert [language for _text, language in speech.synthesized] == ["ta", "ta"]
    assert "Respond only in ta" in llm.profile.instructions


@pytest.mark.live_provider
@pytest.mark.skipif(not os.getenv("GNANI_API_KEY"), reason="GNANI_API_KEY is not configured")
def test_live_gnani_stt_when_key_is_configured() -> None:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(16000)
        audio.writeframes(b"\0\0" * 1600)

    async def run() -> None:
        provider = GnaniProvider(os.environ["GNANI_API_KEY"])
        result = await asyncio.wait_for(provider.transcribe(buffer.getvalue(), "en", "wav"), timeout=40)
        assert isinstance(result.text, str)
        assert result.language
        assert result.latency_ms >= 0
    asyncio.run(run())


@pytest.mark.live_provider
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY is not configured")
def test_live_openai_responses_stream_when_key_is_configured() -> None:
    async def run() -> None:
        provider = OpenAIResponsesProvider(os.environ["OPENAI_API_KEY"], os.getenv("MAYA_LLM_MODEL", "gpt-4.1-mini"))
        stream = provider.stream([{"role": "user", "content": "Reply with one short greeting."}], PersonalityProfile())
        first_delta = await asyncio.wait_for(anext(stream), timeout=60)
        assert isinstance(first_delta, str) and first_delta
        await stream.aclose()
    asyncio.run(run())
