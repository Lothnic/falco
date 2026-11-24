"""Build synthetic raw -> clean Hinglish (and English replay) dictation pairs.

No external corpus and no personal text: clean targets come from the
templates in lexicon.py, and the raw side is corrupted the way an ASR plus a
real speaker sounds -- fillers, stutters, self-corrections, Roman/Devanagari
mixing and common recognition confusions.

    python ml/research/hinglish_v0/build_pairs.py --count 4000
"""
import argparse
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from config import DATA, SEED, SYSTEM
from lexicon import (
    DAYS,
    ENGLISH_DEADLINES,
    ENGLISH_TIMES,
    HINGLISH_TIMES,
    NUMBERS,
    clean_english,
    clean_hinglish,
)

FILLERS = ("um", "uh", "matlab", "yaani", "like", "arre", "accha")
CUES_HI = ("no wait", "arre nahi", "I mean", "matlab", "sorry")
CUES_EN = ("no wait", "I mean", "sorry", "actually")

# Roman Hindi words that Whisper sometimes writes in Devanagari. The target
# stays Roman, so the adapter learns to restore the Hinglish script.
DEVANAGARI = {
    "mujhe": "मुझे", "hai": "है", "hain": "हैं", "kal": "कल", "parson": "परसों",
    "aaj": "आज", "karna": "करना", "kar": "कर", "raha": "रहा", "hoon": "हूँ",
    "ke": "के", "ka": "का", "ki": "की", "ko": "को", "se": "से", "mein": "में",
    "par": "पर", "tak": "तक", "nahi": "नहीं", "haan": "हाँ", "aur": "और",
    "lekin": "लेकिन", "phir": "फिर", "abhi": "अभी", "bahut": "बहुत",
    "thoda": "थोड़ा", "jaldi": "जल्दी", "baad": "बाद", "pehle": "पहले",
    "saath": "साथ", "liye": "लिए", "chahiye": "चाहिए", "kya": "क्या",
}

CONFUSIONS = (
    ("b", "v"), ("v", "b"), ("sh", "s"), ("s", "sh"),
    ("j", "z"), ("z", "j"), ("ph", "f"), ("f", "ph"),
)


def _word(value):
    return re.compile(rf"(?<!\w){re.escape(value)}(?!\w)", re.IGNORECASE)


def insert_filler(text, rng):
    words = text.split()
    if len(words) < 2:
        return text
    filler = rng.choice(FILLERS)
    position = rng.randrange(1, len(words))
    words.insert(position, filler + ",")
    return " ".join(words)


def stutter(text, rng):
    words = text.split()
    if not words:
        return text
    words.insert(1, words[0].lower())
    return " ".join(words)


def self_correct(text, rng, language):
    groups = ((DAYS, HINGLISH_TIMES) if language == "hi"
              else (ENGLISH_DEADLINES, ENGLISH_TIMES))
    for pool in (*groups, NUMBERS):
        found = [value for value in pool if _word(value).search(text)]
        if not found:
            continue
        value = rng.choice(found)
        candidates = [candidate for candidate in pool if candidate != value
                      and candidate.casefold() not in value.casefold()
                      and value.casefold() not in candidate.casefold()]
        if not candidates:
            continue
        wrong = rng.choice(candidates)
        cue = rng.choice(CUES_HI if language == "hi" else CUES_EN)
        return _word(value).sub(f"{wrong} {cue} {value}", text, count=1)
    return text


def script_mix(text, rng):
    present = [word for word in DEVANAGARI if _word(word).search(text)]
    if not present:
        return text
    chosen = rng.sample(present, k=min(len(present), rng.randint(1, 3)))
    for word in chosen:
        text = _word(word).sub(DEVANAGARI[word], text, count=1)
    return text


def asr_noise(text, rng):
    # Lower-case a canonical English term (API -> api, Friday -> friday).
    canonical = [word for word in re.findall(r"\b[A-Z][A-Za-z0-9.]*\b", text)
                 if word.lower() in text.lower()]
    if canonical and rng.random() < 0.5:
        term = rng.choice(canonical)
        text = _word(term).sub(term.lower(), text, count=1)
    # One b/v, sh/s, j/z or ph/f confusion.
    words = re.findall(r"[A-Za-z]+", text)
    candidates = [word for word in words
                  if any(old in word.lower() for old, _ in CONFUSIONS)]
    if candidates:
        word = rng.choice(candidates)
        for old, new in CONFUSIONS:
            if old in word.lower():
                broken = re.sub(old, new, word, count=1, flags=re.IGNORECASE)
                text = _word(word).sub(broken, text, count=1)
                break
    # A dropped word, or the final period missing. Content words are never
    # dropped: the target cannot be recovered from audio that never carried
    # them, and a refiner must not be trained to invent text.
    if rng.random() < 0.5:
        text = text.rstrip(".")
    return text


def break_case_and_punctuation(text, rng):
    if not text:
        return text
    text = text[0].lower() + text[1:]
    if rng.random() < 0.5:
        text = text.rstrip(".")
    return text


def corrupt(clean, rng, language):
    """A raw transcript for *clean*, with at least one corruption.

    Self-corrections go last so their wrong value and cue survive the other
    noise: a correction that lost the corrected word would be unrecoverable.
    """
    raw = clean
    if rng.random() < 0.25:
        raw = stutter(raw, rng)
    if rng.random() < 0.75:
        raw = insert_filler(raw, rng)
    if language == "hi" and rng.random() < 0.55:
        raw = script_mix(raw, rng)
    if rng.random() < 0.55:
        raw = asr_noise(raw, rng)
    if rng.random() < 0.50:
        raw = break_case_and_punctuation(raw, rng)
    if rng.random() < 0.30:
        raw = self_correct(raw, rng, language)
    if raw == clean:
        raw = insert_filler(raw, rng)
    return raw


def build(count, seed=SEED, hinglish_fraction=0.75):
    """*count* unique pairs, shuffled, with the messages the trainer uses."""
    rng = random.Random(seed)
    rows, seen = [], set()
    attempts = 0
    while len(rows) < count and attempts < count * 50:
        attempts += 1
        hinglish = rng.random() < hinglish_fraction
        clean = clean_hinglish(rng) if hinglish else clean_english(rng)
        if clean in seen:
            continue
        seen.add(clean)
        language = "hi" if hinglish else "en"
        raw = corrupt(clean, rng, language)
        rows.append({
            "id": f"{language}-{len(rows):06d}",
            "language": language,
            "raw": raw,
            "clean": clean,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": raw},
                {"role": "assistant", "content": clean},
            ],
        })
    rng.shuffle(rows)
    return rows


def write(rows, out_dir=DATA):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dev_count = max(1, round(len(rows) * 0.1)) if rows else 0
    dev, train = rows[:dev_count], rows[dev_count:]
    for name, part in (("all.jsonl", rows), ("train.jsonl", train), ("dev.jsonl", dev)):
        with (out_dir / name).open("w", encoding="utf-8") as handle:
            for row in part:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return out_dir, len(train), len(dev)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--hinglish-fraction", type=float, default=0.75)
    parser.add_argument("--out-dir", type=Path, default=DATA)
    args = parser.parse_args()

    rows = build(args.count, args.seed, args.hinglish_fraction)
    out_dir, train_count, dev_count = write(rows, args.out_dir)
    print(f"wrote {len(rows)} pairs to {out_dir} (train {train_count}, dev {dev_count})")
    for row in rows[:3]:
        print(f"\n[{row['language']}] raw:   {row['raw']}\n         clean: {row['clean']}")


if __name__ == "__main__":
    main()
