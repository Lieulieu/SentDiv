"""
Event-based backtest for SENTDIV.

Signals are computed on candle t and executed on candle t+1 to avoid
lookahead bias.
"""

from __future__ import annotations

from signals.divergence import analyze_series


def run_backtest(
    rows: list[dict],
    starting_capital: float = 10_000.0,
    position_pct: float = 0.10,
    fee_bps: float = 20.0,
    max_hold_days: int = 14,
) -> dict:
    enriched = analyze_series(rows)
    cash = starting_capital
    position_units = 0.0
    entry_price = 0.0
    entry_idx = 0
    trades: list[dict] = []
    equity_curve: list[float] = []

    for idx in range(len(enriched) - 1):
        today = enriched[idx]
        tomorrow = enriched[idx + 1]
        execution_price = tomorrow["close"]
        signal = today["signal"]
        action = today["action"]
        confidence = today["confidence"]

        if position_units == 0 and action == "LONG" and confidence >= 70:
            notional = cash * position_pct
            fee = _fee(notional, fee_bps)
            position_units = (notional - fee) / execution_price
            cash -= notional
            entry_price = execution_price
            entry_idx = idx + 1
            trades.append(
                {
                    "timestamp": tomorrow["timestamp"],
                    "type": "BUY",
                    "price": round(execution_price, 6),
                    "notional": round(notional, 2),
                    "reason": signal,
                }
            )

        elif position_units > 0:
            hold_days = idx + 1 - entry_idx
            stop_loss = execution_price <= entry_price * 0.90
            take_profit = execution_price >= entry_price * 1.22
            exit_signal = action in ("EXIT_OR_SHORT", "REDUCE") or today["onchain_flow_index"] < 0
            time_stop = hold_days >= max_hold_days

            if stop_loss or take_profit or exit_signal or time_stop:
                proceeds = position_units * execution_price
                fee = _fee(proceeds, fee_bps)
                cash += proceeds - fee
                pnl_pct = ((execution_price - entry_price) / entry_price) * 100
                trades.append(
                    {
                        "timestamp": tomorrow["timestamp"],
                        "type": "SELL",
                        "price": round(execution_price, 6),
                        "pnl_pct": round(pnl_pct, 2),
                        "reason": _exit_reason(stop_loss, take_profit, exit_signal, time_stop, signal),
                    }
                )
                position_units = 0.0
                entry_price = 0.0

        mark_price = today["close"]
        equity_curve.append(cash + position_units * mark_price)

    if position_units > 0:
        last = enriched[-1]
        proceeds = position_units * last["close"]
        cash += proceeds - _fee(proceeds, fee_bps)
        pnl_pct = ((last["close"] - entry_price) / entry_price) * 100
        trades.append(
            {
                "timestamp": last["timestamp"],
                "type": "SELL",
                "price": round(last["close"], 6),
                "pnl_pct": round(pnl_pct, 2),
                "reason": "END_OF_BACKTEST",
            }
        )
        position_units = 0.0

    ending_capital = cash
    round_trips = [t for t in trades if t["type"] == "SELL"]
    wins = sum(1 for t in round_trips if t.get("pnl_pct", 0) > 0)
    losses = sum(1 for t in round_trips if t.get("pnl_pct", 0) <= 0)

    return {
        "token": rows[0]["token"] if rows else "UNKNOWN",
        "starting_capital": round(starting_capital, 2),
        "ending_capital": round(ending_capital, 2),
        "total_return_pct": round(((ending_capital - starting_capital) / starting_capital) * 100, 2),
        "max_drawdown_pct": _max_drawdown(equity_curve, starting_capital),
        "trades": trades,
        "trade_count": len(round_trips),
        "wins": wins,
        "losses": losses,
        "win_rate": round((wins / len(round_trips)) * 100, 2) if round_trips else 0.0,
        "latest_signal": enriched[-1] if enriched else {},
    }


def _fee(notional: float, fee_bps: float) -> float:
    return notional * fee_bps / 10_000


def _exit_reason(stop_loss: bool, take_profit: bool, exit_signal: bool, time_stop: bool, signal: str) -> str:
    if stop_loss:
        return "STOP_LOSS"
    if take_profit:
        return "TAKE_PROFIT"
    if exit_signal:
        return signal
    if time_stop:
        return "TIME_STOP"
    return "RULE_EXIT"


def _max_drawdown(equity_curve: list[float], starting_capital: float) -> float:
    peak = starting_capital
    max_dd = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        if peak:
            max_dd = max(max_dd, (peak - equity) / peak * 100)
    return round(max_dd, 2)
