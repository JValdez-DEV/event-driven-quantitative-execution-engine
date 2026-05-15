import pandas as pd
import numpy as np
from datetime import datetime

# Configuration for the "100 to 6400" visualization
STARTING_BALANCE = 100.00
RISK_PER_TRADE_R = 1.0  # Each trade risks 1 unit of 'R'
REWARD_RATIO = 4.0      # Hybrid Percoco 1:4 Target

def generate_excel_log():
    # Path to your historical backtest source or ledger
    ledger_path = '/root/trade_hunter/trade_ledger.csv'
    output_path = '/root/trade_hunter/backtest_visualized.csv'
    
    if not pd.io.common.file_exists(ledger_path):
        print("[!] No ledger found to export.")
        return

    # Load data
    df = pd.read_csv(ledger_path, names=['Timestamp', 'Ticker', 'Entry', 'Qty', 'Side', 'SL', 'Strategy', 'Status'])
    
    # Filter for completed backtest trades (WIN or LOSS)
    results_df = df[df['Status'].str.contains('WIN|LOSS', na=False)].copy()
    
    # Calculate R-Units Earned per trade
    # Win = +4R, Loss = -1R
    results_df['R_Earned'] = results_df['Status'].apply(lambda x: REWARD_RATIO if "WIN" in x else -RISK_PER_TRADE_R)
    
    # Calculate Cumulative R
    results_df['Cumulative_R'] = results_df['R_Earned'].cumsum()
    
    # Calculate Theoretical Growth ($100 base where 1R = $100)
    # This shows the "Blossoming" effect
    results_df['Theoretical_Balance'] = STARTING_BALANCE + (results_df['Cumulative_R'] * 100)
    
    # Add Win Rate Tracking
    results_df['Is_Win'] = results_df['R_Earned'].apply(lambda x: 1 if x > 0 else 0)
    results_df['Running_Win_Rate'] = results_df['Is_Win'].expanding().mean() * 100

    # Export with Excel-friendly headers
    results_df.to_csv(output_path, index=False)
    print(f"--- EXPORT COMPLETE ---")
    print(f"File Location: {output_path}")
    print(f"Final Cumulative R: {results_df['Cumulative_R'].iloc[-1]}R")
    print(f"Final Theoretical Balance: ${results_df['Theoretical_Balance'].iloc[-1]:,.2f}")

if __name__ == "__main__":
    generate_excel_log()
