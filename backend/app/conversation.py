"""Conversation contracts and cancellable mock stream, ready for a configured LLM adapter."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import AsyncIterator, Protocol

import httpx

log = logging.getLogger("maya.conversation")


@dataclass(frozen=True)
class PersonalityProfile:
    name: str = "Maya"
    instructions: str = "Be concise, warm, and clear. Never claim to have taken an action that was not performed."


class LLMProvider(Protocol):
    def capabilities(self) -> dict: ...
    def stream(self, messages: list[dict[str, str]], profile: PersonalityProfile) -> AsyncIterator[str]: ...


class OpenAIResponsesProvider:
    """OpenAI Responses SSE adapter; the key remains in the backend process."""
    URL = "https://api.openai.com/v1/responses"

    def __init__(self, api_key: str, model: str = "gpt-4.1-mini", timeout: float = 45):
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required")
        self._api_key, self.model, self.timeout = api_key, model, timeout

    def capabilities(self) -> dict:
        return {"name": "OpenAI Responses", "model": self.model, "streaming": True}

    async def stream(self, messages: list[dict[str, str]], profile: PersonalityProfile) -> AsyncIterator[str]:
        user_input = next((message.get("content", "") for message in reversed(messages) if message.get("role") == "user"), "")
        instructions = f"You are {profile.name}. {profile.instructions}"
        started = time.perf_counter()
        first = True
        payload = {"model": self.model, "instructions": instructions, "input": user_input, "stream": True, "store": False}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout, read=None)) as client:
                async with client.stream("POST", self.URL, headers={"Authorization": f"Bearer {self._api_key}"}, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data:") or line[5:].strip() == "[DONE]":
                            continue
                        event = json.loads(line[5:].strip())
                        if event.get("type") == "response.output_text.delta" and isinstance(event.get("delta"), str):
                            if first:
                                log.info("llm first_token_ms=%.1f", (time.perf_counter() - started) * 1000)
                                first = False
                            yield event["delta"]
                        elif event.get("type") == "error":
                            raise RuntimeError("OpenAI returned a streaming error")
        except asyncio.CancelledError:
            raise
        except (httpx.HTTPError, json.JSONDecodeError, RuntimeError):
            raise RuntimeError("LLM request failed; check OPENAI_API_KEY, model access, and network") from None


class GeminiProvider:
    """Google Gemini streaming GenerateContent adapter; credentials stay backend-only."""
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse"

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash", timeout: float = 45):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required")
        self._api_key, self.model, self.timeout = api_key, model, timeout

    def capabilities(self) -> dict:
        return {"name": "Google Gemini", "model": self.model, "streaming": True}

    async def stream(self, messages: list[dict[str, str]], profile: PersonalityProfile) -> AsyncIterator[str]:
        user_input = next((message.get("content", "") for message in reversed(messages) if message.get("role") == "user"), "")
        payload = {
            "systemInstruction": {"parts": [{"text": f"You are {profile.name}. {profile.instructions}"}]},
            "contents": [{"role": "user", "parts": [{"text": user_input}]}],
            "generationConfig": {"responseMimeType": "text/plain"},
        }
        started = time.perf_counter()
        first = True
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout, read=None)) as client:
                async with client.stream("POST", self.URL.format(model=self.model), headers={"x-goog-api-key": self._api_key}, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data:") or line[5:].strip() == "[DONE]":
                            continue
                        event = json.loads(line[5:].strip())
                        for candidate in event.get("candidates", []):
                            for part in candidate.get("content", {}).get("parts", []):
                                text = part.get("text")
                                if isinstance(text, str) and text:
                                    if first:
                                        log.info("llm first_token_ms=%.1f", (time.perf_counter() - started) * 1000)
                                        first = False
                                    yield text
        except asyncio.CancelledError:
            raise
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            if status in (400, 401, 403, 404):
                raise RuntimeError(f"Gemini rejected the request (HTTP {status}). Check GEMINI_API_KEY, model name, and API access.") from None
            raise RuntimeError(f"Gemini request failed (HTTP {status}). Check network and quota.") from None
        except (httpx.HTTPError, json.JSONDecodeError):
            raise RuntimeError("Gemini request failed. Check network and provider configuration.") from None


class MockLLMProvider:
    """Clearly labeled mock; returns a fixed explanation and performs no inference."""
    def capabilities(self) -> dict:
        return {"name": "MOCK (no language model)", "streaming": True}

    async def stream(self, messages: list[dict[str, str]], profile: PersonalityProfile) -> AsyncIterator[str]:
        del profile
        prompt = messages[-1].get("content", "") if messages else ""
        for word in f"Mock mode received: {prompt}".split(" "):
            yield word + " "
            await asyncio.sleep(0)


def sentence_chunks(stream: AsyncIterator[str]) -> AsyncIterator[str]:
    async def chunks() -> AsyncIterator[str]:
        buffer = ""
        async for token in stream:
            buffer += token
            while match := re.search(r"[.!?](?:[\"'’)]*)\s+", buffer):
                yield buffer[:match.end()].strip()
                buffer = buffer[match.end():]
        if buffer.strip():
            yield buffer.strip()
    return chunks()


async def stream_sentences(stream: AsyncIterator[str]) -> AsyncIterator[tuple[str, str]]:
    """Yield ('delta', token) immediately and ('sentence', text) at punctuation boundaries."""
    buffer = ""
    async for token in stream:
        yield "delta", token
        buffer += token
        while match := re.search(r"[.!?](?:[\"'’)]*)\s+", buffer):
            sentence = buffer[:match.end()].strip()
            buffer = buffer[match.end():]
            if sentence:
                yield "sentence", sentence
    if buffer.strip():
        yield "sentence", buffer.strip()


class Cancellation:
    def __init__(self) -> None:
        self._event = asyncio.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    async def guard(self, stream: AsyncIterator[str]) -> AsyncIterator[str]:
        iterator = aiter(stream)
        while not self.cancelled:
            next_item = asyncio.create_task(anext(iterator))
            cancelled = asyncio.create_task(self._event.wait())
            try:
                done, pending = await asyncio.wait({next_item, cancelled}, return_when=asyncio.FIRST_COMPLETED)
            except BaseException:
                next_item.cancel(); cancelled.cancel()
                await asyncio.gather(next_item, cancelled, return_exceptions=True)
                raise
            for task in pending:
                task.cancel()
            if cancelled in done:
                next_item.cancel()
                await asyncio.gather(next_item, return_exceptions=True)
                break
            cancelled.cancel()
            await asyncio.gather(cancelled, return_exceptions=True)
            try:
                yield next_item.result()
            except StopAsyncIteration:
                break


class VoiceActivityDetector:
    """RMS threshold VAD with adjustable sensitivity and silence hangover."""
    def __init__(self, threshold: float = 0.035, silence_ms: int = 750):
        if not 0 < threshold < 1 or silence_ms < 100:
            raise ValueError("Invalid VAD settings")
        self.threshold, self.silence_ms = threshold, silence_ms
        self.speaking = False
        self._quiet_ms = 0

    def process(self, rms: float, frame_ms: int) -> str:
        if rms >= self.threshold:
            self.speaking, self._quiet_ms = True, 0
            return "speech"
        if not self.speaking:
            return "silence"
        self._quiet_ms += frame_ms
        if self._quiet_ms >= self.silence_ms:
            self.speaking, self._quiet_ms = False, 0
            return "end"
        return "silence"
