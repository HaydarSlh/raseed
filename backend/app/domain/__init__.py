"""Domain layer: pure Pydantic models and value objects. No imports from api/services/repositories/infra (constitution Art. I)."""

# Import all models so that Alembic autogenerate and SQLAlchemy metadata can discover them.
from app.domain.audit import AuditLog  # noqa: F401
from app.domain.correction import Correction  # noqa: F401
from app.domain.drift_signal import DriftSignal  # noqa: F401
from app.domain.erasure_audit import ErasureAudit  # noqa: F401
from app.domain.goal import Goal  # noqa: F401
from app.domain.knowledge import KnowledgeDocument, KnowledgePassage  # noqa: F401
from app.domain.memory import Memory  # noqa: F401
from app.domain.model_registry import ModelRegistry  # noqa: F401
from app.domain.retrain_run import RetrainRun  # noqa: F401
from app.domain.transaction import Transaction  # noqa: F401
from app.domain.user import User  # noqa: F401
from app.domain.user_settings import UserSettings  # noqa: F401
