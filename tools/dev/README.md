# tools/dev

Developer tooling, separate from the app. The refiner benchmark runs locally;
the two labeling and speech scripts below send data to cloud APIs.

- `muse_bench.py`: uploads recordings from your local corpus to Meta's Muse
  speech API and compares its transcripts with Phonon's. Needs `MODEL_API_KEY`.
- `label_opus.py`: sends vocabulary candidates to OpenRouter for keep/drop
  labels (step 3 of `tools/profile-miner/judge/runner.sh`). Needs
  `OPENROUTER_API_KEY`.

## Refiner benchmark

From the repository root, compare ordinary Phonon decoding with DFlash2 on
your hardware. Supply the downloaded b12210 `llama-server`, pinned target,
and matching drafter paths:

```sh
PYTHONPATH=linux/src python3 tools/dev/bench_refiner.py \
  --server /path/to/llama-server --model /path/to/target.gguf \
  --drafter /path/to/phonon-refiner-1.7b-dflash2-drafter.gguf \
  --output /tmp/refiner-benchmark.json
```

The benchmark uses synthetic dictation, warms both configurations, checks
complete and streamed output parity, and records first-text latency, total
latency, and the server's draft acceptance counters. It starts temporary
servers without changing your running Falco service. `--draft-tokens 4`
tests a smaller block; the application's default is 7. Results from one
device do not establish speedups on other hardware.
