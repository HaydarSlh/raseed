# Heavy trainer image (torch). Built ONLY under the `training` compose profile —
# never part of a default `docker compose up`, never on a request path (Art. III).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

COPY . .

CMD ["python", "train.py"]
