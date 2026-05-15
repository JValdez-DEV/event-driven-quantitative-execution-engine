import pandas as pd
import os
import sys

def run_audit(mode="LIVE"):
    file_path = '/root/trade_hunter/backtest_ledger.csv' if mode == "BACKTEST" else '/root/trade_hunter/trade_ledger.csv'
    title = "180-DAY BACKTEST" if mode == "BACKTEST" else "LIVE PAPER TRADES"
    
    print(f"\n[INITIATING {mode} LEDGER AUDIT...]")
    
    if not os.path.exists(file_path):
        print(f"[ERROR] {file_path} not found. No data to report.")
        return

    try:
        df = pd.read_csv(file_path)
        if df.empty:
            print("[!] Ledger exists but contains no trade data yet.")
            return
            
        print("="*65)
        print(f" 🦅 TRADE HUNTER V4.7 | {title}")
        print("="*65)
        
        if mode == "BACKTEST":
            wins = len(df[df['Result'] == 'WIN'])
            losses = len(df[df['Result'] == 'LOSS'])
            win_rate = (wins / len(df)) * 100 if len(df) > 0 else 0
            print(f"[*] Total Executed Signals : {len(df)}")
            print(f"[*] Total Wins             : {wins}")
            print(f"[*] Total Losses           : {losses}")
            print(f"[*] Win Rate (1:4 RR)      : {win_rate:.2f}%")
        else:
            print(f"[*] Total Executed Signals : {len(df)}")
            print(f"[*] Audit Timeframe        : {df['Timestamp'].min()} TO {df['Timestamp'].max()}")
            
        print("-" * 65)
        print("[TARGET DISTRIBUTION]")
        asset_counts = df['Ticker'].value_counts()
        for ticker, count in asset_counts.items():
            print(f"  > {ticker}: {count} signals")
            
        print("-" * 65)
        print(f"[LATEST 5 {mode} ACQUISITIONS]")
        if mode == "BACKTEST":
            latest = df.tail(5)[['Timestamp', 'Ticker', 'Entry_Price', 'Result']]
        else:
            latest = df.tail(5)[['Timestamp', 'Ticker', 'Side', 'Entry_Price', 'Status']]
            
        print(latest.to_string(index=False))
        print("="*65 + "\n")

    except Exception as e:
        print(f"[FATAL] Audit framework failed: {e}")

if __name__ == "__main__":
    mode = sys.argv[1].upper() if len(sys.argv) > 1 else "LIVE"
    run_audit(mode)
