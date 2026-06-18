"""
Deterministic sample dataset for SENTDIV.

The sample rows mimic the schema expected from CMC Agent Hub / Skills
Marketplace data adapters. They are not marketed as historical truth; they
exist so judges can run the Skill without credentials and inspect the strategy
logic end to end.
"""

from __future__ import annotations

from datetime import date, timedelta
from math import sin


TOKENS = ("BNB", "CMC20", "TWT")


def load_sample_series(token: str = "BNB", periods: int = 60) -> list[dict]:
    token = token.upper()
    if token not in TOKENS:
        token = "BNB"

    start = date(2026, 1, 1)
    rows: list[dict] = []
    price = {"BNB": 610.0, "CMC20": 100.0, "TWT": 1.35}[token]
    volume_base = {"BNB": 1_100_000_000, "CMC20": 500_000_000, "TWT": 32_000_000}[token]
    market_cap_base = {"BNB": 92_000_000_000, "CMC20": 20_000_000_000, "TWT": 550_000_000}[token]

    for i in range(periods):
        phase = _phase_profile(token, i)
        price *= 1 + phase["price_return"]
        volume = volume_base * (1 + phase["volume_boost"] + 0.05 * sin(i / 3))

        rows.append(
            {
                "timestamp": (start + timedelta(days=i)).isoformat(),
                "token": token,
                "close": round(price, 6),
                "volume": round(volume, 2),
                "market_cap": round(market_cap_base * (price / {"BNB": 610.0, "CMC20": 100.0, "TWT": 1.35}[token]), 2),
                "mention_velocity": phase["mention_velocity"],
                "engagement_velocity": phase["engagement_velocity"],
                "sentiment_momentum": phase["sentiment_momentum"],
                "kol_breadth": phase["kol_breadth"],
                "holder_accumulation": phase["holder_accumulation"],
                "dex_buy_pressure": phase["dex_buy_pressure"],
                "active_address_growth": phase["active_address_growth"],
                "liquidity_inflow": phase["liquidity_inflow"],
                "exchange_deposit_pressure": phase["exchange_deposit_pressure"],
                "realized_volatility": phase["realized_volatility"],
            }
        )

    return rows


def _phase_profile(token: str, i: int) -> dict:
    baseline = {
        "price_return": 0.001 + 0.004 * sin(i / 5),
        "volume_boost": 0.02 * sin(i / 4),
        "mention_velocity": 10 + 2 * sin(i / 6),
        "engagement_velocity": 9 + 2 * sin(i / 7),
        "sentiment_momentum": 4 + 1.5 * sin(i / 5),
        "kol_breadth": 5 + 1 * sin(i / 8),
        "holder_accumulation": 6 + 1.5 * sin(i / 5),
        "dex_buy_pressure": 5 + 1.5 * sin(i / 4),
        "active_address_growth": 5 + 1.0 * sin(i / 6),
        "liquidity_inflow": 4 + 1.0 * sin(i / 7),
        "exchange_deposit_pressure": 3 + 1.0 * sin(i / 5),
        "realized_volatility": 0.035 + 0.01 * abs(sin(i / 6)),
    }

    if token == "BNB" and 24 <= i <= 38:
        # Hidden accumulation: flow moves first, social remains quiet.
        baseline.update(
            {
                "price_return": 0.002 if i < 33 else 0.014,
                "volume_boost": 0.10,
                "mention_velocity": 9,
                "engagement_velocity": 8,
                "sentiment_momentum": 3,
                "kol_breadth": 4,
                "holder_accumulation": 24 + (i - 24) * 0.8,
                "dex_buy_pressure": 22 + (i - 24) * 0.6,
                "active_address_growth": 16,
                "liquidity_inflow": 18,
                "exchange_deposit_pressure": 2,
            }
        )

    if token == "CMC20" and 30 <= i <= 45:
        # Hype without flow: social explodes, on-chain support fades.
        baseline.update(
            {
                "price_return": 0.015 if i < 38 else -0.018,
                "volume_boost": 0.55,
                "mention_velocity": 30 + (i - 30) * 1.4,
                "engagement_velocity": 28 + (i - 30) * 1.1,
                "sentiment_momentum": 22,
                "kol_breadth": 19,
                "holder_accumulation": 3,
                "dex_buy_pressure": 2,
                "active_address_growth": 5,
                "liquidity_inflow": 2,
                "exchange_deposit_pressure": 18 + (i - 30) * 0.8,
                "realized_volatility": 0.08,
            }
        )

    if token == "TWT" and 20 <= i <= 44:
        # Mostly aligned growth: useful as a neutral/control case.
        baseline.update(
            {
                "price_return": 0.006,
                "volume_boost": 0.18,
                "mention_velocity": 17,
                "engagement_velocity": 16,
                "sentiment_momentum": 12,
                "kol_breadth": 11,
                "holder_accumulation": 16,
                "dex_buy_pressure": 15,
                "active_address_growth": 13,
                "liquidity_inflow": 12,
                "exchange_deposit_pressure": 5,
            }
        )

    return baseline
