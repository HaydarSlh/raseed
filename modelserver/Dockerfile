# Lean serving image — onnxruntime + numpy + tokenizers only, NO torch (constitution Art. III).
# Build context: modelserver/ directory.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# ONNX StringNormalizer requires en_US.UTF-8 locale (used by TF-IDF lowercase op).
RUN apt-get update -qq && apt-get install -y --no-install-recommends locales \
    && sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen \
    && locale-gen \
    && rm -rf /var/lib/apt/lists/*

ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8

# Install serving deps.
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Put source as a proper modelserver/ package so "from modelserver.X import" works.
COPY . modelserver/
RUN touch modelserver/__init__.py

# Artifacts directory (real .onnx is in modelserver/artifacts/ from the COPY above).
RUN mkdir -p artifacts

EXPOSE 8080

CMD ["uvicorn", "modelserver.app:app", "--host", "0.0.0.0", "--port", "8080"]
