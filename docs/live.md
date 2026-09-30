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

### Simulate paper fills

Paper trading is opt-in. Add a `LivePaperConfig` to the start request to simulate balances,
positions, fees, and equity without submitting exchange orders. Each quote currency gets a separate
account. The defaults are 100 units of initial funding, a 0.001 fee rate, and separate paper output.
Set `output=MIX` only when paper events also need to appear in retained signals; that still requires
signal relay and uses account storage.

```python
from qtsurfer.api.client.models import LivePaperConfig, LivePaperConfigOutput

run = session.start_live(
    strategy_id,
    StartLiveRequest(
        sources=[source],
        name="ETH paper run",
        paper=LivePaperConfig(initial_funding=1_000, fee_rate=0.001,
                              percent_amount_to_lock=20,
                              output=LivePaperConfigOutput.MIX),
    ),
)
paper = session.get_live_run_paper(run.run_id)
for account in paper.accounts:
    print(account.currency, account.equity, len(account.open_positions))
```

Without a `paper` block, paper reads return a typed `ResponseError` with status `404`.
`get_live_run_paper(run_id)` reads the current
snapshot. `get_live_run_paper_equity(run_id, currency=None, since_ms=None, cursor=None, limit=None)`
reads oldest-first history; omit `currency` to combine quote accounts. Cursor takes precedence over
`since_ms`; `get_next_live_run_paper_equity(run_id, page)` follows the server link while preserving
currency, time, and page size.

```python
equity = session.get_live_run_paper_equity(
    run.run_id, currency="USDT", since_ms=started_at_ms, limit=100
)
next_equity = session.get_next_live_run_paper_equity(run.run_id, equity)
```

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

`send_live_command(run_id, command, properties=None)` sends an owner-only transient event to a
running strategy implementing the engine's `CommandRequestHandler`. The `properties` mapping is
delivered alongside the command. Commands are not saved on the run or replayed to replicas started
later; use `update_live_params` for state that must survive restarts.

```python
accepted = session.send_live_command(
    run.run_id,
    "rebalance",
    properties={"targetWeight": 0.25, "reason": "risk threshold"},
)
print(accepted.command_id, accepted.effective_at_ms)
```

The accepted response is not confirmation that the strategy finished handling the event. The
generated response is a `LiveCommandResult` on `202` and a `ResponseError` on documented failures.
A `503` means the command was not sent and may be retried. The endpoint has no idempotency key, so
an ambiguous network failure may have delivered a distinct command; avoid blind retries.

## Retained signals

`get_live_signals(run_id, since_ms=None, instrument=None, signal_type=None, cursor=None, limit=None)` returns
oldest-first signals. `signal_type="paper"` selects paper events when the run uses `paper.output=MIX`.
`cursor` takes precedence over `since_ms`; deduplicate `signal_id` when
combining history and real-time delivery. If a cursor expires, restart without it and use
`available_since_ms` as the earliest readable point.

```python
page = session.get_live_signals(run.run_id, instrument="ETH/USDT", limit=100)
for signal in page.signals:
    print(signal.signal_id, signal.kind)

next_page = session.get_next_live_signals(run.run_id, page)
```

The continuation helper retains `since_ms`, `instrument`, `signal_type`, and `limit`. `get_live()`
also carries optional `reason` text when the platform stopped or failed a run; treat unrecognised
reason text as an opaque explanation, not a value to parse.
