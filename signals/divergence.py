"""
Sentiment/on-chain divergence signal engine.
"""

from __future__ import annotations

from statistics import mean, pstdev


SOCIAL_WEIGHTS = {
    "mention_velocity": 0.35,
    "engagement_velocity": 0.25,
    "sentiment_momentum": 0.20,
    "kol_breadth": 0.20,
}

FLOW_WEIGHTS = {
    "holder_accumulation": 0.30,
    "dex_buy_pressure": 0.25,
    "active_address_growth": 0.20,
    "liquidity_inflow": 0.15,
    "exchange_deposit_pressure": -0.10,
}


def analyze_series(rows: list[dict], lookback: int = 30) -> list[dict]:
    enriched: list[dict] = []
    for idx, row in enumerate(rows):
        history = rows[max(0, idx - lookback) : idx + 1]
        social_index, social_missing = _weighted_zscore(row, history, SOCIAL_WEIGHTS)
        flow_index, flow_missing = _weighted_zscore(row, history, FLOW_WEIGHTS)
        divergence = social_index - flow_index
        signal = classify_signal(idx, rows, enriched, social_index, flow_index, divergence)

        missing_data = social_missing + flow_missing
        data_quality = _data_quality(len(missing_data), len(SOCIAL_WEIGHTS) + len(FLOW_WEIGHTS))
        confidence = score_confidence(row, signal, social_index, flow_index, divergence, data_quality)

        enriched.append(
            {
                **row,
                "social_heat_index": round(social_index, 4),
                "onchain_flow_index": round(flow_index, 4),
                "divergence_score": round(divergence, 4),
                "signal": signal["signal"],
                "action": signal["action"],
                "confidence": confidence,
                "explanation": signal["explanation"],
                "missing_data": missing_data,
            }
        )
    return enriched


def latest_signal(rows: list[dict], lookback: int = 30) -> dict:
    enriched = analyze_series(rows, lookback)
    return enriched[-1]


def classify_signal(
    idx: int,
    raw_rows: list[dict],
    enriched_rows: list[dict],
    social_index: float,
    flow_index: float,
    divergence: float,
) -> dict:
    price = raw_rows[idx].get("close", 0)
    ma20 = _moving_average(raw_rows, idx, "close", 20)
    price_ok = price >= ma20 * 0.98 if ma20 else True
    flow_falling = _is_flow_falling(enriched_rows)

    if flow_index >= 1.0 and social_index <= 0.25 and price_ok:
        return {
            "signal": "BULLISH_HIDDEN_ACCUMULATION",
            "action": "LONG",
            "explanation": "On-chain flow is rising while social heat remains muted, suggesting accumulation before narrative expansion.",
        }

    if social_index >= 1.25 and flow_index <= 0:
        return {
            "signal": "BEARISH_HYPE_WITHOUT_FLOW",
            "action": "EXIT_OR_SHORT",
            "explanation": "Social heat is elevated but on-chain flow does not confirm it, suggesting hype without durable demand.",
        }

    if social_index >= 2.0 and flow_falling:
        return {
            "signal": "CROWDED_EXIT",
            "action": "REDUCE",
            "explanation": "Social heat is crowded while flow is weakening, so the strategy reduces exposure.",
        }

    if social_index >= 0.5 and flow_index >= 0.5:
        return {
            "signal": "BULLISH_CONFIRMATION",
            "action": "HOLD_LONG",
            "explanation": "Social attention and on-chain flow agree, supporting an existing long position.",
        }

    return {
        "signal": "NEUTRAL",
        "action": "HOLD",
        "explanation": "No strong sentiment/on-chain divergence is present.",
    }


def score_confidence(
    row: dict,
    signal: dict,
    social_index: float,
    flow_index: float,
    divergence: float,
    data_quality: float,
) -> int:
    divergence_strength = min(abs(divergence) / 2.5, 1.0)
    liquidity_quality = 1.0 if row.get("volume", 0) >= 10_000_000 else 0.55
    trend_alignment = _trend_alignment(signal["signal"], social_index, flow_index)
    volatility = row.get("realized_volatility", 0.05)
    risk_adjustment = max(0.0, min(1.0, 1.0 - (volatility / 0.15)))

    raw = (
        30 * divergence_strength
        + 25 * data_quality
        + 20 * liquidity_quality
        + 15 * trend_alignment
        + 10 * risk_adjustment
    )

    if signal["signal"] == "NEUTRAL":
        raw = min(raw, 49)

    return int(round(max(0, min(100, raw))))


def _weighted_zscore(row: dict, history: list[dict], weights: dict[str, float]) -> tuple[float, list[str]]:
    score = 0.0
    used_weight = 0.0
    missing: list[str] = []

    for field, weight in weights.items():
        current = row.get(field)
        values = [r.get(field) for r in history if r.get(field) is not None]
        if current is None or len(values) < 3:
            missing.append(field)
            continue

        score += weight * _zscore(float(current), [float(v) for v in values])
        used_weight += abs(weight)

    if used_weight == 0:
        return 0.0, missing

    return score / used_weight, missing


def _zscore(current: float, values: list[float]) -> float:
    sigma = pstdev(values)
    if sigma == 0:
        return 0.0
    return (current - mean(values)) / sigma


def _moving_average(rows: list[dict], idx: int, field: str, window: int) -> float | None:
    values = [r.get(field) for r in rows[max(0, idx - window + 1) : idx + 1] if r.get(field) is not None]
    if not values:
        return None
    return mean(values)


def _is_flow_falling(enriched_rows: list[dict]) -> bool:
    if len(enriched_rows) < 3:
        return False
    last_three = [row["onchain_flow_index"] for row in enriched_rows[-3:]]
    return last_three[0] > last_three[1] > last_three[2]


def _trend_alignment(signal: str, social_index: float, flow_index: float) -> float:
    if signal == "BULLISH_HIDDEN_ACCUMULATION":
        return 1.0 if flow_index > social_index else 0.6
    if signal == "BEARISH_HYPE_WITHOUT_FLOW":
        return 1.0 if social_index > flow_index else 0.6
    if signal == "BULLISH_CONFIRMATION":
        return 0.8
    if signal == "CROWDED_EXIT":
        return 0.75
    return 0.3


def _data_quality(missing_count: int, total_fields: int) -> float:
    return max(0.0, min(1.0, 1 - (missing_count / total_fields)))
