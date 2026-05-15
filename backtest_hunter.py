import os, time, csv, pandas as pd, pandas_ta as ta
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests
import alpaca_trade_api as tradeapi

load_dotenv()

# Configuration
CRYPTO = ['XBTUSD', 'ETHUSD']
STOCKS = ['NVDA', 'TSLA', 'AMD', 'MSFT']
BACKTEST_DAYS = 180
CSV_FILE = '/root/trade_hunter/backtest_ledger.csv'

# Alpaca Setup
api = tradeapi.REST(os.getenv('ALPACA_KEY'), os.getenv('ALPACA_SECRET'), 'https://paper-api.alpaca.markets', 'v2')

def get_crypto_data(pair, days):
    """Fetches historical 15m data from Kraken."""
    print(f"  > Fetching historical data for {pair}...")
    since = int((datetime.now() - timedelta(days=days)).timestamp())
    url = f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval=15&since={since}"
    try:
        res = requests.get(url).json()
        key = list(res['result'].keys())[0]
        df = pd.DataFrame(res['result'][key], columns=['t','o','h','l','c','v','w','cnt'])
        df['t'] = pd.to_datetime(df['t'], unit='s')
        df[['h','l','c']] = df[['h','l','c']].astype(float)
        df.set_index('t', inplace=True)
        return df
    except: return pd.DataFrame()

def process_logic(df, symbol, asset_type):
    trades = []
    if df.empty or len(df) < 200: return trades
    
    # Pillar 1: Trend Filter
    df['SMA_200'] = ta.sma(df['c' if 'c' in df else 'close'], length=200)
    close_col = 'c' if 'c' in df else 'close'
    high_col = 'h' if 'h' in df else 'high'
    low_col = 'l' if 'l' in df else 'low'

    # Iterate through the data, ensuring we don't go out of bounds
    for i in range(200, len(df)):
        price = df[close_col].iloc[i]
        sma200 = df['SMA_200'].iloc[i]
        
        # 1. Price must be above 200 SMA
        if price > sma200:
            
            # Pillar 2: ChoCH (Change of Character / Break of recent high)
            choch = price > df[high_col].iloc[i-11:i].max()
            
            if choch:
                # Pillar 3: FVG (Fair Value Gap) 
                # Detection: Current Low > High of 2 candles ago
                fvg = df[low_col].iloc[i] > df[high_col].iloc[i-2]
                
                if fvg:
                    entry = price
                    sl = df[low_col].iloc[i-5:i].min()
                    if entry <= sl: continue # Safety check
                    
                    # Target: 1:4 Risk/Reward
                    tp = entry + ((entry - sl) * 4) 
                    
                    # OUT-OF-BOUNDS FIX: Default to OPEN, scan only up to the last available candle
                    outcome = "OPEN"
                    for j in range(i+1, len(df)): 
                        if df[high_col].iloc[j] >= tp:
                            outcome = "WIN"
                            break
                        if df[low_col].iloc[j] <= sl:
                            outcome = "LOSS"
                            break
                    trades.append([df.index[i], symbol, entry, outcome, asset_type])
    return trades

def run_backtest():
    print(f"--- INITIATING HYBRID PERCOCO 180-DAY BACKTEST (V4.7 | 1:4 RR) ---")
    all_trades = []

    # 1. Process Stocks
    start_str = (datetime.now() - timedelta(days=BACKTEST_DAYS)).strftime('%Y-%m-%d')
    for symbol in STOCKS:
        print(f"[STOCK] Processing {symbol}...")
        try:
            df = api.get_bars(symbol, '15Min', start=start_str, feed='iex').df
            all_trades.extend(process_logic(df, symbol, "STOCK"))
        except Exception as e: print(f"  ! Alpaca Error: {e}")

    # 2. Process Crypto
    for coin in CRYPTO:
        print(f"[CRYPTO] Processing {coin}...")
        df = get_crypto_data(coin, BACKTEST_DAYS)
        all_trades.extend(process_logic(df, coin, "CRYPTO"))

    # Write Results to Ledger
    with open(CSV_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Timestamp', 'Ticker', 'Entry_Price', 'Result', 'Asset_Class'])
        writer.writerows(all_trades)
    
    print(f"--- BACKTEST COMPLETE: {len(all_trades)} trades logged to {CSV_FILE} ---")

if __name__ == "__main__":
    run_backtest()
