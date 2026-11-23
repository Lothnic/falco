"""Streaming dictation: hear the recording in phrases while the speaker
talks, so the release only has to transcribe the last one.

The phrases are cut at pauses, never mid-word, so no word straddles a seam.
Everything before the seam is already committed, and the release transcribes
only from a little before it: that is what keeps the wait after the key from
growing with the length of the dictation.

The committed span and the tail overlap by a moment of audio, so the words
at the seam are heard twice. splice() drops the repeated ones by lining the
two sides up word by word, and tolerates one misheard word in a longer
overlap (the same speech heard with and without its right context rarely
comes out identical). When a seam can't be lined up at all the recording is
transcribed whole as before: a slow dictation is better than a wrong one.

Off unless streaming_dictation is set in config.toml.
"""
import difflib
import re

from .logger import setup_logger

logger = setup_logger(__name__)

_WORD = re.compile(r"\w+(?:['’-]\w+)*")

# Shorter dictations are transcribed whole at release: there is too little
# audio to save, and one pass is easier to trust.
MIN_STREAM_S = 6.0

# Audio re-heard at the start of each span. Every span but the first begins
# this far before the seam, so the words there are heard with the sound
# before them and appear in both halves: that is what splice() lines up. It
# also keeps a soft word onset ("h", "f", "s") from being lost at a cut.
LEAD_KEEP_S = 1.5

# A commit waits for this much speech since the last one. A click or a cough
# between two phrases is not worth a transcription.
MIN_COMMIT_S = 1.0

# At release the tail starts this far before the seam, so there are enough
# words on both sides to line up. The same amount a commit re-hears.
OVERLAP_S = LEAD_KEEP_S

# Past this many seconds the streaming stopwatch is no longer tracked: a very
# long recording keeps its committed text and streams on regardless.
MAX_COMMIT_S = 120.0

# The longest run of words searched for at a seam, either side.
_SEAM_WORDS = 24

# How alike two overlap candidates must be for a longer one to be taken over
# a shorter exact one ("..." heard as "... .").
_SEAM_RATIO = 0.7


def words(text: str) -> list[str]:
    """The words of *text*, folded for comparison: what splice() lines up."""
    return [m.group().casefold() for m in _WORD.finditer(text)]


def _overlap(head: list[str], tail: list[str]) -> int:
    """How many of *tail*'s first words are *head*'s last words heard again:
    the longest k for which they line up, allowing one word to differ when k
    is 3 or more. 0 when nothing lines up."""
    most = min(len(head), len(tail), _SEAM_WORDS)
    for size in range(most, 0, -1):
        left, right = head[-size:], tail[:size]
        if left == right:
            return size
        if size >= 3:
            same = sum(1 for a, b in zip(left, right, strict=True) if a == b)
            # One word may have been misheard on either side of the seam;
            # two in a long overlap still reads as the same words.
            allowed = 1 if size < 8 else 2
            if size - same <= allowed and \
                    difflib.SequenceMatcher(None, left, right).ratio() >= _SEAM_RATIO:
                return size
    return 0


def splice(head: str, tail: str):
    """*head* with *tail* joined at their seam, and whether the seam lined
    up. The words the two sides share are dropped from *tail*; what is left
    is added after *head*.

    A seam that doesn't line up is still joined, with the flag False: the
    caller then decides whether to trust it."""
    head = head.strip()
    tail = tail.strip()
    if not head:
        return tail, True
    if not tail:
        return head, True
    matches = list(_WORD.finditer(tail))
    if not matches:
        return _join(head, tail), False
    shared = _overlap(words(head), [m.group().casefold() for m in matches])
    rest = tail[matches[shared - 1].end():] if shared else tail
    return _join(head, rest), shared > 0


def _join(head: str, rest: str) -> str:
    """*head* and *rest* with the space between them a sentence needs, and
    none before punctuation or after a line break.

    *rest* normally begins with the space that followed the seam in the
    transcription, so its own leading whitespace is the separator."""
    if not rest:
        return head
    if head.endswith(("\n", " ")) or rest[0].isspace() or rest[0] in ".,;:!?…)]}\"'":
        return head + rest
    return f"{head} {rest}"


class Streamer:
    """One recording's committed words, and which audio is still to hear.

    The audio stays with the caller: every span is seconds from the start of
    the recording, so a caller slices its own frames. A span is a half-open
    (start, end) pair."""

    def __init__(self, min_stream_s: float = MIN_STREAM_S):
        self.committed = ""
        # The end of the audio `committed` covers: where the next seam is.
        self.cut_s = 0.0
        self.min_stream_s = min_stream_s
        self.rounds = 0
        # Cleared when a seam can't be lined up: the recording is then
        # transcribed whole, exactly as it was before streaming.
        self.trusted = True

    def commit_span(self, total_s: float):
        """The audio to transcribe now, or None when there is nothing worth
        committing yet. The gate is on speech *since the last commit*, not on
        the span's length: the span re-hears a little before the seam
        (LEAD_KEEP_S), which would otherwise satisfy it at once."""
        if not self.trusted:
            return None
        if total_s - self.cut_s < MIN_COMMIT_S:
            return None
        if total_s - self.cut_s > MAX_COMMIT_S:
            return None
        start = max(0.0, self.cut_s - LEAD_KEEP_S) if self.cut_s else 0.0
        return start, total_s

    def accept(self, text: str, end_s: float):
        """Add what a commit span was heard as, and move the seam to its end.
        A span with no words leaves the seam where it was: nothing was said
        there, and the next span starts from the same place."""
        if not self.trusted or end_s <= self.cut_s:
            return
        said = (text or "").strip()
        if not said:
            self.cut_s = end_s
            return
        joined, lined_up = splice(self.committed, said)
        if not lined_up and self.rounds:
            logger.info("Streaming: a phrase didn't line up with the one before; "
                        "the release will transcribe the whole recording")
            self.trusted = False
            return
        self.committed = joined
        self.cut_s = end_s
        self.rounds += 1

    def release_span(self, total_s: float):
        """The tail to transcribe at release (a (start, end) pair), or None
        to transcribe the whole recording as before.

        None means streaming saved nothing: too short, nothing committed, or
        a seam that couldn't be vouched for."""
        if not self.trusted or not self.committed.strip():
            return None
        if total_s < self.min_stream_s:
            return None
        if float(total_s) <= self.cut_s:
            return None      # everything said was already heard
        return max(0.0, self.cut_s - OVERLAP_S), float(total_s)

    def result(self, tail_text: str):
        """The full text from the committed phrases and *tail_text*, or None
        when the seam doesn't line up and the caller must redo it whole.

        The caller passes the tail transcribed from the span release_span()
        gave it, so the words at the seam are in both halves."""
        if not self.trusted:
            return None
        said = (tail_text or "").strip()
        if not said:
            # A trailing pause with no words in the tail: the committed text
            # is the whole answer.
            return self.committed or None
        joined, lined_up = splice(self.committed, said)
        if not lined_up:
            logger.info("Streaming: the release text didn't line up; transcribing whole")
            return None
        return joined or None

    def snapshot(self):
        """A frozen copy, for the release to read while a commit still in
        flight writes to this one. Its own state never changes again."""
        frozen = Streamer(self.min_stream_s)
        frozen.committed = self.committed
        frozen.cut_s = self.cut_s
        frozen.rounds = self.rounds
        frozen.trusted = self.trusted
        return frozen
