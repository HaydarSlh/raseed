# Backend image (also used by the `worker` and one-shot `migrate` services).
# Lean Python base; NO torch here — the trainer is the single heavy image (Art. III).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first for layer caching.
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

# Copy application code.
COPY . .

EXPOSE 8000

# Boot the empty app; compose overrides the command for migrate/worker.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
