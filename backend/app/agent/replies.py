"""Short spoken confirmations for app commands in each supported language.

Phrased as in-progress ("opening"), because launch is not yet verified by a window check.
The non-English phrasings are drafts: please have a native speaker confirm them.
"""
from __future__ import annotations

OPENING = {
    "en": "Opening {app}.", "hi": "{app} खोला जा रहा है।", "ml": "{app} തുറക്കുന്നു.",
    "kn": "{app} ತೆರೆಯಲಾಗುತ್ತಿದೆ.", "ta": "{app} திறக்கப்படுகிறது.", "te": "{app} తెరుస్తున్నాను.",
    "bn": "{app} খোলা হচ্ছে।", "mr": "{app} उघडत आहे.", "gu": "{app} ખોલી રહ્યું છે.",
    "pa": "{app} ਖੋਲ੍ਹਿਆ ਜਾ ਰਿਹਾ ਹੈ।",
}
CLOSING = {
    "en": "Closing {app}.", "hi": "{app} बंद किया जा रहा है।", "ml": "{app} അടയ്ക്കുന്നു.",
    "kn": "{app} ಮುಚ್ಚಲಾಗುತ್ತಿದೆ.", "ta": "{app} மூடப்படுகிறது.", "te": "{app} మూసివేస్తున్నాను.",
    "bn": "{app} বন্ধ করা হচ্ছে।", "mr": "{app} बंद करत आहे.", "gu": "{app} બંધ કરી રહ્યું છે.",
    "pa": "{app} ਬੰਦ ਕੀਤਾ ਜਾ ਰਿਹਾ ਹੈ।",
}


def spoken_report(command, task, language: str) -> tuple[str, str]:
    """Return (text, language_to_speak_it_in). Anything not localized is spoken in English."""
    if task.status == "completed":
        table = OPENING if command.tool == "apps.open" else CLOSING if command.tool == "apps.close" else None
        if table:
            app = str(command.args.get("name", "")).title()
            lang = language if language in table else "en"
            return table[lang].format(app=app), lang
    return task.report, "en"
