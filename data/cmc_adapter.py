"""
CMC response adapter for SENTDIV row schema.

CMC market data is real. Some social/on-chain fields may not be available on
every API plan, so this adapter exposes conservative proxy fields and marks
their source in each row.
"""

from __future__ import annotations

from datetime import date, timedelta
from statistics import mean

from data.cmc_client import CmcApiError, CmcClient


def load_cmc_series(
    token: str,
    periods: int = 60,
    interval: str = "daily",
    network_slug: str = "bsc",
    contract_address: str | None = None,
) -> list[dict]:
    client = CmcClient()
    token_info = client.cryptocurrency_map(token)
    cmc_id = int(token_info["id"])
    symbol = token_info.get("symbol", token.upper())

    data_mode = "cmc_historical"
    fallback_reason = None
    try:
        ohlcv_payload = client.ohlcv_historical(cmc_id, periods, interval)
        candles = _extract_ohlcv_quotes(ohlcv_payload)
    except CmcApiError as exc:
        fallback_reason = str(exc)
        quote_payload = _safe_latest_quote(client, symbol)
        candles = _build_latest_proxy_candles(symbol, quote_payload, periods)
        data_mode = "cmc_latest_proxy"

    if len(candles) < 5:
        raise CmcApiError("CMC OHLCV response did not contain enough candles for SENTDIV analysis.")

    fear_greed = _safe_fear_greed(client)
    dex_context = _safe_dex_context(client, network_slug, contract_address) if contract_address else {}

    rows: list[dict] = []
    for idx, candle in enumerate(candles):
        close = candle["close"]
        volume = candle["volume"]
        market_cap = candle["market_cap"]
        prev = candles[idx - 1] if idx > 0 else candle
        volume_ma = _window_mean(candles, idx, "volume", 7)
        market_cap_change = _pct_change(market_cap, prev["market_cap"])
        close_change = _pct_change(close, prev["close"])
        volume_ratio = volume / volume_ma if volume_ma else 1.0

        # SHI proxies: real CMC market attention and sentiment proxies.
        mention_velocity = 10 * volume_ratio
        engagement_velocity = 8 * volume_ratio + max(close_change, 0) * 0.2
        sentiment_momentum = fear_greed + close_change
        kol_breadth = 5 + max(volume_ratio - 1, 0) * 4

        # OFI proxies: conservative flow approximations from CMC market/DEX data.
        liquidity_multiplier = dex_context.get("liquidity_multiplier", 1.0)
        holder_accumulation = max(market_cap_change, 0) + max(close_change, 0) * 0.5
        dex_buy_pressure = max(close_change, 0) * volume_ratio * liquidity_multiplier
        active_address_growth = max(volume_ratio - 1, 0) * 8
        liquidity_inflow = max(market_cap_change, 0) * liquidity_multiplier
        exchange_deposit_pressure = max(-close_change, 0) * volume_ratio

        rows.append(
            {
                "timestamp": candle["timestamp"],
                "token": symbol,
                "close": close,
                "volume": volume,
                "market_cap": market_cap,
                "mention_velocity": mention_velocity,
                "engagement_velocity": engagement_velocity,
                "sentiment_momentum": sentiment_momentum,
                "kol_breadth": kol_breadth,
                "holder_accumulation": holder_accumulation,
                "dex_buy_pressure": dex_buy_pressure,
                "active_address_growth": active_address_growth,
                "liquidity_inflow": liquidity_inflow,
                "exchange_deposit_pressure": exchange_deposit_pressure,
                "realized_volatility": _realized_volatility(candles, idx, 14),
                "data_source": "cmc",
                "data_mode": data_mode,
                "proxy_fields": [
                    "mention_velocity",
                    "engagement_velocity",
                    "sentiment_momentum",
                    "kol_breadth",
                    "holder_accumulation",
                    "dex_buy_pressure",
                    "active_address_growth",
                    "liquidity_inflow",
                    "exchange_deposit_pressure",
                ],
                "cmc_context": {
                    "cmc_id": cmc_id,
                    "network_slug": network_slug,
                    "contract_address": contract_address,
                    "fear_greed_latest": fear_greed,
                    "fallback_reason": fallback_reason,
                    **dex_context,
                },
            }
        )

    return rows


def _safe_latest_quote(client: CmcClient, symbol: str) -> dict:
    try:
        return client.quotes_latest(symbol)
    except CmcApiError:
        return client.quotes_latest_legacy(symbol)


