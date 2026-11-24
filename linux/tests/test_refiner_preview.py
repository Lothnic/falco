from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from localdictation import refiner_preview, recording_state


@pytest.fixture
def preview(monkeypatch):
    rec = recording_state.Recording(preview_generation=4)
    rec.streamer = SimpleNamespace(committed='meet on friday')
    state = SimpleNamespace(is_recording=True, current=rec)
    monkeypatch.setattr(refiner_preview.rs, 'state', state)
    monkeypatch.setattr(refiner_preview.live, 'rune_live_preview', True)
    monkeypatch.setattr(refiner_preview.focused_window, 'is_password', lambda: False)
    overlay = Mock()
    callback = refiner_preview.for_recording(rec, overlay, 'meet on friday')
    return rec, state, overlay, callback


def test_recording_preview_uses_only_its_current_committed_text(preview):
    rec, _, overlay, callback = preview
    callback('Meet\non Friday.')
    overlay.set_preview.assert_called_once_with(4, 'Meet on Friday.')
    rec.streamer.committed = 'meet on friday at noon'
    callback('Old refinement')
    assert overlay.set_preview.call_count == 1


def test_release_detaches_the_preview_but_keeps_the_reusable_generation(preview):
    rec, state, overlay, callback = preview
    rec.captured = True
    state.is_recording = False
    assert callback('Meet on Friday.') is None
    overlay.set_preview.assert_not_called()


def test_new_recording_cancels_the_old_preview_generation(preview):
    _, state, overlay, callback = preview
    state.current = recording_state.Recording()
    assert callback('Old refinement') is False
    overlay.set_preview.assert_not_called()


def test_password_focus_clears_and_disables_recording_preview(preview, monkeypatch):
    rec, _, overlay, callback = preview
    monkeypatch.setattr(refiner_preview.focused_window, 'is_password', lambda: True)
    assert callback('Secret') is False
    overlay.set_preview.assert_called_once_with(4, '')
    assert rec.preview_generation is None


def test_finishing_callback_is_scoped_and_checks_cancellation(preview):
    rec, _, overlay, _ = preview
    assert refiner_preview.current() is None
    with refiner_preview.processing(overlay, 5, rec.message):
        callback = refiner_preview.current()
        callback('Meet on Friday.')
        overlay.set_processing_preview.assert_called_once_with(5, 'Meet on Friday.')
        rec.message.cancelled = True
        assert callback('More') is False
        assert overlay.set_processing_preview.call_count == 1
    assert refiner_preview.current() is None


def test_finishing_preview_stays_off_without_opt_in(preview, monkeypatch):
    rec, _, overlay, _ = preview
    monkeypatch.setattr(refiner_preview.live, 'rune_live_preview', False)
    with refiner_preview.processing(overlay, 5, rec.message):
        assert refiner_preview.current() is None
    overlay.set_processing_preview.assert_not_called()
