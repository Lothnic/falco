"""Refining a dictation while the speaker is still talking.

The rule these tests defend: a guessed refinement is used only for the exact
transcript it was made for, so this can save time but can never change what
is typed."""
from localdictation import refiner_prefetch


def _guess(text, refine, serial):
    """Offer a guess and wait for it, so the test has no timing to lose."""
    thread = refiner_prefetch.offer(text, refine, serial)
    if thread is not None:
        thread.join(timeout=5)
        assert not thread.is_alive(), "the guess never finished"
    return thread


def test_a_guess_is_used_for_the_text_it_was_made_for():
    serial = refiner_prefetch.begin()
    _guess("hello there", lambda t: t.upper(), serial)
    assert refiner_prefetch.take("hello there", serial) == "HELLO THERE"


def test_a_guess_is_never_used_for_different_text():
    """The finished transcript is usually longer than the guess: it must not
    borrow the shorter text's refinement."""
    serial = refiner_prefetch.begin()
    _guess("hello there", lambda t: t.upper(), serial)
    assert refiner_prefetch.take("hello there and more", serial) is None


def test_a_new_recording_drops_the_last_guess():
    serial = refiner_prefetch.begin()
    _guess("first dictation", lambda t: t.upper(), serial)
    refiner_prefetch.begin()     # the next recording starts
    assert refiner_prefetch.take("first dictation", serial) is None


def test_an_old_serial_cannot_take_the_new_guess():
    old = refiner_prefetch.begin()
    new = refiner_prefetch.begin()
    _guess("the text", lambda t: t.upper(), new)
    assert refiner_prefetch.take("the text", new) == "THE TEXT"
    assert refiner_prefetch.take("the text", old) is None


def test_an_empty_text_is_not_guessed():
    serial = refiner_prefetch.begin()
    called = []
    assert _guess("   ", lambda t: called.append(t) or t, serial) is None
    assert called == []
    assert refiner_prefetch.take("", serial) is None


def test_a_failed_guess_leaves_nothing_to_use():
    serial = refiner_prefetch.begin()

    def explode(_text):
        raise RuntimeError("the refiner isn't loaded")

    _guess("some words", explode, serial)
    assert refiner_prefetch.take("some words", serial) is None
    assert not refiner_prefetch.waiting(serial)


def test_the_same_text_is_not_guessed_twice():
    """A pause after a pause commits the same text again; asking the model
    twice would waste the processor for nothing."""
    serial = refiner_prefetch.begin()
    count = []

    def refine(text):
        count.append(text)
        return text

    _guess("one phrase", refine, serial)
    assert _guess("one phrase", refine, serial) is None
    assert len(count) == 1


def test_a_guess_still_running_is_not_started_again():
    serial = refiner_prefetch.begin()
    running = []

    def slow(text):
        running.append(text)
        return text

    first = refiner_prefetch.offer("waiting phrase", slow, serial)
    second = refiner_prefetch.offer("waiting phrase", slow, serial)
    assert second is None            # the first is still going
    first.join(timeout=5)
    assert running == ["waiting phrase"]


def test_an_answer_for_a_newer_recording_is_not_kept_for_the_old_one():
    """A guess in flight when the next recording starts must not be stored
    under the old recording's serial."""
    serial = refiner_prefetch.begin()

    def start_new_recording_then_answer(text):
        refiner_prefetch.begin()      # the next recording begins mid-guess
        return text.upper()

    _guess("racing text", start_new_recording_then_answer, serial)
    assert refiner_prefetch.take("racing text", serial) is None


def test_a_guess_for_another_mode_or_engine_is_never_reused():
    serial = refiner_prefetch.begin()
    thread = refiner_prefetch.offer('hello there', str.upper, serial, key=('minimal', 1))
    thread.join(timeout=5)
    assert refiner_prefetch.take('hello there', serial, key=('casual', 1)) is None
    assert refiner_prefetch.take('hello there', serial, key=('minimal', 2)) is None
    assert refiner_prefetch.take('hello there', serial, key=('minimal', 1)) == 'HELLO THERE'


def test_release_can_wait_for_an_exact_request_already_in_flight():
    import threading
    started, finish = threading.Event(), threading.Event()
    serial = refiner_prefetch.begin()

    def slow(text):
        started.set()
        assert finish.wait(5)
        return text.upper()

    worker = refiner_prefetch.offer('hello there', slow, serial, key='minimal')
    assert started.wait(5)
    result = []
    waiting = threading.Thread(target=lambda: result.append(refiner_prefetch.take(
        'hello there', serial, key='minimal', wait=5)))
    waiting.start()
    finish.set()
    worker.join(timeout=5)
    waiting.join(timeout=5)
    assert result == ['HELLO THERE']