def _build_latest_proxy_candles(symbol: str, payload: dict, periods: int) -> list[dict]:
    quote_data = _extract_latest_quote(payload, symbol)
    quote = _extract_usd_quote(quote_data)
    close = float(quote.get("price") or 0)
    volume = float(quote.get("volume_24h") or 0)
    market_cap = float(quote.get("market_cap") or 0)
    p1h = float(quote.get("percent_change_1h") or 0)
    p24h = float(quote.get("percent_change_24h") or 0)
    p7d = float(quote.get("percent_change_7d") or 0)

    if close <= 0:
        raise CmcApiError("CMC latest quote did not include a valid price.")

    start = date.today() - timedelta(days=periods - 1)
    candles: list[dict] = []
    base_7d_step = p7d / max(min(periods, 7), 1) / 100

    for idx in range(periods):
        distance = periods - 1 - idx
        drift = base_7d_step * distance
        intraday = (p24h / 100) * min(distance, 1)
        close_i = close / max(0.1, 1 + drift + intraday)
        volume_i = volume * (1 + 0.03 * ((idx % 5) - 2))
        market_cap_i = market_cap * (close_i / close) if market_cap else 0
        candles.append(
            {
                "timestamp": (start + timedelta(days=idx)).isoformat(),
                "close": close_i,
                "volume": max(volume_i, 0),
                "market_cap": max(market_cap_i, 0),
            }
        )

    candles[-1]["close"] = close
    candles[-1]["volume"] = volume
    candles[-1]["market_cap"] = market_cap
    if periods >= 2 and p1h:
        candles[-2]["close"] = close / (1 + p1h / 100)
    return candles


def _extract_usd_quote(quote_data: dict) -> dict:
    quote = quote_data.get("quote", {})
    if isinstance(quote, list):
        for item in quote:
            if str(item.get("symbol", "")).upper() == "USD":
                return item
        return quote[0] if quote else {}
    if isinstance(quote, dict):
        return quote.get("USD", quote)
    return {}


def _extract_latest_quote(payload: dict, symbol: str) -> dict:
    data = payload.get("data") or {}
    if isinstance(data, list):
        for item in data:
            if str(item.get("symbol", "")).upper() == symbol.upper():
                return item
        if data:
            return data[0]

    token = data.get(symbol.upper())
    if isinstance(token, list):
        token = token[0] if token else {}
    if isinstance(token, dict):
        return token
    raise CmcApiError(f"CMC latest quote response did not contain {symbol}.")


def _extract_ohlcv_quotes(payload: dict) -> list[dict]:
    data = payload.get("data") or {}
    quotes = data.get("quotes") or []
    candles: list[dict] = []

    for item in quotes:
        quote = (item.get("quote") or {}).get("USD") or {}
        close = quote.get("close")
        volume = quote.get("volume")
        if close is None or volume is None:
            continue
        candles.append(
            {
                "timestamp": item.get("time_close") or quote.get("timestamp") or item.get("timestamp"),
                "close": float(close),
                "volume": float(volume),
                "market_cap": float(quote.get("market_cap") or 0),
            }
        )

    return candles


def _safe_fear_greed(client: CmcClient) -> float:
    try:
        payload = client.fear_and_greed_latest()
    except CmcApiError:
        return 50.0

    data = payload.get("data")
    if isinstance(data, list) and data:
        value = data[0].get("value")
    elif isinstance(data, dict):
        value = data.get("value")
    else:
        value = None

    try:
        return float(value)
    except (TypeError, ValueError):
        return 50.0


def _safe_dex_context(client: CmcClient, network_slug: str, contract_address: str | None) -> dict:
    if not contract_address:
        return {}

    context: dict = {}
    try:
        pools = client.dex_token_pools(network_slug, contract_address)
        context["dex_pools_available"] = bool(pools.get("data"))
        context["liquidity_multiplier"] = 1.1 if context["dex_pools_available"] else 1.0
    except CmcApiError as exc:
        context["dex_pools_error"] = str(exc)
        context["liquidity_multiplier"] = 1.0

    try:
        liquidity = client.dex_token_liquidity(network_slug, contract_address)
        context["dex_liquidity_available"] = bool(liquidity.get("data"))
        if context["dex_liquidity_available"]:
            context["liquidity_multiplier"] = 1.2
    except CmcApiError as exc:
        context["dex_liquidity_error"] = str(exc)

    return context


def _window_mean(rows: list[dict], idx: int, field: str, window: int) -> float:
    values = [row[field] for row in rows[max(0, idx - window + 1) : idx + 1] if row.get(field) is not None]
    return mean(values) if values else 0.0


def _pct_change(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return ((current - previous) / previous) * 100


def _realized_volatility(rows: list[dict], idx: int, window: int) -> float:
    returns: list[float] = []
    start = max(1, idx - window + 1)
    for pos in range(start, idx + 1):
        returns.append(_pct_change(rows[pos]["close"], rows[pos - 1]["close"]) / 100)
    if not returns:
        return 0.0
    avg = mean(returns)
    variance = mean([(ret - avg) ** 2 for ret in returns])
    return variance**0.5
