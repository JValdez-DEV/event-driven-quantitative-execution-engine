import os, time, csv, pandas as pd, pandas_ta as ta
from datetime import datetime, timedelta
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi

load_dotenv()

CSV_FILE = '/root/trade_hunter/trade_ledger.csv'
STOCKS = ['NVDA', 'TSLA', 'AMD', 'MSFT']
STRATEGY = "V4.7 HYBRID PERCOCO"

# Initialize Alpaca API
api = tradeapi.REST(os.getenv('ALPACA_KEY'), os.getenv('ALPACA_SECRET'), 'https://paper-api.alpaca.markets', 'v2')
last_alert = {symbol: None for symbol in STOCKS}

def log_trade(ticker, price, sl):
    qty = 5 # Standard paper unit
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(CSV_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, ticker, price, qty, "BUY", sl, STRATEGY, "PAPER"])
    print(f"\a\n[!!!] ALERT: BUY order logged for {ticker} at ${price:.2f} (SL: ${sl:.2f})", flush=True)

def scan_markets():
    print(f"--- STOCK HUNTER V4.7 (HYBRID PERCOCO) INITIALIZED ---", flush=True)
    while True:
        try:
            now = datetime.now().strftime('%H:%M:%S')
            # Pulse heartbeat to show activity in tmux
            print(f"[{now}] Pulse: Scanning {STOCKS}...", end="\n", flush=True)
            
            # Fetch data for technical indicators
            start_str = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
            for symbol in STOCKS:
                df = api.get_bars(symbol, '15Min', start=start_str, feed='iex').df
                if df.empty or len(df) < 200: continue
                
                # 1. Trend Pillar (200 SMA)
                df['SMA_200'] = ta.sma(df['close'], length=200)
                
                i = -2 # Check the most recent closed candle
                price = df['close'].iloc[i]
                sma200 = df['SMA_200'].iloc[i]
                candle_time = df.index[i]
                
                if price > sma200:
                    # 2. ChoCH Pillar (Change of Character)
                    choch = price > df['high'].iloc[i-11:i].max()
                    
                    if choch:
                        # 3. FVG Pillar (Fair Value Gap)
                        fvg = df['low'].iloc[i] > df['high'].iloc[i-2]
                        
                        if fvg and last_alert[symbol] != candle_time:
                            sl = df['low'].iloc[i-5:i].min()
                            log_trade(symbol, price, sl)
                            last_alert[symbol] = candle_time
        except Exception as e:
            # Prevent crash if API is rate-limited or market is closed
            pass
            
        time.sleep(300) # Wait 5 minutes for next candle cycle

if __name__ == "__main__":
    scan_markets()
