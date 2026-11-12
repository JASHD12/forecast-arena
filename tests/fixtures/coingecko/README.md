# CoinGecko fixtures

Real responses of `https://api.coingecko.com/api/v3/coins/<id>/market_chart?vs_currency=usd&days=365&interval=daily`,
recorded on 2026-11-12 at about 20:32 UTC through the keyless public API (which the
CoinGecko documentation offers for testing), with the project User-Agent.

**Reduced**: only the `prices` array is kept (`market_caps` and `total_volumes` dropped);
gzipped. Each file has 365 points stamped 00:00 UTC (2025-11-13 to 2026-11-12) plus the
current price at recording time as the last point. Coins: bitcoin, ethereum, solana,
ripple (XRP), binancecoin (BNB).

Data provided by CoinGecko (https://www.coingecko.com).
