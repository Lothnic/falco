"""The local AI's files: llama.cpp's prebuilt llama-server (the Vulkan build,
which also carries every CPU variant: it uses the graphics card when there
is one and the processor otherwise) and the refiner model chosen for the
dictation language. Phonon's 1.7B English refiner is the default; a 1B
Gemma 3 (or Llama 3.2 1B) handles Hindi and other languages at a smaller
footprint. What they are, where they live, and their downloads, made only
when the user turns on a feature that needs them, so the package does not
grow. ai_server runs them.
"""
import os

from . import engine_process
from .logger import setup_logger

logger = setup_logger(__name__)

LLAMA_TAG = "b12210"
LLAMA_ASSET = f"llama-{LLAMA_TAG}-bin-ubuntu-vulkan-x64.tar.gz"
LLAMA_URL = f"https://github.com/ggml-org/llama.cpp/releases/download/{LLAMA_TAG}/{LLAMA_ASSET}"
# From GitHub's own digest of the release asset; the download is refused if
# it does not match, so a tampered or truncated engine is never run.
LLAMA_SHA256 = "85aa8b17a081b343a57398ca5fb112b6713a47114993a8b677c5aa1b2106d232"
LLAMA_SIZE_MB = 30

# The refiner models. The 1B entries are smaller than Phonon's 1.7B and
# support Hindi; "auto" picks by the dictation language.
REFINER_MODELS = {
    "phonon": {
        "label": "Phonon English (1.7B)",
        "repo": "Infatoshi/phonon-refiner-1.7b",
        "file": "phonon-refiner-1.7b-Q4_K_S-e4.gguf",
        "size_mb": 989,
        "license": "LFM Open License",
        "hindi": False,
    },
    "gemma-3-1b": {
        "label": "Gemma 3 1B",
        "repo": "unsloth/gemma-3-1b-it-GGUF",
        "file": "gemma-3-1b-it-Q4_K_M.gguf",
        "size_mb": 810,
        "license": "Gemma Terms of Use",
        "hindi": True,
    },
    "llama-3.2-1b": {
        "label": "Llama 3.2 1B",
        "repo": "unsloth/Llama-3.2-1B-Instruct-GGUF",
        "file": "Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        "size_mb": 810,
        "license": "Llama 3.2 Community License",
        "hindi": True,
    },
}
DEFAULT_MODEL = "phonon"
HINDI_MODEL = "gemma-3-1b"

# Kept for the code that names the default model (uninstall, Help).
MODEL_REPO = REFINER_MODELS[DEFAULT_MODEL]["repo"]
MODEL_FILE = REFINER_MODELS[DEFAULT_MODEL]["file"]
MODEL_SIZE_MB = REFINER_MODELS[DEFAULT_MODEL]["size_mb"]
DRAFTER_FILE = "phonon-refiner-1.7b-dflash2-drafter.gguf"
DRAFTER_SIZE_TEXT = "215 MB"


def _size_text(mb):
    """*mb* megabytes as people read a download's size: "30 MB", "1.1 GB"."""
    return f"{mb / 1000:.1f} GB" if mb >= 1000 else f"{mb} MB"


LLAMA_SIZE_TEXT = _size_text(LLAMA_SIZE_MB)
MODEL_SIZE_TEXT = _size_text(MODEL_SIZE_MB)
# What turning the AI on downloads, its engine included: the size every
# window and Help give.
DOWNLOAD_SIZE_TEXT = _size_text(MODEL_SIZE_MB + LLAMA_SIZE_MB)


def _language_code(cfg):
    try:
        from .recommend import effective_language
        code = str(effective_language(cfg))
    except Exception:
        code = getattr(cfg, "dictation_language", "") or ""
    return code.casefold().split("-")[0].split("_")[0]


def selected_model(cfg=None):
    """The model to run: an explicit choice, or by the dictation language.

    "auto" keeps Phonon for English and uses the 1B Hindi model when the
    language is Hindi; the user can also name a model outright."""
    if cfg is None:
        from .config import load_config
        cfg = load_config()
    choice = getattr(cfg, "refiner_model", "auto")
    if choice in REFINER_MODELS:
        return choice
    return HINDI_MODEL if _language_code(cfg) == "hi" else DEFAULT_MODEL


