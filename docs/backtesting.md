# Backtests and parameter sweeps

The Python SDK exposes the explicit stages for callers that need to own their job ids: compile,
prepare, poll, execute, and read the result.

```python
compiled = session.compile_strategy(source)
prepared = session.prepare(
    exchange_id="binance", type_="ticker", instrument="BTC/USDT", from_=from_, to=to
)
execution = session.execute(
    exchange_id="binance", type_="ticker", prepare_job_id=prepared.job_id,
    strategy_id=compiled.strategy_id,
)
response = session.get_backtest_result(
    exchange_id="binance", type_="ticker", job_id=execution.job_id
)
```

`get_backtest_result` intentionally returns a raw `httpx.Response`: a running job returns `202`
with a partial result body, so inspect the status before parsing terminal results.

## Equity curves and sweeps

Submit `sweep(...)` after preparation, then use `get_sweep_result`, `get_sweep_sensitivity`, and
`get_sweep_run_equity_curve`. Curves are present only when retained by the request; reading any
other trial returns `404`. The shared API [equity-curve guide](https://qtsurfer.github.io/docs/equity_curves.html)
defines transforms, differential decoding, metadata, and the meaning of equity.

Walk-forward changes the operation into per-fold optimize-then-score validation. Its rows represent
folds rather than parameter-grid positions.
