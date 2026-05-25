"""SDK error hierarchy.

Mirrors the conventions used by the Java / TypeScript SDKs so error
handling looks idiomatic across the three languages:

* ``QTSError`` is the catch-all base.
* ``QTSAuthError`` covers missing-apikey and JWT-exchange failures.

Additional subclasses (download / preparation / execution) will land as
the SDK gains workflow surface in future minor releases.
"""

from __future__ import annotations


class QTSError(Exception):
    """Root of the QTSurfer SDK exception hierarchy.

    Carries an optional HTTP status code (when the underlying transport
    surfaced one) to make refresh-on-401 and custom error handling easy.
    """

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        if cause is not None:
            self.__cause__ = cause


class QTSAuthError(QTSError):
    """Raised when ``auth()`` cannot obtain a JWT.

    Triggered by:

    * No API key supplied (neither argument nor ``QTSURFER_APIKEY`` env var).
    * ``POST /v1/auth/token`` returned a 4xx (typically 401 — invalid /
      revoked / expired apikey).
    * The endpoint returned a 2xx but the body was empty or undecodeable.
    """
