# Evaluation Harness

Two evaluations tied to the capstone's "measure what you build" goals:

1. **Parser eval** — regex vs LLM fallback rate, per-template hit counts, latency
2. **Categorizer eval** — zero-shot baseline, learning-loop accuracy curve, confusion matrix

## Running

### One-time: generate the labeled set

```bash
cd backend
python -m scripts.regenerate_labeled_set
# → writes evals/labeled_set.json (154 examples, 17 categories)
```

Deterministic from `--seed` (default 42). Re-run with `--force` to overwrite.

### Parser eval (free, no LLM calls by default)

```bash
python -m scripts.run_parser_eval
# → evals/results/parser_eval_real_fixtures.{txt,json}
# → evals/results/parser_eval_synthetic.{txt,json}
```

Add `--with-llm-fallback` to also route regex-missed messages through Haiku (costs tokens).

### Categorizer eval (costs tokens)

```bash
python -m scripts.run_categorizer_eval           # full run: 3 seeds, batch 10
python -m scripts.run_categorizer_eval --quick   # 1 seed, batch 20 (faster)
# → evals/results/categorizer_eval.{txt,json}
# → evals/results/accuracy_curve.png
```

Estimated cost per full run: under $0.50 with Haiku.

## What the categorizer eval measures

**Setup.** The 154-example labeled set is split 70/30 stratified by category. The
classifier is evaluated on the hold-out. The learning loop is simulated by adding
corrections from the train set in batches and re-measuring hold-out accuracy.

**Four numbers reported.**

| Metric | What it means |
|---|---|
| Zero-shot accuracy | Classifier with NO few-shots, just the taxonomy |
| Oracle ceiling | Classifier with ALL train examples available as few-shots |
| Random-order curve | Accuracy vs N corrections, corrections added in random order |
| Stratified-order curve | Same, but one example per category first |

**The headline chart** (`accuracy_curve.png`) plots both curves against zero-shot
baseline and oracle ceiling. This is the artifact that shows the learning loop
actually works.

## Methodology caveats

### Labeled set is synthetic
The examples are deterministically rendered from templates + seeded RNG, not from
real user transactions. Labels are the *intended* categories of the generator, not
human-verified labels. For a fully rigorous report, spot-check 20 random rows by
hand and report agreement.

### Zero-shot numbers are an upper bound on baseline difficulty
The synthetic data is cleaner than real data — merchants are distinct, names
match category conventions. Real-world zero-shot accuracy will likely be lower.
Report both or note this caveat in the writeup.

### Accuracy curve depends on correction order
The "stratified" curve shows what's possible if the UI surfaces one uncertain
transaction per category first. The "random" curve is what happens if users
correct in whatever order they see. The gap between the two curves is a
product-design insight: active learning matters.

### Cost control
Haiku is cheap but not free. `--quick` mode uses 1 seed to smoke-test before a
full run. During development, also consider reducing `--quick` to run against a
smaller subset of the labeled set.

## Extending

- To add a **new classifier** (e.g., a local Qwen model), implement a `classify_fn`
  that matches the signature in `categorizer_eval._classify` and swap it in
  `build_accuracy_curve`.
- To test **different few-shot retrieval strategies** (e.g., k=3 vs k=5,
  different similarity thresholds), extend `MemoryFewShotStore.retrieve`.
- To measure **real user data**, replace the `load_labeled_set` call with a
  loader that pulls from your production DB where `user_corrected=True`.
