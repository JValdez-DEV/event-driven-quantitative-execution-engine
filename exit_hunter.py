import os, time, csv, pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import requests
import alpaca_trade_api as tradeapi

load_dotenv()

LEDGER_FILE = '/root/trade_hunter/trade_ledger.csv'
ALPACA_API = tradeapi.REST(os.getenv('ALPACA_KEY'), os.getenv('ALPACA_SECRET'), 'https://paper-api.alpaca.markets', 'v2')

def get_price(ticker):
    """Fetches live price for valuation/exit checks."""
    if ticker in ['XBTUSD', 'ETHUSD']:
        try:
            url = f"https://api.kraken.com/0/public/Ticker?pair={ticker}"
            res = requests.get(url).json()
            key = list(res['result'].keys())[0]
            return float(res['result'][key]['c'][0])
        except: return None
    else: # Stocks
        try:
            return float(ALPACA_API.get_latest_bar(ticker).c)
        except: return None

def scan_exits():
    print(f"--- EXIT WATCHER V4.7 INITIALIZED (MONITORING TARGETS) ---")
    while True:
        if not os.path.exists(LEDGER_FILE):
            time.sleep(60)
            continue

        # Load ledger and filter for rows that haven't been closed yet
        df = pd.read_csv(LEDGER_FILE, names=['Timestamp', 'Ticker', 'Price', 'Qty', 'Side', 'SL', 'Strategy', 'Status'])
        open_trades = df[df['Status'] == 'PAPER'].index

        for idx in open_trades:
            trade = df.iloc[idx]
            ticker = trade['Ticker']
            entry = float(trade['Price'])
            sl = float(trade['SL'])
            qty = float(trade['Qty'])
            
            # Calculate 1:4 Take Profit
            tp = entry + ((entry - sl) * 4)
            current_price = get_price(ticker)
            
            if current_price is None: continue

            outcome = None
            if current_price >= tp:
                outcome = "WIN (1:4 HIT)"
            elif current_price <= sl:
                outcome = "LOSS (SL HIT)"

            if outcome:
                print(f"\n[EXECUTION] Closing {ticker} at {current_price} | {outcome}")
                # Update status in the dataframe
                df.at[idx, 'Status'] = outcome
                # Log the closing event to a separate history or just update the master
                df.to_csv(LEDGER_FILE, index=False, header=False)
                
        now = datetime.now().strftime('%H:%M:%S')
        print(f"[{now}] Exit Watcher: Monitoring {len(open_trades)} positions...", end="\r", flush=True)
        time.sleep(30) # Check every 30 seconds for higher precision

if __name__ == "__main__":
    scan_exits()
