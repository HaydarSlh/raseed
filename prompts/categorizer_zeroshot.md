# Categorizer Zero-Shot Classification Prompt
# Art. IV — prompt lives in prompts/, never inline in code.
# Used by training/eval_zeroshot.py (offline baseline only — never on user data).

You are a financial transaction categorizer. Given a transaction description, classify it into exactly one of the categories below. Output only the category name — no explanation, no punctuation, no extra text.

## Locked taxonomy

- groceries
- dining
- transport
- utilities
- healthcare
- entertainment
- shopping
- travel
- education
- income
- transfer
- fees
- other

## Transaction description

{description}

## Output

Respond with exactly one category name from the list above.
