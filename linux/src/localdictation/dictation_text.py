"""What a dictation's words go through before they're typed: the snippets
and Your Words (custom_commands.py), the spoken-command rules, filler words,
numbers as digits, punctuation, plain text for terminals and code editors,
and the AI's self-corrections when they're on."""
import re

from . import custom_commands, focused_window, keyboard_output
from . import live_settings as live
from . import recording_state as rs
from .logger import setup_logger
from .normalize import (
    append_auto_punct,
    normalize_text,
    plain_for_app,
    safe_to_lowercase_first_word,
    swiss_spelling,
)

logger = setup_logger(__name__)


def restore_opening_word(raw: str, refined: str) -> str:
    """Keep a spoken discourse opener when cleanup dropped it.

    Restrict this to unambiguous first words and avoid masking collapsed
    single-word model output. Preserve capitalization when a proper name is
    possible; only lowercase a word observed in lowercase in the transcript.
    """
    source = raw.split()
    output = refined.split()
    if len(source) < 2 or len(output) < 2:
        return refined
    opener = source[0].rstrip(',.').lower()
    if opener not in {'okay', 'ok', 'well', 'and', 'now'}:
        return refined
    first = output[0].strip('.,!?;:\"\'').lower()
    if first == opener or (first in {'ok', 'okay'} and opener in {'ok', 'okay'}):
        return refined
    body = refined.lstrip()
    word = re.match(r'[A-Za-z]+', body)
    if word and word.group().istitle() and re.search(r'\b' + re.escape(word.group().lower()) + r'\b', raw):
        body = body[0].lower() + body[1:]
    return ('Okay' if opener in {'ok', 'okay'} else opener.capitalize()) + ', ' + body


def apply_custom_commands(text: str) -> tuple[str, dict[str, str]]:
    """The user's custom voice commands applied to the transcribed *text*
    (custom_commands.apply), with Your Words."""
    result, protected = custom_commands.apply(text, live.commands, live.words)
    if result != text:
        logger.info(f"Custom commands applied: {live.loggable(text)} -> {live.loggable(result)}")
    return result, protected


def numbers_to_digits(text: str) -> str:
    """*text* with spoken numbers as digits, when that option is on."""
    if not live.numbers_mode:
        return text
    from .spoken_numbers import to_digits
    return to_digits(text, live.numbers_language,
                     small_as_words=live.numbers_mode == "small_as_words")


def _clean_up(text, ai):
    """The cleanup options: the rules first ("um", "the the"), then the AI
    for sentences with a self-correction (unless *ai* is False)."""
    if live.remove_fillers:
        from .cleanup import clean_fillers_and_repeats
        text = clean_fillers_and_repeats(text)
    return text


def _carry_on_sentence(text):
    """*text* carrying on the sentence the last dictation left unfinished
    (it ended on "and", or undo took back its end): its first letter small,
    unless it went to another window, where it's a new sentence (a message
    after "meet me at noon and" in KWrite mustn't begin with a small letter)."""
    focused = focused_window.window_class()
    if (not keyboard_output.not_where_typed(focused) and text[0].isupper()
            and safe_to_lowercase_first_word(text, live.words)):
        text = text[0].lower() + text[1:]
        logger.info("Lowercased first letter for mid-sentence continuation")
    rs.state.continue_mid_sentence = False
    return text


def prepare_text(raw: str, smart_quotes: bool, auto_period: bool, auto_space: bool,
                 app_kind: str = "", ai: bool = True) -> str:
    """Apply voice commands, normalize, handle mid-sentence, add auto-period/space.

    *app_kind* ("terminal", "code" or ""): the focused app wants plain text
    (no closing period, straight quotes; in a terminal, no starting capital
    either).
    *ai* False skips the AI self-corrections: Type at pause asks the AI about
    a phrase together with the one before it instead (type_at_pause.correct_across_pause).

    Returns the final text string ready for injection.
    """
    if app_kind:
        # A shell or a compiler doesn't read “curly” quotes as quotes.
        auto_period = smart_quotes = False
    # Send the unmodified transcript to the model before command placeholders
    # and normalization. Reject empty or implausibly long/short generations.
    if ai and live.ai_corrections and live.ai_engine is not None and raw.strip():
        candidate = live.ai_engine.correct(raw, timeout=max(20.0, len(raw) / 20))
        before = len(raw.split())
        after = len(candidate.split()) if candidate else 0
        if candidate and after <= 2 * before and (before <= 8 or after >= 0.4 * before):
            raw = restore_opening_word(raw, candidate)
        else:
            logger.info("Refiner unavailable or output failed length guard; using transcript")
    # Apply custom voice commands (phrase → replacement)
    # Quoted replacements come back as placeholder tokens in `protected`
    processed, protected = apply_custom_commands(raw)
    # Your Words, first pass: before tidying, a hyphen inside a word can only
    # have come from the engine ("Tux-Talk"), so it may join here.
    if live.words:
        from .custom_words import fix_spelling
        processed = fix_spelling(processed, live.words)

    # Normalize text (capitalization, punctuation, etc.). auto_period is passed
    # through because this pass otherwise ends every line with a full stop of
    # its own, and append_auto_punct below would never get to decide.
    text = normalize_text(
        processed if smart_quotes else processed.replace("\u201c","\"").replace("\u201d","\""),
        auto_period=auto_period,
    )
    # A lone "open quote" or "close quote" becomes a curly quote inside
    # normalize_text, so the preference is applied to its output as well.
    if not smart_quotes:
        text = text.replace("\u201c", "\"").replace("\u201d", "\"")

    # Optional cleanup, while quoted custom-command replacements are still
    # placeholders, so a literal replacement is never "cleaned". Rules first
    # ("um", "the the"), then the AI for sentences with a self-correction.
    text = _clean_up(text, ai)

    # Your Words, second pass: "tux talk" -> "TuxTalk" and iPhone's capitals
    # back after a sentence start made it IPhone. After snippets, so a snippet
    # whose phrase contains the split-up word still matches; while quoted
    # snippets are still placeholders, so a literal one is never touched; and
    # with no hyphen joins, since by now a hyphen means the user said "dash".
    if live.words:
        from .custom_words import fix_spelling
        text = fix_spelling(text, live.words, hyphens=False)

    # Spoken numbers as digits. Before the quoted snippets come back, so a
    # literal snippet is typed exactly as written.
    text = numbers_to_digits(text)

    # Restore quoted (literal) custom command replacements before any further
    # processing so that auto-period/space checks see the real final text.
    text = custom_commands.restore_protected(text, protected)

    # Swiss Standard German writes ss where the engines write ß. Last, so it
    # also covers snippets, Your Words and the AI's corrections.
    if live.swiss_spelling:
        text = swiss_spelling(text)

    if rs.state.continue_mid_sentence and text:
        text = _carry_on_sentence(text)

    # Auto-period and auto-space. When the utterance ends with a line-break
    # command, the period lands BEFORE the break and no trailing space is
    # added, so "hello new line" leaves no orphan ". " on the next line.
    text = append_auto_punct(text, auto_period, auto_space)
    if app_kind:
        text = plain_for_app(text, app_kind)
    logger.info(f"Normalized text: {live.loggable(text)}")
    return text
