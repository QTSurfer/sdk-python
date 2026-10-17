# Exchanges and instruments

Start with an authenticated session; every example below uses `session`:

```python
from qtsurfer_sdk import auth

session = auth()  # reads QTSURFER_APIKEY
```

## List exchanges

`list_exchanges()` returns the current exchange catalogue. It takes no parameters and is not cached.
Every exchange names its `venue_type` (`cex` / `dex`), `segments`, and `live_segments`.
Only `live_segments` can feed live runs; a catalogue segment need not have live data.

```python
exchanges = session.list_exchanges()
print(exchanges[0].id)
```

## List instruments

`list_instruments(exchange_id, segment=None)` returns an `InstrumentListResponse` for CEX or
`PoolListResponse` for DEX, retaining `data`, `meta`, and `field_links`. `meta.venue_type`
identifies the kind. Omit `segment` for CEX spot or the DEX's first protocol; otherwise
use one of the exchange's discovered `segments`.

```python
spot = session.list_instruments("binance")
futures = session.list_instruments("binance", segment="futures")
print(spot.data[0].coverage.tickers)

pools = session.list_instruments("robinhood", segment="uniswap-v3")
for pool in pools.data:
    print(pool.id, pool.symbol, pool.tvl_usd, pool.volume24h_usd)
```

## Download market data

Pool `id` is the address to put in a live source; `symbol` names its signals. Discovery
lists at most 50 pools with the most 24-hour USD volume among those with at least
$10,000 liquidity, refreshed hourly. A live run may use an unlisted pool too.
`last_price` and `volume24h` are in quote currency, and pool values can be one hour old.
Missing price, volume, and pool creation time are `UNSET`, never `None`; CEX `settle`
is optional and belongs to futures instruments. Unknown exchange/segment is `400`;
an unavailable catalogue is `404`. DEX ids cannot prepare or backtest managed data.

The SDK does not wrap `download_tickers` or `download_klines`; use public binary `sync_detailed` through
`session.call` and consume `response.content`. `hour` is one UTC hour (`YYYY-MM-DDTHH`); `format`
defaults to Lastra and may be `parquet`.

```python
from datetime import UTC, datetime, timedelta
from qtsurfer.api.client.api.exchange import download_tickers

hour = (datetime.now(UTC) - timedelta(hours=2)).strftime("%Y-%m-%dT%H")
response = session.call(
    lambda client: download_tickers.sync_detailed(
        "binance", "BTC", "USDT", hour=hour, client=client
    )
)
if response.status_code == 200:
    print(response.headers.get("X-Data-Status"), response.headers.get("X-Data-Through"))
    with open("BTC_USDT.lastra", "wb") as output:
        output.write(response.content)
else:
    print(response.parsed.reason, response.headers.get("Retry-After"))
```

Import from `qtsurfer.api.client.api.exchange`: private generated downloads do not handle
successful binary responses. `format_` defaults to Lastra; pass `DownloadTickersFormat.PARQUET`
(or `DownloadKlinesFormat.PARQUET`). Lastra uses `application/vnd.qtsurfer.lastra`,
and `ts` is microseconds since epoch (`X-Ts-Unit: micros`, column `ts_unit: micros`);
Parquet keeps millisecond timestamps. Bytes and headers are returned unchanged.

The window is seven days. `400 OUTSIDE_WINDOW` includes `response.parsed.next_`, a typed
`ErrorNextCall` for a CEX dataset import; add a name before submitting its body.
See [dataset imports](datasets.md#import-exchange-history). Recent hours can return
`200` provisional (`X-Data-Status: provisional`, `X-Data-Through` in ISO-8601 UTC regardless
of `ts` units), or `404 NOT_YET_AVAILABLE` with `Retry-After`; handle both and ask again.
Provisional bytes can grow: do not archive them as a complete hour. `404 NO_DATA` means
the stored hour contains no instrument rows. `503 TEMPORARILY_UNAVAILABLE` is retryable
after `Retry-After`; malformed/future hours are `400`. Unknown reasons should be handled
like an absent reason, using status and message.
