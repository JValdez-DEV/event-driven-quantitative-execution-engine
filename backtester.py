import alpaca_trade_api as tradeapi
import pandas as pd
import pandas_ta as ta
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Initialize Alpaca (Used for deep historical data for both markets)
api = tradeapi.REST(os.getenv('ALPACA_KEY'), os.getenv('ALPACA_SECRET'), 'https://paper-api.alpaca.markets', 'v2')

# THE FULL SENTINEL GRID
# Stocks: High-volatility tech and index trackers
# Crypto: Major layer-1s and infrastructure (Alpaca format requires the '/')
TEST_ASSETS = [
    'NVDA', 'AMD', 'AAPL', 'TSLA', 'MSFT', 'QQQ', 
    'BTC/USD', 'ETH/USD', 'SOL/USD', 'LINK/USD'
]

DAYS_TO_TEST = 30

def run_backtest(symbol):
    print(f"\n========================================")
    print(f"🛠️ INITIATING BACKTEST: {symbol} ({DAYS_TO_TEST} Days)")
    print(f"========================================")
    
    try:
        # 1. Fetch Deep Historical 5-Minute Data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=DAYS_TO_TEST)
        
        print("📥 Downloading historical data...")
        bars = api.get_bars(symbol, '5Min', start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d')).df
        
        if bars.empty:
            print("❌ No data found.")
            return

        # Ensure index is datetime for resampling
        bars.index = pd.to_datetime(bars.index)
        
        # 2. Resample to 15-Minute for the Macro Trend & ChoCH
        df15 = bars.resample('15Min').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'})
        df15 = df15.dropna()
        
        # Calculate 100 SMA on 15m
        df15['SMA_100'] = ta.sma(df15['close'], length=100)
        # Calculate Rolling 10-bar High for ChoCH
        df15['Rolling_High'] = df15['high'].rolling(window=10).max().shift(1)
        
        # 3. Re-align 15m indicators back to the 5m chart
        bars = bars.join(df15[['SMA_100', 'Rolling_High']], how='left')
        bars[['SMA_100', 'Rolling_High']] = bars[['SMA_100', 'Rolling_High']].ffill()

        # Drop rows where SMA hasn't calculated yet
        bars = bars.dropna()

        print(f"✅ Data aligned. Scanning {len(bars)} total 5-minute candles...")

        # 4. The V4.2 Scanner Loop
        triggers = 0
        for i in range(3, len(bars)):
            price = bars['close'].iloc[i]
            sma = bars['SMA_100'].iloc[i]
            rolling_high = bars['Rolling_High'].iloc[i]

            # Primary Filter
            if price < sma: continue

            # Signal A: ChoCH
            if price > rolling_high:
                # Signal B: FVG (Candle 1 High vs Candle 3 Low)
                c1_high = bars['high'].iloc[i-2]
                c3_low = bars['low'].iloc[i]
                
                if c3_low > c1_high:
                    triggers += 1
                    entry = (c1_high + c3_low) / 2
                    timestamp = bars.index[i].strftime('%Y-%m-%d %H:%M')
                    print(f"  🚨 [TRIGGER] {timestamp} | Entry: ${entry:.2f}")

        print(f"\n📊 RESULTS FOR {symbol}:")
        print(f"Total 'At-Bats' (Setups Found): {triggers}")
        if triggers == 0:
            print("⚠️ The V4.2 conditions were too strict for this asset over the last 30 days.")
            
    except Exception as e:
        print(f"Error testing {symbol}: {e}")

if __name__ == "__main__":
    for asset in TEST_ASSETS:
        run_backtest(asset)
