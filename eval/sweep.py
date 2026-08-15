"""Threshold sweep engine for finding optimal semantic similarity τ.

Evaluates cache hit/miss accuracy across a range of similarity thresholds
using the paraphrase and near-miss evaluation pairs.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class SweepResult:
    """Results for a single threshold value."""

    threshold: float
    true_positives: int  # paraphrases correctly matched
    false_positives: int  # near-misses incorrectly matched
    true_negatives: int  # near-misses correctly rejected
    false_negatives: int  # paraphrases incorrectly rejected
    precision: float
    recall: float
    f1: float
    accuracy: float


def compute_similarity(embeddings_a: np.ndarray, embeddings_b: np.ndarray) -> np.ndarray:
    """Compute cosine similarities between paired embeddings."""
    # Normalized embeddings → dot product = cosine similarity
    sims = np.sum(embeddings_a * embeddings_b, axis=1)
    return sims


def sweep_thresholds(
    paraphrase_sims: np.ndarray,
    near_miss_sims: np.ndarray,
    tau_min: float = 0.80,
    tau_max: float = 0.99,
    tau_step: float = 0.01,
) -> list[SweepResult]:
    """Evaluate accuracy at each threshold in the range."""
    results: list[SweepResult] = []
    thresholds = np.arange(tau_min, tau_max + tau_step / 2, tau_step)

    for tau in thresholds:
        tp = int(np.sum(paraphrase_sims >= tau))
        fn = int(np.sum(paraphrase_sims < tau))
        fp = int(np.sum(near_miss_sims >= tau))
        tn = int(np.sum(near_miss_sims < tau))

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0.0

        results.append(
            SweepResult(
                threshold=round(float(tau), 3),
                true_positives=tp,
                false_positives=fp,
                true_negatives=tn,
                false_negatives=fn,
                precision=round(precision, 4),
                recall=round(recall, 4),
                f1=round(f1, 4),
                accuracy=round(accuracy, 4),
            )
        )

    return results


def run_sweep(
    tau_range: str = "0.80:0.99:0.01",
    output_path: str | None = None,
) -> list[SweepResult]:
    """Run a full threshold sweep with the evaluation pairs.

    Requires sentence-transformers to compute embeddings.
    """
    from eval.pairs import NEAR_MISS_PAIRS, PARAPHRASE_PAIRS
    from gateway.embed.provider import SentenceTransformerEmbedder

    # Parse range
    parts = tau_range.split(":")
    tau_min, tau_max, tau_step = float(parts[0]), float(parts[1]), float(parts[2])

    print("Loading embedding model...")
    embedder = SentenceTransformerEmbedder()

    # Compute embeddings for all pairs
    print(f"Computing embeddings for {len(PARAPHRASE_PAIRS)} paraphrase pairs...")
    para_a = [p[0] for p in PARAPHRASE_PAIRS]
    para_b = [p[1] for p in PARAPHRASE_PAIRS]
    para_emb_a = embedder._load_model().encode(para_a, normalize_embeddings=True)
    para_emb_b = embedder._load_model().encode(para_b, normalize_embeddings=True)

    print(f"Computing embeddings for {len(NEAR_MISS_PAIRS)} near-miss pairs...")
    miss_a = [p[0] for p in NEAR_MISS_PAIRS]
    miss_b = [p[1] for p in NEAR_MISS_PAIRS]
    miss_emb_a = embedder._load_model().encode(miss_a, normalize_embeddings=True)
    miss_emb_b = embedder._load_model().encode(miss_b, normalize_embeddings=True)

    # Compute similarities
    para_sims = compute_similarity(para_emb_a, para_emb_b)
    miss_sims = compute_similarity(miss_emb_a, miss_emb_b)

    print(f"Paraphrase similarities: mean={para_sims.mean():.4f} std={para_sims.std():.4f}")
    print(f"Near-miss similarities: mean={miss_sims.mean():.4f} std={miss_sims.std():.4f}")

    # Sweep
    results = sweep_thresholds(para_sims, miss_sims, tau_min, tau_max, tau_step)

    # Find best F1
    best = max(results, key=lambda r: r.f1)
    print(f"\nBest threshold: τ={best.threshold:.3f} (F1={best.f1:.4f}, "
          f"precision={best.precision:.4f}, recall={best.recall:.4f})")

    # Save results
    out = Path(output_path) if output_path else Path("eval/results/sweep_redis.json")

    out.parent.mkdir(parents=True, exist_ok=True)
    output_data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tau_range": {"min": tau_min, "max": tau_max, "step": tau_step},
        "best": {
            "threshold": best.threshold,
            "f1": best.f1,
            "precision": best.precision,
            "recall": best.recall,
        },
        "results": [
            {
                "tau": r.threshold,
                "tp": r.true_positives,
                "fp": r.false_positives,
                "tn": r.true_negatives,
                "fn": r.false_negatives,
                "precision": r.precision,
                "recall": r.recall,
                "f1": r.f1,
                "accuracy": r.accuracy,
            }
            for r in results
        ],
    }
    out.write_text(json.dumps(output_data, indent=2))
    print(f"Results saved to {out}")

    return results


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Threshold sweep for semantic cache")
    parser.add_argument(
        "--tau-range",
        default="0.80:0.99:0.01",
        help="min:max:step (default: 0.80:0.99:0.01)",
    )
    parser.add_argument("--output", default=None, help="Output JSON path")
    args = parser.parse_args()

    run_sweep(tau_range=args.tau_range, output_path=args.output)


if __name__ == "__main__":
    main()
