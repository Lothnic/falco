"""Read OpenAI SSE chat deltas without ever treating partial output as final."""
import json
import time

from .logger import setup_logger

logger = setup_logger(__name__)


def notify_preview(callback, text):
    """A failed overlay must never discard a successfully refined dictation."""
    try:
        return callback(text)
    except Exception as e:
        logger.warning(f"Refiner preview unavailable ({type(e).__name__})")
        return None


class PreviewCancelled(Exception):
    """The recording or finishing job that requested the preview ended."""


def read_chat(response, on_preview, timeout):
    """Return a complete answer; raise on truncation, malformed SSE or a lost pipe.

    The callback gets cumulative text, at most twenty times a second. False
    cancels this request. Preview callbacks must never inject text into an app.
    """
    deadline = time.monotonic() + timeout
    emitted_at = 0.0
    pieces = []
    length = 0
    finished = False
    event = []

    def emit(text):
        if notify_preview(on_preview, text) is False:
            raise PreviewCancelled()

    for raw in response:
        if time.monotonic() > deadline:
            raise TimeoutError("Refinement stream exceeded its deadline")
        line = raw.decode("utf-8").rstrip("\r\n")
        if line.startswith("data:"):
            event.append(line[5:].lstrip(" "))
        elif not line and event:
            data, event = "\n".join(event), []
            if data == "[DONE]":
                if not finished:
                    raise ValueError("Refinement stream ended without a completed answer")
                answer = "".join(pieces).strip()
                emit(answer)
                return answer
            chunk = json.loads(data)
            if "error" in chunk:
                raise ValueError("Refinement server returned a stream error")
            choices = chunk.get("choices", [])
            if not choices:  # optional final usage packet
                continue
            choice = choices[0]
            delta = choice.get("delta", {}).get("content")
            if delta:
                if finished or not isinstance(delta, str):
                    raise ValueError("Invalid refinement delta")
                pieces.append(delta)
                length += len(delta)
                if length > 65536:
                    raise ValueError("Refinement stream exceeded its text limit")
                now = time.monotonic()
                if now - emitted_at >= 0.05:
                    emit("".join(pieces))
                    emitted_at = now
            reason = choice.get("finish_reason")
            if reason is not None:
                if reason != "stop":
                    raise ValueError("Refinement stream did not finish normally")
                finished = True
    raise ValueError("Refinement stream was interrupted")
