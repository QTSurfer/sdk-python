# Authentication

`auth()` exchanges an API key for a short-lived JWT. The returned
`AuthenticatedSession` keeps it in memory by default, refreshes once after a `401`, and retries
the failed call once.

```python
from qtsurfer_sdk import auth

session = auth()  # reads QTSURFER_APIKEY
# Or: session = auth("ak_...")
```

Pass `base_url` or a `TokenStore` when the default environment and in-memory storage do not suit
the application. The store owns its security policy. `session.client` remains available for an
explicit generated-client call through `session.call(...)`.
