# Strategies and validation

Start with an authenticated session; every example below uses `session`:

```python
from qtsurfer_sdk import auth

session = auth()  # reads QTSURFER_APIKEY
```

`compile_strategy(source)` registers Java source and returns the strategy id. It sends raw
`text/plain`, which the generated client cannot express, so the SDK adapts it directly.

```python
compiled = session.compile_strategy(source)
print(compiled.strategy_id)
```

## Validate and inspect

`validate_strategy(strategy_id)` is idempotent; a response that did not queue work is not itself a
pass verdict. `get_strategy(strategy_id)` returns the state and latest validation verdict. Poll it
with an application deadline while validation is pending.

```python
outcome = session.validate_strategy(compiled.strategy_id)
state = session.get_strategy(compiled.strategy_id)
print(outcome, state.validation)
```

## List, read source, and delete

`list_strategies()` lists registered strategies. `get_strategy_code(strategy_id)` returns the
registered source. `delete_strategy(strategy_id)` removes the registration; historical runs remain.

```python
for strategy in session.list_strategies():
    print(strategy.strategy_id)
source_text = session.get_strategy_code(compiled.strategy_id)
session.delete_strategy(compiled.strategy_id)
```

A passed bounded validation is not a trading-performance or safety guarantee.

For indicators, `emitBuy`/`emitSell`, information signals, order configuration, and chart metadata,
see the API's [Coding Java strategies](https://qtsurfer.github.io/docs/strategy_coding.html) guide
and the [`qtsurfer-java-strategy`](https://github.com/QTSurfer/strategy-skills) skill.
