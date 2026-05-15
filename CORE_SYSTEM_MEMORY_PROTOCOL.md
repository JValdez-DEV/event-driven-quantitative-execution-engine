# Core System Memory Protocol

This repository runs on a constrained production environment and has known historical regression classes that must not be reintroduced. Every change to the V3.6 execution, optimizer, or backtest stack must be checked against this protocol before commit.

> **Production constraint:** The target deployment is a 1GB RAM Ubuntu droplet. Code must assume tight memory pressure and must prefer deterministic, sequential execution over convenience abstractions that hold large datasets in memory.

## Non-Negotiable Regression Guards

| Guard | Requirement |
|---|---|
| **OOM Safeguard** | Never load multi-asset or multi-timeframe DataFrames concurrently. Optimizers and backtests must process one ticker and one timeframe, or one ticker, at a time. |
| **Explicit Memory Pruning** | At the end of each ticker or timeframe loop, large DataFrames and temporary arrays must be explicitly deleted, followed immediately by `gc.collect()`. |
| **Dynamic Timeframe Routing** | `ticker_config.json` ingestion must remain intact. The live engine and backtester must respect the configured timeframe per ticker. |
| **Asset-Class Symbol Isolation** | Equity symbols routed to Alpaca must remain clean ticker strings such as `MSFT` and `TSLA`. Crypto symbols routed through CCXT/Kraken may use pair formatting such as `BTC/USD`. Do not apply `/USD` suffixes to Alpaca equity tickers. |
| **Risk Controls** | The Daily Loss Limit circuit breaker, 1R breakeven behavior, and optimized Score 60 matrix must survive every merge. |

## Required Memory Cleanup Pattern

Any loop that loads historical market data must release local references before the next asset or timeframe is loaded. The canonical cleanup pattern is:

```python
del df
import gc
gc.collect()
```

When multiple frames exist, delete each large object explicitly:

```python
del df_1m
del df_tf
del trades
import gc
gc.collect()
```

## Pre-Commit Checklist

Before pushing code that touches `live_engine.py`, `massive_backtest.py`, or `parameter_optimizer.py`, verify that Python syntax passes, no merge conflict markers remain, and the following features are present together: dynamic timeframe config ingestion, Alpaca clean equity symbols, Kraken/crypto pair formatting isolation, Daily Loss Limit, 1R breakeven, NVDA/SOL ADX-volume Score 60 rules, and sequential memory-safe processing in any historical-data script.
