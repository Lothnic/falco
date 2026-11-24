"""Clean Roman Hinglish and English sentences for synthetic dictation pairs.

Synthetic-only training needs a lot of clean targets. These templates mix
Hindi grammar with English technical/business nouns, which is the shape of
Hinglish dictation. They are deliberately plain; the corruption layer makes
the raw side look like ASR output.
"""

HINGLISH_NOUNS = (
    "meeting", "deploy", "server", "database", "pull request", "code", "bug",
    "release", "calendar", "email", "laptop", "project", "dashboard", "API",
    "test", "build", "branch", "merge", "review", "demo", "ticket", "sprint",
    "deadline", "client", "invoice", "report", "spreadsheet", "phone",
    "message", "photo", "video", "file", "folder", "link", "document",
    "password", "login", "backup", "update", "error", "log", "config",
    "script", "model", "prompt", "token", "cache", "queue", "job", "worker",
    "endpoint", "response", "request", "migration", "schema", "table",
    "column", "query", "index", "latency", "memory", "disk", "CPU", "GPU",
    "network", "battery", "charger", "call", "note", "task", "list", "plan",
    "idea", "question", "answer", "problem", "solution", "office",
)

CONTAINER_NOUNS = (
    "folder", "document", "dashboard", "project", "branch", "queue",
    "calendar", "report", "spreadsheet", "laptop",
)

HINDI_VERBS = (
    "check karna", "update karna", "fix karna", "dekhna", "bhejna", "banana",
    "test karna", "merge karna", "deploy karna", "review karna", "book karna",
    "cancel karna", "plan karna", "samajhna", "bolna", "likhna", "padhna",
    "kholna", "band karna", "le jaana", "le aana", "yaad rakhna",
)

ENGLISH_VERBS = (
    "check", "update", "fix", "review", "merge", "deploy", "test", "send",
    "open", "close", "book", "cancel", "plan", "read", "write", "bring",
    "take", "share", "finish", "start",
)

DAYS = ("aaj", "kal", "parson", "Monday", "Friday", "weekend")
HINGLISH_TIMES = ("subah", "shaam", "raat", "thodi der mein", "3 baje",
                  "5 baje", "6 baje", "lunch ke baad")
ENGLISH_TIMES = ("today", "tomorrow", "this evening", "tonight", "at 3",
                 "at 5", "at 6 PM", "in a bit", "after lunch")
ENGLISH_DEADLINES = ("3 PM", "tomorrow", "Friday", "after lunch")

NUMBERS = ("ek", "do", "teen", "char", "paanch", "chhe", "saat", "aath",
           "nau", "das", "20", "25", "50", "100")
ENGLISH_NUMBERS = ("two", "three", "five", "ten", "20", "25", "50", "100")

NAMES = ("Rahul", "Priya", "Amit", "Neha", "Arjun", "Sneha", "Vikram",
         "Anjali", "Rohan", "Kavya", "Sanjay", "Pooja")

HINGLISH_TEMPLATES = (
    "Mujhe {noun} {time} tak {hindi_verb} hai.",
    "{day} {time} {noun} {hindi_verb} hai.",
    "Team ko {noun} ke baare mein {hindi_verb} hai.",
    "Please {english_verb} the {noun} {day}.",
    "Main {noun} check kar raha hoon, phir {noun2} update kar dunga.",
    "{day} {noun} ka {noun2} ready chahiye.",
    "{name} ne {noun} {english_verb} kiya, lekin {noun2} abhi baaki hai.",
    "{time} {name} ke saath {noun} {hindi_verb} hai.",
    "{noun} ka {noun2} {time} tak {hindi_verb} hai.",
    "Agar {noun} theek hai toh {noun2} {hindi_verb} hai.",
    "{name} ko {number} {noun} {time} tak chahiye.",
    "Mujhe {noun} aur {noun2} dono ke liye {hindi_verb} hai.",
    "{noun} ke liye {number} log {day} aa rahe hain.",
    "Please {english_verb} {noun2} after the {noun}.",
    "Main {time} {name} ko {noun} ke baare mein message karunga.",
    "{day} ko {noun} {hindi_verb} hai.",
    "{day} tak {noun} ready chahiye.",
    "{day} {time} {noun} check karna hai.",
)

ENGLISH_TEMPLATES = (
    "Please {english_verb} the {noun} {time}.",
    "I will {english_verb} the {noun} and send the {noun2}.",
    "The {noun} is ready, but the {noun2} needs a review.",
    "{name} will {english_verb} the {noun} {time}.",
    "Can you {english_verb} the {noun2} after the {noun}?",
    "We need {number} more {noun} {time}.",
    "The {noun} and the {noun2} are in the {noun3}.",
    "{name} said the {noun} is blocked until {deadline}.",
)

_SLOTS = {
    "noun": HINGLISH_NOUNS,
    "noun2": HINGLISH_NOUNS,
    "noun3": CONTAINER_NOUNS,
    "hindi_verb": HINDI_VERBS,
    "english_verb": ENGLISH_VERBS,
    "day": DAYS,
    "time": HINGLISH_TIMES,
    "deadline": ENGLISH_DEADLINES,
    "name": NAMES,
    "number": NUMBERS,
}


def _pick(rng, seq):
    return rng.choice(seq)


def _different(rng, seq, avoid):
    return _pick(rng, [value for value in seq if value != avoid] or list(seq))


def clean_hinglish(rng):
    """One clean Roman-Hinglish sentence."""
    template = _pick(rng, HINGLISH_TEMPLATES)
    values = {slot: _pick(rng, seq) for slot, seq in _SLOTS.items()}
    values["noun2"] = _different(rng, HINGLISH_NOUNS, values["noun"])
    sentence = template.format(**values)
    return sentence[0].upper() + sentence[1:]


def clean_english(rng):
    """One clean English sentence, so the adapter does not forget English."""
    template = _pick(rng, ENGLISH_TEMPLATES)
    values = {slot: _pick(rng, seq) for slot, seq in _SLOTS.items()}
    values["noun2"] = _different(rng, HINGLISH_NOUNS, values["noun"])
    values["noun3"] = _different(rng, CONTAINER_NOUNS, values["noun3"])
    values["time"] = _pick(rng, ENGLISH_TIMES)
    values["number"] = _pick(rng, ENGLISH_NUMBERS)
    sentence = template.format(**values)
    return sentence[0].upper() + sentence[1:]
