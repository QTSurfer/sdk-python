# Strategies and validation

`compile_strategy` registers Java source and returns its `strategy_id`. Validate before an
expensive run: validation loads the class and drives a bounded synthetic series.

```python
compiled = session.compile_strategy(source)
outcome = session.validate_strategy(compiled.strategy_id)
state = session.get_strategy(compiled.strategy_id)
```

Validation is idempotent. A response that did not queue work is not necessarily a passed verdict;
poll `get_strategy` with an application deadline while validation is pending. A passed bounded
check is a useful floor, not a trading-performance guarantee.

For indicators, `emitBuy`/`emitSell`, information signals, order configuration, and chart metadata,
see the API's [Coding Java strategies](https://qtsurfer.github.io/docs/strategy_coding.html) guide
and the [`qtsurfer-java-strategy`](https://github.com/QTSurfer/strategy-skills) skill.
