import pandas as pd
from massive import RESTClient
from datetime import datetime, timedelta
import time
import os
from dotenv import load_dotenv

load_dotenv()

# --- V3.6 MASTER DATA CONFIGURATION ---
MASSIVE_API_KEY = os.getenv("MASSIVE_API_KEY")
WATCHLIST = ["NVDA", "TSLA", "AMD", "MSFT", "X:BTCUSD", "X:ETHUSD", "X:SOLUSD"]
DAYS_HISTORY = 180
CHUNK_DAYS = 14  # Smaller chunks for 1m density to prevent timeout
DATA_DIR = "/root/trade_hunter/massive_data"

# We hoard 1m only. The Backtest Engine will resample this into 
# your "best-performing" timeframes (5m, 15m, etc.) locally.
TIMEFRAMES = [1] 
# ---------------------------------------

if not MASSIVE_API_KEY:
    print("[!] Error: MASSIVE_API_KEY not found in .env file.")
    exit(1)

client = RESTClient(MASSIVE_API_KEY)

def hoard_master_data(ticker, tf):
    print(f"\n[*] HOARDING MASTER 1M DATA: {ticker}")
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=DAYS_HISTORY)
    
    all_aggs = []
    current_start = start_date
    
    while current_start <= end_date:
        current_end = min(current_start + timedelta(days=CHUNK_DAYS), end_date)
        try:
            print(f"    -> Pulling {current_start.strftime('%Y-%m-%d')} to {current_end.strftime('%Y-%m-%d')}")
            
            aggs = client.list_aggs(
                ticker,
                tf,
                "minute",
                current_start.strftime("%Y-%m-%d"),
                current_end.strftime("%Y-%m-%d"),
                adjusted=False, 
                limit=50000
            )
            
            for agg in aggs:
                all_aggs.append(agg)
                
            # Rate Limit Cooldown
            time.sleep(12) 
            current_start = current_end + timedelta(days=1)
            
        except Exception as e:
            if '429' in str(e):
                print(f"    [!] Rate Limit. 70s Cooldown...")
                time.sleep(70)
            else:
                print(f"[!] Error on {ticker}: {e}")
                break
                
    if all_aggs:
        df = pd.DataFrame(all_aggs)
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.sort_values('timestamp').drop_duplicates(subset=['timestamp'])
            
            df = df.rename(columns={
                'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'
            })
            
            safe_ticker = ticker.replace(":", "_")
            file_path = f"{DATA_DIR}/{safe_ticker}_1m_master.csv"
            
            if not os.path.exists(DATA_DIR):
                os.makedirs(DATA_DIR)
                
            df.to_csv(file_path, index=False)
            print(f"[+] SUCCESS: {len(df)} rows saved to {file_path}")

if __name__ == "__main__":
    for ticker in WATCHLIST:
        hoard_master_data(ticker, 1)
