# Exchanges and instruments

Discover the catalog before selecting a data window. Coverage is live platform state and is not
cached by the SDK.

```python
exchanges = session.list_exchanges()
spot = session.list_instruments("binance")
futures = session.list_instruments("binance", segment="futures")
print(spot[0].coverage.tickers)
```

The generated `qtsurfer-api-client` remains the endpoint-level interface for download operations;
use it through `session.call(...)` when a raw API operation is deliberately required.
