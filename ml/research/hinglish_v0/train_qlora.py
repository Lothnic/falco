"""QLoRA SFT for a Hinglish adapter on top of Phonon's refiner.

The base is `Infatoshi/phonon-refiner-1.7b` (LFM3-1.7B, full bf16 weights in
the HF repo). On an 8 GB card this uses 4-bit NF4, LoRA r16, batch 1,
gradient accumulation 8, sequence 1024 and gradient checkpointing. The
English replay rows in the data keep the adapter from forgetting English.

    python train_qlora.py --dry-run --train data/train.jsonl
    uv run --with torch --with transformers --with peft --with trl \
      --with datasets --with accelerate --with bitsandbytes --with jiwer \
      python train_qlora.py --train data/train.jsonl --output adapters/phonon-hinglish

Not run by the app or CI; this is the offline training entry point.
"""
import argparse
import inspect
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from config import BASE_MODEL, MAX_SEQ_LEN, SEED


def read_jsonl(path):
    rows = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def apply_template(tokenizer, messages, add_generation_prompt=False):
    """The tokenizer's chat template, with thinking off when it accepts it."""
    kwargs = {"tokenize": False, "add_generation_prompt": add_generation_prompt}
    for extra in ({"enable_thinking": False}, {}):
        try:
            text = tokenizer.apply_chat_template(messages, **kwargs, **extra)
        except TypeError:
            continue
        except Exception:  # noqa: BLE001 - a broken template falls back to plain roles
            return "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        if isinstance(text, list):
            text = text[0]
        return str(text)
    return "\n".join(f"{message['role']}: {message['content']}" for message in messages)


def render(tokenizer, rows, limit=0):
    records = []
    for row in rows[:limit] if limit else rows:
        records.append({"text": apply_template(tokenizer, row["messages"])})
    return records


def load_tokenizer(model_id):
    from transformers import AutoProcessor, AutoTokenizer

    last = None
    for loader in (AutoTokenizer, AutoProcessor):
        try:
            tokenizer = loader.from_pretrained(model_id, trust_remote_code=True)
            if hasattr(tokenizer, "padding_side"):
                tokenizer.padding_side = "right"
            inner = getattr(tokenizer, "tokenizer", None)
            if inner is not None and hasattr(inner, "padding_side"):
                inner.padding_side = "right"
            if getattr(tokenizer, "pad_token", None) is None and getattr(
                    tokenizer, "eos_token", None):
                tokenizer.pad_token = tokenizer.eos_token
            return tokenizer
        except Exception as exc:  # noqa: BLE001 - try the processor next
            last = exc
    raise RuntimeError(f"could not load a tokenizer for {model_id}: {last}")


def load_model(model_id):
    import torch
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig

    quant = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    kwargs = {
        "quantization_config": quant,
        "device_map": {"": 0},
        "trust_remote_code": True,
        "dtype": torch.bfloat16,
    }
    try:
        return AutoModelForCausalLM.from_pretrained(
            model_id, attn_implementation="sdpa", **kwargs)
    except Exception:  # noqa: BLE001 - this model may not support SDPA
        return AutoModelForCausalLM.from_pretrained(model_id, **kwargs)


def lora_config(rank):
    from peft import LoraConfig, TaskType

    return LoraConfig(
        r=rank,
        lora_alpha=rank * 2,
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        target_modules="all-linear",
    )


