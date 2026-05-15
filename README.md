# Trade Hunter V3.6 (Velocity Architecture)

## Core Objective
An institutional-grade, fully autonomous algorithmic trading system designed for high-expectancy execution across Equities (Alpaca API) and Crypto (CCXT). The system runs as a persistent daemon, identifying structural imbalances and executing with strict risk telemetry.

## Infrastructure Stack
- **Host:** DigitalOcean Droplet (Ubuntu 24.04)
- **Language:** Python 3.12
- **Data Analysis:** pandas_ta, numpy (Vectorized for microsecond calculation)
- **Deployment:** systemd (trade_hunter.service)
- **State Management:** Git CI/CD Pipeline

## Strategy Logic: Velocity FVG
The bot strictly operates on the **5-Minute (5m)** timeframe. A trade is only executed when the "Three-Stage Lock" is bypassed.

1. **Structural Lock:** - Price must be above the SMA200 (Trend alignment).
   - A valid Change of Character (ChoCH) must be detected.
   - A Bullish Fair Value Gap (FVG) must be formed.
2. **Momentum Lock (Dynamic Score Matrix):**
   - **Volume:** > 1.2x of the 20-period Volume MA.
   - **RSI:** Bound between 40 and 65 (preventing parabolic traps).
   - **ADX (Trend Strength):** Must be > 25 (filters out ranging/chop markets).
3. **Execution Lock:**
   - A Limit Order is placed at the FVG_Mid. Price must retrace to fill. No market-chasing.

## Risk Protocol & Telemetry
- **Capital Allocation:** 1% risk of total account equity per trade.
- **Reward Ratio:** Fixed 1:4 (Risk/Reward).
- **1R Breakeven:** Automated stop-loss migration to entry price once the asset achieves a 1:1 risk/reward.
- **Circuit Breaker:** Hard -3% Daily Loss Limit. System halts trading and resets at 00:00 UTC.

## Maintenance Commands
**Audit Live Stream:**
journalctl -u trade_hunter.service -f

**Hot-Reload Daemon (Post-Git Pull):**
systemctl restart trade_hunter.service
