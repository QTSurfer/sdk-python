# qtsurfer-sdk

<p align="center">
  <a href="https://pypi.org/project/qtsurfer-sdk/"><img src="https://img.shields.io/pypi/v/qtsurfer-sdk.svg" alt="PyPI"></a>
  <img src="https://img.shields.io/pypi/pyversions/qtsurfer-sdk.svg" alt="Python versions">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License"></a>
</p>

Opinionated Python SDK for [QTSurfer](https://qtsurfer.com), built on top of [`qtsurfer-api-client`](https://github.com/QTSurfer/api-client-python).

Where `qtsurfer-api-client` gives you one function per API endpoint, this package adds **auth helpers**, **token refresh**, and **pluggable token storage** — go from an API key to a typed API call in two lines.

> The strategy code itself stays on the JVM — QTSurfer's backtest engine is Java. This SDK is for orchestration: minting tokens, calling endpoints, processing results.

## Installation

```bash
pip install qtsurfer-sdk
# or, with uv:
uv add qtsurfer-sdk
```

Requires Python 3.11+.

The transitive [`qtsurfer-api-client`](https://github.com/QTSurfer/api-client-python) (auto-generated from the OpenAPI spec) comes along automatically.

> **Import path**: this package imports as `qtsurfer_sdk` (sibling to the auto-generated `qtsurfer.api.client.*` tree). Two top-level names keep the SDK and the raw client cleanly separate and avoid Python's regular-vs-namespace-package quirks.

## Quick start

One call: API key in, ready-to-use session out. JWT refresh on 401 is handled for you.

```python
from qtsurfer.api.client._generated.api.exchange import get_exchanges
from qtsurfer_sdk import auth

# Reads QTSURFER_APIKEY from env when no argument is passed.
session = auth()
# Or: session = auth("ak_...")

# Use any qtsurfer-api-client function via session.call — refresh-on-401
# is wired in for you.
exchanges = session.call(lambda c: get_exchanges.sync(client=c))
for ex in exchanges:
    print(ex.id, ex.name)
```

### Environment

| Variable          | Purpose                                       |
| ----------------- | --------------------------------------------- |
| `QTSURFER_APIKEY` | API key consumed by `auth()` when no arg is passed |

### Pluggable token storage

Tokens are kept in memory by default. Implement `TokenStore` (a `Protocol`) to back tokens by an on-disk file, a secret manager, or a desktop keychain:

```python
import json
from pathlib import Path

from qtsurfer.api.client._generated.models import AuthTokenResponse
from qtsurfer_sdk import TokenStore, auth


class FileStore(TokenStore):
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> AuthTokenResponse | None:
        if not self.path.exists():
            return None
        return AuthTokenResponse.from_dict(json.loads(self.path.read_text()))

    def save(self, token: AuthTokenResponse) -> None:
        self.path.write_text(json.dumps(token.to_dict()))

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)


session = auth(store=FileStore(Path.home() / ".qtsurfer" / "token.json"))
```

### Refresh-on-401

Wrap any api-client call in `session.call(fn)` and the SDK handles the 401 → refresh → retry dance for you. Use `*_detailed` variants when you want to inspect the raw `Response`:

```python
from qtsurfer.api.client._generated.api.exchange import get_instruments

# Plain sync — refresh happens transparently on a single 401.
instruments = session.call(lambda c: get_instruments.sync(client=c, exchange_id="binance"))

# Detailed sync — same refresh semantics, but the wrapper inspects
# response.status_code instead of relying on an exception.
resp = session.call(lambda c: get_instruments.sync_detailed(client=c, exchange_id="binance"))
print(resp.status_code, resp.parsed)
```

A second 401 after the refresh is surfaced to the caller as-is — no retry loops.

## Error hierarchy

```python
from qtsurfer_sdk import QTSAuthError, QTSError

try:
    session = auth()
except QTSAuthError as exc:
    print(f"auth failed: {exc}")
```

* `QTSError` — base class for all SDK errors.
* `QTSAuthError` — missing apikey, invalid apikey, or non-2xx from `POST /v1/auth/token`.

## Roadmap

* **v0.1 — auth helper ✅** (this release)
* **v0.2 — workflow orchestration** (`session.backtest(...)`, `session.tickers(...)`, `session.klines(...)`) matching the Java/TS SDK surface
* **v0.3 — async overload** mirroring `*_asyncio` API-client variants
* **v0.4 — domain handles** (`Strategy`, `Backtest`) with progress callbacks

## License

Apache-2.0 — see [LICENSE](./LICENSE).
