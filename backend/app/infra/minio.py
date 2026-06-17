"""MinIO adapter for model artifacts ONLY — never user data or raw statement files (constitution Art. II).

Artifacts are content-addressed: bucket key = categorizer/<sha256>/<filename>.
The trainer uploads; the model-server downloads by SHA. The backend never reads
artifact bytes directly — it passes the SHA to the model-server /reload endpoint.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import structlog
from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings

log = structlog.get_logger(__name__)

_ARTIFACT_FILES = ("categorizer.onnx", "tokenizer.json", "model_card.json")


def _get_client() -> Minio:
    settings = get_settings()
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_root_user,
        secret_key=settings.minio_root_password,
        secure=False,
    )


def _ensure_bucket(client: Minio, bucket: str) -> None:
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        log.info("minio.bucket.created", bucket=bucket)


def upload_artifact(sha256: str, files: dict[str, bytes]) -> None:
    """Upload artifact files for a given SHA to MinIO.

    Args:
        sha256: Content hash of the ONNX model file — used as the bucket key prefix.
        files: Mapping of filename → bytes. Expected keys: categorizer.onnx,
               tokenizer.json, model_card.json (the trainer builds this dict).
    """
    settings = get_settings()
    client = _get_client()
    _ensure_bucket(client, settings.minio_artifacts_bucket)

    for filename, data in files.items():
        key = f"categorizer/{sha256}/{filename}"
        client.put_object(
            settings.minio_artifacts_bucket,
            key,
            io.BytesIO(data),
            length=len(data),
        )
        log.info("minio.artifact.uploaded", sha256=sha256, key=key)


def download_artifact(sha256: str, dest_dir: Path) -> dict[str, Path]:
    """Download all artifact files for a given SHA to dest_dir.

    Returns:
        Mapping of filename → local Path.

    Raises:
        S3Error: if any artifact file is missing in MinIO.
    """
    settings = get_settings()
    client = _get_client()
    dest_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}
    for filename in _ARTIFACT_FILES:
        key = f"categorizer/{sha256}/{filename}"
        local_path = dest_dir / filename
        try:
            client.fget_object(settings.minio_artifacts_bucket, key, str(local_path))
            paths[filename] = local_path
            log.info("minio.artifact.downloaded", sha256=sha256, key=key)
        except S3Error as exc:
            log.error("minio.artifact.missing", sha256=sha256, key=key, error=str(exc))
            raise
    return paths


def load_model_card(sha256: str) -> dict:
    """Fetch and parse model_card.json for a given artifact SHA from MinIO.

    The model card carries holdout metrics AND the drift reference
    (training category histogram + normalized-merchant set).
    """
    settings = get_settings()
    client = _get_client()
    key = f"categorizer/{sha256}/model_card.json"
    try:
        response = client.get_object(settings.minio_artifacts_bucket, key)
        data = json.loads(response.read())
        log.info("minio.model_card.loaded", sha256=sha256)
        return data
    except S3Error as exc:
        log.error("minio.model_card.missing", sha256=sha256, error=str(exc))
        raise
