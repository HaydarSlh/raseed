"""Unit tests for the statement parser: PAN/IBAN scrubbing, column alias matching,
and the no-raw-bytes-persisted contract (constitution Art. II / R2)."""

from __future__ import annotations

import pandas as pd
import pytest

from app.services.parsing import parse_statement


def _make_csv(**kwargs) -> bytes:
    defaults = {
        "Date": ["2026-06-01", "2026-06-02"],
        "Amount": [-12.50, 1500.00],
        "Description": ["LIDL GB NOTTINGHAM", "SALARY PAYROLL"],
    }
    defaults.update(kwargs)
    df = pd.DataFrame(defaults)
    return df.to_csv(index=False).encode()


def test_basic_parse():
    rows = parse_statement(_make_csv())
    assert len(rows) == 2
    assert rows[0].description == "LIDL GB NOTTINGHAM"
    assert float(rows[1].amount) == 1500.00


def test_pan_scrubbed():
    csv = _make_csv(Description=["4111 1111 1111 1111 PAYMENT", "Normal txn"])
    rows = parse_statement(csv)
    assert "[REDACTED]" in rows[0].description
    assert "4111" not in rows[0].description


def test_iban_scrubbed():
    csv = _make_csv(Description=["Transfer to GB29NWBK60161331926819", "Other"])
    rows = parse_statement(csv)
    assert "[REDACTED]" in rows[0].description


def test_missing_required_columns_raises():
    csv = b"Amount,Note\n10.0,foo\n"
    with pytest.raises(ValueError, match="Could not identify required columns"):
        parse_statement(csv, filename="bad.csv")


def test_column_aliases():
    df = pd.DataFrame({
        "Transaction Date": ["2026-06-10"],
        "Transaction Amount": [-5.00],
        "Transaction Description": ["COFFEE SHOP"],
    })
    rows = parse_statement(df.to_csv(index=False).encode())
    assert len(rows) == 1
    assert rows[0].description == "COFFEE SHOP"


def test_empty_file_raises():
    with pytest.raises(ValueError):
        parse_statement(b"", filename="empty.csv")


def test_no_file_bytes_returned():
    """Parsing must never return raw file bytes — only structured ParsedRow objects."""
    raw = _make_csv()
    rows = parse_statement(raw)
    for row in rows:
        # ParsedRow is a Pydantic model; it must not carry raw bytes
        assert not isinstance(row, bytes)
        assert not hasattr(row, "raw")
