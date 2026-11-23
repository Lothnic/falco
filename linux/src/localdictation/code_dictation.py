"""Developer mode: the words of code, not prose.

Spoken file names ("main dot py"), identifiers named by casing ("camel case
get user id"), a few unambiguous symbols ("backtick", "open paren") and
common developer spellings ("github") become code. Applied only when
developer mode says so: in a code editor or terminal, or everywhere when the
user chooses Always. Code dictation skips the prose refiner so it cannot
rewrite code.
"""
import re

_EXTENSIONS = frozenset({
    "py", "pyi", "js", "jsx", "ts", "tsx", "mjs", "cjs", "json", "jsonc",
    "md", "mdx", "txt", "yaml", "yml", "toml", "ini", "cfg", "conf", "sh",
    "bash", "zsh", "fish", "rs", "go", "java", "kt", "kts", "c", "h", "cc",
    "cpp", "cxx", "hpp", "cs", "rb", "php", "swift", "m", "mm", "sql",
    "html", "htm", "css", "scss", "sass", "less", "xml", "svg", "vue",
    "svelte", "astro", "graphql", "gql", "proto", "lua", "r", "pl", "ex",
    "exs", "erl", "hs", "clj", "scala", "dart", "zig", "nim", "v", "asm",
    "s", "ipynb", "csv", "tsv", "parquet", "lock", "env",
})
_EXT = "|".join(sorted(_EXTENSIONS, key=len, reverse=True))

_JOINS = {"underscore": "_", "dash": "-", "hyphen": "-"}

# A spoken file name: one word, or words joined by "underscore"/"dash",
# followed by "dot" and a known extension. Requiring the extension is what
# keeps "the dot product" out.
_FILENAME = re.compile(
    rf"\b(?P<stem>[A-Za-z0-9]+(?:\s+(?:underscore|dash|hyphen)\s+[A-Za-z0-9]+)*)"
    rf"\s+dot\s+(?P<ext>{_EXT})\b", re.IGNORECASE)

# "src slash components slash button.tsx": at least one spoken separator, and
# the result must look like a path (a dot in a part or two separators), so
# "this slash that" stays words.
_PATH = re.compile(
    r"\b[A-Za-z0-9_.-]+(?:\s+(?:slash|backslash)\s+[A-Za-z0-9_.-]+){1,}\b",
    re.IGNORECASE)

_CASING = re.compile(
    r"\b(?P<kind>camel|snake|kebab|pascal|constant|upper|lower)\s+case[,:]?\s+"
    r"(?P<words>[A-Za-z0-9]+(?:\s+[A-Za-z0-9]+){0,8})", re.IGNORECASE)

_STOPS = frozenset({"and", "then", "for", "to", "in", "with", "on", "at",
                    "from", "please", "the", "a", "an"})

_SYMBOLS = {
    "open paren": "(", "close paren": ")",
    "open parenthesis": "(", "close parenthesis": ")",
    "open brace": "{", "close brace": "}",
    "open bracket": "[", "close bracket": "]",
    "backtick": "`", "tilde": "~", "semicolon": ";",
    "ampersand": "&", "at sign": "@", "fat arrow": "=>",
    "forward slash": "/", "backslash": "\\", "double colon": "::",
}
_SYMBOL_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(k) for k in sorted(_SYMBOLS, key=len, reverse=True))
    + r")\b", re.IGNORECASE)

# Conservative: only spellings that are developer names in this mode. Common
# English words (react, rust, go, swift, python, pandas) stay as written.
_CANONICAL = {
    "github": "GitHub", "git hub": "GitHub", "github actions": "GitHub Actions",
    "gitlab": "GitLab", "javascript": "JavaScript", "java script": "JavaScript",
    "typescript": "TypeScript", "type script": "TypeScript",
    "nodejs": "Node.js", "node js": "Node.js", "node.js": "Node.js",
    "npm": "npm", "pnpm": "pnpm", "vite": "Vite",
    "nextjs": "Next.js", "next js": "Next.js", "next.js": "Next.js",
    "docker": "Docker", "docker compose": "Docker Compose",
    "kubernetes": "Kubernetes", "kubectl": "kubectl", "kube control": "kubectl",
    "postgres": "Postgres", "post gres": "Postgres", "postgresql": "PostgreSQL",
    "redis": "Redis", "mongodb": "MongoDB", "mongo db": "MongoDB",
    "supabase": "Supabase", "firebase": "Firebase",
    "vercel": "Vercel", "netlify": "Netlify", "cloudflare": "Cloudflare",
    "fastapi": "FastAPI", "django": "Django", "pytorch": "PyTorch",
    "tensorflow": "TensorFlow", "numpy": "NumPy", "graphql": "GraphQL",
    "json": "JSON", "yaml": "YAML", "toml": "TOML",
    "linux": "Linux", "ubuntu": "Ubuntu", "debian": "Debian",
    "wayland": "Wayland", "x11": "X11", "gnome": "GNOME", "kde": "KDE",
    "systemd": "systemd", "pipewire": "PipeWire", "pipe wire": "PipeWire",
    "pulseaudio": "PulseAudio", "pulse audio": "PulseAudio",
    "ffmpeg": "FFmpeg", "falco": "Falco", "parakeet": "Parakeet",
    "phonon": "Phonon", "t3 code": "T3 Code", "t3code": "T3 Code",
    "vs code": "VS Code", "vscode": "VS Code", "neovim": "Neovim",
    "vim": "Vim", "emacs": "Emacs",
}
_CANONICAL_RE = re.compile(
    r"(?<![\w.])(?:" + "|".join(
        re.escape(k) for k in sorted(_CANONICAL, key=len, reverse=True))
    + r")(?!\w)", re.IGNORECASE)


