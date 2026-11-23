"""Checks for the Phonon refiner integration."""
from unittest.mock import patch

import pytest

from localdictation import ai_cleanup, ai_download, dictation_text
from localdictation.window_classes import refiner_mode_for_window


def test_model_and_training_prompt():
    assert ai_download.MODEL_REPO == "Infatoshi/phonon-refiner-1.7b"
    messages = ai_cleanup._correction_messages("Send it on Friday")
    assert messages[1] == {"role": "user", "content": "Send it on Friday"}
    assert "Writing mode: minimal (notes and documents)." in messages[0]["content"]


@pytest.mark.parametrize(("window", "mode"), [
    ("COM.DISCORDAPP.DISCORD", "casual"),
    ("com.slack.Slack", "formal"),
    ("org.mozilla.Thunderbird", "formal"),
    ("org.kde.konsole", "prompt"),
    ("ai.opencode.desktop", "prompt"),
    ("discord-photo-viewer", "minimal"),
    (None, "minimal"),
])
def test_refiner_writing_modes_use_application_ids(window, mode):
    assert refiner_mode_for_window(window) == mode
    assert f"Writing mode: {mode} (" in ai_cleanup._correction_messages("Hello", mode)[0]["content"]


def test_casual_mode_only_suppresses_auto_period_when_refinement_succeeds(monkeypatch):
    class Engine:
        def correct(self, text, timeout, mode):
            assert mode == "casual"
            return self.answer

    engine = Engine()
    monkeypatch.setattr(dictation_text.live, "ai_corrections", True)
    monkeypatch.setattr(dictation_text.live, "ai_engine", engine)
    engine.answer = "sounds good"
    assert dictation_text.prepare_text(
        "sounds good", False, True, False, refiner_mode="casual") == "sounds good"
    engine.answer = None
    assert dictation_text.prepare_text(
        "sounds good", False, True, False, refiner_mode="casual").endswith(".")


def test_full_raw_transcript_is_refined_before_commands():
    class Engine:
        def correct(self, text, timeout, mode):
            assert text == "hello um world"
            return "Hello world"

    with patch.object(dictation_text.live, "ai_corrections", True), \
         patch.object(dictation_text.live, "ai_engine", Engine()), \
         patch.object(dictation_text, "apply_custom_commands", side_effect=lambda x: (x, {})) as commands:
        dictation_text.prepare_text("hello um world", False, False, False)
    commands.assert_called_once_with("Hello world")


def test_implausible_refinement_falls_back_to_transcript():
    class Engine:
        def correct(self, text, timeout, mode):
            return "unrelated " * 30

    raw = "one two three four five six seven eight nine ten"
    with patch.object(dictation_text.live, "ai_corrections", True), \
         patch.object(dictation_text.live, "ai_engine", Engine()), \
         patch.object(dictation_text, "apply_custom_commands", side_effect=lambda x: (x, {})) as commands:
        dictation_text.prepare_text(raw, False, False, False)
    commands.assert_called_once_with(raw)


def test_refiner_restores_dropped_openers_conservatively():
    restore = dictation_text.restore_opening_word
    assert restore('Okay, the build is ready', 'The build is ready') == 'Okay, the build is ready'
    assert restore('Well, Alice can help', 'Alice can help') == 'Well, Alice can help'
    assert restore('And we can go', 'And we can go') == 'And we can go'
    assert restore('Okay, cancel that', 'Cancel') == 'Cancel'
    assert restore('So we can go', 'We can go') == 'We can go'


def test_restoration_runs_after_refiner_output_check():
    class Engine:
        def correct(self, text, timeout, mode):
            return 'The build is ready'

    with patch.object(dictation_text.live, 'ai_corrections', True), \
         patch.object(dictation_text.live, 'ai_engine', Engine()), \
         patch.object(dictation_text, 'apply_custom_commands', side_effect=lambda x: (x, {})) as commands:
        dictation_text.prepare_text('Okay, the build is ready', False, False, False)
    commands.assert_called_once_with('Okay, the build is ready')
