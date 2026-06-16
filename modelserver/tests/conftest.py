"""Pytest fixtures for the model-server test suite.

T014 — creates a tiny deterministic fixture ONNX + tokenizer + taxonomy + thresholds
so all US1 tests run without a real trained model or the Kaggle dataset.

Fixture ONNX: neural-style (int64 input_ids + attention_mask → float logits)
that always returns highest logit for categories[0] ("groceries").
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Generator

import numpy as np
import onnx
import onnx.helper as helper
import onnx.numpy_helper as numpy_helper
import pytest
import yaml
from onnx import TensorProto
from starlette.testclient import TestClient
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import Whitespace

CATEGORIES = [
    "groceries", "dining", "transport", "utilities", "healthcare",
    "entertainment", "shopping", "travel", "education", "income",
    "transfer", "fees", "other",
]
NUM_CATS = len(CATEGORIES)


def make_fixture_onnx(num_cats: int, path: Path) -> None:
    """Minimal ONNX: input_ids + attention_mask → logits (always predicts category[0])."""
    weights = np.zeros((1, num_cats), dtype=np.float32)
    weights[0, 0] = 10.0  # groceries always wins

    weight_init = numpy_helper.from_array(weights, name="W")
    axes_init = numpy_helper.from_array(np.array([1], dtype=np.int64), name="reduce_axes")

    nodes = [
        helper.make_node("Cast", ["input_ids"], ["float_ids"], to=TensorProto.FLOAT),
        helper.make_node("ReduceSum", ["float_ids", "reduce_axes"], ["reduced"], keepdims=1),
        helper.make_node("MatMul", ["reduced", "W"], ["logits"]),
    ]
    graph = helper.make_graph(
        nodes,
        "fixture_categorizer",
        inputs=[
            helper.make_tensor_value_info("input_ids", TensorProto.INT64, [None, None]),
            helper.make_tensor_value_info("attention_mask", TensorProto.INT64, [None, None]),
        ],
        outputs=[
            helper.make_tensor_value_info("logits", TensorProto.FLOAT, [None, num_cats]),
        ],
        initializer=[weight_init, axes_init],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 8
    onnx.checker.check_model(model)
    onnx.save(model, str(path))


def make_fixture_tokenizer(categories: list[str], path: Path) -> None:
    vocab: dict[str, int] = {"[PAD]": 0, "[UNK]": 1, "[CLS]": 2, "[SEP]": 3}
    for word in [*categories, "STARBUCKS", "STORE", "WALMART", "AMAZON", "PAYMENT", "COFFEE"]:
        for part in word.upper().split():
            if part not in vocab:
                vocab[part] = len(vocab)
    tok = Tokenizer(WordLevel(vocab=vocab, unk_token="[UNK]"))
    tok.pre_tokenizer = Whitespace()
    tok.save(str(path))


def make_fixture_taxonomy(categories: list[str], path: Path) -> None:
    data = {"version": "1.0.0", "categories": categories, "consolidation_map": {}}
    with path.open("w") as f:
        yaml.dump(data, f)


def make_fixture_thresholds(categories: list[str], path: Path) -> None:
    thresholds = {cat: 0.5 for cat in categories}
    data = {
        "categorizer": {
            "macro_f1_min": None,
            "beat_baseline_margin": None,
            "min_per_class_f1": None,
            "max_inference_latency_ms": None,
            "operating_thresholds": thresholds,
        }
    }
    with path.open("w") as f:
        yaml.dump(data, f)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture(scope="session")
def fixture_artifact_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the fixture artifact directory once per session."""
    base = tmp_path_factory.mktemp("artifacts")
    make_fixture_onnx(NUM_CATS, base / "categorizer.onnx")
    make_fixture_tokenizer(CATEGORIES, base / "tokenizer.json")
    make_fixture_taxonomy(CATEGORIES, base / "taxonomy.yaml")
    make_fixture_thresholds(CATEGORIES, base / "eval_thresholds.yaml")
    return base


@pytest.fixture(scope="session")
def fixture_sha256(fixture_artifact_dir: Path) -> str:
    return sha256_of(fixture_artifact_dir / "categorizer.onnx")


@pytest.fixture()
def test_client(
    fixture_artifact_dir: Path,
    fixture_sha256: str,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    """TestClient backed by the fixture artifact. Server starts and stops around each test."""
    monkeypatch.setenv("MODELSERVER_ARTIFACT_DIR", str(fixture_artifact_dir))
    monkeypatch.setenv("MODELSERVER_EXPECTED_SHA256", fixture_sha256)
    monkeypatch.setenv(
        "MODELSERVER_TAXONOMY_PATH", str(fixture_artifact_dir / "taxonomy.yaml")
    )
    monkeypatch.setenv(
        "MODELSERVER_THRESHOLDS_PATH", str(fixture_artifact_dir / "eval_thresholds.yaml")
    )

    from modelserver.config import Settings

    test_settings = Settings()

    import modelserver.app as app_module

    monkeypatch.setattr(app_module, "settings", test_settings)

    with TestClient(app_module.app) as client:
        yield client
