"""Trainer entrypoint: the single deliberately heavy image (torch + transformers). Runs only under the `training` compose profile / RQ `training` queue — never on a request path (constitution Art. III). Stub in Phase 0."""

from __future__ import annotations


def main() -> None:
    """Phase 5 implements the partial-unfreeze CPU retrain that emits a new ONNX
    artifact (+ model card + pinned SHA) to MinIO. Initial foundation training is
    offline in Colab on GPU. Phase 0 only proves this image is profile-gated and
    absent from the default boot."""
    print("raseed trainer stub — no training in Phase 0")


if __name__ == "__main__":
    main()
