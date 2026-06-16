"""T026 — Gemini zero-shot baseline (US3).

Runs the Gemini zero-shot classification prompt (Art. IV — loaded from
prompts/categorizer_zeroshot.md) over a sample of the validation set.
Records macro-F1, per-class F1, latency, and token cost.

Runs OFFLINE over the Kaggle dataset only — never over user data (Art. II).

Usage:
    python training/eval_zeroshot.py [--sample 500] [--data-dir training/data]
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import pandas as pd
import yaml
from sklearn.metrics import f1_score

REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "training" / "data"
PROMPT_PATH = REPO_ROOT / "prompts" / "categorizer_zeroshot.md"
TAXONOMY_PATH = REPO_ROOT / "training" / "taxonomy.yaml"

# Adapter settings (mirrors backend retry policy: 3 attempts, expo backoff, 4xx no-retry).
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.0  # seconds


def _load_taxonomy() -> list[str]:
    with TAXONOMY_PATH.open() as f:
        return list(yaml.safe_load(f)["categories"])


def _load_prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _call_gemini(client, prompt: str, model: str = "gemini-2.0-flash-lite") -> tuple[str, int, int]:
    """Call Gemini with retry. Returns (text, input_tokens, output_tokens)."""
    import time as _time

    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            text = response.text.strip()
            usage = getattr(response, "usage_metadata", None)
            in_tok = getattr(usage, "prompt_token_count", 0) or 0
            out_tok = getattr(usage, "candidates_token_count", 0) or 0
            return text, int(in_tok), int(out_tok)
        except Exception as exc:
            status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
            if status and 400 <= int(status) < 500:
                raise  # 4xx: no retry (adapter policy)
            if attempt == MAX_RETRIES - 1:
                raise
            backoff = RETRY_BACKOFF_BASE * (2 ** attempt)
            print(f"  Retrying in {backoff}s after: {exc}")
            _time.sleep(backoff)
    raise RuntimeError("unreachable")


def _normalize(raw: str, categories: list[str]) -> str:
    """Map raw Gemini output to a taxonomy category, or 'other' if unrecognised."""
    cleaned = raw.lower().strip().rstrip(".")
    for cat in categories:
        if cat in cleaned:
            return cat
    return "other"


def run_eval(sample_n: int = 500, data_dir: Path = DATA_DIR) -> dict:
    categories = _load_taxonomy()
    prompt_template = _load_prompt_template()

    val_df = pd.read_parquet(data_dir / "val.parquet")
    if sample_n and len(val_df) > sample_n:
        val_df = val_df.sample(n=sample_n, random_state=42).reset_index(drop=True)
    print(f"Evaluating Gemini zero-shot on {len(val_df)} samples…")

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY or GOOGLE_API_KEY must be set for zero-shot eval."
        )

    from google import genai  # type: ignore[import-untyped]

    client = genai.Client(api_key=api_key)

    predictions: list[str] = []
    total_in, total_out = 0, 0
    latencies: list[float] = []

    for i, row in val_df.iterrows():
        prompt = prompt_template.replace("{description}", str(row["description"]))
        t0 = time.perf_counter()
        raw, in_tok, out_tok = _call_gemini(client, prompt)
        lat_ms = (time.perf_counter() - t0) * 1000
        pred = _normalize(raw, categories)
        predictions.append(pred)
        total_in += in_tok
        total_out += out_tok
        latencies.append(lat_ms)

        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(val_df)} done…")

    # Metrics.
    macro_f1 = float(f1_score(
        val_df["category"], predictions,
        labels=categories, average="macro", zero_division=0,
    ))
    per_class = f1_score(
        val_df["category"], predictions,
        labels=categories, average=None, zero_division=0,
    )
    import numpy as np

    avg_latency_ms = float(np.mean(latencies))
    p95_latency_ms = float(np.percentile(latencies, 95))

    # Cost estimate (Gemini Flash-Lite pricing as of 2026).
    cost_per_1m_in = 0.075   # USD / 1M input tokens
    cost_per_1m_out = 0.30   # USD / 1M output tokens
    total_cost_usd = (total_in / 1_000_000) * cost_per_1m_in + (total_out / 1_000_000) * cost_per_1m_out

    print(f"Macro-F1:      {macro_f1:.4f}")
    print(f"Avg latency:   {avg_latency_ms:.1f} ms  p95: {p95_latency_ms:.1f} ms")
    print(f"Total tokens:  {total_in:,} in / {total_out:,} out")
    print(f"Estimated cost: ${total_cost_usd:.4f} USD for {len(val_df)} samples")

    results = {
        "model": "gemini-zero-shot",
        "sample_n": len(val_df),
        "macro_f1": round(macro_f1, 4),
        "per_class_f1": {
            cat: round(float(sc), 4)
            for cat, sc in zip(categories, per_class)
        },
        "avg_latency_ms": round(avg_latency_ms, 2),
        "p95_latency_ms": round(p95_latency_ms, 2),
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "estimated_cost_usd": round(total_cost_usd, 6),
        "cost_per_call_usd": round(total_cost_usd / len(val_df), 8),
    }

    out_path = data_dir / "zeroshot_results.json"
    with out_path.open("w") as f:
        json.dump(results, f, indent=2)
    print(f"Results written to {out_path}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Gemini zero-shot baseline eval.")
    parser.add_argument("--sample", type=int, default=500)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    run_eval(sample_n=args.sample, data_dir=args.data_dir)


if __name__ == "__main__":
    main()
