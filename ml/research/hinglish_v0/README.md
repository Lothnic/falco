# Hinglish refiner v0

Continue **Phonon's own refiner** with a small Hinglish adapter instead of
training a new base. `Infatoshi/phonon-refiner-1.7b` is the full LFM3-1.7B
fine-tune (`Lfm3ForCausalLM`, bf16 weights in the HF repo), and LFM3 lists
Hindi among its 16 languages. That keeps the prompt, chat template, GGUF
pipeline and app integration exactly as they are.

This directory is the offline training/eval scaffold. It is not run by the
app or CI.

## Why Phonon rather than Gemma

- The HF repo has the full bf16 weights, not only the shipped Q4 GGUF, so
  QLoRA can continue from the exact model users run.
- Same prompt (`_correction_messages`), same LFM3 chat template, same
  llama.cpp/GGUF path, same `REFINER_MODELS` registry.
- English ability is already there; a Hinglish adapter plus English replay
  is less likely to regress English than a new base.

**Caveats.** Phonon was trained on English data (model card `language: en`).
Roman Hinglish is mostly Latin and should adapt well; Devanagari is further
out of distribution. Mix English replay into training, and evaluate English
as well as Hinglish. If quality is not enough, the same scaffold can target
Qwen3-1.7B or Gemma 3 1B instead.

## Hardware

The laptop RTX 4060 has 8 GB, so this uses **4-bit QLoRA**: NF4 base, LoRA
r16, batch 1, gradient accumulation 8, sequence 1024, gradient checkpointing.
A full-quality run with more data belongs on the 96 GB training box described
in `ml/AGENTS.md`.

## Quick start

```bash
cd ml/research/hinglish_v0

# 1. Synthetic raw -> clean pairs (75% Hinglish, 25% English replay).
python build_pairs.py --count 4000

# 2. Check the data without installing torch.
python train_qlora.py --dry-run --train data/train.jsonl
python eval.py --dry-run --data data/dev.jsonl

# The builder tests are pure stdlib.
python -m pytest tests --confcutdir=. -q

# 3. QLoRA. The base is Phonon's full HF weights.
uv run --with torch --with transformers --with peft --with trl \
  --with datasets --with accelerate --with bitsandbytes --with jiwer \
  python train_qlora.py --train data/train.jsonl --output adapters/phonon-hinglish

# 4. Held-out scores.
uv run --with torch --with transformers --with peft --with bitsandbytes \
  --with datasets --with jiwer python eval.py \
  --model Infatoshi/phonon-refiner-1.7b --adapter adapters/phonon-hinglish \
  --data data/dev.jsonl --out eval/hinglish.jsonl
```

If the Phonon repo's `Lfm3ForCausalLM` architecture will not load, the script
stops rather than quietly training the plain LFM3 base (which would throw
Phonon's English refiner away). Use a transformers version that supports
LFM3, or merge Phonon's `model.safetensors` into `LiquidAI/LFM3-1.7B` first.

## Data

`build_pairs.py` generates the clean side from templates and corrupts it the
way real dictation sounds:

- fillers (`um`, `uh`, `matlab`, `yaani`, `like`, `arre`), stutters;
- self-corrections with `no wait`, `arre nahi`, `I mean`, `matlab`, `sorry`;
- Roman/Devanagari mixing that the model must restore to Roman;
- b/v, sh/s, j/z, ph/f recognition confusions, lost capitals/punctuation.

Content words are never dropped: the target cannot be recovered from audio
that never carried them, and a refiner must not learn to invent text.
Self-corrections are applied last so their wrong value and cue survive.

The JSONL rows are:

```json
{"id": "hi-000001", "language": "hi", "raw": "...", "clean": "...",
 "messages": [{"role": "system", "content": "..."},
              {"role": "user", "content": "..."},
              {"role": "assistant", "content": "..."}]}
```

Data and adapters stay out of git (`data/`, `adapters/`).

## What “good” means

`eval.py` reports, overall and per language:

- **WER** against the clean target, and **raw_wer** as the baseline;
- **damage**: output worse than the raw transcript;
- **script_ok**: Roman Hinglish output has no Devanagari, Devanagari targets
  keep Devanagari;
- **filler** and **cue**: leftover fillers or correction phrases.

The adapter is only useful if Hinglish WER/damage improve *and* English stays
at least as good as the base. A model that raises English damage does not ship.

## Export and app integration

Merge the adapter, convert to GGUF, and add it to the app's registry:

```bash
python - <<'PY'
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM
base = AutoModelForCausalLM.from_pretrained(
    "Infatoshi/phonon-refiner-1.7b", torch_dtype=torch.bfloat16,
    trust_remote_code=True, device_map="cpu")
model = PeftModel.from_pretrained(base, "adapters/phonon-hinglish")
model.merge_and_unload().save_pretrained("export/phonon-hinglish")
PY
# llama.cpp is a separate checkout:
# python convert_hf_to_gguf.py export/phonon-hinglish --outtype q8_0 \
#   --outfile export/phonon-hinglish-q8.gguf
# llama-quantize export/phonon-hinglish-q8.gguf \
#   export/phonon-hinglish-Q4_K_M.gguf Q4_K_M
```

Upload the GGUF to a repo and add an entry in
`linux/src/localdictation/ai_download.py`:

```python
"phonon-hinglish": {
    "label": "Phonon Hinglish (1.7B)",
    "repo": "<your-hf-repo>",
    "file": "phonon-hinglish-Q4_K_M.gguf",
    "size_mb": 1100,
    "license": "LFM Open License",
    "hindi": True,
    "prompt": "phonon",
},
```

Two app-side changes are needed when it ships:

1. Add `"phonon-hinglish"` to `REFINER_MODEL_IDS`.
2. Make the refiner prompt model-aware: a `"prompt": "phonon"` model must get
   `_correction_messages` plus the Hinglish/Roman-script line that this
   directory trains with (`config.SYSTEM`), not the generic few-shot prompt.
   `_phonon_selected()` currently keys only on the id `"phonon"`.

The adapter is not trained to translate; the system prompt says to keep the
transcript's language and script. Keep that line in the app prompt.

## Limits of this first run

- Synthetic-only templates are a start, not a product corpus. The clean side
  is template-generated, so the adapter can overfit those shapes.
- No real Hinglish ASR pairs. Add the app's raw/refined pairs (opt-in, local)
  or public code-mixed corpora after the pipeline is proven.
- The target is Roman Hinglish. Devanagari Hinglish needs its own target
  convention or a script-conditioned prompt.
- Name spellings are still best handled by Your Words / the auto-learning
  dictionary; this adapter fixes the sentence around them.
