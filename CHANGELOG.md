# Changelog

All notable changes to `qtsurfer-sdk` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
- `backtest_result` returns `sync_detailed` so poll loops can handle the
  `202`-running state without the generated `sync` KeyError'ing on partial
  results.

### Changed

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
