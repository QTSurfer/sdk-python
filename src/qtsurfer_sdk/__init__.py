"""QTSurfer Python SDK.

Public surface::

    from qtsurfer_sdk import auth, AuthenticatedSession, TokenStore, InMemoryTokenStore
    from qtsurfer_sdk import QTSAuthError, QTSError

The :func:`auth` helper is the recommended entry point: one call exchanges
a long-lived API key for a short-lived JWT and returns an
:class:`AuthenticatedSession` that transparently refreshes the JWT on 401.
"""

from qtsurfer.api.client.models import (
    AuthTokenErrorCode,
    EquityCurveOutMode,
    ErrorNextCall,
    GetLiveRunPaperEquityMeasure,
    InstrumentCatalogueResponse,
    InstrumentListResponse,
    InsufficientScopeErrorCode,
    KeyScopes,
    LivePaperConfigAccounts,
    LivePaperEquityCurve,
    PoolDetail,
    PoolListResponse,
)

from qtsurfer_sdk._errors import (
    QTSAuthError,
    QTSCanceledError,
    QTSCompileError,
    QTSDownloadError,
    QTSError,
    QTSExecutionError,
    QTSInsufficientScopeError,
    QTSLiveSignalCursorExpiredError,
    QTSPreparationError,
    QTSTimeoutError,
    QTSUploadError,
)
from qtsurfer_sdk._session import APIKEY_ENV_VAR, AuthenticatedSession, auth
from qtsurfer_sdk._tokens import InMemoryTokenStore, TokenStore

__all__ = [
    "APIKEY_ENV_VAR",
    "AuthenticatedSession",
    "AuthTokenErrorCode",
    "EquityCurveOutMode",
    "ErrorNextCall",
    "GetLiveRunPaperEquityMeasure",
    "InstrumentCatalogueResponse",
    "InstrumentListResponse",
    "InsufficientScopeErrorCode",
    "InMemoryTokenStore",
    "KeyScopes",
    "LivePaperConfigAccounts",
    "LivePaperEquityCurve",
    "PoolDetail",
    "PoolListResponse",
    "QTSAuthError",
    "QTSCanceledError",
    "QTSCompileError",
    "QTSDownloadError",
    "QTSError",
    "QTSExecutionError",
    "QTSInsufficientScopeError",
    "QTSLiveSignalCursorExpiredError",
    "QTSPreparationError",
    "QTSTimeoutError",
    "QTSUploadError",
    "TokenStore",
    "auth",
]
