"""
Small CoinMarketCap API client for SENTDIV.

The client intentionally avoids printing secrets and only reads CMC_API_KEY
from the process environment or a local .env file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://pro-api.coinmarketcap.com"


class CmcApiError(RuntimeError):
    """Raised when CMC data cannot be fetched or parsed."""


class CmcClient:
    def __init__(self, api_key: str | None = None, base_url: str = BASE_URL) -> None:
        self.api_key = api_key or _load_api_key()
        self.base_url = base_url.rstrip("/")
        if not self.api_key:
            raise CmcApiError("CMC_API_KEY is missing. Add it to sentdiv-skill/.env or your environment.")

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        query = f"?{urlencode(params or {})}" if params else ""
        url = f"{self.base_url}{path}{query}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "X-CMC_PRO_API_KEY": self.api_key,
            },
            method="GET",
        )

        try:
            with urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise CmcApiError(f"CMC HTTP {exc.code} for {path}: {_safe_error_body(body)}") from exc
        except URLError as exc:
            raise CmcApiError(f"CMC network error for {path}: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise CmcApiError(f"CMC returned invalid JSON for {path}") from exc

    def cryptocurrency_map(self, symbol: str) -> dict:
        payload = self.get("/v1/cryptocurrency/map", {"symbol": symbol.upper()})
        data = payload.get("data") or []
        if not data:
            raise CmcApiError(f"Could not resolve CMC id for symbol {symbol}")
        return data[0]

    def ohlcv_historical(self, cmc_id: int, count: int, interval: str = "daily") -> dict:
        return self.get(
            "/v2/cryptocurrency/ohlcv/historical",
            {
                "id": cmc_id,
                "time_period": interval,
                "count": count,
                "convert": "USD",
            },
        )

    def quotes_latest(self, symbol: str) -> dict:
        return self.get("/v3/cryptocurrency/quotes/latest", {"symbol": symbol.upper(), "convert": "USD"})

    def quotes_latest_legacy(self, symbol: str) -> dict:
        return self.get("/v1/cryptocurrency/quotes/latest", {"symbol": symbol.upper(), "convert": "USD"})

    def fear_and_greed_latest(self) -> dict:
        return self.get("/v3/fear-and-greed/latest")

    def dex_token_pools(self, network_slug: str, contract_address: str) -> dict:
        return self.get(
            "/v1/dex/token/pools",
            {
                "network_slug": network_slug,
                "contract_address": contract_address,
            },
        )

    def dex_token_liquidity(self, network_slug: str, contract_address: str) -> dict:
        return self.get(
            "/v1/dex/token-liquidity/query",
            {
                "network_slug": network_slug,
                "contract_address": contract_address,
            },
        )


def _load_api_key() -> str | None:
    if os.getenv("CMC_API_KEY"):
        return os.getenv("CMC_API_KEY")

    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return None

    for line in env_path.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#") or "=" not in clean:
            continue
        key, value = clean.split("=", 1)
        if key.strip() == "CMC_API_KEY":
            return value.strip().strip('"').strip("'")
    return None


def _safe_error_body(body: str) -> str:
    if len(body) > 500:
        return body[:500] + "..."
    return body
