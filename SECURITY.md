# Security Policy

## Secret Management

All secrets (API keys, database passwords, JWT secrets, Slack webhook URLs, Vault tokens)
are resolved from **HashiCorp Vault** at application startup. No secret is hardcoded in
source code or committed to the repository.

The application startup configuration (`app/core/config.py`) uses pydantic-settings with
`extra='forbid'` and fails immediately on startup if a required secret is missing from Vault.

A CI gate (Gate #6) runs `detect-secrets` on every pull request and blocks merge if any
secret pattern is detected in application source, prompts, or frontend code. The baseline
of known false positives is committed at `.secrets.baseline`.

**For local development**: copy `.env.example` to `.env` and fill in test values. The `.env`
file is in `.gitignore` and must never be committed.

## PII Redaction Boundary

The following personally-identifiable information patterns are redacted **in-process** before
any text reaches the LLM, any log line, or any external trace:

| Pattern | Replaced with |
|---------|---------------|
| Credit/debit card numbers (PAN, 13–19 digits) | `[REDACTED-CARD]` |
| IBAN account numbers | `[REDACTED-IBAN]` |
| UK phone numbers (`+44` or `07…` format) | `[REDACTED-PHONE]` |
| Email addresses | `[REDACTED-EMAIL]` |
| API keys matching `sk-…` pattern | `[REDACTED-KEY]` |
| Google API keys matching `AIza…` pattern | `[REDACTED-KEY]` |

Redaction is applied by `backend/app/services/agent/rails.py:redact()` at the call sites in
`backend/app/api/chat.py`, before the message is forwarded to the LLM or appended to session
memory. Raw statement files are never persisted (parsed in-memory, PAN/IBAN scrubbed in the
parser before anything reaches a database).

## Model Unlearning Limitation

When a user requests account deletion (right-to-erasure), all their data is hard-deleted from
every persistent store — transactions, corrections, goals, memories, pgvector embeddings, and
Redis sessions. An erasure audit record is retained for operator compliance review.

**However**: if a user's category corrections were used in a model that has already been
retrained and promoted to champion, those corrections are incorporated into the model's
weights. Removing specific examples from a trained neural-network model requires a full
retraining cycle on data that excludes those examples ("machine unlearning"), which is not
currently implemented.

**What this means in practice**: After erasure, your data no longer exists in any database
or session store. The trained model's behavior may still be subtly influenced by patterns in
your historical corrections, but no personally-identifiable information is accessible or
stored. If you need assurance of full model unlearning, please contact us (see below) to
request a full model retrain cycle that excludes your data.

## Reporting a Vulnerability

If you discover a security vulnerability in Raseed, please report it responsibly:

**Email**: salehaidar64@gmail.com

**Subject**: `[SECURITY] <brief description>`

**Response SLA**:
- Acknowledgement within **48 hours**
- Initial triage within **5 business days**
- Fix timeline communicated within **10 business days** of confirmed triage

Please include:
- A description of the vulnerability and its potential impact
- Steps to reproduce (proof of concept if possible)
- Your contact information for follow-up

We ask that you do not publicly disclose the vulnerability until we have had a reasonable
opportunity to investigate and release a fix. We appreciate responsible disclosure and will
credit researchers who follow this process.
