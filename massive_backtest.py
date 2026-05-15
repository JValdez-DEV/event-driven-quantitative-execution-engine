import pandas as pd
import pandas_ta as ta
import glob
import os
from datetime import datetime, timedelta

# --- CONFIGURATION ---
DATA_DIR = "/root/trade_hunter/massive_data"
RISK_PCT = 0.01  
REWARD_MULT = 4.0 
# ---------------------

def run_backtest(file_path):
    filename = os.path.basename(file_path)
    ticker = filename.split('_1m_master')[0]
    
    initial_capital = 10000 if ticker.startswith("X_") or "USD" in ticker else 100000
    
    # 1. Load 1m Raw Data
    df_1m = pd.read_csv(file_path)
    
    # --- ROBUST COLUMN DETECTION ---
    # Find the time column regardless of case
    time_col = next((c for c in df_1m.columns if c.lower() in ['timestamp', 'time', 'date']), None)
    if not time_col:
        return ticker, 0, 0, 0, initial_capital, 0, 0, 0
    
    df_1m[time_col] = pd.to_datetime(df_1m[time_col])
    df_1m.set_index(time_col, inplace=True)
    df_1m.sort_index(inplace=True)
    
    # Standardize OHLC names to Title Case for pandas_ta
    df_1m.columns = [c.capitalize() for c in df_1m.columns]

    # 2. Resample to 5m for Signal Generation
    df_5m = df_1m.resample('5min').agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna()

    if len(df_5m) < 200:
        return ticker, initial_capital, 0, 0, initial_capital, 0, 0, 0

    # --- INDICATORS (Calculated on 5m) ---
    df_5m['SMA200'] = ta.sma(df_5m['Close'], length=200)
    df_5m['RSI'] = ta.rsi(df_5m['Close'], length=14)
    df_5m['Vol_MA20'] = ta.sma(df_5m['Volume'], length=20)
    df_5m['Recent_High'] = df_5m['High'].rolling(window=10).max().shift(1)
    
    df_5m['c1_High'] = df_5m['High'].shift(2)
    df_5m['c2_Low'] = df_5m['Low'].shift(1)
    df_5m['FVG_Bullish'] = df_5m['Low'] > df_5m['c1_High']
    df_5m['FVG_Mid'] = (df_5m['Low'] + df_5m['c1_High']) / 2
    df_5m['FVG_Stop'] = df_5m['c2_Low']

    # --- OPTIMIZED SCORE 60 MATRIX ---
    df_5m['ADX'] = ta.adx(df_5m['High'], df_5m['Low'], df_5m['Close'], length=14)['ADX_14']
    
    def get_score(row, ticker):
        vol_mult = 1.2 if ticker in ["NVDA", "X_SOLUSD"] else 1.0
        rsi_max = 65 if ticker in ["NVDA", "X_SOLUSD"] else 70
        min_adx = 25 if ticker in ["NVDA", "X_SOLUSD"] else 0
        
        s_vol = 30 if row['Volume'] > (row['Vol_MA20'] * vol_mult) else 0
        s_rsi = 30 if 40 <= row['RSI'] <= rsi_max else 0
        s_penalty = -20 if (min_adx > 0 and row['ADX'] < min_adx) else 0
        return s_vol + s_rsi + s_penalty

    df_5m['Score'] = df_5m.apply(lambda x: get_score(x, ticker), axis=1)
    df_5m['Trend_Up'] = df_5m['Close'] > df_5m['SMA200']
    df_5m['ChoCH'] = df_5m['Close'] > df_5m['Recent_High']

    # --- SIMULATION ---
    balance = initial_capital
    in_trade = False
    entry_price = stop_loss = take_profit = initial_risk = qty = 0
    risk_eliminated = False
    wins = bes = losses = 0

    df_1m['5m_group'] = df_1m.index.floor('5min')

    for idx, row in df_1m.iterrows():
        signal_time = row['5m_group'] - timedelta(minutes=5)
        
        if in_trade:
            if not risk_eliminated and row['High'] >= (entry_price + initial_risk):
                risk_eliminated = True
                stop_loss = entry_price

            if row['Low'] <= stop_loss:
                pnl = (stop_loss - entry_price) * qty
                balance += pnl
                in_trade = False
                if pnl > 0: wins += 1
                elif pnl == 0: bes += 1
                else: losses += 1
            elif row['High'] >= take_profit:
                pnl = (take_profit - entry_price) * qty
                balance += pnl
                in_trade = False
                wins += 1
        
        elif not in_trade and signal_time in df_5m.index:
            sig = df_5m.loc[signal_time]
            if sig['Trend_Up'] and sig['ChoCH'] and sig['FVG_Bullish'] and sig['Score'] >= 60:
                if row['Low'] <= sig['FVG_Mid'] and row['Close'] >= sig['c1_High']:
                    in_trade = True
                    entry_price = row['Close']
                    stop_loss = sig['FVG_Stop']
                    if stop_loss >= entry_price: stop_loss = entry_price * 0.99
                    initial_risk = entry_price - stop_loss
                    take_profit = entry_price + (initial_risk * REWARD_MULT)
                    qty = (balance * RISK_PCT) / initial_risk
                    risk_eliminated = False

    total = wins + losses + bes
    wr = (wins / total * 100) if total > 0 else 0
    return ticker, balance, total, wr, initial_capital, wins, bes, losses

if __name__ == "__main__":
    csv_files = glob.glob(os.path.join(DATA_DIR, "*_1m_master.csv"))
    print(f"\n{'='*80}\nV3.6 VELOCITY - MASSIVE BACKTEST (1m PRECISION)\n{'='*80}")
    print(f"{'TICKER':<10} | {'TRADES':<8} | {'W/BE/L':<12} | {'WIN RATE':<10} | {'NET PNL'}")
    print("-" * 80)

    for f in sorted(csv_files):
        t, bal, count, wr, init, w, b, l = run_backtest(f)
        if count == 0 and bal == init: continue # Skip files that failed to load
        wbel = f"{w}/{b}/{l}"
        print(f"{t:<10} | {count:<8} | {wbel:<12} | {wr:>6.2f}%    | ${bal-init:,.2f}")
