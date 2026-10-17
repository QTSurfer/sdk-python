# API coverage

This update targets API spec **0.128.37** through `qtsurfer-api-client==0.128.37`.
Every OpenAPI operation is accounted for below. Endpoint-only entries
are deliberate choices, called with `session.call(...)`.

| Domain | SDK surface | DX boundary |
| --- | --- | --- |
| Authentication | `auth`, refresh-on-401, `TokenStore` | `auth()` owns API-key exchange and retries one `401`. |
| Exchange | `list_exchanges`, `list_instruments` | `download_tickers` and `download_klines` use the API client's public binary adapters. |
| Strategy | `compile_strategy`, `validate_strategy`, `get_strategy`, `list_strategies(include_deleted)`, `get_strategy_code`, `delete_strategy` | `compile_strategy` adapts `text/plain`, unsupported by the generator. Deleted entries carry `deleted_at`. |
| Backtesting | `prepare`, `get_prepare_status`, `execute`, `get_backtest_result`, `cancel_backtest` | Explicit stages preserve durable job ids for application-owned polling. |
| Sweeps | `sweep`, `get_sweep_result`, `get_sweep_sensitivity`, `get_sweep_run_equity_curve`, `cancel_sweep` | The caller owns pagination and polling policy. |
| Dataset | `create_dataset`, `list_datasets(include_deleted)`, `get_dataset`, `delete_dataset`, `open_dataset_upload`, `upload_dataset_file`, `finalize_dataset_upload`, `get_dataset_upload` | `import_dataset` and `get_dataset_import` remain generated-client operations. Deleted entries carry `deleted_at`; presigned upload bytes never carry the API token. |
| Account | `get_account`, `get_account_usage` | `max_sweep_cartesian` reports the account's Cartesian sweep cap; check shared storage before retaining signals. |
| Live Execution | `start_live`, `get_live`, `stop_live`, `list_live`, `list_public_live`, `update_live`, `update_live_params`, `send_live_command`, `get_live_signals`, `get_next_live_signals`, `get_live_run_paper`, `get_live_run_paper_equity`, `get_next_live_run_paper_equity` | Paper simulation is opt-in. Signal and paper-equity continuation preserve filters. `mint_live_connection_token` remains generated-client only because the SDK has no managed WebSocket client. |

The generated `qtsurfer-api-client` is the endpoint-level escape hatch, not a competing SDK
surface. Its version is pinned with the SDK, so callers must not assume it exposes a newer API spec.

## Operation coverage

