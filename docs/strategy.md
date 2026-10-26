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

The typed compile result also exposes `requires`, the plan capabilities needed by the compiled
source. The current value `CompileStrategyResponse200RequiresItem.INDICATORS_PRO` means that the
strategy uses Pro indicators. Registration succeeds on every plan, but validation, backtests,
sweeps, and live starts return HTTP `402` when the plan lacks a required capability. The SDK raises
`QTSError` with `status == 402`, `retryable == False`, and the optional `upgrade_url`; change the plan
before retrying. `get_strategy()` does not return this compile-only field.

```python
from qtsurfer.api.client.models import CompileStrategyResponse200RequiresItem
from qtsurfer.api.client.types import UNSET

compiled = session.compile_strategy(source)
if compiled.requires is not UNSET and CompileStrategyResponse200RequiresItem.INDICATORS_PRO in compiled.requires:
    print("This strategy needs a plan with Pro indicators")
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

`list_strategies()` lists active registrations. Pass `include_deleted=True` to include soft-deleted
entries with `deleted_at`, useful when reconciling a local catalogue. `get_strategy_code(strategy_id)`
returns the registered source. `delete_strategy(strategy_id)` removes the active registration;
historical runs remain.

```python
for strategy in session.list_strategies(include_deleted=True):
    print(strategy.strategy_id)
    if strategy.deleted_at:
        print("deleted at", strategy.deleted_at)
source_text = session.get_strategy_code(compiled.strategy_id)
session.delete_strategy(compiled.strategy_id)
```

A passed bounded validation is not a trading-performance or safety guarantee.

For indicators, `emitBuy`/`emitSell`, information signals, order configuration, and chart metadata,
see the API's [Coding Java strategies](https://www.qtsurfer.com/docs/developers/api/strategy_coding) guide
and the [`qtsurfer-java-strategy`](https://github.com/QTSurfer/strategy-skills) skill.
