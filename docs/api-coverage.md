# API coverage

This release targets API spec **0.126.2** through `qtsurfer-api-client==0.126.2`. Every spec
operation is either wrapped below or deliberately left to the generated client.

| Domain | SDK surface | DX boundary |
| --- | --- | --- |
| Authentication | `auth`, refresh-on-401, `TokenStore` | `auth()` owns API-key exchange and retries one `401`. |
| Exchange | `list_exchanges`, `list_instruments` | `download_tickers` and `download_klines` remain available through the generated binary client. |
| Strategy | `compile_strategy`, `validate_strategy`, `get_strategy`, `list_strategies`, `get_strategy_code`, `delete_strategy` | `compile_strategy` adapts `text/plain`, unsupported by the generator. |
| Backtesting | `prepare`, `get_prepare_status`, `execute`, `get_backtest_result`, `cancel_backtest` | Explicit stages preserve durable job ids for application-owned polling. |
| Sweeps | `sweep`, `get_sweep_result`, `get_sweep_sensitivity`, `get_sweep_run_equity_curve`, `cancel_sweep` | The caller owns pagination and polling policy. |
| Dataset | `create_dataset`, `list_datasets`, `get_dataset`, `delete_dataset`, `open_dataset_upload`, `upload_dataset_file`, `finalize_dataset_upload`, `get_dataset_upload` | `import_dataset` and `get_dataset_import` remain generated-client operations. Presigned upload bytes never carry the API token. |
| Account | `get_account`, `get_account_usage` | Check limits and shared storage before retaining signals. |
| Live Execution | `start_live`, `get_live`, `stop_live`, `list_live`, `list_public_live`, `update_live`, `update_live_params`, `get_live_signals`, `get_next_live_signals` | Own-run and public-run listings are distinct. `mint_live_connection_token` remains generated-client only because the SDK has no managed WebSocket client. |

The generated `qtsurfer-api-client` is the endpoint-level escape hatch, not a competing SDK
surface. Its version is pinned with the SDK, so callers must not assume it exposes a newer API spec.
