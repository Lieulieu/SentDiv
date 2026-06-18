# SENTDIV - Sentiment / On-chain Divergence Skill

SENTDIV is a CMC Strategy Skill for BNB Hackathon 2026 Track 2. It flags moments where **social heat** and **on-chain flow** disagree, then turns that divergence into a backtestable trading strategy.

The thesis is simple:

> Social heat shows where the crowd is looking. On-chain flow shows where money is moving. Divergence between the two can reveal early accumulation or dangerous hype.

## Why This Fits Track 2

Track 2 asks for a CMC Skill that turns market data into a trading strategy. SENTDIV focuses on:

- A clear strategy spec, not live execution.
- Deterministic rules for `SHI`, `OFI`, divergence, confidence, entry, and exit.
- Event-based backtesting with next-candle execution to avoid lookahead bias.
- Agent-native JSON output that can be routed by CMC Agent Hub or MCP.

## Skill Outputs

The Skill returns:

- `BULLISH_HIDDEN_ACCUMULATION`: on-chain flow is strong while social heat is quiet.
- `BEARISH_HYPE_WITHOUT_FLOW`: social heat is high but flow does not confirm it.
- `BULLISH_CONFIRMATION`: social and flow agree.
- `CROWDED_EXIT`: social heat is crowded while flow weakens.
- `NEUTRAL`: no actionable divergence.

## Run Locally

```bash
cd sentdiv-skill
python main.py --token BNB
python main.py --token BNB --backtest
python main.py --token CMC20 --backtest --json
```

No API key is required for the sample mode. The sample dataset is deterministic and exists so judges can inspect the strategy logic end to end. Production data should be mapped from CMC Agent Hub / Skills Marketplace sources into the same schema.

## Run With Real CMC Data

Create `sentdiv-skill/.env`:

```env
CMC_API_KEY=your_key_here
```

Then run:

```bash
python main.py --source cmc --token BNB --periods 60 --backtest
python main.py --source cmc --token CMC20 --periods 60 --backtest --json
python main.py --source cmc --token CMC20 --network bsc --contract-address <bsc_contract> --backtest
```

CMC mode currently uses:

- `/v1/cryptocurrency/map` to resolve stable CMC ids.
- `/v2/cryptocurrency/ohlcv/historical` for real historical candles.
- `/v3/fear-and-greed/latest` as a global sentiment proxy.
- Optional `/v1/dex/token/pools` and `/v1/dex/token-liquidity/query` when a BSC contract address is provided.

If your CMC plan does not include one of these endpoints, the CLI returns a clear error. If DEX context fails, SENTDIV still runs with market-data proxies and records the DEX error in `cmc_context`.

## Project Structure

```text
sentdiv-skill/
├── main.py
├── data/
│   ├── cmc_adapter.py
│   ├── cmc_client.py
│   └── sample_data.py
├── signals/
│   └── divergence.py
├── strategy/
│   └── backtest.py
├── output/
│   └── report.py
└── specs/
    └── skill_spec.md
```

## CMC Skills Mapping

- Community, Feeds, Topics, Articles, Sentiment -> `SHI`
- DexScan, DEX data, Exchange Inflows/Outflows -> `OFI`
- Markets and Market Overview -> universe and liquidity filters
- Technical Analysis -> trend alignment
- Indicators and Derivatives -> risk overlay
- CMC AI, Agent Hub, MCP, AI Alerts -> skill routing, explanations, alerts

## BNB Testnet Role

CMC data is off-chain real market data. BNB Testnet should be used for the demo layer, not as the source of CMC data:

- Store a signal hash or latest signal summary on a testnet contract.
- Let a dApp read the backend signal and show a transparent audit trail.
- Simulate trade intent or strategy approval without live execution.

This keeps the Track 2 submission focused on a backtestable strategy Skill while still showing a credible path to an agent/dApp workflow.

## Backtest Discipline

- Signal at candle `t` executes at candle `t+1`.
- Position size defaults to 10% of portfolio.
- Fee defaults to 20 bps per side.
- Exit rules include stop loss, take profit, time stop, bearish hype, crowded exit, and flow reversal.

