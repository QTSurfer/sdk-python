# qtsurfer-sdk

<p align="center">
  <a href="https://pypi.org/project/qtsurfer-sdk/"><img src="https://img.shields.io/pypi/v/qtsurfer-sdk.svg" alt="PyPI"></a>
  <img src="https://img.shields.io/pypi/pyversions/qtsurfer-sdk.svg" alt="Python versions">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License"></a>
</p>

Opinionated Python SDK for [QTSurfer](https://qtsurfer.com), built on top of
[`qtsurfer-api-client`](https://github.com/QTSurfer/api-client-python).

Where `qtsurfer-api-client` gives you one function per API endpoint, this package
adds **auth helpers**, **token refresh**, **pluggable token storage**, and
**high-level workflows** (strategies, backtest, sweep, datasets) — go from an API
key to a typed backtest in a few lines.

> The strategy code itself stays on the JVM — QTSurfer's backtest engine is Java.
> This SDK is for orchestration: minting tokens, calling endpoints, processing results.

## Installation

```bash
pip install qtsurfer-sdk
# or, with uv:
uv add qtsurfer-sdk
```

Requires Python 3.11+. The transitive [`qtsurfer-api-client`](https://github.com/QTSurfer/api-client-python)
(auto-generated from the OpenAPI spec) comes along automatically.

> **Import path**: this package imports as `qtsurfer_sdk` (sibling to the
> auto-generated `qtsurfer.api.client.*` tree). Two top-level names keep the SDK
> and the raw client cleanly separate.

## Quick start

```python
from qtsurfer_sdk import auth

# Reads QTSURFER_APIKEY from env when no argument is passed.
session = auth()

# Or point at a different API base (defaults to production):
# session = auth("ak_...", base_url="https://api.qtsurfer.net/v1")

exchanges = session.exchanges()
for ex in exchanges:
    print(ex.id, ex.name)
```

JWT refresh on 401 is handled for you (refresh once, retry once).

## Workflows

The SDK exposes a workflow surface mirroring `sdk-java` / `sdk-ts`. Every method
is routed through the session (refresh-on-401) and returns the api-client's
typed model objects.

### Strategy

```python
src = '''public class EmaCross extends AbstractTickerStrategy { ... }'''

comp = session.compile_strategy(src)       # {"strategyId": "...", "declaredProperties": [...]}
sid = comp["strategyId"]

session.validate_strategy(sid)             # 202/pending or already-recorded verdict
state = session.strategy_state(sid)        # validation, notices, requiredSources
session.list_strategies()                  # your registered strategies
code = session.get_strategy_code(sid)      # read back the exact source
session.delete_strategy(sid)               # release it
```

### Catalog

```python
session.exchanges()                                   # [Exchange, ...]
session.instruments("binance")                        # 1876 instruments
session.instruments("binance", segment="spot")        # a specific segment
```

### Backtest

```python
# 1. prepare a data window -> a job id
acc = session.prepare(
    exchange_id="binance", type_="ticker",
    instrument="BTC/USDT", from_="2026-08-18", to="2026-08-19",
)
pid = acc.job_id

# 2. poll until Completed
import time
while True:
    st = session.prepare_status(exchange_id="binance", type_="ticker", job_id=pid)
    if st.status == "Completed":
        break
    time.sleep(3)

# 3. execute a compiled strategy over the prepared window
ex = session.execute(
    exchange_id="binance", type_="ticker",
    prepare_job_id=pid, strategy_id=sid,
)
jid = ex.job_id

# 4. poll the result (202-while-running; read state.status + results when 200)
resp = session.backtest_result(exchange_id="binance", type_="ticker", job_id=jid)
results = resp.parsed.results          # pnl, totalTrades, sharpeRatio, equityCurve...
```

### Sweep

```python
accepted = session.sweep(
    exchange_id="binance", type_="ticker",
    request_id=pid,                     # the prepare job id
    strategy_id=sid,
    params={"cycle.seconds": {"values": [10, 20, 30]}},  # note: annotation name, not field
    objective="sharpe",
)
swid = accepted.sweep_id

res = session.sweep_result(exchange_id="binance", type_="ticker", request_id=pid, sweep_id=swid)
for row in res.leaderboard:
    print(row.rank, row.sharpe, row.params)

session.sweep_sensitivity(exchange_id="binance", type_="ticker", request_id=pid, sweep_id=swid)
session.sweep_run_equity_curve(..., run_ix=0)     # a retained trial's curve
session.cancel_sweep(...)
```

### Datasets (bring your own data)

```python
created = session.create_dataset(name="My BTC ticks", instrument="BTC/USDT")
# created.dataset_id, created.upload_id, created.upload.url (presigned R2 URL)
# PUT your CSV to created.upload.url (no auth header needed), then:
session.finalize_upload(dataset_id=created.dataset_id, upload_id=created.upload_id)
# poll:
state = session.dataset_upload(dataset_id=created.dataset_id, upload_id=created.upload_id)
# state.status == "ready" -> backtest against it with exchange_id="user":
acc = session.prepare(exchange_id="user", type_="ticker", dataset_id=created.dataset_id, from_=..., to=...)

session.list_datasets()
session.get_dataset(dataset_id)
session.delete_dataset(dataset_id)
```

### Raw client access

Every workflow goes through the session's underlying generated
`AuthenticatedClient`. To call an endpoint the workflows don't wrap, or to
inspect a raw `Response`:

```python
from qtsurfer.api.client._generated.api.exchange import get_exchanges

session.call(lambda c: get_exchanges.sync(client=c))          # plain
resp = session.call(lambda c: get_exchanges.sync_detailed(client=c))  # raw Response
```

## Environment

| Variable          | Purpose                                              |
| ----------------- | ---------------------------------------------------- |
| `QTSURFER_APIKEY` | API key consumed by `auth()` when no arg is passed   |

## Pluggable token storage

Tokens are kept in memory by default. Implement `TokenStore` (a `Protocol`) to
back them by file, secret manager, or keychain:

```python
import json
from pathlib import Path
from qtsurfer.api.client._generated.models import AuthTokenResponse
from qtsurfer_sdk import TokenStore, auth

class FileStore(TokenStore):
    def __init__(self, path: Path): self.path = path
    def load(self) -> AuthTokenResponse | None:
        return AuthTokenResponse.from_dict(json.loads(self.path.read_text())) if self.path.exists() else None
    def save(self, token: AuthTokenResponse) -> None: self.path.write_text(json.dumps(token.to_dict()))
    def clear(self) -> None: self.path.unlink(missing_ok=True)

session = auth(store=FileStore(Path.home() / ".qtsurfer" / "token.json"))
```

## Error hierarchy

```python
from qtsurfer_sdk import QTSError, QTSAuthError, QTSPreparationError, QTSExecutionError
```

* `QTSError` — base for all SDK errors (carries optional `.status`).
* `QTSAuthError` — missing/invalid apikey, or non-2xx from `POST /auth/token`.
* `QTSCompileError` — `POST /strategy` could not compile/register.
* `QTSPreparationError` — a `prepare` stage failed.
* `QTSExecutionError` — a backtest/sweep execution failed.
* `QTSTimeoutError`, `QTSCanceledError`, `QTSDownloadError` — reserved (poll deadline, cancel, downloads).

## Roadmap

* **v0.1 — auth helper** ✅
* **v0.2 — high-level workflows** ✅ (strategies, catalog, backtest, sweep, datasets)
* **v0.3 — async overload** mirroring `*_asyncio` api-client variants
* **v0.4 — domain handles** (`Strategy`, `Backtest`) with progress callbacks

## License

Apache-2.0 — see [LICENSE](./LICENSE).
