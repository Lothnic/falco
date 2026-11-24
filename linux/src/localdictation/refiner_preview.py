"""Provisional refiner text for Rune. No callback here types into the target app."""
import threading
from contextlib import contextmanager

from . import focused_window
from . import live_settings as live
from . import recording_state as rs

_local = threading.local()


def current():
    """The finishing job's callback, scoped to the dictation worker thread."""
    return getattr(_local, "callback", None)


def _short(text):
    return " ".join(text.split())[-160:]


def for_recording(rec, overlay, source):
    """Display only for the same recording and the same committed transcript."""
    generation = rec.preview_generation
    if generation is None or overlay is None:
        return None

    def preview(text):
        if rec.message.cancelled or (rs.state.is_recording and rs.state.current is not rec):
            return False
        # A release can reuse the result currently being generated. Detach
        # its recording preview, but let that exact-transcript request finish.
        if not rs.state.is_recording or rec.captured:
            return None
        if not live.rune_live_preview or rec.preview_generation != generation:
            return None
        if focused_window.is_password():
            overlay.set_preview(generation, "")
            rec.preview_generation = None
            return False
        # A newer commit may arrive while this response is still streaming.
        if rec.streamer is not None and rec.streamer.committed.strip() == source:
            overlay.set_preview(generation, _short(text))
        return None

    return preview


@contextmanager
def processing(overlay, generation, message):
    """Bind streaming to this finishing job; late packets can't touch a new one."""
    previous = current()
    setter = getattr(overlay, "set_processing_preview", None)

    def preview(text):
        if message.cancelled:
            return False
        if not live.rune_live_preview:
            setter(generation, "")
        elif focused_window.is_password():
            setter(generation, "")
            return False
        else:
            setter(generation, _short(text))
        return None

    _local.callback = preview if setter and generation is not None and live.rune_live_preview else None
    try:
        yield
    finally:
        _local.callback = previous
