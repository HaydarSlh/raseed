"""Agent tools package.

Importing this package registers every tool with the registry (each module calls
register_tool at import time). The agent loop imports the registry via this package,
so these side-effect imports must run for dispatch() to find any tool.
"""

# noqa: F401 — imported for their register_tool side effects.
from app.services.agent.tools import (  # noqa: F401
    analysis,
    goals,
    knowledge,
    memory,
    reads,
    writes,
)
