# Changelog

All notable changes to `qtsurfer-sdk` are documented here.

## [0.7.0] — 2026-10-26

### Added ✨

- `compile_strategy()` returns the compiled source's plan requirements, such as
  `CompileStrategyResponse200RequiresItem.INDICATORS_PRO`. Plan refusals raise `QTSError` with
  `status == 402`, `retryable == False`, and an optional `upgrade_url`.
- `start_live()` accepts `StartLiveRequest.sandbox_minutes` and returns the stream-aware
  `LiveRunWithStream` model with the granted duration.

### Changed 🔄

- Target OpenAPI `0.128.48` through `qtsurfer-api-client==0.128.48`; the strategy and live guides
  explain capability checks, trial defaults, limits, and retry behavior.

```python
from pathlib import Path

from qtsurfer.api.client.models import (
    LiveSourceRequest,
    LiveSourceRequestType,
    LiveSourceRequestVenueType,
    StartLiveRequest,
)
from qtsurfer_sdk import auth

session = auth()  # reads QTSURFER_APIKEY
compiled = session.compile_strategy(Path("MyStrategy.java").read_text())
print(compiled.requires)
source = LiveSourceRequest(
    venue_type=LiveSourceRequestVenueType.CEX,
    exchange="binance",
    segment="spot",
    type_=LiveSourceRequestType.TICKER,
    instruments=["BTC/USDT"],
)
run = session.start_live(
    compiled.strategy_id,
    StartLiveRequest(sources=[source], sandbox_minutes=120),
)
print(run.sandbox_minutes)
```

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.0] — 2026-10-23

### Added ✨

- Raise `QTSInsufficientScopeError` for protected operations refused with `403`; it exposes the
  typed `insufficient_scope` code and required `resource:action` scope.
- Read the revised paper-equity curve with account or instrument selection, PnL measures, transforms,
  and continuation that preserves all filters. Paper results now expose per-instrument metrics and
  mark-to-market positions.
- Preserve the API's `retryable` flag on generic workflow `QTSError` instances.

### Changed 🔄

- Target OpenAPI `0.128.46` through `qtsurfer-api-client==0.128.46`.
- A ready dataset's type reflects its ingested data, and kline preparation requires a `klines` version.
- Paper accounts can be shared by quote currency or isolated per instrument.

## [0.5.0] — 2026-10-17

### Added ✨

- Discover decentralized pools through `list_instruments(exchange_id, segment)` while retaining
  the typed catalogue envelope and `meta.venue_type`. Public exports include `PoolDetail`,
  `PoolListResponse`, `InstrumentListResponse` and `InstrumentCatalogueResponse`.
- Inspect nonempty API-key grants as a `KeyScopes` resource-to-actions map on token and account
  responses. JSON-backed token stores preserve grants and metadata; historical empty arrays
  round-trip as empty maps. Individual operation scopes are reported but not yet enforced.
- Authentication `QTSAuthError` preserves `.status`, typed `.code`, and the server's exact
  `.message`. A `403` `apikey_without_scopes` is not retried: create a key with at least one
  scope in the web app where the deployment requires scopes.
- Workflow `QTSError` now retains `.reason`, typed `.next_call`, and `.retry_after` so callers
  can handle structured recovery without parsing the server message.
- Guides cover DEX live sources, centralized-exchange history imports and their asynchronous
  failures, and hourly binary adapters with provisional metadata and seven-day recovery.

### Changed 🔄

- Target OpenAPI `0.128.37`: live source venue types are `cex` / `dex` enums; exchange discovery
  requires venue and segment metadata, instrument symbols are required, and absent market values
  are `UNSET`. Replace old `venue_type="cx"` construction with `LiveSourceRequestVenueType.CEX`.
- Hourly downloads use the API client's public binary adapters. Lastra timestamps are microseconds;
  retain response headers and retry recent unavailable hours or import older history as a dataset.
- Imports remain deliberate endpoint-layer operations through `session.call(...)`; the dataset
  guide provides a complete typed CEX submission and resumable polling example.

## [0.4.2] — 2026-10-10

### Added

- `start_live()` supports `StartLiveRequest(sandbox=True)` to repeat the sandbox trial for a
  strategy that already passed it. Update the pinned generated client to `0.128.25`, which also
  exposes the intervening live-execution API additions.

## [0.4.1] — 2026-09-30

### Fixed

- Raise `QTSError` for non-2xx workflow responses, preserving the HTTP status and server message instead of returning an error model as a successful result.
- Keep expired live-signal cursors mapped to `QTSLiveSignalCursorExpiredError`.

## [0.4.0] — 2026-09-30

### Added

- Simulate live fills with `StartLiveRequest.paper`, inspect account state with `get_live_run_paper()`, and page equity history with filter-preserving `get_next_live_run_paper_equity()`.
- Deliver owner-only transient strategy commands with `send_live_command()` and arbitrary JSON `properties` without restarting a run.
- Include soft-deleted strategies and datasets in `list_strategies(include_deleted=True)` and `list_datasets(include_deleted=True)`; retain signal-type filters across page continuation.

### Changed

- Target OpenAPI `0.128.14` through `qtsurfer-api-client==0.128.14`; account limits include `max_sweep_cartesian` and live-run details include an optional stop/failure `reason`.
- Default `auth()` to the staging beta API at `https://api.qtsurfer.net/v1` rather than the reserved production host.

## [0.3.1] — 2026-09-23

- Use absolute GitHub URLs for README guide and license links so they resolve on PyPI.

