# Authentication

`auth(apikey=None, *, base_url=DEFAULT_BASE_URL, store=None)` exchanges a long-lived API key for a
JWT. Omit `apikey` to read `QTSURFER_APIKEY`. The default base URL is the production API, and the
default token store is in-memory.

```python
from qtsurfer_sdk import auth

session = auth()  # reads QTSURFER_APIKEY
session = auth("ak_...", base_url="https://api.qtsurfer.net/v1")
```

The session refreshes once after a `401` and retries that request once. A second failure surfaces to
the caller.

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

## Call a generated endpoint

`session.call(fn)` applies the same refresh-on-401 policy when the SDK has no high-level wrapper.
Binary download responses must be consumed as bytes rather than parsed as JSON.

```python
from qtsurfer.api.client._generated.api.exchange import download_tickers

response = session.call(lambda client: download_tickers.sync_detailed(
    "binance", "BTC", "USDT", client=client
))
payload = response.content
```
