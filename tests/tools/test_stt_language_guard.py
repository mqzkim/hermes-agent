from tools.stt_language_guard import (
    apply_stt_language_guard,
    char_allowed_by_languages,
    char_script_name,
    language_label,
    normalize_allowed_languages,
    transcript_violates_language_guard,
)


def test_normalize_allowed_languages_handles_aliases_and_duplicates():
    assert normalize_allowed_languages("Korean, eng; ko 한국어 en-US") == ["ko", "en"]
    assert normalize_allowed_languages(["hangul", "EN", "en"]) == ["ko", "en"]
    assert normalize_allowed_languages(None) == []
    assert normalize_allowed_languages(123) == []


def test_language_label_formats_human_readable_list():
    assert language_label([]) == "configured languages"
    assert language_label(["ko"]) == "Korean"
    assert language_label(["ko", "en"]) == "Korean or English"
    assert language_label(["ko", "en", "xx"]) == "Korean, English or xx"


def test_script_helpers_classify_known_and_unknown_characters():
    assert "HANGUL" in char_script_name("한")
    assert char_script_name("\ud800") == ""
    assert char_allowed_by_languages("한", ["ko"])
    assert char_allowed_by_languages("A", ["en"])
    assert char_allowed_by_languages("?", ["ko"])
    assert not char_allowed_by_languages("你", ["ko", "en"])


def test_transcript_violation_is_conservative():
    assert transcript_violates_language_guard("那你們現在可以找到香港的東西案嗎?", ["ko", "en"])
    assert transcript_violates_language_guard("आिनामने व़ि़ियोने ग्योने सरे", ["ko", "en"])
    assert not transcript_violates_language_guard("내가 뭐라고 했지?", ["ko", "en"])
    assert not transcript_violates_language_guard("What did I say?", ["ko", "en"])
    assert not transcript_violates_language_guard("한글 plus English", ["ko", "en"])
    assert not transcript_violates_language_guard("你?", ["ko", "en"])


def test_apply_guard_wraps_out_of_policy_script_transcripts():
    result = {
        "success": True,
        "transcript": "那你們現在可以找到香港的東西案嗎?",
        "provider": "local",
    }
    guarded = apply_stt_language_guard(result, {"allowed_languages": ["ko", "en"]})

    assert guarded["success"] is True
    assert guarded["transcript"] != result["transcript"]
    assert "likely STT error" in guarded["transcript"]
    assert "Korean or English" in guarded["transcript"]
    assert "那你們現在可以找到香港的東西案嗎?" in guarded["transcript"]
    assert guarded["language_guard"] == "wrapped"
    assert guarded["raw_transcript"] == "那你們現在可以找到香港的東西案嗎?"


def test_apply_guard_leaves_allowed_or_disabled_results_unchanged():
    success = {"success": True, "transcript": "내가 뭐라고 했지?", "provider": "local"}
    assert apply_stt_language_guard(success, {"allowed_languages": "ko,en"}) == success
    assert apply_stt_language_guard(success, {}) == success

    empty = {"success": True, "transcript": "", "provider": "local"}
    assert apply_stt_language_guard(empty, {"allowed_languages": ["ko"]}) == empty

    failed = {"success": False, "transcript": "那你", "error": "boom"}
    assert apply_stt_language_guard(failed, {"allowed_languages": ["ko"]}) == failed
