"""Application-level errors with stable API codes."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Error that is safe to expose to API clients."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 422,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.context = context or {}
