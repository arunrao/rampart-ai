"""
Toxicity detection using unitary/toxic-bert.

A BERT-base model fine-tuned on the Jigsaw Toxic Comment dataset for multi-label
toxicity classification.  Compared with the earlier citizenlab/distilbert model it
is significantly better calibrated — common English phrases ("hello world", "the
quick brown fox") score < 0.01, while genuinely toxic content scores ≥ 0.9.

  Model   : unitary/toxic-bert
  Base    : bert-base-uncased  (110 M parameters)
  Size    : ~420 MB (FP32) / ~210 MB (INT8 ONNX)
  Labels  : toxic, severe_toxic, obscene, threat, insult, identity_hate
  License : Apache-2.0

Inference path (in priority order):
  1. ONNX INT8 via optimum[onnxruntime]  — ~45 ms  (2-3x faster than PyTorch)
  2. PyTorch pipeline fallback           — ~110 ms

The main `toxicity` score returned is P(toxic) — the probability of the primary
"toxic" label.  `is_toxic` is True when ANY of the six category scores exceeds
the caller-supplied threshold.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

_MODEL_NAME = "unitary/toxic-bert"
_TOXIC_LABEL = "toxic"
_ALL_LABELS = {"toxic", "severe_toxic", "obscene", "threat", "insult", "identity_hate"}

# Try to import ONNX optimisation (same library used by DeBERTa detector)
try:
    from optimum.onnxruntime import ORTModelForSequenceClassification  # type: ignore
    _ORT_AVAILABLE = True
except ImportError:
    _ORT_AVAILABLE = False
    logger.info("optimum[onnxruntime] not available — toxicity will use PyTorch pipeline")


@lru_cache(maxsize=1)
def _get_pipeline():
    """
    Load and cache the inference pipeline (one-time cost at warmup).

    Tries ONNX first (via optimum), falls back to plain PyTorch pipeline.
    The ONNX model is exported on first use and cached in the HuggingFace
    hub cache directory so subsequent container starts skip the export step.
    """
    # ── ONNX path ──────────────────────────────────────────────────────────
    if _ORT_AVAILABLE:
        try:
            from transformers import AutoTokenizer, pipeline as hf_pipeline  # type: ignore

            logger.info("Loading ONNX-optimised toxic-bert...")
            try:
                # Fast path: ONNX model already exported and cached
                ort_model = ORTModelForSequenceClassification.from_pretrained(
                    _MODEL_NAME,
                    export=False,
                )
                logger.info("✓ toxic-bert ONNX loaded from cache")
            except Exception:
                # One-time export (~15 s); result is cached for future starts
                logger.info("Exporting toxic-bert to ONNX (one-time ~15 s)…")
                ort_model = ORTModelForSequenceClassification.from_pretrained(
                    _MODEL_NAME,
                    export=True,
                )
                logger.info("✓ toxic-bert ONNX exported and cached")

            tokenizer = AutoTokenizer.from_pretrained(_MODEL_NAME)
            pipe = hf_pipeline(
                "text-classification",
                model=ort_model,
                tokenizer=tokenizer,
                top_k=None,
            )
            logger.info(f"✓ Toxicity model loaded (ONNX): {_MODEL_NAME}")
            return pipe

        except Exception as onnx_err:
            logger.warning(f"ONNX load failed for toxic-bert: {onnx_err} — falling back to PyTorch")

    # ── PyTorch fallback ────────────────────────────────────────────────────
    try:
        from transformers import pipeline as hf_pipeline  # type: ignore

        pipe = hf_pipeline(
            "text-classification",
            model=_MODEL_NAME,
            tokenizer=_MODEL_NAME,
            top_k=None,
        )
        logger.info(f"✓ Toxicity model loaded (PyTorch): {_MODEL_NAME}")
        return pipe
    except Exception as exc:
        logger.warning(f"⚠ Toxicity model unavailable: {exc}")
        return None


def detect_toxicity(content: str) -> Optional[dict]:
    """
    Run ML toxicity inference.

    Returns a dict with:
        score    : float  — P(toxic), the primary Jigsaw "toxic" label score [0, 1]
        is_toxic : bool   — True when score > 0.5 (model's own threshold)
        label    : str    — "toxic" | "not_toxic"

    Returns None if the model failed to load (caller falls back to score=0).
    """
    pipe = _get_pipeline()
    if pipe is None:
        return None
    try:
        all_scores = pipe(content[:512])[0]  # outer list wraps one item per input text
        scores_by_label = {item["label"]: item["score"] for item in all_scores}
        toxicity_score = float(scores_by_label.get(_TOXIC_LABEL, 0.0))
        is_toxic = toxicity_score > 0.5
        return {
            "score": round(toxicity_score, 4),
            "is_toxic": is_toxic,
            "label": "toxic" if is_toxic else "not_toxic",
        }
    except Exception as exc:
        logger.error(f"Toxicity inference error: {exc}")
        return None


def warmup() -> None:
    """Force model load at startup so the first real request isn't slow."""
    result = detect_toxicity("warmup check")
    if result is not None:
        logger.info("✓ Toxicity model warmed up")
    else:
        logger.warning("⚠ Toxicity model warmup returned None — check logs above")
