# Exchanges and instruments

Start with an authenticated session; every example below uses `session`:

```python
from qtsurfer_sdk import auth

session = auth()  # reads QTSURFER_APIKEY
```

## List exchanges

`list_exchanges()` returns the current exchange catalogue. It takes no parameters and is not cached.

```python
exchanges = session.list_exchanges()
print(exchanges[0].id)
```

## List instruments

`list_instruments(exchange_id, segment=None)` defaults to `spot`; pass `futures` for that market.
Coverage describes live platform availability.

```python
spot = session.list_instruments("binance")
futures = session.list_instruments("binance", segment="futures")
print(spot[0].coverage.tickers)
```

## Download market data

The SDK does not wrap `download_tickers` or `download_klines`; use generated `sync_detailed` through
`session.call` and consume `response.content`. `hour` is one UTC hour (`YYYY-MM-DDTHH`); `format`
defaults to Lastra and may be `parquet`.

```python
from qtsurfer.api.client._generated.api.exchange import download_tickers

response = session.call(lambda client: download_tickers.sync_detailed(
    "binance", "BTC", "USDT", hour="2026-01-15T10", client=client
))
with open("BTC_USDT_h10.lastra", "wb") as output:
    output.write(response.content)
```
