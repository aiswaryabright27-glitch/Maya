import pytest

from app.agent.router import route

ENGLISH_SPOKEN_BUT_WRITTEN_IN_INDIC = [
    "ओपन कैलकुलेटर", "ओपन कैलक्युलेटर", "ओपन नोटपैड", "ഓപ്പൺ കാൽക്കുലേറ്റർ", "ஓபன் கால்குலேட்டர்",
    "ఓపెన్ కాలిక్యులేటర్", "ಓಪನ್ ಕ್ಯಾಲ್ಕುಲೇಟರ್", "ওপেন ক্যালকুলেটর",
]
NATIVE = ["कैलकुलेटर खोलो", "नोटपैड खोलो", "നോട്ട്പാഡ് തുറക്കൂ", "કેલ્ક્યુલેટર ખોલો", "ਕੈਲਕੁਲੇਟਰ ਖੋਲ੍ਹੋ"]


@pytest.mark.parametrize("text", ["open calculator", "can you please open notepad for me", "launch chrome", "start notepad", "notepad kholo"])
def test_latin_phrases_open_apps(text):
    assert route(text).tool == "apps.open"


@pytest.mark.parametrize("text", ENGLISH_SPOKEN_BUT_WRITTEN_IN_INDIC)
def test_english_command_written_in_indic_script_replies_in_english(text):
    r = route(text)
    assert r.tool == "apps.open" and r.reply_language == "en"


@pytest.mark.parametrize("text", NATIVE)
def test_native_verbs_keep_the_users_language(text):
    r = route(text)
    assert r.tool == "apps.open" and r.reply_language is None


@pytest.mark.parametrize("text", ["close notepad", "क्लोज कैलकुलेटर", "नोटपैड बंद करो"])
def test_close(text):
    assert route(text).tool == "apps.close"


@pytest.mark.parametrize("text", ["tell me a joke", "what is a calculator used for", "कैलकुलेटर क्या होता है", "നിനക്ക് സുഖമാണോ"])
def test_chat_is_not_a_command(text):
    assert route(text).kind == "conversation"
