# Authentication

`auth(apikey=None, *, base_url=DEFAULT_BASE_URL, store=None)` exchanges a long-lived API key for a
JWT. Omit `apikey` to read `QTSURFER_APIKEY`. The default base URL is the staging beta API, and the
default token store is in-memory.

```python
from qtsurfer_sdk import auth

session = auth()  # reads QTSURFER_APIKEY
session = auth("ak_...", base_url="https://api.qtsurfer.net/v1")
```

The session refreshes once after a `401` and retries that request once. A second failure surfaces to
the caller.

A deployment that requires scopes refuses an otherwise valid key with none at token exchange:
`QTSAuthError.status == 403`, `.code == AuthTokenErrorCode.APIKEY_WITHOUT_SCOPES`
(`apikey_without_scopes`). The exception's `.message` preserves the server's exact explanation;
`str(error)` also includes HTTP context. No token is minted or saved, and the SDK does not retry
that rejection. Create an API key with at least one scope in the web app and use the new key.
This also applies if a token refresh fails during another request: the original operation is not
retried after the rejected refresh.

```python
from qtsurfer_sdk import AuthTokenErrorCode, QTSAuthError, auth

try:
    session = auth()
except QTSAuthError as error:
    if error.code == AuthTokenErrorCode.APIKEY_WITHOUT_SCOPES:
        print("Create an API key with at least one scope in the web app.")
    raise
```

## Manage token storage

Pass a `TokenStore` implementation to load, save, and clear JWTs in the application's chosen store.
The application owns that store's security policy.

```python
from qtsurfer_sdk import InMemoryTokenStore

session = auth(store=InMemoryTokenStore())
token = session.ensure_token()
refreshed = session.refresh()
session.clear()
```

`ensure_token()` reuses memory or stored state, `refresh()` always exchanges the API key again, and
`clear()` clears the cache and configured store.

The token's optional `scopes` is a `KeyScopes` resource-to-actions map, for example
`{"backtests": ["read", "write", "execute"], "exchanges": ["read"]}`. An empty map
means no scopes. Each listed resource has at least one action: a scope is a resource and
an action. Inspect `token.scopes.to_dict()` when present; the same map is required
on `session.get_account().scopes`. Protected operations enforce their required scopes and return
`403 insufficient_scope` when the key lacks one. Custom token stores should persist `token.to_dict()` and
restore with `AuthTokenResponse.from_dict(...)`, preserving the entire map and tier.
Historical stored `scopes: []` is read as the empty map and saved back as `{}`.

## Call a generated endpoint

`session.call(fn)` applies the same refresh-on-401 policy when the SDK has no high-level wrapper.
Binary download responses must be consumed as bytes rather than parsed as JSON.
An operation-level scope refusal is not refreshed or retried: catch `QTSInsufficientScopeError`,
inspect its `required` scope, and grant that scope to the API key before retrying.

```python
from datetime import UTC, datetime, timedelta
from qtsurfer.api.client.api.exchange import download_tickers

response = session.call(
    lambda client: download_tickers.sync_detailed(
        "binance",
        "BTC",
        "USDT",
        client=client,
        hour=(datetime.now(UTC) - timedelta(hours=1)).strftime("%Y-%m-%dT%H"),
    )
)
payload = response.content
```
