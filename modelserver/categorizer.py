"""Categorizer: artifact seam, inference, calibration, per-category thresholds.

Architecture:
  get_current_artifact() → ArtifactRef   ← thin seam (Phase 2: mounted-file provider)
  Categorizer.__init__(ref) → loads ONNX + tokenizer through the seam
  Categorizer.predict(description, top_k) → PredictResponse

Phase 5 swaps in a MinIO-by-SHA provider for get_current_artifact() without
touching boot or hash-verification logic (both depend only on the seam).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import structlog
import yaml

import onnxruntime as ort  # noqa: E402

from modelserver.schemas import CategoryScore, PredictResponse

log = structlog.get_logger()

# Sentinel: categories whose operating threshold is always_review.
ALWAYS_REVIEW = "always_review"


@dataclass(frozen=True)
class ArtifactRef:
    """Resolved artifact paths — the only thing boot/hash-verify logic depends on."""

    onnx_path: Path
    tokenizer_path: Path


def get_current_artifact(artifact_dir: Path) -> ArtifactRef:
    """Mounted-file provider (Phase 2).

    Phase 5 replaces this function body with a MinIO-by-SHA provider.
    Boot and hash-verification logic in app.py MUST NOT reference artifact_dir
    directly — they call this function instead.
    """
    return ArtifactRef(
        onnx_path=artifact_dir / "categorizer.onnx",
        tokenizer_path=artifact_dir / "tokenizer.json",
    )


class Categorizer:
    """Loads an ONNX model + tokenizer and serves calibrated predictions."""

    def __init__(
        self,
        artifact_ref: ArtifactRef,
        taxonomy_path: Path,
        thresholds_path: Path,
        max_sequence_length: int = 128,
    ) -> None:
        self._categories = self._load_taxonomy(taxonomy_path)
        self._thresholds = self._load_thresholds(thresholds_path)
        self._max_len = max_sequence_length

        # ONNX session — CPU only (no CUDA in serving image).
        so = ort.SessionOptions()
        so.log_severity_level = 3  # ERROR only
        self._session = ort.InferenceSession(
            str(artifact_ref.onnx_path),
            sess_options=so,
            providers=["CPUExecutionProvider"],
        )

        # Detect model type from ONNX input signature.
        first_input = self._session.get_inputs()[0]
        self._model_type = "classical" if "string" in first_input.type else "neural"

        if self._model_type == "neural":
            if not artifact_ref.tokenizer_path.exists():
                raise FileNotFoundError(
                    f"tokenizer.json missing for neural model: {artifact_ref.tokenizer_path}"
                )
            from tokenizers import Tokenizer  # noqa: PLC0415

            self._tokenizer = Tokenizer.from_file(str(artifact_ref.tokenizer_path))
            self._tokenizer.enable_truncation(max_length=self._max_len)
            self._tokenizer.enable_padding(
                pad_id=0, pad_token="[PAD]", length=self._max_len
            )
        else:
            self._tokenizer = None

        log.info(
            "categorizer_loaded",
            model_type=self._model_type,
            categories=len(self._categories),
        )

    # ── Inference ────────────────────────────────────────────────────────────

    def predict(self, description: str, top_k: int = 3) -> PredictResponse:
        start = _perf_ms()
        raw = self._run_onnx(description)  # [num_categories]
        # Classical (skl2onnx) ONNX already emits calibrated probabilities that sum to
        # 1 — re-applying softmax would collapse them toward uniform (1/N) and make the
        # operating thresholds (computed on these same probabilities) unreachable.
        # Neural models emit raw logits, which still need softmax.
        probs = raw if self._model_type == "classical" else _softmax(raw)

        # Top-k alternatives (sorted desc), primary at rank 0.
        top_k = min(top_k, len(self._categories))
        top_indices = np.argsort(probs)[::-1][:top_k]

        primary_idx = int(top_indices[0])
        primary_cat = self._categories[primary_idx]
        primary_conf = float(probs[primary_idx])

        alternatives = [
            CategoryScore(category=self._categories[int(i)], score=float(probs[int(i)]))
            for i in top_indices
        ]

        # Per-category low-confidence flag.
        threshold = self._thresholds.get(primary_cat)
        low_confidence: bool
        if threshold == ALWAYS_REVIEW or threshold is None:
            low_confidence = True
        else:
            low_confidence = primary_conf < float(threshold)

        latency_ms = _perf_ms() - start
        log.info(
            "predict",
            category=primary_cat,
            confidence=round(primary_conf, 4),
            low_confidence=low_confidence,
            latency_ms=round(latency_ms, 2),
        )

        return PredictResponse(
            category=primary_cat,
            confidence=primary_conf,
            alternatives=alternatives,
            low_confidence=low_confidence,
        )

    # ── Private helpers ──────────────────────────────────────────────────────

    def _run_onnx(self, description: str) -> np.ndarray:
        """Run ONNX inference; returns raw logits as [num_categories] array."""
        if self._model_type == "neural":
            encoding = self._tokenizer.encode(description)
            input_ids = np.array([encoding.ids], dtype=np.int64)
            attention_mask = np.array([encoding.attention_mask], dtype=np.int64)
            feeds: dict[str, Any] = {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
            }
        else:
            feeds = {self._session.get_inputs()[0].name: np.array([[description]])}

        outputs = self._session.run(None, feeds)
        # skl2onnx Pipeline: outputs[0] = label string [1], outputs[1] = [{cat: prob, ...}]
        # Neural ONNX: outputs[0] = logits [1, num_classes] or [num_classes]
        if len(outputs) >= 2:
            proba = outputs[1]
            if isinstance(proba, list) and len(proba) > 0 and isinstance(proba[0], dict):
                # Classical: probability dict keyed by class label.
                prob_dict = proba[0]
                return np.array([prob_dict.get(cat, 0.0) for cat in self._categories], dtype=np.float32)
            if hasattr(proba, "shape"):
                # Neural: ndarray [1, num_classes]
                return proba[0] if proba.ndim == 2 else proba
        logits = outputs[0]
        if hasattr(logits, "ndim") and logits.ndim == 2:
            return logits[0]
        return logits

    @staticmethod
    def _load_taxonomy(taxonomy_path: Path) -> list[str]:
        with taxonomy_path.open() as f:
            tax = yaml.safe_load(f)
        return list(tax["categories"])

    @staticmethod
    def _load_thresholds(thresholds_path: Path) -> dict[str, Any]:
        """Return operating_thresholds map, or empty dict if not yet populated."""
        if not thresholds_path.exists():
            return {}
        with thresholds_path.open() as f:
            data = yaml.safe_load(f)
        if not data:
            return {}
        return (data.get("categorizer") or {}).get("operating_thresholds") or {}


def _softmax(logits: np.ndarray) -> np.ndarray:
    exps = np.exp(logits - np.max(logits))
    return exps / exps.sum()


def _perf_ms() -> float:
    import time

    return time.perf_counter() * 1000
