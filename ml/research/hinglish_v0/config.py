"""Hinglish refiner v0: continue Phonon's LFM3-1.7B refiner with QLoRA.

The base is the shipped Phonon refiner itself (Infatoshi/phonon-refiner-1.7b,
LFM3-1.7B, Hindi among its 16 languages), so the prompt, chat template, GGUF
pipeline and app integration stay the same. Only the adapter is new.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

# Full bf16 weights, not just the GGUF: load in 4-bit and train a LoRA on top.
BASE_MODEL = "Infatoshi/phonon-refiner-1.7b"

SEED = 20261124

# The prompt the refiner was trained on, plus the two lines a Hinglish
# adapter needs. Keep the app's _correction_messages() in this exact shape
# when the adapter is wired into REFINER_MODELS.
SYSTEM = (
    "Rewrite the raw dictation transcript into the exact text the speaker intended. "
    "Fix recognition errors and technical terms, keep the speaker's wording and casing style, "
    "do not add or drop content. The transcript may be in English, Hindi, Hinglish or another "
    "language: keep its language and script exactly, and never translate it. Hinglish is "
    "written in Roman letters; do not convert it to Devanagari.\n"
    "Writing mode: minimal (notes and documents)."
)

WRITING_MODE = "minimal"
MAX_SEQ_LEN = 1024
