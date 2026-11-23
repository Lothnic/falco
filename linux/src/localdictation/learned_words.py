"""A dictionary that learns names from the refiner's own corrections.

When the refiner changes only the spelling or capitals of a word in the
middle of a dictation ("github" -> "GitHub", "tux talk" -> "TuxTalk"), that
is a proper noun the speech model doesn't know. After seeing the same fix
twice, the word joins Your Words, so the engine is steered towards it and
the spelling pass gets it right before the refiner has to.

Only case/hyphenation fixes are learned, never a rewrite ("gonna" -> "going
to"), and never a sentence's first word, whose capital is grammar rather
than a name. The user can turn it off or clear what was learned in
Preferences > Words; custom_words.txt stays the user's own list.
"""
import difflib
import json
import os
import re
import threading

from . import config
from .logger import setup_logger

logger = setup_logger(__name__)

FILE_NAME = "learned_words.json"
MIN_SEEN = 2
MIN_LETTERS = 3

_TOKEN = re.compile(r"\w+(?:['’\-]\w+)*")
_STRIP = re.compile(r"[\s'’\-]")
_lock = threading.Lock()


def path():
    """learned_words.json, beside custom_words.txt and custom_commands.toml."""
    return os.path.join(os.path.dirname(config.CUSTOM_COMMANDS_PATH), FILE_NAME)


def _letters(word):
    return _STRIP.sub("", word).casefold()


def _upper_score(word):
    return sum(1 for char in word if char.isupper())


def _load():
    try:
        with open(path(), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {key: value for key, value in data.items()
            if isinstance(value, dict) and isinstance(value.get("word"), str)
            and isinstance(value.get("count"), int)}


def _save(data):
    try:
        config.write_text_atomic(path(), json.dumps(
            data, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    except OSError as e:
        logger.info(f"Could not save learned words: {e}")


def _sentence_start(text, position):
    before = text[:position].rstrip()
    return not before or before[-1] in ".?!"


def _candidate(raw_text, raw_tokens, ref_block, start):
    """The proper noun *ref_block* spells, or None when it isn't one."""
    if len(ref_block) != 1:
        return None
    word = ref_block[0]
    if _sentence_start(raw_text, start):
        return None
    if len(_letters(word)) < MIN_LETTERS or not any(char.isupper() for char in word):
        return None
    joined_raw = "".join(_letters(token.group()) for token in raw_tokens)
    if joined_raw != _letters(word):
        return None
    return word


def observe(raw, refined):
    """Learn the proper nouns the refiner fixed in this dictation.

    Returns the words that just reached the threshold, so the caller can add
    them to the running word list at once."""
    from . import live_settings as live
    if not live.learn_words or not raw or not refined:
        return []
    raw_matches = list(_TOKEN.finditer(raw))
    ref_matches = list(_TOKEN.finditer(refined))
    raw_words = [match.group() for match in raw_matches]
    ref_words = [match.group() for match in ref_matches]
    if not raw_words or not ref_words:
        return []

    with _lock:
        data = _load()
        active_before = {key for key, value in data.items()
                         if value["count"] >= MIN_SEEN}
        changed = False
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
                None, raw_words, ref_words).get_opcodes():
            if tag != "replace" or i1 >= i2 or j1 >= j2:
                continue
            word = _candidate(raw, raw_matches[i1:i2], ref_words[j1:j2],
                              raw_matches[i1].start())
            if word is None:
                continue
            key = word.casefold()
            entry = data.get(key)
            if entry is None:
                data[key] = {"word": word, "count": 1}
            else:
                entry["count"] += 1
                if _upper_score(word) > _upper_score(entry["word"]):
                    entry["word"] = word
            changed = True
        if not changed:
            return []
        _save(data)
        newly = [value["word"] for key, value in data.items()
                 if value["count"] >= MIN_SEEN and key not in active_before]
        if newly:
            logger.info("Learned from the refiner: " + ", ".join(newly))
        return newly


def all_entries():
    """(word, count) for everything learned so far, alphabetically."""
    with _lock:
        data = _load()
    return sorted(((value["word"], value["count"]) for value in data.values()),
                  key=lambda pair: pair[0].casefold())


def words():
    """The learned words that have been seen enough to use."""
    return [word for word, count in all_entries() if count >= MIN_SEEN]


def merge(user_words):
    """*user_words* with the learned ones that aren't already there."""
    seen = {word.casefold() for word in user_words}
    extra = [word for word in words() if word.casefold() not in seen]
    return list(user_words) + extra


def clear():
    """Forget everything learned; the user's own words are untouched."""
    with _lock:
        _save({})
    logger.info("Cleared the words learned from the refiner")
