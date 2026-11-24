"""Refining a dictation before the key comes up.

The refiner is the slowest step of a dictation that uses it: a local model
reading the whole transcript. Streaming dictation already hears the words
while the speaker talks (streaming.py), and this does the same for the
refiner: with the text so far committed, the refined version is worked out
during the recording, so at release there is nothing left to wait for.

The text typed never depends on this. The refiner's answer is kept beside the
exact transcript it was computed for, and only reused when the finished
transcript is that same text, character for character. Anything else is
refined the ordinary way at release; this can only save time, never change
the words.

The guess is worth making because most dictations end quietly: the speaker
pauses, then lets go of the key, and the last thing they said is already
committed. A guess that misses costs processor time during the recording and
nothing else, so it is made once per pause and only while the worker is idle.
"""
import threading
import time

from .logger import setup_logger

logger = setup_logger(__name__)

# One dictation at a time: the recording in progress. A dictation that starts
# replaces whatever the last one was thinking about.
_lock = threading.Lock()
_changed = threading.Condition(_lock)
_key = None
_asked = ""          # the transcript the answer below belongs to
_answer = None       # its refinement, or None while it isn't known
_running = False     # whether a refine is under way
_serial = 0          # bumps with each new recording, to drop a stale answer


def begin() -> int:
    """A new recording: forget the last one's guess. Returns its serial, which
    offer() and take() carry so a late answer can't be used for it."""
    global _asked, _answer, _running, _serial
    with _lock:
        _asked, _answer = "", None
        _serial += 1
        _changed.notify_all()
        return _serial


def offer(text: str, refine, serial: int, *, key=None):
    """Work out the refined *text* in the background, for a dictation whose
    serial is *serial*. *refine* is how to ask (dictation_text's own call,
    so the prompt is exactly the release's). Nothing when the text is empty,
    already guessed, or a guess is still running.

    Returns the thread doing the work, or None when nothing was started; a
    caller that must know the guess is finished (a test) can join it."""
    global _asked, _answer, _running, _key
    text = (text or "").strip()
    if not text:
        return None
    with _lock:
        if serial != _serial or _running or (text == _asked and key == _key):
            return None
        _asked, _answer, _running = text, None, True
        _key = key

    def run():
        global _answer, _running
        answer = None
        try:
            answer = refine(text)
        except Exception as e:
            logger.info(f"Refiner prefetch: the guess failed ({e}); "
                        f"the release will refine as usual")
        finally:
            with _lock:
                # Kept only if this is still the dictation that asked: a new
                # recording started means its text is not this one's.
                if serial == _serial and _asked == text:
                    _answer = answer
                _running = False
                _changed.notify_all()

    thread = threading.Thread(target=run, daemon=True, name="tt-refine-guess")
    thread.start()
    return thread


def take(text: str, serial: int, *, key=None, wait=0):
    """The guessed refinement of *text*, or None when there is none for
    exactly this text. *serial* is the recording's (begin())."""
    deadline = time.monotonic() + wait
    with _changed:
        while serial == _serial and (text or "").strip() == _asked and key == _key:
            if _answer:
                return _answer
            remaining = deadline - time.monotonic()
            if not _running or remaining <= 0:
                break
            _changed.wait(remaining)
        return None


def waiting(serial: int) -> bool:
    """Whether a guess for *serial* is still running: the release may wait for
    it rather than starting a second refine of the same text."""
    with _lock:
        return serial == _serial and _running
