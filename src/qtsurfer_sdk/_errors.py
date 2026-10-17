"""SDK error hierarchy.

Mirrors the conventions used by the Java / TypeScript SDKs so error
handling looks idiomatic across the three languages:

* ``QTSError`` is the catch-all base.
* ``QTSAuthError`` covers missing-apikey and JWT-exchange failures.
* ``QTSUploadError`` covers credential-free dataset uploads.
"""

from __future__ import annotations

from qtsurfer.api.client.models import AuthTokenErrorCode, ErrorNextCall


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
        reason: str | None = None,
        next_call: ErrorNextCall | None = None,
        retry_after: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.reason = reason
        self.next_call = next_call
        self.retry_after = retry_after
        if cause is not None:
            self.__cause__ = cause


class QTSAuthError(QTSError):
    """Raised when ``auth()`` cannot obtain a JWT.

    Triggered by:

    * No API key supplied (neither argument nor ``QTSURFER_APIKEY`` env var).
    * ``POST /v1/auth/token`` returned a 4xx (401 for an invalid, revoked or
      expired key; 403 ``apikey_without_scopes`` where scopes are required).
    * The endpoint returned a 2xx but the body was empty or undecodeable.
    """

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        cause: BaseException | None = None,
        reason: str | None = None,
        next_call: ErrorNextCall | None = None,
        retry_after: str | None = None,
        code: AuthTokenErrorCode | None = None,
        server_message: str | None = None,
    ) -> None:
        """Keep the typed authentication code and the server's exact message.

        ``apikey_without_scopes`` needs a replacement key with scopes from the
        web app. It is not retried automatically. ``message`` retains the HTTP
        context in ``str(error)``; ``error.message`` is the server text when present.
        """
        super().__init__(
            message,
            status=status,
            cause=cause,
            reason=reason,
            next_call=next_call,
            retry_after=retry_after,
        )
        self.code = code
        self.message = server_message if server_message is not None else message


class QTSCompileError(QTSError):
    """Raised when ``POST /strategy`` cannot compile/register a strategy."""


class QTSPreparationError(QTSError):
    """Raised when preparing market data (``prepare_backtest``) fails."""


class QTSExecutionError(QTSError):
    """Raised when a backtest/sweep execution fails or errors mid-run."""


class QTSTimeoutError(QTSError):
    """Raised when a poll loop reaches its deadline before a job resolves."""


class QTSCanceledError(QTSError):
    """Raised when an in-flight run is canceled (or the caller aborts)."""


class QTSDownloadError(QTSError):
    """Raised when downloading tickers/klines fails."""


class QTSUploadError(QTSError):
    """Raised when a direct dataset upload fails without exposing its presigned URL."""


class QTSLiveSignalCursorExpiredError(QTSError):
    """Raised when retention has removed the position addressed by a signal cursor."""

    def __init__(self, message: str, *, available_since_ms: int | None = None) -> None:
        super().__init__(message, status=410)
        self.available_since_ms = available_since_ms
