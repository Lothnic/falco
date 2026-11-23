from types import SimpleNamespace
from unittest.mock import Mock

from localdictation import recording, recording_state


def test_live_preview_limits_extra_recognition_to_the_recent_window(monkeypatch):
    rec = recording_state.Recording(samplerate=10, preview_generation=4)
    rec.frames = [b"\x01\x00" * 10] * 6
    overlay = Mock()
    submit = Mock()
    monkeypatch.setattr(recording, "indicator", overlay)
    monkeypatch.setattr(recording.dictation_worker, "idle", lambda: True)
    monkeypatch.setattr(recording.dictation_worker, "submit", submit)
    render = Mock()
    monkeypatch.setattr(recording, "_render_preview", render)

    recording._queue_preview(rec, 10)
    submit.assert_not_called()
    recording._queue_preview(rec, 10)
    submit.assert_called_once()
    submit.call_args.args[0]()
    render.assert_called_once_with(rec, overlay, 4, rec.frames[-4:])
    assert len(rec.frames) == 6


def test_live_preview_drops_results_after_recording_ends(monkeypatch):
    rec = recording_state.Recording(preview_generation=4)
    state = SimpleNamespace(is_recording=True, current=rec)
    monkeypatch.setattr(recording.rs, "state", state)
    monkeypatch.setattr(recording.focused_window, "is_password", lambda: False)
    overlay = Mock()

    def finish_during_preview(_audio):
        state.is_recording = False
        return "An old draft"

    monkeypatch.setattr(recording.engine, "preview_transcript", finish_during_preview)
    recording._render_preview(rec, overlay, 4, [b"\x01\x00"])
    overlay.set_preview.assert_not_called()