| OpenAPI operation | SDK method or deliberate endpoint-only access | Guide |
| --- | --- | --- |
| `authenticate` | `auth`, `ensure_token`, `refresh`, `TokenStore` | [Auth](auth.md) |
| `getAccount` | `get_account` | [Account](account.md) |
| `getAccountUsage` | `get_account_usage` | [Account](account.md) |
| `listExchanges` | `list_exchanges` | [Exchange](exchange.md) |
| `listInstruments` | `list_instruments(exchange_id)` | [Exchange](exchange.md) |
| `listSegmentInstruments` | `list_instruments(exchange_id, segment)` | [Exchange](exchange.md) |
| `downloadTickers` | Endpoint-only public binary adapter `api.exchange.download_tickers`; application owns files/retries | [Exchange](exchange.md) |
| `downloadKlines` | Endpoint-only public binary adapter `api.exchange.download_klines`; application owns files/retries | [Exchange](exchange.md) |
| `compileStrategy` | `compile_strategy`; SDK adapts unsupported generated text/plain body | [Strategy](strategy.md) |
| `validateStrategy` | `validate_strategy` | [Strategy](strategy.md) |
| `getStrategy` | `get_strategy` | [Strategy](strategy.md) |
| `listStrategies` | `list_strategies(include_deleted=False)` | [Strategy](strategy.md) |
| `deleteStrategy` | `delete_strategy` | [Strategy](strategy.md) |
| `getStrategyCode` | `get_strategy_code` | [Strategy](strategy.md) |
| `prepareBacktest` | `prepare` | [Backtesting](backtesting.md) |
| `getPrepareStatus` | `get_prepare_status` | [Backtesting](backtesting.md) |
| `executeBacktest` | `execute` | [Backtesting](backtesting.md) |
| `getBacktestResult` | `get_backtest_result` (raw HTTP response) | [Backtesting](backtesting.md) |
| `cancelBacktest` | `cancel_backtest` | [Backtesting](backtesting.md) |
| `executeSweep` | `sweep` | [Backtesting](backtesting.md) |
| `getSweepResult` | `get_sweep_result` | [Backtesting](backtesting.md) |
| `cancelSweep` | `cancel_sweep` | [Backtesting](backtesting.md) |
| `getSweepSensitivity` | `get_sweep_sensitivity` | [Backtesting](backtesting.md) |
| `getSweepRunEquityCurve` | `get_sweep_run_equity_curve` | [Backtesting](backtesting.md) |
| `createDataset` | `create_dataset` | [Datasets](datasets.md) |
| `listDatasets` | `list_datasets(include_deleted=False)` | [Datasets](datasets.md) |
| `getDataset` | `get_dataset` | [Datasets](datasets.md) |
| `deleteDataset` | `delete_dataset` | [Datasets](datasets.md) |
| `openDatasetUpload` | `open_dataset_upload`; `upload_dataset_file` sends bytes separately | [Datasets](datasets.md) |
| `finalizeDatasetUpload` | `finalize_dataset_upload` | [Datasets](datasets.md) |
| `getDatasetUpload` | `get_dataset_upload` | [Datasets](datasets.md) |
| `importDataset` | Endpoint-only `api.dataset.import_dataset`; source-specific imports stay at endpoint layer | [Datasets](datasets.md#import-exchange-history) |
| `getDatasetImport` | Endpoint-only `api.dataset.get_dataset_import`; application persists ids and polls imports | [Datasets](datasets.md#import-exchange-history) |
| `startLive` | `start_live` | [Live](live.md) |
| `getLive` | `get_live` | [Live](live.md) |
| `stopLive` | `stop_live` | [Live](live.md) |
| `listLive` | `list_live` (owned runs) | [Live](live.md) |
| `listPublicLive` | `list_public_live` (public catalogue) | [Live](live.md) |
| `getLiveRun` | Endpoint-only `api.live_execution.get_live_run`; specific run-id access stays at endpoint layer | [Live](live.md#run-ids-and-stream-urls) |
| `updateLive` | `update_live` | [Live](live.md) |
| `updateLiveParams` | `update_live_params` accepts a mapping or generated request | [Live](live.md) |
| `sendLiveCommand` | `send_live_command` | [Live](live.md) |
| `getLiveRunSignals` | `get_live_signals`, `get_next_live_signals` | [Live](live.md) |
| `getLiveRunPaper` | `get_live_run_paper` | [Live](live.md) |
| `getLiveRunPaperEquity` | `get_live_run_paper_equity`, `get_next_live_run_paper_equity` | [Live](live.md) |
| `rotateLiveStream` | Endpoint-only `api.live_execution.rotate_live_stream`; SDK has no managed connection | [Live](live.md#run-ids-and-stream-urls) |
| `revokeLiveStream` | Endpoint-only `api.live_execution.revoke_live_stream`; SDK has no managed connection | [Live](live.md#run-ids-and-stream-urls) |
| `mintLiveConnectionToken` | Endpoint-only `api.live_execution.mint_live_connection_token`; SDK has no managed connection | [Live](live.md#run-ids-and-stream-urls) |

AsyncAPI 0.3.0 `history` is also not part of the generated REST client. The SDK does not manage a
WebSocket connection, so callers that need it must use a compatible WebSocket/Centrifugo client.
