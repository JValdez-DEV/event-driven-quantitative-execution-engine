import os, time, csv, pandas as pd, pandas_ta as ta
from datetime import datetime
import requests

CSV_FILE = '/root/trade_hunter/trade_ledger.csv'
CRYPTO = ['XBTUSD', 'ETHUSD', 'SOLUSD', 'ADAUSD', 'DOTUSD', 'MATICUSD']
STRATEGY = "V4.8 SAFE PERCOCO"
STARTING_CASH = 10000.00  # Your fixed cap

last_alert = {coin: None for coin in CRYPTO}

def get_available_balance():
    """Calculates remaining virtual cash by scanning the ledger."""
    if not os.path.exists(CSV_FILE):
        return STARTING_CASH
    
    try:
        df = pd.read_csv(CSV_FILE, names=['Timestamp', 'Ticker', 'Price', 'Qty', 'Side', 'SL', 'Strategy', 'Status'])
        # Only deduct cash for trades that are still 'PAPER' (open)
        # or closed 'LOSS'. (Simplified: deduct entry cost for all signals)
        spent = (df['Price'].astype(float) * df['Qty'].astype(float)).sum()
        return STARTING_CASH - spent
    except:
        return STARTING_CASH

def log_trade(ticker, price, sl):
    balance = get_available_balance()
    # Dynamic Quantity: Calculate max qty based on 10% of total starting cash 
    # to ensure you can hold multiple positions without margin.
    target_spend = 1500.00 
    qty = round(target_spend / price, 4)
    
    cost = price * qty
    
    if balance >= cost:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(CSV_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, ticker, price, qty, "BUY", sl, STRATEGY, "PAPER"])
        print(f"\n[!!!] EXECUTION: Bought {qty} {ticker} at ${price} (Cost: ${cost:.2f})")
    else:
        print(f"\n[SKIP] Signal for {ticker} ignored. Insufficient Balance: ${balance:.2f}")

def get_crypto_data(pair):
    url = f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval=15"
    try:
        res = requests.get(url).json()
        key = list(res['result'].keys())[0]
        df = pd.DataFrame(res['result'][key], columns=['t','o','h','l','c','v','w','cnt'])
        df[['h','l','c']] = df[['h','l','c']].astype(float)
        return df
    except: return pd.DataFrame()

def scan_markets():
    print(f"--- CRYPTO HUNTER V4.8 (SAFE MODE) INITIALIZED ---")
    while True:
        current_bal = get_available_balance()
        now = datetime.now().strftime('%H:%M:%S')
        print(f"[{now}] Balance: ${current_bal:,.2f} | Scanning...", end="\n", flush=True)
        
        for coin in CRYPTO:
            df = get_crypto_data(coin)
            if df.empty or len(df) < 200: continue
            df['SMA_200'] = ta.sma(df['c'], length=200)
            i = -2 
            price = df['c'].iloc[i]
            sma200 = df['SMA_200'].iloc[i]
            
            if price > sma200:
                if price > df['h'].iloc[i-11:i].max():
                    if df['l'].iloc[i] > df['h'].iloc[i-2]:
                        if last_alert[coin] != df['t'].iloc[i]:
                            sl = df['l'].iloc[i-5:i].min()
                            log_trade(coin, price, sl)
                            last_alert[coin] = df['t'].iloc[i]
        time.sleep(300) 

if __name__ == "__main__":
    scan_markets()
