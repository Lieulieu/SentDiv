"""
SENTDIV - Sentiment / On-chain Divergence Skill.

Usage:
    python main.py --token BNB
    python main.py --token CMC20 --backtest
    python main.py --token BNB --json
    python main.py --source cmc --token BNB --backtest
"""

from __future__ import annotations

import argparse
import sys

from data.cmc_adapter import load_cmc_series
from data.cmc_client import CmcApiError
from data.sample_data import load_sample_series
from output.report import print_backtest, print_json, print_signal
from signals.divergence import latest_signal
from strategy.backtest import run_backtest


def analyze(
    token: str,
    periods: int,
    as_json: bool,
    with_backtest: bool,
    source: str,
    interval: str,
    network: str,
    contract_address: str | None,
) -> None:
    rows = load_rows(token, periods, source, interval, network, contract_address)
    signal = latest_signal(rows)

    if with_backtest:
        results = run_backtest(rows)
        payload = {
            "skill": "sentdiv-skill",
            "mode": source,
            "signal": signal,
            "backtest": results,
        }
        if as_json:
            print_json(payload)
        else:
            print_signal(signal)
            print_backtest(results)
        return

    payload = {
        "skill": "sentdiv-skill",
        "mode": source,
        "signal": signal,
    }

    if as_json:
        print_json(payload)
    else:
        print_signal(signal)


def load_rows(
    token: str,
    periods: int,
    source: str,
    interval: str,
    network: str,
    contract_address: str | None,
) -> list[dict]:
    if source == "sample":
        return load_sample_series(token, periods)
    if source == "cmc":
        return load_cmc_series(
            token=token,
            periods=periods,
            interval=interval,
            network_slug=network,
            contract_address=contract_address,
        )
    raise ValueError(f"Unsupported source: {source}")


def main() -> None:
    parser = argparse.ArgumentParser(description="SENTDIV - Sentiment / On-chain Divergence Skill")
    parser.add_argument("--token", default="BNB", help="Token symbol, e.g. BNB, CMC20, TWT")
    parser.add_argument("--periods", type=int, default=60, help="Number of candles to analyze")
    parser.add_argument("--source", choices=["sample", "cmc"], default="sample", help="Data source")
    parser.add_argument("--interval", default="daily", help="CMC OHLCV time period, default: daily")
    parser.add_argument("--network", default="bsc", help="DEX network slug for CMC DEX endpoints")
    parser.add_argument("--contract-address", help="Token contract address for DEX context")
    parser.add_argument("--backtest", action="store_true", help="Run event-based strategy backtest")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output")
    args = parser.parse_args()

    try:
        analyze(
            token=args.token.upper(),
            periods=args.periods,
            as_json=args.json,
            with_backtest=args.backtest,
            source=args.source,
            interval=args.interval,
            network=args.network,
            contract_address=args.contract_address,
        )
    except CmcApiError as exc:
        print(f"CMC data error: {exc}", file=sys.stderr)
        print("Tip: verify CMC_API_KEY and whether your CMC plan supports the requested endpoint.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
