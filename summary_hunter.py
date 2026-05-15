import pandas as pd
import os
from datetime import datetime

LEDGER_FILE = '/root/trade_hunter/trade_ledger.csv'

def generate_daily_report():
    if not os.path.exists(LEDGER_FILE):
        print("[!] No ledger found. No trades to summarize.")
        return

    # Load data with standardized columns
    cols = ['Timestamp', 'Ticker', 'Price', 'Qty', 'Side', 'SL', 'Strategy', 'Status']
    df = pd.read_csv(LEDGER_FILE, names=cols)
    
    # Filter for trades closed TODAY
    today = datetime.now().strftime('%Y-%m-%d')
    # Look for status updates containing "WIN" or "LOSS" from today
    # Note: This logic assumes your Exit Watcher writes a timestamp or we filter by entry
    daily_df = df[df['Timestamp'].str.contains(today)]
    
    wins = len(df[df['Status'].str.contains("WIN", na=False)])
    losses = len(df[df['Status'].str.contains("LOSS", na=False)])
    open_trades = len(df[df['Status'] == "PAPER"])
    
    # Calculate R-Units (1 Win = +4R | 1 Loss = -1R)
    r_units = (wins * 4) - losses
    
    print("\n" + "═"*45)
    print(f" 🦅 TRADE HUNTER | DAILY PERFORMANCE REPORT")
    print(f" DATE: {today}")
    print("═"*45)
    print(f"[*] Total Trades Found : {len(daily_df)}")
    print(f"[*] Completed Wins     : {wins}")
    print(f"[*] Completed Losses   : {losses}")
    print(f"[*] Current Open       : {open_trades}")
    print("-" * 45)
    print(f"[*] NET DAILY PERFORMANCE: {r_units:+.2f} R")
    
    if r_units > 0:
        print(" STATUS: PROFITABLE DAY")
    elif r_units < 0:
        print(" STATUS: DRAWDOWN ADVISORY")
    else:
        print(" STATUS: BREAK-EVEN / NO EXITS")
    print("═"*45 + "\n")

if __name__ == "__main__":
    generate_daily_report()
