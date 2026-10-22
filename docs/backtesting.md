# Backtests and parameter sweeps

Start with an authenticated session; every example below uses `session`:

```python
from qtsurfer_sdk import auth

session = auth()  # reads QTSURFER_APIKEY
```

The Python SDK exposes explicit stages so applications can persist job ids and own polling. `prepare`
requires `exchange_id`, `from_`, and `to`; set either `instrument` or `dataset_id` (optionally pin
`dataset_version_id`). `type_` defaults to `ticker`; `cadence` is optional.

Managed `ticker`, `funding`, and `kline` preparations accept the same fifteen labels:
`1s`, `5s`, `1m`, `3m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `8h`, `12h`, `1d`,
`1w`, `1q`; omitted means `1s`. Kline cadence selects bar width once at preparation.
Dataset preparation defaults to its version's cadence and accepts an exact multiple
of that cadence; `rt` data can be resampled to any fixed cadence.

```python
compiled = session.compile_strategy(source)
prepared = session.prepare(
    exchange_id="binance", type_="ticker", instrument="BTC/USDT", from_=from_, to=to
)
execution = session.execute(
    exchange_id="binance",
    type_="ticker",
    prepare_job_id=prepared.job_id,
    strategy_id=compiled.strategy_id,
)
response = session.get_backtest_result(
    exchange_id="binance", type_="ticker", job_id=execution.job_id
)
```

`get_prepare_status(exchange_id, type_, job_id)` reads preparation state. `execute(exchange_id,
type_, prepare_job_id, strategy_id, store_signals=False)` submits execution; request signal storage
only when needed because it consumes account quota. `get_backtest_result(...)` returns a raw
`httpx.Response`: inspect `status_code` (`202` still running, `200` terminal) before parsing JSON.
`cancel_backtest(exchange_id, type_, job_id)` requests cancellation.

```python
status = session.get_prepare_status(exchange_id="binance", type_="ticker", job_id=prepared.job_id)
execution = session.execute(
    exchange_id="binance",
    type_="ticker",
    prepare_job_id=prepared.job_id,
    strategy_id=compiled.strategy_id,
    store_signals=False,
)
response = session.get_backtest_result(
    exchange_id="binance",
    type_="ticker",
    job_id=execution.job_id,
)
if response.status_code == 202:
    session.cancel_backtest(exchange_id="binance", type_="ticker", job_id=execution.job_id)
```

## Equity curves and sweeps

`sweep(...)` takes the prepared `request_id`, strategy id, and parameter axes. Defaults are grid
sampling, Sharpe objective, no stored signals, and no walk-forward folds. `samples` and `seed` apply
to samplers that use them; `walk_forward` selects fold-based validation.

```python
sweep = session.sweep(
    exchange_id="binance",
    type_="ticker",
    request_id=prepared.job_id,
    strategy_id=compiled.strategy_id,
    params={"ema.fast": {"values": [9, 12]}, "ema.slow": {"values": [21, 26]}},
)
result = session.get_sweep_result(
    exchange_id="binance",
    type_="ticker",
    request_id=prepared.job_id,
    sweep_id=sweep.sweep_id,
)
```

`get_sweep_sensitivity(...)` aggregates parameter marginals and heatmaps. `get_sweep_run_equity_curve`
reads one curve only if retained; unretained trials return `404`. `cancel_sweep(...)` requests stop.
The shared API [equity-curve guide](https://www.qtsurfer.com/docs/developers/api/equity_curves) defines
transforms and metadata.

Walk-forward changes the operation into per-fold optimize-then-score validation. Its rows represent
folds rather than parameter-grid positions.
