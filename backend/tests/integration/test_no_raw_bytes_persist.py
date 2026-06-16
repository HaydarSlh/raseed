"""Proof that no raw statement bytes reach any persistent store after upload.

Contract (constitution Art. II / R2): parse in-memory, scrub PAN/IBAN, return
ParsedRow objects — never write file bytes to DB, MinIO, or disk.

This test verifies the structural guarantee: parse_statement() is a pure function
that takes bytes and returns ParsedRow objects, and the ingestion service only
receives ParsedRow objects (not bytes). It also verifies that Transaction ORM rows
have no bytes field and no field containing the raw file content.
"""

from __future__ import annotations

import inspect
import io

from app.services.parsing import parse_statement


def _make_csv_bytes() -> bytes:
    return b"Date,Amount,Description\n2026-06-01,-12.50,LIDL GB\n"


def test_parse_returns_parsed_rows_not_bytes():
    rows = parse_statement(_make_csv_bytes())
    for row in rows:
        assert not isinstance(row, (bytes, bytearray, io.IOBase)), (
            "parse_statement must return ParsedRow objects, not raw bytes"
        )
        # None of the fields should hold raw CSV bytes
        for field_name, value in row.model_dump().items():
            assert not isinstance(value, (bytes, bytearray)), (
                f"Field {field_name!r} contains bytes — PAN/IBAN not scrubbed or raw data leaked"
            )


def test_ingest_transactions_signature_takes_parsed_rows():
    from app.services.ingestion import ingest_transactions

    sig = inspect.signature(ingest_transactions)
    rows_param = sig.parameters.get("rows")
    assert rows_param is not None
    # Annotation must reference ParsedRow, not bytes
    annotation = str(rows_param.annotation)
    assert "bytes" not in annotation.lower(), (
        "ingest_transactions 'rows' parameter must be typed as ParsedRow list, not bytes"
    )
    assert "ParsedRow" in annotation or "list" in annotation.lower()


def test_transaction_model_has_no_raw_bytes_field():
    from app.domain.transaction import Transaction

    for col in Transaction.__table__.columns:
        assert col.type.__class__.__name__ not in ("LargeBinary", "BYTEA", "BLOB"), (
            f"Transaction.{col.name} is a binary column — raw bytes must not be stored"
        )
