"""QTSurfer Python SDK.

Public surface::

    from qtsurfer_sdk import auth, AuthenticatedSession, TokenStore, InMemoryTokenStore
    from qtsurfer_sdk import QTSAuthError, QTSError

The :func:`auth` helper is the recommended entry point: one call exchanges
a long-lived API key for a short-lived JWT and returns an
:class:`AuthenticatedSession` that transparently refreshes the JWT on 401.
"""

from qtsurfer_sdk._errors import QTSAuthError, QTSError
from qtsurfer_sdk._session import APIKEY_ENV_VAR, AuthenticatedSession, auth
from qtsurfer_sdk._tokens import InMemoryTokenStore, TokenStore

__all__ = [
    "APIKEY_ENV_VAR",
    "AuthenticatedSession",
    "InMemoryTokenStore",
    "QTSAuthError",
    "QTSError",
    "TokenStore",
    "auth",
]
