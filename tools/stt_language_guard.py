"""Language guard for speech-to-text transcripts.

The guard is intentionally script-based and conservative. It does not try to
identify every language; it only detects when a transcript is mostly outside the
user-configured script set so Hermes does not confidently interpret STT
hallucinations as real foreign-language utterances.
"""

from __future__ import annotations

import unicodedata
from typing import Any, Dict, Optional

_LANGUAGE_LABELS = {
    "en": "English",
    "ko": "Korean",
    "zh": "Chinese",
    "ja": "Japanese",
    "hi": "Hindi",
}

_LANGUAGE_SCRIPT_MARKERS = {
    "en": ("LATIN",),
    "ko": ("HANGUL",),
    "zh": ("CJK", "BOPOMOFO"),
    "ja": ("HIRAGANA", "KATAKANA", "CJK"),
    "hi": ("DEVANAGARI",),
}


def normalize_allowed_languages(value: Any) -> list[str]:
    """Normalize ``stt.allowed_languages`` into ISO-ish lowercase codes."""
    if not value:
        return []
    if isinstance(value, str):
        raw_items = value.replace(";", ",").replace(" ", ",").split(",")
    elif isinstance(value, (list, tuple, set)):
        raw_items = value
    else:
        return []

    aliases = {
        "english": "en",
        "eng": "en",
        "korean": "ko",
        "kor": "ko",
        "hangul": "ko",
        "한글": "ko",
        "한국어": "ko",
    }
    normalized: list[str] = []
    for item in raw_items:
        code = str(item).strip().lower().replace("_", "-")
        if not code:
            continue
        code = aliases.get(code, code.split("-")[0])
        if code not in normalized:
            normalized.append(code)
    return normalized


def language_label(allowed_languages: list[str]) -> str:
    labels = [_LANGUAGE_LABELS.get(code, code) for code in allowed_languages]
    if not labels:
        return "configured languages"
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + " or " + labels[-1]


def char_script_name(ch: str) -> str:
    try:
        return unicodedata.name(ch)
    except ValueError:
        return ""


def is_neutral_transcript_char(ch: str) -> bool:
    if ch.isascii() and not ch.isalpha():
        return True
    category = unicodedata.category(ch)
    return category[0] in {"N", "P", "S", "Z", "C"}


def char_allowed_by_languages(ch: str, allowed_languages: list[str]) -> bool:
    if is_neutral_transcript_char(ch):
        return True
    name = char_script_name(ch)
    for lang in allowed_languages:
        markers = _LANGUAGE_SCRIPT_MARKERS.get(lang)
        if markers and any(marker in name for marker in markers):
            return True
    return False


def transcript_violates_language_guard(transcript: str, allowed_languages: list[str]) -> bool:
    """Return True when a transcript is mostly outside configured scripts."""
    signal = 0
    allowed = 0
    disallowed = 0
    for ch in transcript:
        if is_neutral_transcript_char(ch):
            continue
        signal += 1
        if char_allowed_by_languages(ch, allowed_languages):
            allowed += 1
        else:
            disallowed += 1

    if signal < 3:
        return False
    allowed_ratio = allowed / signal
    disallowed_ratio = disallowed / signal
    return disallowed_ratio >= 0.60 and allowed_ratio <= 0.30


def apply_stt_language_guard(result: Dict[str, Any], stt_config: Optional[dict] = None) -> Dict[str, Any]:
    """Wrap out-of-policy STT output so the agent does not trust wrong scripts."""
    if not result.get("success"):
        return result
    transcript = str(result.get("transcript") or "").strip()
    if not transcript:
        return result

    cfg = stt_config or {}
    allowed_languages = normalize_allowed_languages(cfg.get("allowed_languages"))
    if not allowed_languages:
        return result
    if not transcript_violates_language_guard(transcript, allowed_languages):
        return result

    label = language_label(allowed_languages)
    guarded = dict(result)
    guarded["raw_transcript"] = transcript
    guarded["language_guard"] = "wrapped"
    guarded["transcript"] = (
        "[STT language guard: This transcript is outside the configured "
        f"voice languages ({label}) and is likely STT error. Do not interpret "
        "or translate it as a real foreign-language utterance. Treat the user "
        f"as speaking {label}; infer from context when safe, otherwise ask for "
        f"clarification. Raw transcript: {transcript}]"
    )
    return guarded
