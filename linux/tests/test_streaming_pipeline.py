"""The streaming dictation path end to end: phrases committed while the
speaker talks, then a release that hears only the tail and splices it on.

The engine is a stub that answers from a script, so nothing here needs a
microphone or a model."""
import numpy as np

from localdictation import pipeline, recording_state, streaming


class _Job:
    """The pipeline's job, built by hand: the fields _hear_streamed reads."""

    def __init__(self, streamer):
        self.streamer = streamer
        self.language = None
        self.chunk_role = None
        self.beeps_on = False
        self.message = recording_state.Message()


def _audio(seconds, rate=16000):
    return np.zeros(int(seconds * rate), dtype=np.float32)


def test_release_hears_only_the_tail(monkeypatch):
    """A 20 s recording with two phrases committed hears 1.5 s of overlap and
    the last phrase, not the whole 20 s."""
    heard = []

    def transcribe(audio, language=None):
        heard.append(len(audio) / 16000)
        return "the store and bought milk"

    monkeypatch.setattr(pipeline.engine, "transcribe", transcribe)
    streamer = streaming.Streamer()
    streamer.accept("I went to the store", 10.0)

    job = _Job(streamer)
    text = pipeline._hear_streamed(_audio(14.0), job)

    assert text == "I went to the store and bought milk"
    # 14 - (10 - OVERLAP) seconds, not 14.
    assert heard == [14.0 - (10.0 - streaming.OVERLAP_S)]


def test_a_short_recording_hears_everything(monkeypatch):
    heard = []
    monkeypatch.setattr(pipeline.engine, "transcribe",
                        lambda audio, language=None: heard.append(len(audio) / 16000) or "few words")
    streamer = streaming.Streamer()
    streamer.accept("a few words", 2.0)

    assert pipeline._hear_streamed(_audio(2.0), _Job(streamer)) is None
    assert heard == []      # the caller transcribes the whole recording instead


def test_a_seam_that_does_not_line_up_falls_back_to_the_whole_recording(monkeypatch):
    """The tail is heard but doesn't match, so the caller must redo it whole:
    a wrong splice would type the wrong text."""
    def transcribe(audio, language=None):
        return "a completely different sentence"

    monkeypatch.setattr(pipeline.engine, "transcribe", transcribe)
    streamer = streaming.Streamer()
    streamer.accept("I went to the store", 10.0)

    assert pipeline._hear_streamed(_audio(14.0), _Job(streamer)) is None


def test_a_silent_tail_keeps_the_committed_text(monkeypatch):
    monkeypatch.setattr(pipeline.engine, "transcribe", lambda audio, language=None: "")
    streamer = streaming.Streamer()
    streamer.accept("I went to the store", 10.0)

    assert pipeline._hear_streamed(_audio(14.0), _Job(streamer)) == "I went to the store"


def test_untrusted_streaming_never_shortens_the_release(monkeypatch):
    called = []
    monkeypatch.setattr(pipeline.engine, "transcribe",
                        lambda audio, language=None: called.append(1) or "x")
    streamer = streaming.Streamer()
    streamer.trusted = False

    assert pipeline._hear_streamed(_audio(14.0), _Job(streamer)) is None
    assert called == []


def test_the_release_reads_a_snapshot_not_the_live_streamer(monkeypatch):
    """A commit still in flight must not change what the release reads."""
    streamer = streaming.Streamer()
    streamer.accept("I went to the store", 4.0)
    frozen = streamer.snapshot()
    # The next commit re-hears the seam, as a real span does.
    streamer.accept("to the store and bought milk", 8.0)

    assert frozen.committed == "I went to the store"
    assert frozen.cut_s == 4.0
    assert streamer.committed == "I went to the store and bought milk"
    assert streamer.cut_s == 8.0
