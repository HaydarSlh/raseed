# Data Model: Dashboard UI

The frontend owns no persistent data. These are the **view models** the SPA holds in
component state, each mapped one-to-one from a Phase 3 backend response. Field names and
types mirror the actual backend Pydantic response models (see
[contracts/ui-api-contract.md](./contracts/ui-api-contract.md)) so the TypeScript types
in `src/api/types.ts` stay faithful to the wire format.

## TransactionView

Source: `GET /dashboard` → `transactions[]` (backend `TransactionOut`).

| Field | Type | Notes |
|-------|------|-------|
| `id` | `string` (UUID) | React list key. |
| `txn_date` | `string \| null` | ISO datetime; backend field is `txn_date` (← `occurred_at`). Render as date; null renders as "—". |
| `amount` | `number \| null` | Signed; negative = spend, positive = income. |
| `category` | `string \| null` | Read-only badge; null/empty → "uncategorized". |
| `confidence` | `number \| null` | 0–1 model confidence; may inform a tooltip. |
| `provenance` | `string` | `rule` \| `model` (also `llm`/`human` possible later). Drives the source chip. |
| `needs_review` | `boolean` | Drives the amber review indicator. |
| `is_anomaly` | `boolean` | Drives the row highlight; cross-references AnomalyView. |

**Display rules**: sorted by `txn_date` descending; anomalous rows visually
distinguished; `needs_review` rows carry a distinct indicator; category shown read-only.

## ForecastView

Source: `GET /dashboard` → `forecast` (backend `ForecastOut`).

| Field | Type | Notes |
|-------|------|-------|
| `horizon_days` | `number` | Typically 30. |
| `is_cold_start` | `boolean` | True → render the "not enough history yet" notice, not the chart. |
| `points` | `ForecastPointView[]` | Empty when cold-start. |

### ForecastPointView

| Field | Type | Notes |
|-------|------|-------|
| `date` | `string` (ISO date) | Chart X axis. |
| `projected_balance` | `number` | Chart Y axis (single line). |
| `lower` | `number` | Present in payload; unused in v1 (uncertainty band out of scope). |
| `upper` | `number` | Present in payload; unused in v1. |

**Display rules**: when `is_cold_start` is true OR `points` is empty, show the cold-start
notice; otherwise plot `projected_balance` over `date`.

## AnomalyView

Source: `GET /dashboard` → `anomalies[]` (backend `AnomalyOut`).

| Field | Type | Notes |
|-------|------|-------|
| `transaction_id` | `string` (UUID) | Links back to a TransactionView row. |
| `anomaly_type` | `string` | e.g. `statistical_outlier`, `duplicate_charge` — shown as a human label. |
| `reason` | `string` | Short explanation for the panel. |

**Display rules**: listed in a collapsible panel labeled by type; the referenced
transaction row is highlighted in the main table.

## SubscriptionView

Source: `GET /dashboard` → `subscriptions[]` (backend `SubscriptionOut`).

| Field | Type | Notes |
|-------|------|-------|
| `merchant` | `string` | Card title. |
| `cadence` | `string` | e.g. `monthly`, `weekly`, `yearly`. |
| `typical_amount` | `number` | Shown on the card. |
| `next_charge_date` | `string \| null` | ISO date or null. |
| `price_increase` | `boolean` | Drives a "price increased" badge. |

**Display rules**: one card per subscription; price-increase badge when true.

## UploadResultView

Source: `POST /uploads` response (backend `UploadResponse`).

| Field | Type | Notes |
|-------|------|-------|
| `ingested` | `number` | "N imported". |
| `needs_review` | `number` | "M flagged for review". |
| `duplicates_skipped` | `number` | Drives the "nothing new imported" message when `ingested == 0`. |
| `recompute_enqueued` | `boolean` | Whether derived data will refresh shortly. |

## ManualEntryInput

Source: form state → `POST /transactions` body (backend `ManualTransactionRequest`).

| Field | Type | Validation |
|-------|------|------------|
| `txn_date` | `string` (date) | Required. |
| `amount` | `number` | Required; non-zero (backend rejects 0). |
| `description` | `string` | Required; 1–1024 chars. |
| `merchant` | `string \| null` | Optional. |
| `currency` | `string` | Defaults to `GBP`. |

**Validation rules**: submit disabled until `txn_date`, `amount` (non-zero), and
`description` are present (FR-006). A duplicate entry returns backend `409` → surfaced
as a readable "already recorded" message.

## Relationships

- `AnomalyView.transaction_id` references `TransactionView.id` (highlight cross-link).
- `TransactionView.is_anomaly` is the denormalized flag the table uses directly, so the
  table needs no join against `anomalies[]` to highlight rows.
- All four collections arrive together in the single `GET /dashboard` payload; the SPA
  fetches once and distributes them to the panels.
