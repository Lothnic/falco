"""When a recording streams: the option on, and no Type at pause or voice
edit taking the audio another way.

The pause detector is stubbed: it needs the voice detector, and with it the
speech model, which these tests are not about."""
from localdictation import chunking, engine, live_settings, recording_state, type_at_pause
from localdictation.voice_detector import Unavailable


class _FakePauseDetector:
    """Stands in for chunking.PauseDetector: it only has to exist."""

    def __init__(self, pause_seconds, sample_rate):
        self.pause_seconds = pause_seconds
        self.sample_rate = sample_rate


def _arms(monkeypatch, *, streaming_on, chunk_pause, edit_mode=False, detector=None,
          can_preview=True):
    """Arm a recording with those options, and return it."""
    monkeypatch.setattr(live_settings, "streaming_dictation", streaming_on)
    monkeypatch.setattr(live_settings, "chunk_pause_seconds", chunk_pause)
    monkeypatch.setattr(type_at_pause.dictation_worker, "worker", lambda: None)
    monkeypatch.setattr(chunking, "PauseDetector", detector or _FakePauseDetector)
    monkeypatch.setattr(engine, "can_preview", lambda: can_preview)
    rec = recording_state.Recording(edit_mode=edit_mode)
    rec.samplerate = 16000
    type_at_pause.arm_chunker(rec)
    return rec


def test_streaming_arms_a_streamer_and_its_pause_detector(monkeypatch):
    rec = _arms(monkeypatch, streaming_on=True, chunk_pause=0)
    assert rec.streamer is not None
    assert isinstance(rec.stream_pause, _FakePauseDetector)
    assert rec.stream_pause.pause_seconds == type_at_pause.STREAM_PAUSE_S


def test_streaming_is_off_by_default(monkeypatch):
    rec = _arms(monkeypatch, streaming_on=False, chunk_pause=0)
    assert rec.streamer is None
    assert rec.stream_pause is None


def test_type_at_pause_keeps_the_audio_for_itself(monkeypatch):
    """Cutting phrases takes them out of rec.frames, so a streamer's spans
    would no longer line up: they never run together."""
    rec = _arms(monkeypatch, streaming_on=True, chunk_pause=1.0)
    assert rec.chunker is not None
    assert rec.streamer is None


def test_a_voice_edit_never_streams(monkeypatch):
    """Its instruction needs the whole recording."""
    rec = _arms(monkeypatch, streaming_on=True, chunk_pause=0, edit_mode=True)
    assert rec.streamer is None


def test_without_a_voice_detector_the_recording_goes_on_whole(monkeypatch):
    """The detector needs the voice detector; without it the recording is
    transcribed whole at release, as before."""
    def unavailable(*args, **kwargs):
        raise Unavailable("no voice detector")

    rec = _arms(monkeypatch, streaming_on=True, chunk_pause=0, detector=unavailable)
    assert rec.streamer is None
    assert rec.stream_pause is None


def test_an_engine_that_cannot_preview_never_streams(monkeypatch):
    """Whisper and the GPU Parakeet have no in-recording recognition, so a
    commit would hear nothing: streaming there would only add work."""
    rec = _arms(monkeypatch, streaming_on=True, chunk_pause=0, can_preview=False)
    assert rec.streamer is None
    assert rec.stream_pause is None
