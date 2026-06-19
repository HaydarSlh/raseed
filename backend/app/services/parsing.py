"""Statement parser: reads CSV-class file bytes in-memory, scrubs PAN/IBAN, yields
ParsedRow instances. Raw bytes never hit disk or MinIO (constitution Art. II).

Supported formats (v1): bank CSV exports with column aliases for date/amount/description.
"""

from __future__ import annotations

import io
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

import pandas as pd

from app.schemas.ingestion import ParsedRow

# Regex patterns for PAN (card numbers) and IBAN — scrubbed before returning rows.
_PAN_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{4,30}\b")
_SCRUB = "[REDACTED]"

# Column aliases: any of these names (case-insensitive) map to a canonical field.
_DATE_COLS = {"date", "transaction date", "value date", "valuedate", "trx date", "date posted"}
_AMOUNT_COLS = {"amount", "transaction amount", "debit/credit", "value", "net amount"}
_DESC_COLS = {"description", "transaction description", "details", "narration", "memo", "particulars"}
_MERCHANT_COLS = {"merchant", "payee", "merchant name", "beneficiary"}
_CURRENCY_COLS = {"currency", "ccy"}


def _scrub(text: str) -> str:
    text = _PAN_RE.sub(_SCRUB, text)
    return _IBAN_RE.sub(_SCRUB, text)


def _find_col(df_cols: list[str], aliases: set[str]) -> str | None:
    lower = {c.lower(): c for c in df_cols}
    for alias in aliases:
        if alias in lower:
            return lower[alias]
    return None


def _parse_amount(raw: str | float | int) -> Decimal:
    """Convert CSV cell to a signed Decimal (negative = debit)."""
    if isinstance(raw, (int, float)):
        return Decimal(str(raw))
    cleaned = str(raw).replace(",", "").replace(" ", "").strip()
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"Cannot parse amount: {raw!r}") from exc


def _parse_date(raw: str | datetime) -> datetime:
    if isinstance(raw, datetime):
        return raw
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%d %b %Y", "%Y%m%d"):
        try:
            return datetime.strptime(str(raw).strip(), fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {raw!r}")


def parse_statement(file_bytes: bytes, filename: str = "") -> list[ParsedRow]:
    """Parse a CSV-class statement from raw bytes and return scrubbed ParsedRow list.

    Raises ValueError for unrecognisable formats so callers can surface a user-friendly
    error without crashing the ingestion pipeline.
    """
    try:
        df = pd.read_csv(io.BytesIO(file_bytes))
    except Exception as exc:
        raise ValueError(f"Cannot read CSV: {exc}") from exc

    cols = list(df.columns)
    date_col = _find_col(cols, _DATE_COLS)
    amount_col = _find_col(cols, _AMOUNT_COLS)
    desc_col = _find_col(cols, _DESC_COLS)
    merchant_col = _find_col(cols, _MERCHANT_COLS)
    currency_col = _find_col(cols, _CURRENCY_COLS)

    if date_col is None or amount_col is None or desc_col is None:
        raise ValueError(
            f"Could not identify required columns (date/amount/description) in {filename!r}. "
            f"Found: {cols}"
        )

    rows: list[ParsedRow] = []
    for _, row in df.iterrows():
        try:
            occurred_at = _parse_date(row[date_col])
            amount = _parse_amount(row[amount_col])
            description = _scrub(str(row[desc_col]).strip())
            merchant = _scrub(str(row[merchant_col]).strip()) if merchant_col else None
            currency = str(row[currency_col]).strip() if currency_col else "USD"
        except (ValueError, KeyError):
            continue  # skip unparseable rows; caller sees them in needs_review count

        rows.append(
            ParsedRow(
                occurred_at=occurred_at,
                amount=amount,
                description=description,
                merchant=merchant if merchant else None,
                currency=currency,
            )
        )

    return rows
