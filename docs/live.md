# Live execution

```python
from qtsurfer_sdk import auth

session = auth()
```

## Start, inspect, and stop

`start_live(strategy_id, request)` starts one compiled strategy. `get_live(strategy_id)` reads its
current run, and `stop_live(strategy_id)` requests a stop; poll state until it finishes.
An incompatible strategy returns `409` before a run is created. Re-register the source with
`compile_strategy()` and retry with its new strategy id. A `409` can also indicate that a run is
already active; inspect the `QTSError` message. See [strategy compatibility](strategy.md).

```python
from qtsurfer.api.client.models import (
    LiveSourceRequest,
    LiveSourceRequestType,
    LiveSourceRequestVenueType,
    StartLiveRequest,
)

source = LiveSourceRequest(
    venue_type=LiveSourceRequestVenueType.CEX,
    exchange="binance",
    segment="spot",
    type_=LiveSourceRequestType.TICKER,
    instruments=["ETH/USDT"],
)
run = session.start_live(
    strategy_id,
    StartLiveRequest(sources=[source], name="ETH breakout", relay=True, sandbox_minutes=120),
)
print(run.sandbox_minutes)  # 120
current = session.get_live(strategy_id)
stopping = session.stop_live(strategy_id)
```

`sandbox_minutes` asks for a minimum sandbox duration from 5 to 1,440 minutes. If omitted, the
plan's shortest trial applies. A request below that plan minimum returns `429`; an invalid
non-integer or out-of-range value returns `400`. The trial can continue beyond its minimum until it
has enough market-feed updates to be judged, up to 24 hours. The effective duration is present on
`start_live()` and `get_live()` responses, and on `get_live_run()` when read through the generated
client; it is absent from runs that have no sandbox trial.

`relay` defaults to `false`. Enable it only when a consumer needs live or retained signals, because
retained signals consume shared account storage.

Discover `venue_type`, exchange, and `live_segments` with `session.list_exchanges()`.
Starts reject combinations outside that discovery with `400`; catalogue `futures` can exist
without live data. Use the `cex` / `dex` enum spellings; legacy `cx` / `dx` are still accepted
server-side but responses use the canonical values.

For a DEX source, discover pools with `session.list_instruments("robinhood", "uniswap-v3")`,
then supply exactly one pool address (not its symbol), `venue_type=LiveSourceRequestVenueType.DEX`,
and `type_=LiveSourceRequestType.KLINE`. Instruments cannot be omitted or wildcarded.

```python
from qtsurfer_sdk import PoolListResponse

pools = session.list_instruments("robinhood", "uniswap-v3")
if not isinstance(pools, PoolListResponse) or not pools.data:
    raise RuntimeError("No pools in this catalogue; choose another known pool address")
dex_source = LiveSourceRequest(
    venue_type=LiveSourceRequestVenueType.DEX,
    exchange=pools.meta.exchange,
    segment=pools.meta.segment,
    type_=LiveSourceRequestType.KLINE,
    instruments=[pools.data[0].id],
)
# strategy_id must name a compiled kline strategy.
run = session.start_live(strategy_id, StartLiveRequest(sources=[dex_source]))
```

The Solana `pumpfun` segment follows a token from its bonding curve to its PumpSwap
pool when the segment appears in `live_segments`. Pass its case-sensitive mint as the
single instrument of a `dex` kline source. This segment has no instrument listing.

## Attach and detach sources

A run can start with `sources=[]` and wait without consuming a live-run slot. Attach a source to
start it, or attach more while it is already reading. Sources on one run must use the same exchange
for a CEX feed or the same chain and protocol for a DEX feed. The accepted response is not completion: it reports
`ATTACHING` or `DETACHING` and, for an active run, the market position where the change will take
effect. Read `session.get_live(strategy_id).attachments` to observe each source's state.

```python
from qtsurfer.api.client.models import AttachLiveSourceRequest
from qtsurfer.api.client import types

accepted = session.attach_live_source(
    run.run_id,
    AttachLiveSourceRequest(
        source=source,
        warm_from=300,
        ref="secondary-feed-1",
    ),
)
print(accepted.attachment_id, accepted.state, accepted.effective_at_ms)

current = session.get_live(strategy_id)
if current is not None and not isinstance(current.attachments, types.Unset):
    for attachment in current.attachments:
        print(attachment.attachment_id, attachment.state, attachment.reason)

detaching = session.detach_live_source(run.run_id, accepted.attachment_id)
print(detaching.state, detaching.effective_at_ms)
```

`ref` makes a retried attach safe: the same value on the same run returns the existing attachment.
Attaching a source the run already has also returns that attachment. `warm_from` defaults as it
does at start; when a run is already reading another source, adding a DEX pool requires
`warm_from=0`. Detaching an attachment that is already detached or being detached is safe to repeat.
Detaching the last source returns the run to `WAITING`; strategy memory is released and paper
accounts are kept. Any open paper positions in the detached source's instruments are reported as
gaps. If the platform refuses a DEX pool because the run already follows another pool for the same
pair, the strategy's `onDetach` callback receives `REFUSED`.

