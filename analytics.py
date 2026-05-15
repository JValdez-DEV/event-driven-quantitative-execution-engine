import sqlite3
import pandas as pd

DB_FILE = "/root/trade_hunter/active_trades.db"

def generate_report():
    try:
        conn = sqlite3.connect(DB_FILE)
        # Read the history table into a DataFrame
        df = pd.read_sql_query("SELECT * FROM history", conn)
        conn.close()
        
        if df.empty:
            print(f"\n[{'-'*40}]")
            print("[*] No closed trades in history yet. The hunting continues.")
            print(f"[{'-'*40}]\n")
            return

        # Calculate Metrics
        total_trades = len(df)
        wins = len(df[df['pnl'] > 0])
        losses = len(df[df['pnl'] <= 0])
        win_rate = (wins / total_trades) * 100
        total_pnl = df['pnl'].sum()

        # Display Dashboard
        print(f"\n{'='*45}")
        print(f" TRADE HUNTER V3.4 | PERFORMANCE DASHBOARD")
        print(f"{'='*45}")
        print(f" Total Trades : {total_trades}")
        print(f" Wins         : {wins}")
        print(f" Losses       : {losses}")
        print(f" Win Rate     : {win_rate:.1f}%")
        
        # Color code PnL terminal output
        if total_pnl > 0:
            print(f" Net PnL      : \033[92m+${total_pnl:.2f}\033[0m") # Green
        else:
            print(f" Net PnL      : \033[91m-${abs(total_pnl):.2f}\033[0m") # Red
        print(f"{'='*45}\n")
        
        # Display latest 5 transactions
        print(" Recent Transactions:")
        recent = df.tail(5)[['symbol', 'reason', 'pnl']]
        for _, row in recent.iterrows():
            pnl_str = f"+${row['pnl']:.2f}" if row['pnl'] > 0 else f"-${abs(row['pnl']):.2f}"
            print(f" -> {row['symbol']:<10} | {row['reason']:<25} | {pnl_str}")
        print()

    except sqlite3.OperationalError:
        print("\n[!] History table does not exist yet. It will be created after the first closed trade.")
    except Exception as e:
        print(f"\n[!] Error generating report: {e}")

if __name__ == "__main__":
    generate_report()
