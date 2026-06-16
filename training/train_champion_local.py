"""Local (CPU) DistilBERT fine-tune — the no-Colab equivalent of categorizer_finetune.ipynb.

Same recipe as the notebook (full fine-tune + temperature-scaling calibration on val,
holdout for final reporting only), but runs on CPU and reads the splits directly from
training/data/ instead of mounting Google Drive. Produces the two files the existing
export path consumes:
  - training/data/champion.onnx            (temperature scalar baked in; dynamic batch+seq)
  - training/data/champion_tokenizer.json

Then run:  python training/export_onnx.py --mode champion

Usage:
    python training/train_champion_local.py [--epochs 3] [--batch 16] [--max-len 64]
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import yaml
from sklearn.metrics import f1_score
from torch.utils.data import DataLoader, Dataset


def _force_torch_backend() -> None:
    """Tell transformers to use torch only — never pull in TF/Flax (avoids the
    numpy-2.x TensorFlow import crash). Must run before importing transformers."""
    os.environ.setdefault("USE_TF", "0")
    os.environ.setdefault("USE_FLAX", "0")
    os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "training" / "data"
TAXONOMY_PATH = REPO_ROOT / "training" / "taxonomy.yaml"
MODEL_NAME = "distilbert-base-uncased"
SEED = 42


class TxnDataset(Dataset):
    def __init__(self, encodings: dict, labels: list[int]) -> None:
        self.encodings = encodings
        self.labels = labels

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, idx: int) -> dict:
        item = {k: torch.tensor(v[idx]) for k, v in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels[idx])
        return item


def main() -> None:
    parser = argparse.ArgumentParser(description="Local CPU DistilBERT fine-tune.")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--max-len", type=int, default=64)
    args = parser.parse_args()

    torch.manual_seed(SEED)
    np.random.seed(SEED)

    _force_torch_backend()
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    with TAXONOMY_PATH.open(encoding="utf-8") as f:
        categories = list(yaml.safe_load(f)["categories"])
    label2id = {c: i for i, c in enumerate(categories)}
    n_labels = len(categories)
    print(f"Categories ({n_labels}): {categories}")

    train_df = pd.read_parquet(DATA_DIR / "train.parquet")
    val_df = pd.read_parquet(DATA_DIR / "val.parquet")
    holdout_df = pd.read_parquet(DATA_DIR / "holdout.parquet")
    print(f"Train: {len(train_df)}  Val: {len(val_df)}  Holdout: {len(holdout_df)}")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    def encode(texts: list[str]) -> dict:
        return dict(
            tokenizer(
                texts,
                truncation=True,
                max_length=args.max_len,
                padding="max_length",
                return_tensors="np",
            )
        )

    train_enc = encode(train_df["description"].tolist())
    train_labels = [label2id[c] for c in train_df["category"]]
    train_ds = TxnDataset(train_enc, train_labels)

    device = torch.device("cpu")
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME, num_labels=n_labels
    ).to(device)

    # ── Manual training loop (CPU; avoids Trainer arg churn across versions) ──
    loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5, weight_decay=0.01)
    model.train()
    for epoch in range(args.epochs):
        running = 0.0
        for step, batch in enumerate(loader):
            optimizer.zero_grad()
            out = model(
                input_ids=batch["input_ids"].to(device),
                attention_mask=batch["attention_mask"].to(device),
                labels=batch["labels"].to(device),
            )
            out.loss.backward()
            optimizer.step()
            running += float(out.loss)
            if step % 50 == 0:
                print(f"  epoch {epoch + 1}/{args.epochs} step {step}/{len(loader)} loss={float(out.loss):.4f}")
        print(f"epoch {epoch + 1} mean loss={running / len(loader):.4f}")

    model.eval()

    def logits_for(df: pd.DataFrame) -> torch.Tensor:
        enc = encode(df["description"].tolist())
        out_logits = []
        with torch.no_grad():
            for i in range(0, len(df), 64):
                ids = torch.tensor(enc["input_ids"][i : i + 64])
                mask = torch.tensor(enc["attention_mask"][i : i + 64])
                out_logits.append(model(input_ids=ids, attention_mask=mask).logits)
        return torch.cat(out_logits)

    # ── Temperature scaling on val ──
    val_logits = logits_for(val_df)
    val_labels = torch.tensor([label2id[c] for c in val_df["category"]])
    temperature = nn.Parameter(torch.ones(1) * 1.5)
    opt_t = torch.optim.LBFGS([temperature], lr=0.01, max_iter=50)
    nll = nn.CrossEntropyLoss()

    def _closure() -> torch.Tensor:
        opt_t.zero_grad()
        loss = nll(val_logits / temperature, val_labels)
        loss.backward()
        return loss

    opt_t.step(_closure)
    T = float(temperature.item())
    print(f"\nLearned temperature: {T:.4f}")

    # ── Holdout evaluation (final reporting only) ──
    holdout_logits = logits_for(holdout_df)
    holdout_preds = (holdout_logits / T).argmax(dim=-1).numpy()
    holdout_true = np.array([label2id[c] for c in holdout_df["category"]])
    macro = f1_score(holdout_true, holdout_preds, average="macro", zero_division=0)
    per_class = f1_score(
        holdout_true, holdout_preds, labels=list(range(n_labels)), average=None, zero_division=0
    )
    print(f"\nDistilBERT holdout macro-F1 (calibrated): {macro:.4f}")
    print("  vs baseline champion holdout macro-F1: 0.8934")
    for cat, sc in zip(categories, per_class):
        print(f"  {cat:18s} {sc:.4f}")

    # ── Export ONNX with temperature baked in (dynamic batch + seq) ──
    class CalibratedModel(nn.Module):
        def __init__(self, base: nn.Module, temp: float) -> None:
            super().__init__()
            self.base = base
            self.register_buffer("temperature", torch.tensor([temp]))

        def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
            return self.base(input_ids=input_ids, attention_mask=attention_mask).logits / self.temperature

    calibrated = CalibratedModel(model, T).to(device).eval()
    dummy_ids = torch.ones(1, args.max_len, dtype=torch.long)
    dummy_mask = torch.ones(1, args.max_len, dtype=torch.long)
    onnx_path = DATA_DIR / "champion.onnx"
    torch.onnx.export(
        calibrated,
        (dummy_ids, dummy_mask),
        str(onnx_path),
        input_names=["input_ids", "attention_mask"],
        output_names=["logits"],
        dynamic_axes={
            "input_ids": {0: "batch", 1: "seq"},
            "attention_mask": {0: "batch", 1: "seq"},
            "logits": {0: "batch"},
        },
        opset_version=14,
    )
    print(f"\nChampion ONNX -> {onnx_path}")

    tok_path = DATA_DIR / "champion_tokenizer.json"
    tokenizer.backend_tokenizer.save(str(tok_path))
    print(f"Champion tokenizer -> {tok_path}")
    print(f"\nNext: python training/export_onnx.py --mode champion  (only if {macro:.4f} > 0.8934 + margin)")


if __name__ == "__main__":
    main()
