# Datasets and uploads

Start with an authenticated session; every example below uses `session`:

```python
from qtsurfer_sdk import auth

session = auth()  # reads QTSURFER_APIKEY
```

## Discover and manage datasets

`list_datasets()` lists active datasets; pass `include_deleted=True` to include soft-deleted entries
with `deleted_at` when reconciling a local catalogue. `get_dataset(dataset_id)` reads one, and
`delete_dataset(dataset_id)` soft-deletes it. These metadata operations use the authenticated
session.

```python
datasets = session.list_datasets(include_deleted=True)
for item in datasets.datasets:
    print(item.dataset_id, item.deleted_at)
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
[dataset reference](https://www.qtsurfer.com/docs/developers/api/datasets) for CSV columns and validation.
Once ready, `Dataset.type_` describes the ingested rows rather than the way they were created: a
file of candles is `klines`, and a `kline` backtest requires a ready `klines` version. A `ticker`
backtest accepts either type. Before the first version is ready, the type is only the creation label.

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

## Import exchange history

Imports deliberately stay at the endpoint layer: use `session.call(...)` for both submission
and polling, retaining refresh-on-401. A CEX source must name a discovered centralized exchange,
`segment="spot"` (the only supported import segment), and `data_type=TICKER` or `KLINES`.
The dataset's type follows that choice. DEX exchange ids are rejected for CEX imports;
use a `DatasetImportDexRequest` with `type_=DEX` for pool history instead.

```python
import time
from datetime import UTC, datetime, timedelta
from qtsurfer.api.client.api.dataset import import_dataset, get_dataset_import
from qtsurfer.api.client.models import (
    DatasetImportRequest,
    DatasetImportRequestType,
    DatasetImportCexRequest,
    DatasetImportCexRequestSegment,
    DatasetImportCexRequestDataType,
    DatasetImportCreated,
    DatasetImportState,
)

end = datetime.now(UTC) - timedelta(days=8)
request = DatasetImportRequest(
    name="BTC history",
    instrument="BTC/USDT",
    from_=end - timedelta(hours=1),
    to=end,
    type_=DatasetImportRequestType.CEX,
    cex=DatasetImportCexRequest(
        exchange="binance",
        segment=DatasetImportCexRequestSegment.SPOT,
        data_type=DatasetImportCexRequestDataType.KLINES,
    ),
)
response = session.call(lambda client: import_dataset.sync_detailed(client=client, body=request))
if response.status_code != 202 or not isinstance(response.parsed, DatasetImportCreated):
    raise RuntimeError(f"Import refused: {response.status_code} {response.parsed}")
created = response.parsed  # datasetId/importId/jobId and the effective cadence when known
deadline = time.monotonic() + 900
while True:
    response = session.call(
        lambda client: get_dataset_import.sync_detailed(
            created.dataset_id,
            created.import_id,
            client=client,
        )
    )
    if response.status_code != 200 or not isinstance(response.parsed, DatasetImportState):
        raise RuntimeError(f"Import status failed: {response.status_code} {response.parsed}")
    state = response.parsed
    if state.status.value == "ready":
        break  # state.version is now usable in a dataset-backed prepare
    if state.status.value == "failed":
        raise RuntimeError(state.error)
    if time.monotonic() >= deadline:
        raise TimeoutError("Import still running; keep its dataset and import ids to resume")
    time.sleep(3)
```

The account plan determines which cadences a managed import can use and its default. Omitted
`cadence` uses that default; a cadence outside the plan returns `402` as `PlanRequiredError`, with
`retryable=False` and an optional `upgrade_url`. To choose one, pass
`DatasetImportRequestCadence(...)`: `1s`, `5s`, `1m`, `3m`, `5m`, `15m`, `30m`, `1h`, `2h`,
`4h`, `8h`, `12h`, `1d`, `1w`, `1q` for CEX ticker or kline imports. A finer cadence than the
range holds, or an inexact multiple, fails asynchronously; `state.error` names the finest available
cadence. A mixed-history range is uniformly coarsened when cadence is omitted.

DEX imports produce candles at the requested cadence, or at the plan default when omitted. The
exception is a plan that includes the source's native rate: omitting `cadence` then keeps per-trade
history and requires `id` and `version` in `DatasetImportDexRequest`. Unsupported source/cadence
combinations can fail asynchronously. Uploads and prepares against `exchange_id="user"` are not
limited by plan cadences.

Solana DEX imports are candle-only. Even Elite uses its plan default (`1s`) when cadence is omitted;
`id`, `version`, and `factory` are never needed. The pool address is base58 and case-sensitive.
Candle imports whose `from_` is earlier than 180 days before the request return `400` immediately on
every network; per-trade DEX imports and CEX imports are not subject to that history limit. DEX
candles may be sparse: an interval with no trades can have no bar.

```python
from qtsurfer.api.client.models import (
    DatasetImportDexRequest,
    DatasetImportDexRequestNetwork,
    DatasetImportRequestCadence,
)

solana_request = DatasetImportRequest(
    name="SOL history",
    instrument="SOL/USDC",
    from_=datetime(2026, 10, 27, tzinfo=UTC),
    to=datetime(2026, 10, 27, 6, tzinfo=UTC),
    type_=DatasetImportRequestType.DEX,
    cadence=DatasetImportRequestCadence.VALUE_4,
    dex=DatasetImportDexRequest(
        network=DatasetImportDexRequestNetwork.SOLANA,
        contract="Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE",
    ),
)
response = session.call(lambda client: import_dataset.sync_detailed(client=client, body=solana_request))
```

Read `session.get_account().max_import_range_hours` before choosing a range. Imports count
against dataset-count, per-dataset byte, total-storage and execution-time limits; `403`
reports tier/quota restrictions, `400` malformed inputs, and failed states include no data,
unresolvable pool, old source history, cadence or time-ceiling failures. Persist ids to
resume polling instead of resubmitting and creating another dataset. A ready dataset uses
the same `exchange_id="user"` preparation path as uploads; only the ready version is usable.
