# API coverage

Measured against API spec **0.111.2**: all 29 operations are reachable through the Python SDK or,
where appropriate, its exposed generated client.

| Section | SDK surface |
| --- | --- |
| Auth | `auth`, refresh-on-401, `TokenStore` |
| Exchange | `list_exchanges`, `list_instruments`; generated client for raw downloads |
| Strategy | `compile_strategy`, `validate_strategy`, `get_strategy`, `list_strategies`, `get_strategy_code`, `delete_strategy` |
| Backtesting | `prepare`, `get_prepare_status`, `execute`, `get_backtest_result`, `cancel_backtest` |
| Sweeps | `sweep`, `get_sweep_result`, `get_sweep_sensitivity`, `get_sweep_run_equity_curve`, `cancel_sweep` |
| Dataset | `create_dataset`, `list_datasets`, `get_dataset`, `delete_dataset`, `open_dataset_upload`, `upload_dataset_file`, `finalize_dataset_upload`, `get_dataset_upload` |

The session deliberately exposes stages for integration with applications that persist job ids. The
generated `qtsurfer-api-client` remains the endpoint-level escape hatch, not a competing SDK surface.
