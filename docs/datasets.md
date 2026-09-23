# Datasets and uploads

Start with an authenticated session; every example below uses `session`:

```python
from qtsurfer_sdk import auth

session = auth()  # reads QTSURFER_APIKEY
```

## Discover and manage datasets

`list_datasets()` lists your datasets, `get_dataset(dataset_id)` reads one, and
`delete_dataset(dataset_id)` soft-deletes it. These metadata operations use the authenticated
session.

```python
datasets = session.list_datasets()
dataset = session.get_dataset(dataset_id)
deleted = session.delete_dataset(dataset_id)
```

## Create and upload a version

Use a dataset for your own ticker CSV. `create_dataset(name, instrument)` creates the dataset and
its first upload session. The session authenticates metadata calls, while the file is sent directly
to the presigned target without a JWT or API key.

```python
from pathlib import Path

created = session.create_dataset(name="My BTC ticks", instrument="BTC/USDT")
session.upload_dataset_file(created, Path("BTC_USDT.csv"))
session.finalize_dataset_upload(
    dataset_id=created.dataset_id,
    upload_id=created.upload_id,
)
state = session.get_dataset_upload(
    dataset_id=created.dataset_id,
    upload_id=created.upload_id,
)
```

Poll `get_dataset_upload(dataset_id, upload_id)` until the state is ready or failed. Only a ready
version is usable; it records the discovered range, cadence, row count, and gap details. See the API
[dataset reference](https://qtsurfer.github.io/docs/datasets.html) for CSV columns and validation.

The upload helper accepts either a `pathlib.Path` or an open binary file. It closes files it opens,
but leaves caller-owned file handles open. Upload/network failures raise `QTSUploadError`; the SDK
does not include the presigned URL in the error because it grants temporary write access. A
successful upload does not start ingestion: always finalize the session.

## Resume and create later versions

For another version, use `open_dataset_upload(dataset_id)`, pass that session to
`upload_dataset_file`, then finalize it. Reopening while pending is safe and returns the active
session; after finalization, it opens the next version's session. A finalized upload id is spent and
a second finalization returns `409`; open a fresh session instead.

```python
upload = session.open_dataset_upload(dataset_id)
with Path("BTC_USDT_next.csv").open("rb") as stream:
    session.upload_dataset_file(upload, stream)
session.finalize_dataset_upload(dataset_id=dataset_id, upload_id=upload.upload_id)
```

Run against a ready version with `exchange_id="user"`, `dataset_id`, and optionally
`dataset_version_id` during `prepare`.

Dataset imports from an existing platform source are available through the generated
`qtsurfer-api-client`; this SDK currently wraps user-file upload and lifecycle operations only.