def _filename(match):
    stem = re.sub(
        r"\s+(underscore|dash|hyphen)\s+",
        lambda j: _JOINS[j.group(1).casefold()], match.group("stem"), flags=re.IGNORECASE)
    return f"{stem}.{match.group('ext').lower()}"


def _path(match):
    text = match.group(0)
    folded = text.casefold()
    if ("." not in text and folded.count(" slash ") < 2
            and folded.count(" backslash ") < 2):
        return text
    return re.sub(r"\s+(slash|backslash)\s+",
                  lambda m: "/" if m.group(1).casefold() == "slash" else "\\",
                  text, flags=re.IGNORECASE)


def _term(word):
    """*word* in its canonical developer spelling when it has one."""
    return _CANONICAL.get(word.casefold(), word)


def _identifier(kind, words):
    if kind == "camel":
        first = _term(words[0])
        rest = [_term(word) for word in words[1:]]
        return (first[:1].lower() + first[1:]
                + "".join(word[:1].upper() + word[1:] for word in rest))
    if kind == "pascal":
        titled = [_term(word) for word in words]
        return "".join(word[:1].upper() + word[1:] for word in titled)
    if kind == "snake":
        return "_".join(_term(word).lower() for word in words)
    if kind == "kebab":
        return "-".join(_term(word).lower() for word in words)
    if kind == "constant":
        return "_".join(_term(word).upper() for word in words)
    if kind == "upper":
        return " ".join(_term(word).upper() for word in words)
    return " ".join(_term(word).lower() for word in words)


def _casing(match):
    words = match.group("words").split()
    cut = len(words)
    for index, word in enumerate(words):
        if word.casefold() in _STOPS:
            cut = index
            break
    if not cut:
        return match.group(0)
    body, tail = words[:cut], words[cut:]
    result = _identifier(match.group("kind").casefold(), body)
    return result + ((" " + " ".join(tail)) if tail else "")


def _symbol(match):
    return _SYMBOLS[match.group(0).casefold()]


def _canonical(match):
    return _CANONICAL[match.group(0).casefold()]


def _tidy_symbols(text):
    for opener, closer in (("(", ")"), ("{", "}"), ("[", "]")):
        text = text.replace(f"{opener} ", opener).replace(f" {closer}", closer)
    # Trim only the spaces inside a pair of backticks: "use ` npm `" keeps the
    # space before the opening one and loses the ones inside.
    return re.sub(r"`[ \t]*(.+?)[ \t]*`", lambda m: f"`{m.group(1)}`", text)


def has_code(text):
    """True when *text* has a spoken filename, path, casing command or symbol.

    Used to decide whether the prose refiner may run: plain prose in a code
    app still gets cleaned up, while a transcript with code in it is kept
    exact."""
    if not text:
        return False
    if _FILENAME.search(text) or _CASING.search(text) or _SYMBOL_RE.search(text):
        return True
    for match in _PATH.finditer(text):
        value = match.group(0)
        folded = value.casefold()
        if ("." in value or folded.count(" slash ") >= 2
                or folded.count(" backslash ") >= 2):
            return True
    return False


def apply(text):
    """*text* with spoken file names, casing, symbols and dev names as code."""
    if not text:
        return text
    text = _FILENAME.sub(_filename, text)
    text = _PATH.sub(_path, text)
    text = _CASING.sub(_casing, text)
    text = _SYMBOL_RE.sub(_symbol, text)
    text = _tidy_symbols(text)
    return _CANONICAL_RE.sub(_canonical, text)