## [0.3.0] — 2026-09-23

### Account visibility and storage

- Read account limits with `get_account()` and current dataset, strategy, signal, and storage usage
  with `get_account_usage()` before starting storage-consuming workflows.

### Live execution

- Start, inspect, stop, and update live runs with `start_live()`, `get_live()`, `stop_live()`, and
  `update_live()`; adjust active strategy parameters with `update_live_params()` using a plain
  Python mapping.
- Browse owned and public runs separately with `list_live()` and `list_public_live()`. Read
  retained signal history with `get_live_signals()` and follow pages with
  `get_next_live_signals()`; expired cursors raise `QTSLiveSignalCursorExpiredError` with the
  earliest available timestamp when supplied by the API.
- Signal relay remains opt-in (`relay=False` by default) because retained signals use shared account
  storage. Check account usage before enabling it for high-volume runs.

### Dataset uploads

- Create, list, inspect, upload, finalize, resume, and delete user datasets. Upload files directly to
  the presigned URL without sending API credentials; finalize each upload to begin ingestion and
  poll until it is ready before using it in `prepare()`.
- Reopening a pending upload is safe; finalized upload sessions cannot be reused (`409`). Upload
  failures raise `QTSUploadError` without exposing the temporary URL.

### Compatibility

- Target OpenAPI 0.126.2 through `qtsurfer-api-client==0.126.2`.

### Added

- `open_dataset_upload(dataset_id)` opens a dataset's current upload session or
  its next version's session after finalization.
- `upload_dataset_file(upload, source)` streams a `Path` or open binary file to
  the session's presigned URL without sending the SDK JWT or API key. Failed PUTs
  and unreadable local files raise `QTSUploadError` without exposing the URL.

### Changed

- Public reads now use explicit names: `list_exchanges`, `list_instruments`,
  `get_strategy`, `get_prepare_status`, `get_backtest_result`,
  `get_sweep_result`, `get_sweep_sensitivity`, `get_sweep_run_equity_curve`,
  `finalize_dataset_upload`, and `get_dataset_upload` replace their terse
  predecessors.
- The generated client dependency is pinned to `qtsurfer-api-client==0.126.2`.
  A spent upload session now has the API's documented `409` finalization response;
  open a new session instead of reusing that upload id.

## [0.2.0] — 2026-08-27

### Added

- High-level workflow surface over `qtsurfer-api-client`, parity with the Java /
  TypeScript SDKs (module `qtsurfer_sdk._workflows`):
  - Strategy: `compile_strategy`, `validate_strategy`, `strategy_state`,
    `list_strategies`, `delete_strategy`, `get_strategy_code`.
  - Catalog: `exchanges`, `instruments` (with optional segment).
  - Backtest: `prepare`, `prepare_status`, `execute`, `backtest_result`,
    `cancel_backtest`.
  - Sweep: `sweep`, `sweep_result`, `sweep_sensitivity`,
    `sweep_run_equity_curve`, `cancel_sweep`.
  - Dataset: `create_dataset`, `list_datasets`, `get_dataset`,
    `delete_dataset`, `finalize_upload`, `dataset_upload`.
- Error hierarchy parity: `QTSCompileError`, `QTSPreparationError`,
  `QTSExecutionError`, `QTSTimeoutError`, `QTSCanceledError`, `QTSDownloadError`.
- `backtest_result` returns a raw `httpx.Response` (not the generated
  `sync` value), so poll loops can handle the `202`-running state without
  the generated parser KeyError'ing on a partially-populated `results`
  body (missing `strategyId` while running).

### Changed

- Workflows exposed as methods on `AuthenticatedSession`
  (`session.exchanges()`, `session.prepare(...)`, `session.backtest_result(...)`,
  ...) in addition to the `_workflows` module functions — parity with the
  Java/TS SDK `AuthenticatedClient` surface.
- README rewritten to document the full workflow surface with reproducible
  examples.
- Dependency pinned to `qtsurfer-api-client==0.110.3` (OpenAPI spec 0.110.3;
  adds the Dataset feature and dataset-backed prepare/execute).
- `import` fixed for the generated auth endpoint moved to
  `qtsurfer.api.client._generated.api.auth.authenticate` in 0.110.3.

### Fixed

- `AuthenticatedSession` now imports the auth operation from its new module
  path, restoring `auth()` against `qtsurfer-api-client` 0.110.x.

## [0.1.0] — 2026-05-25

### Added

- Initial release. `auth(apikey)` helper exchanges a long-lived API key for a short-lived JWT in one call and returns an `AuthenticatedSession`.
  - Reads `QTSURFER_APIKEY` from the environment when no apikey is passed.
  - Caches the JWT in memory by default; adopters can plug in a custom `TokenStore` (file, secret manager, desktop keychain).
  - `session.call(fn)` wraps any `qtsurfer-api-client` call with refresh-on-401: refresh once, retry once, surface the error otherwise.
  - `session.client` exposes the underlying `qtsurfer-api-client` `AuthenticatedClient` for direct typed calls; its `token` attribute is mutated on refresh so in-flight references see the latest JWT.
- `TokenStore` protocol (`load` / `save` / `clear`) with the default `InMemoryTokenStore`.
- `QTSAuthError` (subclass of `QTSError`) for missing-apikey and JWT-exchange failures.
- Depends on `qtsurfer-api-client >= 0.95.1` (provides the `auth` operation and `AuthTokenResponse` / `AuthTokenError` schemas).