The run's `attachments` list is the source of truth for progress. Its `sources` list contains only
sources currently being read. A transient command cannot be delivered while no source is attached,
so `send_live_command()` returns `409` in that state.

The feed emits one candle per second, including flat candles for seconds without trades.
A DEX signal can expose the pool address or token mint as `instrument.id`.
Attachments default to resolving a pool's pair on its first candle. Pass
`resolve_instrument=False` for immediate attachment with an instrument based on the pool address.
A strategy can also detach its own source. Its attachment ends as `DETACHED` with reason
`STRATEGY`; the REST signal history records a `system` signal with kind `DETACH`.

Once a compiled strategy has passed its sandbox trial, subsequent runs start directly in `LIVE`.
Pass `sandbox=True` in `StartLiveRequest` to run it through `SANDBOX` again, for example to inspect
its WebSocket signal history while debugging. The field is available with
`qtsurfer-api-client==0.128.25` or newer; the SDK dependency pin is updated after that client
release is published.

## Run IDs and stream URLs

The API client adds `get_live_run(run_id)`, `rotate_live_stream(run_id)`, and
`revoke_live_stream(run_id)`, plus `stats`, `gate`, and `warm_from` on the generated live-run models.
The high-level SDK does not wrap those run-ID and stream-management operations yet; call them through
the generated client with `session.call(...)`. This keeps the workflow surface stable while the
SDK has no managed WebSocket connection. AsyncAPI `history` is a WebSocket operation, so it is not
available through the REST API client either.

### Simulate paper fills

Paper trading is opt-in. Add a `LivePaperConfig` to the start request to simulate balances,
positions, fees, and equity without submitting exchange orders. By default, each quote currency
gets a separate account; set `accounts=LivePaperConfigAccounts.INSTRUMENT` for one independent
account per instrument. The defaults are 100 units of initial funding, a 0.001 fee rate, and
separate paper output.
Set `output=MIX` only when paper events also need to appear in retained signals; that still requires
signal relay and uses account storage.

```python
from qtsurfer.api.client.models import (
    LivePaperConfig,
    LivePaperConfigAccounts,
    LivePaperConfigOutput,
)
from qtsurfer_sdk import EquityCurveOutMode, GetLiveRunPaperEquityMeasure

run = session.start_live(
    strategy_id,
    StartLiveRequest(
        sources=[source],
        name="ETH paper run",
        paper=LivePaperConfig(
            initial_funding=1_000,
            fee_rate=0.001,
            percent_amount_to_lock=20,
            output=LivePaperConfigOutput.MIX,
            accounts=LivePaperConfigAccounts.INSTRUMENT,
        ),
    ),
)
paper = session.get_live_run_paper(run.run_id)
for account in paper.accounts:
    print(account.currency, account.equity, len(account.open_positions))
```

Without a `paper` block, paper reads raise `QTSError` with status `404`.
`get_live_run_paper(run_id)` reads the current snapshot, including per-instrument realised PnL,
position marks, and account/instrument unrealised and total PnL where available. Positions opened
or changed since the last mark do not have mark values yet.

`get_live_run_paper_equity(run_id, currency=None, instrument=None, measure=None, since_ms=None,
out_mode=None, resample=None, differential=None, cursor=None, limit=None)` returns one equity-curve
response with `meta` and `gaps`. Select a currency account with `currency`, or an instrument account
with `instrument`. For an instrument's curve, `measure` can be `REALISEDPNL` or `TOTALPNL`; account
curves use equity. `get_next_live_run_paper_equity(run_id, curve)` follows the server link while
preserving account selection, measure, transform, time, and page-size filters.

```python
equity = session.get_live_run_paper_equity(
    run.run_id,
    currency="USDT",
    instrument="ETH/USDT",
    measure=GetLiveRunPaperEquityMeasure.TOTALPNL,
    since_ms=started_at_ms,
    out_mode=EquityCurveOutMode.SHORT,
    limit=100,
)
next_curve = session.get_next_live_run_paper_equity(run.run_id, equity)
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
path; a generated request model is accepted for extensions. A run in `WAITING` saves the
parameters for its first source. The result omits `effective_at_ms` in that state.

```python
from qtsurfer.api.client.models import UpdateLiveRequest

session.update_live(run.run_id, UpdateLiveRequest(description="US session"))
from qtsurfer.api.client import types

updated = session.update_live_params(run.run_id, {"emaFast": 12})
if updated is not None and not isinstance(updated.effective_at_ms, types.Unset):
    print("Effective at:", updated.effective_at_ms)
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
generated response is a `LiveCommandResult` on `202`; non-2xx responses raise `QTSError` with
the HTTP status and server error message.
A `503` means the command was not sent and may be retried. The endpoint has no idempotency key, so
an ambiguous network failure may have delivered a distinct command; avoid blind retries.
If the run has no attached source, the API returns `409` because there is no feed position at which
to deliver the command.

## Retained signals

`get_live_signals(run_id, since_ms=None, instrument=None, signal_type=None, cursor=None, limit=None)` returns
oldest-first signals. Request `signal_type="system"` explicitly to read strategy detach
records. These records are only available through REST. `signal_type="paper"` selects paper events when the run uses `paper.output=MIX`.
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