def sft_config(output, args, batch, accum):
    from trl import SFTConfig

    params = inspect.signature(SFTConfig.__init__).parameters
    kwargs = {
        "output_dir": str(Path(output) / "trainer"),
        "num_train_epochs": args.epochs,
        "per_device_train_batch_size": batch,
        "gradient_accumulation_steps": accum,
        "learning_rate": args.lr,
        "lr_scheduler_type": "cosine",
        "warmup_ratio": 0.03,
        "bf16": True,
        "logging_steps": 5,
        "save_strategy": "epoch",
        "report_to": "none",
        "gradient_checkpointing": True,
        "optim": "paged_adamw_8bit",
        "seed": args.seed,
        "dataset_text_field": "text",
        "max_length": args.max_seq_len,
    }
    if args.max_steps > 0:
        kwargs["max_steps"] = args.max_steps
    if "eval_strategy" in params:
        kwargs["eval_strategy"] = "no"
    if "gradient_checkpointing_kwargs" in params:
        kwargs["gradient_checkpointing_kwargs"] = {"use_reentrant": False}
    return SFTConfig(**{key: value for key, value in kwargs.items() if key in params})


def train(args):
    import torch
    from datasets import Dataset
    from peft import prepare_model_for_kbit_training
    from trl import SFTTrainer

    tokenizer = load_tokenizer(args.model)
    rows = read_jsonl(args.train)
    if not rows:
        raise SystemExit(f"empty training set: {args.train}")
    dataset = Dataset.from_list(render(tokenizer, rows, args.limit))
    print(f"rows={len(dataset)} model={args.model} output={args.output}", flush=True)

    model = load_model(args.model)
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    if hasattr(model.config, "use_cache"):
        model.config.use_cache = False
    peft = lora_config(args.lora_r)
    last_error = None
    for batch, accum in ((args.batch_size, args.grad_accum), (1, 16)):
        try:
            torch.cuda.empty_cache()
            config = sft_config(args.output, args, batch, accum)
            trainer_kwargs = {
                "model": model,
                "args": config,
                "train_dataset": dataset,
                "peft_config": peft,
            }
            trainer_params = inspect.signature(SFTTrainer.__init__).parameters
            if "processing_class" in trainer_params:
                trainer_kwargs["processing_class"] = tokenizer
            elif "tokenizer" in trainer_params:
                trainer_kwargs["tokenizer"] = tokenizer
            trainer = SFTTrainer(**trainer_kwargs)
            trainer.train()
            out = Path(args.output)
            out.mkdir(parents=True, exist_ok=True)
            trainer.save_model(str(out))
            tokenizer.save_pretrained(out)
            meta = {
                "base": args.model,
                "rows": len(dataset),
                "batch_size": batch,
                "grad_accum": accum,
                "epochs": args.epochs,
                "lr": args.lr,
                "lora_r": args.lora_r,
                "max_seq_len": args.max_seq_len,
                "seed": args.seed,
            }
            (out / "train_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
            print(json.dumps(meta), flush=True)
            return out
        except torch.cuda.OutOfMemoryError as exc:
            last_error = exc
            print(f"OOM with batch={batch}; retrying with batch=1, accum=16", flush=True)
            torch.cuda.empty_cache()
    raise RuntimeError(f"training OOM after retries: {last_error}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=BASE_MODEL,
                        help=f"HF model or adapter base (default {BASE_MODEL}).")
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=HERE / "adapters" / "phonon-hinglish")
    parser.add_argument("--epochs", type=float, default=2.0)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--max-seq-len", type=int, default=MAX_SEQ_LEN)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--max-steps", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--dry-run", action="store_true",
                        help="Check the data and print a sample without loading torch.")
    args = parser.parse_args()

    rows = read_jsonl(args.train)
    if args.dry_run:
        print(f"{len(rows)} rows in {args.train}; model={args.model}")
        for row in rows[:3]:
            print(f"\nraw:   {row['raw']}\nclean: {row['clean']}")
        return 0
    try:
        train(args)
    except Exception as exc:
        raise SystemExit(
            f"Could not continue from {args.model}: {exc}\n"
            "Do not swap in the plain LFM3 base: that discards Phonon's English refiner. "
            "Install a transformers version that loads the Lfm3ForCausalLM architecture, "
            "or merge Phonon's model.safetensors into the LiquidAI/LFM3-1.7B base first."
        ) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
