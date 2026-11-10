"""Command router: deterministic fast path for simple commands, LLM for the rest.

Handles stop/undo, open/close app, open URL/site, web search and time, in English,
romanized Hinglish/Manglish and the native scripts of the 10 supported languages.
Unknown phrases fall through to conversation (the LLM).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

STOP_RE = re.compile(r"^\s*(?:stop|stop maya|cancel|cancel that|nevermind|never mind|undo that|undo)\b[.!?\s]*$", re.I)
OPEN_URL_RE = re.compile(r"^\s*(?:open|go to|visit)\s+(https?://\S+|www\.\S+)\s*$", re.I)
OPEN_SITE_RE = re.compile(r"^\s*(?:open|go to)\s+(?:the\s+)?(?:website|site)\s+(?:of\s+)?([\w.-]+\.[a-z]{2,})\s*$", re.I)
SEARCH_RE = re.compile(r"^\s*(?:search(?:\s+(?:the\s+)?web)?|google|look up|find online)\s+(?:for\s+)?(.+)$", re.I)
TIME_RE = re.compile(r"^\s*(?:what(?:'s| is)\s+the\s+)?(?:time|date|day)\b", re.I)
TASK_HINT_RE = re.compile(r"\b(?:then|after that|and also|and then|first .+ then|step \d)\b", re.I)

# ---- polite filler words that should never block a command --------------------------
FILLER_PREFIX = re.compile(
    r"^(?:(?:hey|hi|ok|okay)\s+)?maya[,!\s]*|^(?:please|kindly|can you|could you|would you|will you|"
    r"i want you to|i need you to|i want to|i would like to|go ahead and|just)\s+", re.I)
FILLER_SUFFIX = re.compile(r"\s+(?:for me|please|now|right now|na|once|for a moment)$", re.I)

# ---- verbs (any position in the sentence) -------------------------------------------
# English verbs, including English words that the speech engine wrote in an Indic script
# (people speaking English with an Indian accent often get "ओपन कैलकुलेटर" back from STT).
OPEN_VERBS_EN = [
    "open", "opne", "launch", "start", "run", "show me", "bring up",
    "ओपन", "लॉन्च", "लांच", "स्टार्ट", "रन", "ഓപ്പൺ", "ലോഞ്ച്", "സ്റ്റാർട്ട്", "ஓபன்", "ஸ்டார்ட்", "ఓపెన్",
    "ಓಪನ್", "ওপেন", "ઓપન", "ਓਪਨ",
]
CLOSE_VERBS_EN = [
    "close", "quit", "exit", "shut", "kill",
    "क्लोज", "क्लोज़", "क्विट", "ക്ലോസ്", "ക്വിറ്റ്", "க்ளோஸ்", "క్లోజ్", "ಕ್ಲೋಸ್", "ক্লোজ",
]
# Genuinely native verbs (also romanized Hinglish/Manglish): the user is speaking that language.
OPEN_VERBS_NATIVE = [
    "kholo", "kholiye", "kholna", "khol do", "khol de", "chalu karo", "shuru karo", "open karo", "start karo",
    "thurakku", "thurakkoo", "thurakk", "open cheyyu", "open cheyy", "open chey", "open maadi", "open madi",
    "open seyyu", "open cheyyi", "open koro", "open kara",
    "खोलो", "खोलिए", "खोलें", "खोल दो", "खोल दे", "चालू करो", "शुरू करो", "ओपन करो",
    "उघडा", "सुरू करा", "ખોલો", "શરૂ કરો", "ਖੋਲ੍ਹੋ", "ਖੋਲ੍ਹ", "খোলো", "খুলুন", "চালু করো",
    "തുറക്കൂ", "തുറക്ക്", "തുറക്കുക", "ഓപ്പൺ ചെയ്യൂ", "തുറക്കണം",
    "திற", "திறக்கவும்", "திறங்கள்", "ஓபன் செய்",
    "తెరవండి", "తెరువు", "తెరవు", "ఓపెన్ చేయి",
    "ತೆರೆಯಿರಿ", "ತೆರೆ", "ಓಪನ್ ಮಾಡಿ",
]
CLOSE_VERBS_NATIVE = [
    "band karo", "band kar do", "band kijiye", "band kar", "adakku", "adakkoo", "close cheyyu",
    "बंद करो", "बंद कर दो", "बंद करें", "बंद", "അടയ്ക്കൂ", "അടയ്ക്കുക", "അടക്കൂ",
    "மூடு", "மூடவும்", "మూసివేయి", "మూసివేయండి", "ಮುಚ್ಚಿ", "বন্ধ করো", "બંધ કરો", "ਬੰਦ ਕਰੋ", "बंद करा",
]
OPEN_VERBS = OPEN_VERBS_EN + OPEN_VERBS_NATIVE
CLOSE_VERBS = CLOSE_VERBS_EN + CLOSE_VERBS_NATIVE
# Verb skeletons for transliterated English verbs the lists above did not anticipate.
_VERB_SKELETONS = {"open": "pn", "launch": "lnc", "start": "strt", "run": "rn"}

# ---- apps: canonical target + spoken names (Latin and native scripts) ---------------
APPS: dict[str, tuple[str, list[str]]] = {
    "notepad": ("notepad", ["notepad", "note pad", "notepad plus plus", "नोटपैड", "नोटपॅड", "നോട്ട്പാഡ്", "நோட்பேட்",
                            "నోట్‌ప్యాడ్", "నోట్ ప్యాడ్", "ನೋಟ್‌ಪ್ಯಾಡ್", "ನೋಟ್ ಪ್ಯಾಡ್", "নোটপ্যাড", "નોટપેડ", "ਨੋਟਪੈਡ"]),
    "calculator": ("calc", ["calculator", "calc", "कैलकुलेटर", "कैल्कुलेटर", "കാൽക്കുലേറ്റർ", "കാൽകുലേറ്റർ", "கால்குலேட்டர்",
                            "కాలిక్యులేటర్", "ಕ್ಯಾಲ್ಕುಲೇಟರ್", "ক্যালকুলেটর", "કેલ્ક્યુલેટર", "ਕੈਲਕੁਲੇਟਰ"]),
    "vs code": ("code", ["vs code", "vscode", "visual studio code", "वीएस कोड", "വിഎസ് കോഡ്", "விஎஸ் கோட்"]),
    "chrome": ("chrome", ["chrome", "google chrome", "क्रोम", "ക്രോം", "குரோம்", "క్రోమ్", "ಕ್ರೋಮ್", "ক্রোম"]),
    "edge": ("msedge", ["edge", "microsoft edge", "एज"]),
    "firefox": ("firefox", ["firefox", "फायरफॉक्स"]),
    "spotify": ("spotify", ["spotify", "स्पॉटिफाई"]),
    "word": ("winword", ["word", "ms word", "microsoft word", "वर्ड"]),
    "excel": ("excel", ["excel", "ms excel", "microsoft excel", "एक्सेल"]),
    "powerpoint": ("powerpnt", ["powerpoint", "power point", "ppt", "पावरपॉइंट"]),
    "paint": ("mspaint", ["paint", "ms paint", "पेंट"]),
    "terminal": ("wt", ["terminal", "windows terminal", "टर्मिनल"]),
    "command prompt": ("cmd", ["cmd", "command prompt", "कमांड प्रॉम्प्ट"]),
    "powershell": ("powershell", ["powershell", "power shell"]),
    "settings": ("ms-settings:", ["settings", "सेटिंग्स", "സെറ്റിങ്സ്", "அமைப்புகள்"]),
    "file explorer": ("explorer", ["file explorer", "explorer", "files", "फाइल एक्सप्लोरर"]),
    "snipping tool": ("snippingtool", ["snipping tool", "snip"]),
    "camera": ("microsoft.windows.camera:", ["camera", "कैमरा", "ക്യാമറ"]),
    "clock": ("ms-clock:", ["clock", "alarms", "घड़ी"]),
}
# also kept for backward compatibility with older callers
APP_ALIASES = {alias: target for _name, (target, aliases) in APPS.items() for alias in aliases}


@dataclass(frozen=True)
class RoutedCommand:
    kind: str                      # stop | tool | conversation | task
    tool: str | None = None
    args: dict = field(default_factory=dict)
    summary: str = ""
    confidence: float = 1.0
    reply_language: str | None = None   # set when the words were English even if the STT wrote them in an Indic script


# ---- sound-alike matching across scripts -----------------------------------------------
# Speech engines write English app names in many spellings in Indic scripts
# (कैलकुलेटर / कैलक्युलेटर / केलकुलेटर ...). We reduce any word to a rough consonant
# "skeleton" so these all compare equal to the Latin name. Works for every Indic script
# because Unicode character names are like "DEVANAGARI LETTER KA" / "MALAYALAM LETTER KA".
_VOWEL_NAMES = {"A", "AA", "I", "II", "U", "UU", "E", "EE", "AI", "O", "OO", "AU", "AW", "OE", "UE"}
_LATIN_TOKEN = re.compile(r"ch|sh|th|kh|gh|dh|bh|ph|ck|ng|(.)\1|.")
_LATIN_MAP = {"b": "p", "d": "t", "f": "p", "g": "k", "j": "c", "q": "k", "z": "s", "x": "ks",
              "k": "k", "l": "l", "m": "m", "n": "n", "p": "p", "r": "r", "s": "s", "t": "t"}
_DIGRAPH = {"ch": "c", "sh": "s", "th": "t", "kh": "k", "gh": "k", "dh": "t", "bh": "p", "ph": "p", "ck": "k", "ng": "n"}


def _latin_skeleton(word: str) -> str:
    w = re.sub(r"[^a-z]", "", word.lower())
    out: list[str] = []
    for m in _LATIN_TOKEN.finditer(w):
        tok = m.group(0)
        if tok in _DIGRAPH:
            out.append(_DIGRAPH[tok])
        elif len(tok) == 2 and tok[0] == tok[1]:
            out.append(_LATIN_MAP.get(tok[0], ""))
        elif tok == "c":
            nxt = w[m.end():m.end() + 1]
            out.append("s" if nxt in ("e", "i", "y") else "k")
        else:
            out.append(_LATIN_MAP.get(tok, ""))
    return "".join(out)


def skeleton(text: str) -> str:
    out: list[str] = []
    latin_run: list[str] = []

    def flush() -> None:
        if latin_run:
            out.append(_latin_skeleton("".join(latin_run)))
            latin_run.clear()

    for ch in unicodedata.normalize("NFC", text):
        if "a" <= ch.lower() <= "z" and ch.isascii():
            latin_run.append(ch)
            continue
        flush()
        if ord(ch) < 0x0900:
            continue
        try:
            name = unicodedata.name(ch)
        except ValueError:
            continue
        if "CHILLU " in name:
            out.append(_latin_skeleton(name.split("CHILLU ")[1].lower()))
        elif " LETTER " in name:
            base = name.split(" LETTER ")[1]
            if base in _VOWEL_NAMES or base.startswith(("VOCALIC", "CANDRA", "SHORT", "LONG")):
                continue
            base = base.lower()
            base = base[:-1] if len(base) > 1 and base.endswith("a") else base
            out.append("c" if base == "c" else _latin_skeleton(base))
    flush()
    joined = "".join(out)
    return re.sub(r"(.)\1+", r"\1", joined)


_APP_SKELETONS: list[tuple[str, str, str]] = []  # (skeleton, canonical, target)
for _canonical, (_target, _aliases) in APPS.items():
    for _alias in _aliases:
        if _alias.isascii():
            _sk = skeleton(_alias)
            if len(_sk) >= 3:
                _APP_SKELETONS.append((_sk, _canonical, _target))


def _match_skeleton(word_sk: str) -> tuple[str, str] | None:
    if len(word_sk) < 3:
        return None
    best: tuple[float, str, str] | None = None
    for sk, canonical, target in _APP_SKELETONS:
        ratio = 1.0 if sk == word_sk else SequenceMatcher(None, sk, word_sk).ratio()
        if ratio >= 0.86 and (best is None or ratio > best[0]):
            best = (ratio, canonical, target)
    return (best[1], best[2]) if best else None


def _find_app_by_sound(text: str) -> tuple[str, str] | None:
    """Sound-alike app lookup for words written in Indic scripts (single words and word pairs)."""
    words = [w for w in re.split(r"\s+", text) if w and not w.isascii()]
    candidates = words + [a + b for a, b in zip(words, words[1:])]
    for cand in candidates:
        hit = _match_skeleton(skeleton(cand))
        if hit:
            return hit
    return None


def _skeleton_has_verb(text: str, verb_skeletons: dict[str, str]) -> bool:
    for w in re.split(r"\s+", text):
        if w and not w.isascii() and skeleton(w) in verb_skeletons.values():
            return True
    return False


def _normalize(text: str) -> str:
    t = unicodedata.normalize("NFC", text).strip()
    t = t.rstrip(".!?।॥,؟ ")
    for _ in range(3):  # strip stacked fillers: "maya, can you please open ..."
        new = FILLER_PREFIX.sub("", t).strip(" ,")
        new = FILLER_SUFFIX.sub("", new).strip()
        if new == t:
            break
        t = new
    return t


def _find_app(low: str) -> tuple[str, str] | None:
    """Longest spoken alias contained in the text (whole-word for Latin names)."""
    best: tuple[int, str, str] | None = None
    for canonical, (target, aliases) in APPS.items():
        for alias in aliases:
            a = alias.lower()
            if a.isascii():
                hit = re.search(rf"(?<![a-z0-9]){re.escape(a)}(?![a-z0-9])", low)
            else:
                hit = a in low
            if hit and (best is None or len(a) > best[0]):
                best = (len(a), canonical, target)
    return (best[1], best[2]) if best else None


def _count_apps(low: str) -> int:
    found = set()
    for canonical, (_t, aliases) in APPS.items():
        for alias in aliases:
            a = alias.lower()
            hit = re.search(rf"(?<![a-z0-9]){re.escape(a)}(?![a-z0-9])", low) if a.isascii() else a in low
            if hit:
                found.add(canonical)
                break
    return len(found)


def _has_verb(low: str, verbs: list[str]) -> bool:
    for v in verbs:
        v = v.lower()
        if v.isascii():
            if re.search(rf"(?<![a-z0-9]){re.escape(v)}(?![a-z0-9])", low):
                return True
        elif v in low:
            return True
    return False


def route(text: str) -> RoutedCommand:
    t = _normalize(text)
    low = t.lower()
    if STOP_RE.match(t):
        return RoutedCommand("stop", summary="stop")
    m = OPEN_URL_RE.match(t)
    if m:
        url = m.group(1)
        if not url.lower().startswith("http"):
            url = "https://" + url
        return RoutedCommand("tool", "web.open_url", {"url": url}, f"Open {url}")
    site = OPEN_SITE_RE.match(t)
    if site:
        url = "https://" + site.group(1)
        return RoutedCommand("tool", "web.open_url", {"url": url}, f"Open {url}")
    search = SEARCH_RE.match(t)
    if search and search.group(1).strip():
        q = search.group(1).strip()
        return RoutedCommand("tool", "web.search", {"query": q}, f"Search the web for {q}")
    if TIME_RE.match(t):
        return RoutedCommand("tool", "system.time", {}, "Tell the time/date")

    if TASK_HINT_RE.search(t) and len(t.split()) >= 4:
        return RoutedCommand("task", summary=t[:120], confidence=0.6)
    app = _find_app(low) or _find_app_by_sound(t)
    if app:
        name, target = app
        if _count_apps(low) > 1:  # several apps in one sentence: needs the planner
            return RoutedCommand("task", summary=t[:120], confidence=0.6)
        native_close = _has_verb(low, CLOSE_VERBS_NATIVE)
        native_open = _has_verb(low, OPEN_VERBS_NATIVE)
        en_close = _has_verb(low, CLOSE_VERBS_EN)
        en_open = _has_verb(low, OPEN_VERBS_EN) or _skeleton_has_verb(t, {"open": "pn", "launch": "lnc", "start": "strt"})
        # Native verb -> speaker is using that language (reply in it). English verb only -> the
        # speaker said English, even if the STT wrote it in Devanagari/Malayalam/etc.
        reply_lang = None if (native_close or native_open) else "en"
        if native_close or en_close:
            return RoutedCommand("tool", "apps.close", {"name": name}, f"Close {name}", reply_language=reply_lang)
        if native_open or en_open:
            return RoutedCommand("tool", "apps.open", {"name": name, "target": target}, f"Open {name}",
                                 reply_language=reply_lang)
        if len(t.split()) <= 2:  # a bare app name: "calculator", "नोटपैड"
            return RoutedCommand("tool", "apps.open", {"name": name, "target": target}, f"Open {name}",
                                 confidence=0.8)
    return RoutedCommand("conversation", summary=t[:120], confidence=0.9)
