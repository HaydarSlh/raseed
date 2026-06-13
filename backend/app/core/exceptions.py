"""Domain exception hierarchy mapped to structured HTTP errors; users never see a stack trace (constitution Art. I)."""

from __future__ import annotations


class RaseedError(Exception):
    """Base for all domain errors. Each subclass carries an HTTP status and a safe,
    user-facing message; the API layer maps these to structured error responses."""

    status_code: int = 500
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        if message:
            self.message = message


class NotFoundError(RaseedError):
    status_code = 404
    message = "Resource not found."


class ValidationError(RaseedError):
    status_code = 422
    message = "Invalid request."


class AuthError(RaseedError):
    status_code = 401
    message = "Authentication required."


class PermissionError(RaseedError):  # noqa: A001 - domain-specific, distinct from builtin
    status_code = 403
    message = "Not permitted."


class RateLimitError(RaseedError):
    status_code = 429
    message = "Too many requests."


class UpstreamError(RaseedError):
    status_code = 502
    message = "Upstream dependency failed."
