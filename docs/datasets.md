# Dataset uploads

Use a dataset for your own ticker CSV. The session authenticates metadata calls, while the file is
sent directly to the presigned target without a JWT or API key.

```python
from pathlib import Path

created = session.create_dataset(name="My BTC ticks", instrument="BTC/USDT")
session.upload_dataset_file(created, Path("BTC_USDT.csv"))
session.finalize_dataset_upload(dataset_id=created.dataset_id, upload_id=created.upload_id)
state = session.get_dataset_upload(dataset_id=created.dataset_id, upload_id=created.upload_id)
```

Poll until the state is ready or failed. Only a ready version is usable; it records the discovered
range, cadence, row count, and gap details. See the API [dataset reference](https://qtsurfer.github.io/docs/datasets.html)
for CSV columns and validation.

For another version, use `open_dataset_upload(dataset_id)`, pass that session to
`upload_dataset_file`, then finalize it. Reopening while pending is safe; a finalized upload id is
spent and a second finalization returns `409`.

Run against a ready version with `exchange_id="user"`, `dataset_id`, and optionally
`dataset_version_id` during `prepare`.
