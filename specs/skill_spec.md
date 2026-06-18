# SENTDIV Skill Spec

## Name

`sentdiv-skill`

## Purpose

Detect sentiment/on-chain divergence for BNB ecosystem assets and produce a backtestable trading strategy signal.

## Input

```json
{
  "token": "BNB",
  "timeframe": "1d",
  "lookback": 30,
  "rows": [
    {
      "timestamp": "2026-01-01",
      "close": 610.0,
      "volume": 1100000000,
      "mention_velocity": 10,
      "engagement_velocity": 9,
      "sentiment_momentum": 4,
      "kol_breadth": 5,
      "holder_accumulation": 6,
      "dex_buy_pressure": 5,
      "active_address_growth": 5,
      "liquidity_inflow": 4,
      "exchange_deposit_pressure": 3,
      "realized_volatility": 0.04
    }
  ]
}
```

## Real CMC Data Mode

`sentdiv-skill` supports two data sources:

- `sample`: deterministic local data for judge-friendly offline demos.
- `cmc`: real CMC market data loaded with `CMC_API_KEY`.

CLI example:

```bash
python main.py --source cmc --token BNB --periods 60 --backtest
python main.py --source cmc --token CMC20 --network bsc --contract-address <bsc_contract> --backtest --json
```

CMC mode uses:

- `/v1/cryptocurrency/map`
- `/v2/cryptocurrency/ohlcv/historical`
- `/v3/fear-and-greed/latest`
- Optional `/v1/dex/token/pools`
- Optional `/v1/dex/token-liquidity/query`

If full social/KOL/on-chain fields are not available on the active CMC plan, the adapter creates transparent proxy fields from real CMC OHLCV, volume, market cap, Fear & Greed, and optional DEX liquidity context. Proxy fields are marked in each row as `proxy_fields`.

## Core Formulas

```text
SHI_t =
  0.35 * z(mention_velocity_t, 30d)
+ 0.25 * z(engagement_velocity_t, 30d)
+ 0.20 * z(sentiment_momentum_t, 30d)
+ 0.20 * z(kol_breadth_t, 30d)
```

```text
OFI_t =
  0.30 * z(holder_accumulation_t, 30d)
+ 0.25 * z(dex_buy_pressure_t, 30d)
+ 0.20 * z(active_address_growth_t, 30d)
+ 0.15 * z(liquidity_inflow_t, 30d)
- 0.10 * z(exchange_deposit_pressure_t, 30d)
```

```text
DIVERGENCE_t = SHI_t - OFI_t
```

If a field is missing, the engine removes it from that index and renormalizes the remaining weights. Missing fields are returned in `missing_data`.

## Signal Rules

### BULLISH_HIDDEN_ACCUMULATION

- `OFI_t >= +1.0`
- `SHI_t <= +0.25`
- Price is above or near its 20-period moving average
- Action: `LONG`

### BEARISH_HYPE_WITHOUT_FLOW

- `SHI_t >= +1.25`
- `OFI_t <= 0`
- Action: `EXIT_OR_SHORT`

### BULLISH_CONFIRMATION

- `SHI_t >= +0.5`
- `OFI_t >= +0.5`
- Action: `HOLD_LONG`

### CROWDED_EXIT

- `SHI_t >= +2.0`
- `OFI_t` has been falling for recent periods
- Action: `REDUCE`

## Output

```json
{
  "token": "BNB",
  "timestamp": "2026-02-12",
  "signal": "BULLISH_HIDDEN_ACCUMULATION",
  "action": "LONG",
  "confidence": 82,
  "social_heat_index": -0.12,
  "onchain_flow_index": 1.36,
  "divergence_score": -1.48,
  "explanation": "On-chain flow is rising while social heat remains muted, suggesting accumulation before narrative expansion.",
  "missing_data": []
}
```

## Backtest Rules

- Signals are generated at candle `t`.
- Trades execute at candle `t+1`.
- Long entries require `action = LONG` and `confidence >= 70`.
- Default position size is 10% of portfolio.
- Default transaction cost is 20 bps per side.
- Exit on stop loss, take profit, time stop, flow reversal, bearish hype, or crowded exit.

## Judge Prompt

```text
Find sentiment/on-chain divergences for BNB ecosystem tokens over the last 30 days.
Return the top tradeable signal, confidence, explanation, and backtest summary.
```
