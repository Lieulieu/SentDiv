"""
Smoke-test CMC endpoints used or considered by SENTDIV.

This script reads CMC_API_KEY through data.cmc_client.CmcClient and never
prints the key. It reports whether the current key/plan can access each
endpoint family from docs/cmc-api-integrate-skill.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.cmc_client import CmcApiError, CmcClient


def main() -> None:
    parser = argparse.ArgumentParser(description="CMC endpoint smoke test for SENTDIV")
    parser.add_argument("--symbol", default="BNB", help="Token symbol to test")
    parser.add_argument("--network", default="bsc", help="DEX network slug")
    parser.add_argument("--contract-address", help="Optional token contract for DEX endpoints")
    args = parser.parse_args()

    client = CmcClient()
    cmc_id = None

    checks = [
        ("Key info", "/v1/key/info", {}),
        ("Crypto map", "/v1/cryptocurrency/map", {"symbol": args.symbol.upper()}),
        ("Quotes latest v2", "/v2/cryptocurrency/quotes/latest", {"symbol": args.symbol.upper(), "convert": "USD"}),
        ("Quotes latest v3", "/v3/cryptocurrency/quotes/latest", {"symbol": args.symbol.upper(), "convert": "USD"}),
        ("Listings latest", "/v1/cryptocurrency/listings/latest", {"limit": 5, "sort": "market_cap"}),
        ("Trending latest", "/v1/cryptocurrency/trending/latest", {"limit": 5}),
        ("Trending gainers-losers", "/v1/cryptocurrency/trending/gainers-losers", {"limit": 5}),
        ("Fear and Greed latest", "/v3/fear-and-greed/latest", {}),
        ("Global metrics latest", "/v1/global-metrics/quotes/latest", {}),
        ("Community trending token", "/v1/community/trending/token", {}),
        ("Community trending topic", "/v1/community/trending/topic", {}),
        ("Content latest", "/v1/content/latest", {}),
        ("DEX platform list", "/v1/dex/platform/list", {}),
    ]

    print("CMC Smoke Test")
    print("=" * 72)
    for label, path, params in checks:
        payload = run_check(client, label, path, params)
        if label == "Crypto map" and payload:
            cmc_id = extract_cmc_id(payload)

    if cmc_id:
        run_check(
            client,
            "OHLCV latest v2",
            "/v2/cryptocurrency/ohlcv/latest",
            {"id": cmc_id, "convert": "USD"},
        )
        run_check(
            client,
            "OHLCV historical v2",
            "/v2/cryptocurrency/ohlcv/historical",
            {"id": cmc_id, "time_period": "daily", "count": 5, "convert": "USD"},
        )
        run_check(
            client,
            "Quotes historical v3",
            "/v3/cryptocurrency/quotes/historical",
            {"id": cmc_id, "interval": "daily", "count": 5, "convert": "USD"},
        )

    if args.contract_address:
        dex_params = {
            "network_slug": args.network,
            "contract_address": args.contract_address,
        }
        run_check(client, "DEX token", "/v1/dex/token", dex_params)
        run_check(client, "DEX token pools", "/v1/dex/token/pools", dex_params)
        run_check(client, "DEX token liquidity", "/v1/dex/token-liquidity/query", dex_params)
        run_check(client, "DEX token transactions", "/v1/dex/tokens/transactions", dex_params)

    print("=" * 72)
    print("Use OK endpoints for real data. 403 means the API key plan does not include that endpoint.")


def run_check(client: CmcClient, label: str, path: str, params: dict) -> dict | None:
    try:
        payload = client.get(path, params)
        count = response_count(payload)
        print(f"[OK]       {label:<28} {path} ({count})")
        return payload
    except CmcApiError as exc:
        message = str(exc)
        if "HTTP 403" in message:
            print(f"[403 PLAN] {label:<28} {path}")
        elif "HTTP 400" in message:
            print(f"[400 PARAM] {label:<28} {path}")
        elif "HTTP 401" in message:
            print(f"[401 KEY]  {label:<28} {path}")
        elif "HTTP 429" in message:
            print(f"[429 RATE] {label:<28} {path}")
        else:
            print(f"[FAIL]     {label:<28} {path} -> {message[:120]}")
        return None


def response_count(payload: dict) -> str:
    data = payload.get("data")
    if isinstance(data, list):
        return f"{len(data)} rows"
    if isinstance(data, dict):
        return f"{len(data)} keys"
    return "data present"


def extract_cmc_id(payload: dict) -> int | None:
    data = payload.get("data") or []
    if isinstance(data, list) and data:
        return int(data[0]["id"])
    return None


if __name__ == "__main__":
    main()
