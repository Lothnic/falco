"""The optional overlay must not leave dictation without an indicator."""
from threading import Lock
from unittest.mock import Mock

from localdictation.rune_indicator import RuneIndicator


def indicator(recording=True, generation=4):
    result = RuneIndicator.__new__(RuneIndicator)
    result._lock = Lock()
    result._recording = recording
    result._generation = generation
    result._checked_generation = -1
    result._available_generation = -1
    result._fallback_generation = -1
    result.fallback = Mock()
    return result


def test_old_availability_response_cannot_hide_current_fallback():
    overlay = indicator()
    overlay._hide_fallback_if_current(3)
    overlay.fallback.hide_indicator.assert_not_called()
    overlay._fallback_generation = 4
    overlay._hide_fallback_if_current(4)
    overlay.fallback.hide_indicator.assert_called_once()


def test_failed_overlay_restores_gtk_only_while_recording():
    overlay = indicator()
    overlay._restore_fallback_if_current(4)
    overlay.fallback.show_at_position.assert_called_once()
    overlay.fallback.start_recording.assert_called_once()
    overlay._recording = False
    overlay._restore_fallback_if_current(4)
    assert overlay.fallback.show_at_position.call_count == 1


def test_processing_never_hides_a_newer_recording():
    overlay = indicator(recording=False)
    overlay._send = Mock(return_value=True)
    token = overlay.begin_processing()
    assert token == 5
    overlay._recording = True
    overlay._generation += 1
    overlay.end_processing(token)
    assert [call.args[0] for call in overlay._send.call_args_list] == ["show", "processing"]


def test_processing_finishes_when_no_recording_overtook_it():
    overlay = indicator(recording=False)
    overlay._send = Mock(return_value=True)
    token = overlay.begin_processing()
    overlay.end_processing(token)
    assert [call.args[0] for call in overlay._send.call_args_list] == ["show", "processing", "hide"]


def test_start_does_not_flash_gtk_while_rune_is_starting(monkeypatch):
    overlay = indicator(recording=False)
    overlay._send = Mock(return_value=True)
    overlay._available_generation = -1
    overlay._fallback_generation = -1
    monkeypatch.setattr('localdictation.rune_indicator.GLib.timeout_add', lambda *args: 1)
    overlay.show_at_position()
    overlay.start_recording()
    overlay.fallback.show_at_position.assert_not_called()
    overlay.fallback.start_recording.assert_not_called()
    overlay._restore_fallback_if_current(overlay._generation)
    overlay.fallback.show_at_position.assert_called_once()


def test_slow_or_missing_rune_gets_one_gtk_fallback():
    overlay = indicator(recording=True)
    overlay._fallback_after_timeout(4)
    overlay._fallback_after_timeout(4)
    overlay.fallback.show_at_position.assert_called_once()
    overlay.fallback.start_recording.assert_called_once()


def test_ready_rune_does_not_show_fallback_after_timeout():
    overlay = indicator(recording=True)
    overlay._available_generation = 4
    overlay._fallback_after_timeout(4)
    overlay.fallback.show_at_position.assert_not_called()


def test_failed_sidecar_immediately_uses_fallback():
    overlay = indicator(recording=False)
    overlay._send = Mock(return_value=False)
    overlay.show_at_position()
    overlay.fallback.show_at_position.assert_called_once()
    overlay.fallback.start_recording.assert_called_once()
