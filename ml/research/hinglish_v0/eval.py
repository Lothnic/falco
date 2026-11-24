"""Evaluate a Hinglish adapter on a held-out JSONL from build_pairs.py.

Reports the numbers the adapter must not regress: WER against the clean
target, output-script preservation (Roman Hinglish stays Roman), leftover
fillers/correction cues, and damage (rows the refiner made worse than the
raw transcript). `--dry-run` scores the raw transcripts without loading a
model, which is the baseline to beat.

    python eval.py --dry-run --data data/dev.jsonl
    uv run --with torch --with transformers --with peft --with bitsandbytes \
      --with datasets --with jiwer python eval.py \
      --model Infatoshi/phonon-refiner-1.7b --adapter adapters/phonon-hinglish \
      --data data/dev.jsonl
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from config import BASE_MODEL
from train_qlora import apply_template, load_model, load_tokenizer, read_jsonl

DEVANAGARI = re.compile(r"[\u0900-\u097F]")
FILLER = re.compile(r"\b(?:um|uh|matlab|yaani|arre)\b", re.IGNORECASE)
CUE = re.compile(r"\b(?:no wait|arre nahi|i mean|sorry|actually)\b", re.IGNORECASE)


def words(text):
    return re.findall(r"\w+", (text or "").casefold())


def wer(reference, hypothesis):
    """Word error rate, with jiwer when installed and a small fallback."""
    try:
        import jiwer
    except ImportError:
        ref, hyp = words(reference), words(hypothesis)
        matched = sum(1 for a, b in zip(ref, hyp) if a == b)
        return 1.0 - (matched / max(1, len(ref)))
    return jiwer.wer(reference or "", hypothesis or "")


def script_ok(clean, output):
    return bool(DEVANAGARI.search(output)) == bool(DEVANAGARI.search(clean))


def score(row, output):
    clean, raw = row["clean"], row["raw"]
    out_wer = wer(clean, output)
    raw_wer = wer(clean, raw)
    return {
        "wer": out_wer,
        "raw_wer": raw_wer,
        "damage": out_wer > raw_wer,
        "script_ok": script_ok(clean, output),
        "devanagari": bool(DEVANAGARI.search(output)),
        "filler": bool(FILLER.search(output)),
        "cue": bool(CUE.search(output)),
    }


def load_adapter(args):
    from peft import PeftModel

    tokenizer = load_tokenizer(args.model)
    model = load_model(args.model)
    if args.adapter:
        model = PeftModel.from_pretrained(model, args.adapter)
    model.eval()
    return tokenizer, model


def generate(tokenizer, model, row, max_new_tokens):
    import torch

    messages = row["messages"][:2]      # system + user, no assistant target
    prompt = apply_template(tokenizer, messages, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    with torch.inference_mode():
        output = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
        )
    new_tokens = output[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


def report(rows, outputs, label):
    scored = [score(row, output) for row, output in zip(rows, outputs, strict=True)]
    if not scored:
        print(f"{label}: no rows")
        return scored
    count = len(scored)
    print(
        f"{label}: n={count} "
        f"wer={sum(s['wer'] for s in scored) / count:.4f} "
        f"raw_wer={sum(s['raw_wer'] for s in scored) / count:.4f} "
        f"damage={sum(s['damage'] for s in scored) / count:.3f} "
        f"script_ok={sum(s['script_ok'] for s in scored) / count:.3f} "
        f"filler={sum(s['filler'] for s in scored) / count:.3f} "
        f"cue={sum(s['cue'] for s in scored) / count:.3f}"
    )
    return scored


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=BASE_MODEL)
    parser.add_argument("--adapter", default="")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="Score the raw transcripts; do not load a model.")
    args = parser.parse_args()

    rows = read_jsonl(args.data)
    if args.limit:
        rows = rows[:args.limit]
    if not rows:
        raise SystemExit(f"no rows in {args.data}")

    if args.dry_run:
        outputs = [row["raw"] for row in rows]
        scored = report(rows, outputs, "raw")
    else:
        tokenizer, model = load_adapter(args)
        outputs = [generate(tokenizer, model, row, args.max_new_tokens) for row in rows]
        scored = report(rows, outputs, "adapter")

    for group in ("hi", "en"):
        indexes = [i for i, row in enumerate(rows) if row.get("language") == group]
        if indexes:
            report([rows[i] for i in indexes], [outputs[i] for i in indexes], group)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8") as handle:
            for row, output, metrics in zip(rows, outputs, scored, strict=True):
                handle.write(json.dumps({
                    "id": row.get("id"),
                    "language": row.get("language"),
                    "raw": row["raw"],
                    "clean": row["clean"],
                    "output": output,
                    "metrics": metrics,
                }, ensure_ascii=False) + "\n")

    for row, output, metrics in list(zip(rows, outputs, scored, strict=True))[:5]:
        print(f"\n[{row.get('language')}] raw:   {row['raw']}")
        print(f"              clean: {row['clean']}")
        print(f"              out:   {output}")
        print(f"              wer={metrics['wer']:.3f} damage={metrics['damage']} "
              f"script_ok={metrics['script_ok']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
