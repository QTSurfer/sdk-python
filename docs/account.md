# Account limits and usage

```python
from qtsurfer_sdk import auth

session = auth()  # reads QTSURFER_APIKEY
```

## Read account limits

`get_account()` returns the account id, tier, dataset caps, total storage cap, and
`max_sweep_cartesian`, the maximum number of combinations for a full Cartesian sweep.
It also returns `scopes`, the API key's resource-to-actions map, and `api_key_expires_at`, the
UTC expiry of the API key (`None` when it has no expiry). The latter matches `key_exp` on the
token; it is the key's expiry, not the JWT's. See [authentication](auth.md).

```python
account = session.get_account()
print(account.tier, account.max_datasets, account.max_total_storage_bytes)
print("Cartesian sweep cap:", account.max_sweep_cartesian)
print("API key expires at:", account.api_key_expires_at)
```

For dataset imports, `max_import_range_hours` covers DEX pools and
`max_cex_import_range_hours` covers exchange history. `max_concurrent_imports` caps
queued and running imports. When present, `max_cex_history_days` and
`max_cex_import_instruments_per_month` describe exchange history and monthly instrument quotas.

## Read current usage

`get_account_usage()` reports dataset, strategy, signal, and aggregate usage. The optional `cex_import_month` and
`cex_import_instruments` report usage per exchange and segment for the current UTC month.

```python
usage = session.get_account_usage()
print(usage.datasets_used, usage.signals_used, usage.storage_bytes_used)
```

Datasets, strategies, and retained signals share storage. Check available bytes before enabling
signal relay for high-volume runs; see [Live execution](live.md).
