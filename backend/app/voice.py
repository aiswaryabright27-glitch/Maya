"""Phase 2 speech contracts, routing, and bounded provider calls."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator

import httpx

log = logging.getLogger("maya.voice")
LANGUAGES = {"en": "en-IN", "hi": "hi-IN", "ml": "ml-IN", "kn": "kn-IN", "ta": "ta-IN", "te": "te-IN", "bn": "bn-IN", "mr": "mr-IN", "gu": "gu-IN", "pa": "pa-IN"}
VOICES_V25 = {"en": "Kaveri", "hi": "Nalini", "ml": "Reshma", "kn": "Saanvi", "ta": "Asmita", "te": "Suhana", "bn": "Kirra", "mr": "Zahira", "gu": "Falak", "pa": "Mehuli"}
VOICES_V3 = ("Avinash", "Shivani", "Lakshmi", "Kalpana", "Chetana", "Vasudha", "Riyaa", "Tarika", "Shubham", "Prakash", "Devansh", "Yashraj", "Harshad")
SCRIPT_RANGES = {"hi": (0x0900, 0x097F), "bn": (0x0980, 0x09FF), "pa": (0x0A00, 0x0A7F), "gu": (0x0A80, 0x0AFF), "or": (0x0B00, 0x0B7F), "ta": (0x0B80, 0x0BFF), "te": (0x0C00, 0x0C7F), "kn": (0x0C80, 0x0CFF), "ml": (0x0D00, 0x0D7F)}
ROMAN_HINTS = {"hi": {"hai", "hain", "kya", "nahi", "kaise", "mera", "mujhe", "aap", "accha", "karna"}, "ml": {"ente", "sugham", "alla", "njan", "ningal", "cheyyu", "undu", "aanu", "ivide", "entha"}}
LANGUAGE_NAMES = {"english": "en", "hindi": "hi", "malayalam": "ml", "kannada": "kn", "tamil": "ta", "telugu": "te", "bengali": "bn", "marathi": "mr", "gujarati": "gu", "punjabi": "pa", "spanish": "es", "french": "fr", "arabic": "ar"}


@dataclass(frozen=True)
class ProviderCapabilities:
    name: str
    languages: tuple[str, ...]
    streaming: bool
    audio_formats: tuple[str, ...]
    voices: tuple[str, ...] = ()


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str
    latency_ms: float


class SpeechProvider(ABC):
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities: ...

    @abstractmethod
    async def transcribe(self, audio: bytes, language: str, audio_format: str = "wav") -> Transcript: ...

    @abstractmethod
    async def synthesize(self, text: str, language: str, voice: str | None = None) -> AsyncIterator[bytes]: ...


def clean_text_for_speech(text: str) -> str:
    """Strip markdown, URLs, emojis, and unpronounceable formatting for natural TTS."""
    if not text:
        return ""
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", text)
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"https?://\S+|www\.\S+", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("—", ", ").replace("–", ", ").replace("…", "... ")
    text = re.sub(r"[\U00010000-\U0010ffff]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class CircuitBreaker:
    def __init__(self, threshold: int = 6, cooldown: float = 12):
        self.threshold, self.cooldown, self.failures, self.opened_at = threshold, cooldown, 0, 0.0

    def allowed(self) -> bool:
        if self.failures < self.threshold:
            return True
        if time.monotonic() - self.opened_at >= self.cooldown:
            self.failures = 0
            return True
        return False

    def success(self) -> None:
        self.failures, self.opened_at = 0, 0.0

    def failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = time.monotonic()


class GnaniProvider(SpeechProvider):
    BASE = "https://api.vachana.ai"

    def __init__(self, api_key: str, model: str = "prisma-v3.0", tts_model: str = "timbre-v3.0", timeout: float = 30):
        if not api_key:
            raise ValueError("GNANI_API_KEY is required")
        if model not in {"prisma-v2.5", "prisma-v3.0"} or tts_model not in {"timbre-v2.5", "timbre-v3.0"}:
            raise ValueError("Unsupported documented Gnani model")
        self._key, self.model, self.tts_model, self.timeout = api_key, model, tts_model, timeout
        self.breaker = CircuitBreaker()

    def capabilities(self) -> ProviderCapabilities:
        voices = VOICES_V3 if self.tts_model == "timbre-v3.0" else tuple(VOICES_V25.values())
        return ProviderCapabilities("Gnani", tuple(LANGUAGES), True, ("wav", "mp3", "ogg", "flac", "aac", "m4a"), voices)

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        if not self.breaker.allowed():
            raise RuntimeError("Gnani circuit breaker is open")
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(method, url, headers={"X-API-Key-ID": self._key, **kwargs.pop("headers", {})}, **kwargs)
                if response.status_code == 429 or response.status_code >= 500:
                    raise httpx.HTTPStatusError("provider unavailable", request=response.request, response=response)
                response.raise_for_status()
                self.breaker.success()
                return response
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError):
                if attempt == 2:
                    self.breaker.failure()
                    raise RuntimeError("Gnani request failed; check service status and account limits") from None
                await asyncio.sleep(0.15 * (2 ** attempt))
        raise RuntimeError("Gnani request failed")

    async def transcribe(self, audio: bytes, language: str, audio_format: str = "wav") -> Transcript:
        if audio_format.lower() not in {"wav", "mp3", "ogg", "flac", "aac", "m4a"}:
            raise ValueError("Unsupported documented STT audio format")
        locale = "indic-auto" if language == "auto" else LANGUAGES.get(language, language)
        start = time.perf_counter()
        response = await self._request("POST", f"{self.BASE}/stt/v3", data={"model": self.model, "language_code": locale}, files={"audio_file": (f"audio.{audio_format}", audio, f"audio/{audio_format}")})
        payload = response.json()
        text = payload.get("transcript") if "transcript" in payload else payload.get("text")
        if not isinstance(text, str):
            raise RuntimeError("Gnani returned no transcript")
        detected = payload.get("detected_language_code", locale)
        log.info("speech stt completed latency_ms=%.1f", (time.perf_counter() - start) * 1000)
        return Transcript(text, detected, (time.perf_counter() - start) * 1000)

    async def synthesize(self, text: str, language: str, voice: str | None = None) -> AsyncIterator[bytes]:
        cleaned = clean_text_for_speech(text)
        if not cleaned:
            return
        locale = LANGUAGES.get(language, language)
        default_voice = "Shivani" if self.tts_model == "timbre-v3.0" else VOICES_V25.get(language, "Kaveri")
        payload = {"text": cleaned, "voice": voice or default_voice, "model": self.tts_model, "language": locale, "audio_config": {"sample_rate": 24000, "sample_width": 2, "encoding": "linear_pcm", "container": "raw"}}
        start = time.perf_counter()
        if not self.breaker.allowed():
            raise RuntimeError("Gnani circuit breaker is open")
        emitted = False
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    async with client.stream("POST", f"{self.BASE}/api/v1/tts/sse", json=payload, headers={"X-API-Key-ID": self._key, "Accept": "text/event-stream"}) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            raw = line[5:].strip()
                            if not raw:
                                continue
                            event = json.loads(raw)
                            if event.get("type") == "error":
                                raise RuntimeError(f"Gnani TTS error: {event.get('message') or 'unknown'}")
                            encoded = event.get("audio")
                            if encoded:
                                chunk = base64.b64decode(encoded, validate=True)
                                if not emitted:
                                    log.info("speech tts first_audio_ms=%.1f", (time.perf_counter() - start) * 1000)
                                    emitted = True
                                yield chunk
                            if event.get("is_final") is True or str(event.get("is_final")).lower() == "true" or event.get("type") == "complete" or event.get("status") in {"completed", "done"}:
                                break
                self.breaker.success()
                return
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError, ValueError, json.JSONDecodeError):
                if emitted or attempt == 2:
                    self.breaker.failure()
                    raise RuntimeError("Gnani TTS stream failed; check service status and account limits") from None
                await asyncio.sleep(0.15 * (2 ** attempt))


class MockSpeechProvider(SpeechProvider):
    """Clearly labeled deterministic test/demo provider; it does not recognize speech."""
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities("MOCK (no speech recognition)", (), False, ("wav",))

    async def transcribe(self, audio: bytes, language: str, audio_format: str = "wav") -> Transcript:
        del audio, audio_format
        return Transcript("Mock mode does not recognize audio.", language, 0.0)

    async def synthesize(self, text: str, language: str, voice: str | None = None) -> AsyncIterator[bytes]:
        del text, language, voice
        if False:
            yield b""


def detect_language(text: str, preferred: str = "en") -> tuple[str, bool]:
    counts: dict[str, int] = {}
    for char in text:
        cp = ord(char)
        for lang, (low, high) in SCRIPT_RANGES.items():
            if low <= cp <= high:
                counts[lang] = counts.get(lang, 0) + 1
                break
    if counts:
        language = max(counts, key=counts.get)
        # Bengali-script hint is shared by Assamese, which Maya does not support.
        return language, language not in LANGUAGES
    words = set(re.findall(r"[a-z]+", text.lower()))
    scores = {lang: len(words & hints) for lang, hints in ROMAN_HINTS.items()}
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    if ranked[0][1] >= 2 and (len(ranked) == 1 or ranked[0][1] > ranked[1][1]):
        return ranked[0][0], False
    return (preferred if preferred in LANGUAGES else "en"), False


def route_language(text: str, mode: str = "auto", preferred: str = "en", supported: tuple[str, ...] = tuple(LANGUAGES)) -> tuple[str | None, str | None]:
    if mode == "fixed":
        detected = preferred
    else:
        detected, _ = detect_language(text, preferred)
    if detected not in supported:
        return None, f"Speech in {detected} is not available with the configured provider. Choose a supported language or configure another provider."
    return detected, None


def requested_language(text: str) -> str | None:
    match = re.search(r"\b(?:answer|reply|respond|speak)\s+(?:to\s+me\s+)?in\s+(english|hindi|malayalam|kannada|tamil|telugu|bengali|marathi|gujarati|punjabi|spanish|french|arabic)\b", text, re.I)
    return LANGUAGE_NAMES[match.group(1).lower()] if match else None


def is_stop_phrase(text: str) -> bool:
    return re.fullmatch(r"\s*(?:stop|stop maya|cancel|cancel that)[.!?\s]*", text, re.I) is not None
