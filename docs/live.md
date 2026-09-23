# Live execution

```python
from qtsurfer_sdk import auth

session = auth()
```

## Start, inspect, and stop

`start_live(strategy_id, request)` starts one compiled strategy. `get_live(strategy_id)` reads its
current run, and `stop_live(strategy_id)` requests a stop; poll state until it finishes.

```python
from qtsurfer.api.client.models import LiveSource, LiveSourceType, StartLiveRequest

source = LiveSource(
    venue_type="cx", exchange="binance", segment="spot",
    type_=LiveSourceType.TICKER, instruments=["ETH/USDT"],
)
run = session.start_live(
    strategy_id,
    StartLiveRequest(sources=[source], name="ETH breakout", relay=True),
)
current = session.get_live(strategy_id)
stopping = session.stop_live(strategy_id)
```

`relay` defaults to `false`. Enable it only when a consumer needs live or retained signals, because
retained signals consume shared account storage.

## List owned runs

`list_live(cursor=None, limit=None)` lists all owned runs. Omit both for server defaults; use the
returned continuation cursor only for the next page.

```python
page = session.list_live(limit=20)
for item in page.runs:
    print(item.run_id, item.state)
```

`list_public_live(cursor=None, limit=None)` separately browses runs that owners made public; it
does not reveal the owner's strategy or private parameters.

```python
public_page = session.list_public_live(limit=20)
for item in public_page.runs:
    print(item.run_id, item.name)
```

## Update a run

`update_live(run_id, request)` changes name, description, or visibility. `update_live_params(run_id,
params)` changes declared parameters while the run stays active. Pass a plain mapping for the common
path; a generated request model is accepted for extensions.

```python
from qtsurfer.api.client.models import UpdateLiveRequest

session.update_live(run.run_id, UpdateLiveRequest(description="US session"))
session.update_live_params(run.run_id, {"emaFast": 12})
```

## Retained signals

`get_live_signals(run_id, since_ms=None, instrument=None, cursor=None, limit=None)` returns
oldest-first signals. `cursor` takes precedence over `since_ms`; deduplicate `signal_id` when
combining history and real-time delivery. If a cursor expires, restart without it and use
`available_since_ms` as the earliest readable point.

```python
page = session.get_live_signals(run.run_id, instrument="ETH/USDT", limit=100)
for signal in page.signals:
    print(signal.signal_id, signal.kind)

next_page = session.get_next_live_signals(run.run_id, page)
```
