"""
Terminal and JSON report helpers for SENTDIV.
"""

from __future__ import annotations

import json


def print_signal(signal: dict) -> None:
    print("=" * 72)
    print("SENTDIV - Sentiment / On-chain Divergence Skill")
    print("=" * 72)
    print(f"Token:       {signal['token']}")
    print(f"Timestamp:   {signal['timestamp']}")
    print(f"Signal:      {signal['signal']}")
    print(f"Action:      {signal['action']}")
    print(f"Confidence:  {signal['confidence']}/100")
    if signal.get("data_mode"):
        print(f"Data mode:   {signal['data_mode']}")
    print(f"SHI:         {signal['social_heat_index']:+.3f}")
    print(f"OFI:         {signal['onchain_flow_index']:+.3f}")
    print(f"Divergence:  {signal['divergence_score']:+.3f}")
    print()
    print(signal["explanation"])
    if signal.get("data_mode") == "cmc_latest_proxy":
        print("Note: CMC historical OHLCV is unavailable on this API plan; using latest quote proxy mode.")
    if signal.get("missing_data"):
        print(f"Missing data fields: {', '.join(signal['missing_data'])}")
    print("=" * 72)


def print_backtest(results: dict) -> None:
    print("\nBACKTEST")
    print("-" * 72)
    print(f"Token:          {results['token']}")
    print(f"Starting cap:   ${results['starting_capital']:,.2f}")
    print(f"Ending cap:     ${results['ending_capital']:,.2f}")
    print(f"Total return:   {results['total_return_pct']:+.2f}%")
    print(f"Max drawdown:   {results['max_drawdown_pct']:.2f}%")
    print(f"Trades:         {results['trade_count']}")
    print(f"Win rate:       {results['win_rate']:.2f}%")
    print()

    for trade in results["trades"][:12]:
        if trade["type"] == "BUY":
            print(f"{trade['timestamp']} BUY  ${trade['price']:,.6f}  {trade['reason']}")
        else:
            print(
                f"{trade['timestamp']} SELL ${trade['price']:,.6f}  "
                f"PnL {trade.get('pnl_pct', 0):+.2f}%  {trade['reason']}"
            )
    print("-" * 72)


def print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))