def model_spec(model_id=None):
    return REFINER_MODELS[model_id or selected_model()]


def model_size_text(model_id=None):
    return _size_text(model_spec(model_id)["size_mb"])


def download_size_text(model_id=None):
    return _size_text(model_spec(model_id)["size_mb"] + LLAMA_SIZE_MB)


# The folder llama.cpp's archive unpacks to, in _engine_dir().
_SERVER_FOLDER = f"llama-{LLAMA_TAG}"


def _engine_dir():
    from .config import get_data_dir
    return os.path.join(get_data_dir(), "ai-engine", LLAMA_TAG)


def server_binary():
    """Where llama-server is once downloaded."""
    return os.path.join(_engine_dir(), _SERVER_FOLDER, "llama-server")


def model_path(model_id=None):
    """Local path of the selected model, or None."""
    from .download_utils import cached_hub_file
    spec = model_spec(model_id)
    return cached_hub_file(spec["repo"], spec["file"])


def is_installed(model_id=None) -> bool:
    """Engine and the selected model are both downloaded. Cheap: file checks."""
    return os.access(server_binary(), os.X_OK) and model_path(model_id) is not None


def drafter_path(model_id=None):
    """The checked, pinned Phonon drafter, or None; other models have no match."""
    if (model_id or selected_model()) != "phonon":
        return None
    from .download_utils import cached_hub_file
    return cached_hub_file(MODEL_REPO, DRAFTER_FILE)


def make_drafter_download_func():
    """Fetch only the optional drafter, using the target's revision and checksums."""
    from .model_helper import make_model_download_func as _hf_download
    return _hf_download("ai-drafter", repo_id=MODEL_REPO, only_files=(DRAFTER_FILE,))


def make_engine_download_func():
    """DownloadTask function: fetch, verify and unpack the llama.cpp engine."""
    def download(progress_callback, cancel_event):
        """Fetch, check and unpack llama.cpp's server into the engine folder,
        reporting progress; True once it's there. Another download finishing
        first is fine."""
        from .download_utils import (download_area, download_file, install_turn,
                                     recover_cut_off_swaps, replace_folder,
                                     restore_cut_off_swap, unpack_tar)
        engine_dir = _engine_dir()
        recover_cut_off_swaps(engine_dir, (_SERVER_FOLDER,), "ai-engine", "the AI engine")
        if os.access(server_binary(), os.X_OK):
            progress_callback("Already downloaded", 100)
            return True

        def hook(done, total):
            if total:
                progress_callback("Downloading AI engine...", min(95, int(done * 95 / total)))

        # Inside engine_dir: remove_other_versions clears every other folder
        # beside it, which would take a download under way with it.
        with download_area(engine_dir, LLAMA_TAG, old_names=(LLAMA_ASSET,)) as (archive, folder):
            if not download_file(LLAMA_URL, archive, timeout=60, cancel_event=cancel_event,
                                 progress_hook=hook, expected_sha256=LLAMA_SHA256,
                                 report=progress_callback):
                return False
            try:
                progress_callback("Unpacking...", 97)
                unpack_tar(archive, folder)
                with install_turn("ai-engine", "the AI engine"):
                    # A complete engine at every moment: removed first, a
                    # kill before the move left none.
                    for name in os.listdir(folder):
                        restore_cut_off_swap(os.path.join(engine_dir, name),
                                             os.path.join(engine_dir, f".{name}.old"))
                    if not os.access(server_binary(), os.X_OK):    # or another download did it
                        for name in os.listdir(folder):
                            replace_folder(os.path.join(folder, name),
                                           os.path.join(engine_dir, name),
                                           os.path.join(engine_dir, f".{name}.old"))
                    engine_process.remove_other_versions(os.path.dirname(engine_dir), LLAMA_TAG)
            except Exception as e:
                logger.error(f"Could not unpack the AI engine: {e}")
                progress_callback("Could not unpack the download", 0)
                return False
        progress_callback("Done", 100)
        return True
    return download


def make_model_download_func(model_id=None):
    """DownloadTask function: fetch the selected model into the HF cache."""
    from .model_helper import make_model_download_func as _hf_download
    spec = model_spec(model_id)
    return _hf_download("ai-cleanup", repo_id=spec["repo"], only_files=(spec["file"],))
