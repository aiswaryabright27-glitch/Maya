from __future__ import annotations

import asyncio
import os
import pytest
from app.voice import (
    LANGUAGES,
    VOICES_V3,
    VOICES_V25,
    detect_language,
    requested_language,
    route_language,
    GnaniProvider,
    clean_text_for_speech,
)

SAMPLE_PHRASES: dict[str, str] = {
    "en": "Hello Maya, how are you doing today?",
    "hi": "नमस्ते माया, आप कैसी हैं?",
    "ml": "നമസ്കാരം മായ, എങ്ങനെയുണ്ട്?",
    "kn": "ನಮಸ್ಕಾರ ಮಾಯಾ, ಹೇಗಿದ್ದೀರಿ?",
    "ta": "வணக்கம் மாயா, எப்படி இருக்கிறீர்கள்?",
    "te": "నమస్కారం మాయా, ఎలా ఉన్నారు?",
    "bn": "নমস্কার মায়া, আপনি কেমন আছেন?",
    "mr": "नमस्कार माया, तुम्ही कसे आहात?",
    "gu": "નમસ્તે માયા, તમે કેમ છો?",
    "pa": "ਸਤਿ ਸ਼੍ਰੀ ਅਕਾਲ ਮਾਇਆ, ਤੁਸੀਂ ਕਿਵੇਂ ਹੋ?",
}

def test_all_ten_languages_in_matrix() -> None:
    expected = {"en", "hi", "ml", "kn", "ta", "te", "bn", "mr", "gu", "pa"}
    assert set(LANGUAGES.keys()) == expected
    for code, locale in LANGUAGES.items():
        assert locale.endswith("-IN")


def test_script_detection_for_all_ten_languages() -> None:
    for lang_code, phrase in SAMPLE_PHRASES.items():
        detected, unsupported = detect_language(phrase, "en")
        assert not unsupported, f"Language {lang_code} was flagged as unsupported"
        assert detected == lang_code, f"Expected {lang_code}, detected {detected} for '{phrase}'"


def test_explicit_language_requests_for_all_ten_languages() -> None:
    names = {
        "en": "English", "hi": "Hindi", "ml": "Malayalam", "kn": "Kannada",
        "ta": "Tamil", "te": "Telugu", "bn": "Bengali", "mr": "Marathi",
        "gu": "Gujarati", "pa": "Punjabi"
    }
    for code, name in names.items():
        prompt = f"Please respond to me in {name} from now on."
        req = requested_language(prompt)
        assert req == code, f"Failed to extract requested language {name} (expected {code}, got {req})"


def test_code_switching_detection() -> None:
    hinglish = "Haan yaar, main aaj thoda busy hoon"
    assert detect_language(hinglish, "en")[0] == "hi"

    manglish = "Njan ivide undu, ningal entha cheyyunne"
    assert detect_language(manglish, "en")[0] == "ml"


def test_tts_cleaner_preserves_indic_scripts() -> None:
    for code, phrase in SAMPLE_PHRASES.items():
        cleaned = clean_text_for_speech(f"**{phrase}** 😊")
        assert phrase in cleaned, f"Cleaner damaged Indic phrase for {code}"
        assert "😊" not in cleaned


@pytest.mark.live_provider
def test_live_gnani_tts_synthesis_all_languages() -> None:
    key = os.getenv("GNANI_API_KEY")
    if not key:
        pytest.skip("GNANI_API_KEY not configured")

    provider = GnaniProvider(key, tts_model="timbre-v3.0")

    async def run_smoke():
        results = {}
        for code, phrase in SAMPLE_PHRASES.items():
            chunks = []
            try:
                async for chunk in provider.synthesize(phrase, code):
                    chunks.append(chunk)
                    if len(chunks) >= 2:
                        break
                results[code] = "PASS" if len(chunks) > 0 else "FAIL_EMPTY"
            except Exception as e:
                results[code] = f"FAIL_ERROR: {e}"
        return results

    results = asyncio.run(run_smoke())
    for code, status in results.items():
        assert status == "PASS", f"TTS failed for language {code}: {status}"
