"""A refinement guessed while recording is the text actually typed.

The guess must be used only when it was made for the very transcript the
recording produced, and the ordinary refine must run otherwise."""
from localdictation import dictation_text, live_settings, refiner_prefetch


class _Engine:
    """A refiner that answers from a script and counts what it was asked."""

    def __init__(self, answers):
        self.answers = answers
        self.asked = []

    def correct(self, text, timeout=None, *, mode="minimal"):
        self.asked.append(text)
        return self.answers.get(text)


def _settings(monkeypatch, engine):
    monkeypatch.setattr(live_settings, "ai_corrections", True)
    monkeypatch.setattr(live_settings, "ai_engine", engine)


def test_the_guess_is_what_gets_typed(monkeypatch):
    engine = _Engine({"order two boxes": "Order two boxes."})
    _settings(monkeypatch, engine)
    serial = refiner_prefetch.begin()
    thread = refiner_prefetch.offer(
        "order two boxes", lambda t: dictation_text.refine(t, "minimal"), serial,
        key=dictation_text.refinement_key("minimal"))
    thread.join(timeout=5)

    text = dictation_text.prepare_text("order two boxes", True, True, True,
                                       refiner_mode="minimal", serial=serial)
    assert text.startswith("Order two boxes")
    # The guess answered it, so the release asked the model nothing.
    assert engine.asked == ["order two boxes"]


def test_a_guess_for_other_text_is_not_used(monkeypatch):
    engine = _Engine({
        "order two boxes": "Order two boxes.",
        "order two boxes and a bag": "Order two boxes and a bag.",
    })
    _settings(monkeypatch, engine)
    serial = refiner_prefetch.begin()
    thread = refiner_prefetch.offer(
        "order two boxes", lambda t: dictation_text.refine(t, "minimal"), serial)
    thread.join(timeout=5)

    text = dictation_text.prepare_text("order two boxes and a bag", True, True, True,
                                       refiner_mode="minimal", serial=serial)
    assert text.startswith("Order two boxes and a bag")
    # The longer transcript was refined at release, as it has to be.
    assert engine.asked == ["order two boxes", "order two boxes and a bag"]


def test_without_a_serial_the_release_refines_as_usual(monkeypatch):
    engine = _Engine({"plain words": "Plain words."})
    _settings(monkeypatch, engine)
    text = dictation_text.prepare_text("plain words", True, True, True,
                                       refiner_mode="minimal")
    assert text.startswith("Plain words")
    assert engine.asked == ["plain words"]


def test_an_implausible_guess_is_not_typed(monkeypatch):
    """The length guard applies to the guess too: a runaway answer must not
    replace the transcript, whether it came from the guess or the release."""
    engine = _Engine({"short bit": "A far longer answer than anyone said here today"})
    _settings(monkeypatch, engine)
    serial = refiner_prefetch.begin()
    thread = refiner_prefetch.offer(
        "short bit", lambda t: dictation_text.refine(t, "minimal"), serial)
    thread.join(timeout=5)
    # The guess was rejected by the guard, so nothing was stored.
    assert refiner_prefetch.take("short bit", serial) is None

    text = dictation_text.prepare_text("short bit", True, True, True,
                                       refiner_mode="minimal", serial=serial)
    assert "far longer answer" not in text
