"""Checks for the Phonon refiner integration."""
from unittest.mock import patch

from localdictation import ai_cleanup, ai_download, dictation_text


def test_model_and_training_prompt():
    assert ai_download.MODEL_REPO == "Infatoshi/phonon-refiner-1.7b"
    messages = ai_cleanup._correction_messages("Send it on Friday")
    assert messages[1] == {"role": "user", "content": "Send it on Friday"}
    assert "Writing mode: minimal (notes and documents)." in messages[0]["content"]


def test_full_raw_transcript_is_refined_before_commands():
    class Engine:
        def correct(self, text, timeout):
            assert text == "hello um world"
            return "Hello world"

    with patch.object(dictation_text.live, "ai_corrections", True), \
         patch.object(dictation_text.live, "ai_engine", Engine()), \
         patch.object(dictation_text, "apply_custom_commands", side_effect=lambda x: (x, {})) as commands:
        dictation_text.prepare_text("hello um world", False, False, False)
    commands.assert_called_once_with("Hello world")


def test_implausible_refinement_falls_back_to_transcript():
    class Engine:
        def correct(self, text, timeout):
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
        def correct(self, text, timeout):
            return 'The build is ready'

    with patch.object(dictation_text.live, 'ai_corrections', True), \
         patch.object(dictation_text.live, 'ai_engine', Engine()), \
         patch.object(dictation_text, 'apply_custom_commands', side_effect=lambda x: (x, {})) as commands:
        dictation_text.prepare_text('Okay, the build is ready', False, False, False)
    commands.assert_called_once_with('Okay, the build is ready')
