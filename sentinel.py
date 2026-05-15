import os
import time
from datetime import datetime
import ccxt
import pandas as pd
from dotenv import load_dotenv

# Load environment variables (Strict zero-trust protocol)
load_dotenv()

class SentinelAgent:
    def __init__(self):
        # Pull exchange from .env, default to binance if missing
        exchange_id = os.getenv('EXCHANGE_ID', 'binance')
        
        # Initialize CCXT instance
        # Rate limiting enabled to prevent IP bans during 24/7 scraping
        exchange_class = getattr(ccxt, exchange_id)
        self.exchange = exchange_class({
            'enableRateLimit': True,
        })
        
        self.symbol = 'BTC/USDT'
        self.timeframe = '5m'
        self.limit = 100
        self.proximity_threshold = 0.001  # 0.1%

    def fetch_data(self):
        """Scrapes the latest OHLCV data."""
        try:
            ohlcv = self.exchange.fetch_ohlcv(
                self.symbol, 
                timeframe=self.timeframe, 
                limit=self.limit
            )
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            print(f"[{datetime.now()}] Sentinel Error: Network/API failure - {e}")
            return None

    def analyze_market(self, df):
        """Calculates MA20 and checks for the pullback trigger."""
        if df is None or len(df) < 20:
            return

        # Calculate the 20-period Simple Moving Average
        df['MA20'] = df['close'].rolling(window=20).mean()

        # Isolate the most recent completed/current candle
        current_data = df.iloc[-1]
        current_price = current_data['close']
        current_ma20 = current_data['MA20']

        # Ensure MA20 is valid (not NaN due to rolling window)
        if pd.isna(current_ma20):
            return

        # Calculate the percentage difference
        price_diff_pct = abs(current_price - current_ma20) / current_ma20

        print(f"[{datetime.now()}] Sentinel Log -> {self.symbol} | Price: ${current_price:.2f} | MA20: ${current_ma20:.2f} | Diff: {price_diff_pct * 100:.3f}%")

        # The Trigger Logic
        if price_diff_pct <= self.proximity_threshold:
            print(f">>> TARGET IDENTIFIED: {self.symbol} is within 0.1% of MA20. Passing to Analyst Agent. <<<")

    def run_recon_loop(self, interval_seconds=30):
        """Asynchronous-style continuous loop for headless VPS execution."""
        print(f"Starting Sentinel Recon Protocol for {self.symbol} on {self.exchange.id}...")
        while True:
            df = self.fetch_data()
            self.analyze_market(df)
            time.sleep(interval_seconds)

if __name__ == "__main__":
    sentinel = SentinelAgent()
    # Scrapes data every 30 seconds to maintain live monitoring without hitting rate limits
    sentinel.run_recon_loop(interval_seconds=30)
