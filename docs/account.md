# Account limits and usage

```python
from qtsurfer_sdk import auth

session = auth()  # reads QTSURFER_APIKEY
```

## Read account limits

`get_account()` returns the account id, tier, dataset caps, total storage cap, and
`max_sweep_cartesian`, the maximum number of combinations for a full Cartesian sweep.

```python
account = session.get_account()
print(account.tier, account.max_datasets, account.max_total_storage_bytes)
print("Cartesian sweep cap:", account.max_sweep_cartesian)
```

## Read current usage

`get_account_usage()` reports dataset, strategy, signal, and aggregate usage.

```python
usage = session.get_account_usage()
print(usage.datasets_used, usage.signals_used, usage.storage_bytes_used)
```

Datasets, strategies, and retained signals share storage. Check available bytes before enabling
signal relay for high-volume runs; see [Live execution](live.md).
