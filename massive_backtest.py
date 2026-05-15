import pandas as pd
import pandas_ta as ta
import glob
import os
import json
from datetime import datetime, timedelta

# --- CONFIGURATION ---
DATA_DIR = "/root/trade_hunter/massive_data"
RISK_PCT = 0.01  
REWARD_MULT = 4.0 
CONFIG_FILE = "ticker_config.json"
# ---------------------

def load_ticker_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def run_backtest(file_path, tf_override=None):
    filename = os.path.basename(file_path)
    ticker = filename.split('_1m_master')[0]
    
    # Use config if available, else default to 5m
    config = load_ticker_config()
    tf_val = tf_override if tf_override else config.get(ticker, 5)
    tf_str = f"{tf_val}min" if tf_val < 60 else f"{tf_val//60}h"
    
    initial_capital = 10000 if ticker.startswith("X_") or "USD" in ticker else 100000
    
    # 1. Load 1m Raw Data
    try:
        df_1m = pd.read_csv(file_path)
    except Exception:
        return ticker, 0, 0, 0, initial_capital, 0, 0, 0
    
    time_col = next((c for c in df_1m.columns if c.lower() in ['timestamp', 'time', 'date']), None)
    if not time_col:
        return ticker, 0, 0, 0, initial_capital, 0, 0, 0
    
    df_1m[time_col] = pd.to_datetime(df_1m[time_col])
    df_1m.set_index(time_col, inplace=True)
    df_1m.sort_index(inplace=True)
    df_1m.columns = [c.capitalize() for c in df_1m.columns]

    # 2. Resample to Dynamic Timeframe
    df_tf = df_1m.resample(tf_str).agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna()

    if len(df_tf) < 200:
        return ticker, initial_capital, 0, 0, initial_capital, 0, 0, 0

    # --- INDICATORS ---
    df_tf['SMA200'] = ta.sma(df_tf['Close'], length=200)
    df_tf['RSI'] = ta.rsi(df_tf['Close'], length=14)
    df_tf['Vol_MA20'] = ta.sma(df_tf['Volume'], length=20)
    df_tf['Recent_High'] = df_tf['High'].rolling(window=10).max().shift(1)
    
    df_tf['c1_High'] = df_tf['High'].shift(2)
    df_tf['c2_Low'] = df_tf['Low'].shift(1)
    df_tf['FVG_Bullish'] = df_tf['Low'] > df_tf['c1_High']
    df_tf['FVG_Mid'] = (df_tf['Low'] + df_tf['c1_High']) / 2
    df_tf['FVG_Stop'] = df_tf['c2_Low']

    adx_res = ta.adx(df_tf['High'], df_tf['Low'], df_tf['Close'], length=14)
    df_tf['ADX'] = adx_res['ADX_14'] if adx_res is not None else 0
    
    def get_score(row, ticker):
        vol_mult = 1.2 if ticker in ["NVDA", "X_SOLUSD"] else 1.0
        rsi_max = 65 if ticker in ["NVDA", "X_SOLUSD"] else 70
        min_adx = 25 if ticker in ["NVDA", "X_SOLUSD"] else 0
        
        s_vol = 30 if row['Volume'] > (row['Vol_MA20'] * vol_mult) else 0
        s_rsi = 30 if 40 <= row['RSI'] <= rsi_max else 0
        s_penalty = -20 if (min_adx > 0 and row['ADX'] < min_adx) else 0
        return s_vol + s_rsi + s_penalty

    df_tf['Score'] = df_tf.apply(lambda x: get_score(x, ticker), axis=1)
    df_tf['Trend_Up'] = df_tf['Close'] > df_tf['SMA200']
    df_tf['ChoCH'] = df_tf['Close'] > df_tf['Recent_High']

    # --- SIMULATION ---
    balance = initial_capital
    in_trade = False
    entry_price = stop_loss = take_profit = initial_risk = qty = 0
    risk_eliminated = False
    wins = bes = losses = 0

    df_1m['tf_group'] = df_1m.index.floor(tf_str)
    tf_delta = pd.to_timedelta(tf_str)

    for idx, row in df_1m.iterrows():
        signal_time = row['tf_group'] - tf_delta
        
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
        
        elif not in_trade and signal_time in df_tf.index:
            sig = df_tf.loc[signal_time]
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
    return ticker, balance, total, wr, initial_capital, wins, bes, losses, tf_val

if __name__ == "__main__":
    csv_files = glob.glob(os.path.join(DATA_DIR, "*_1m_master.csv"))
    print(f"\n{'='*90}\nV3.6 VELOCITY - DYNAMIC TF BACKTEST\n{'='*90}")
    print(f"{'TICKER':<10} | {'TF':<4} | {'TRADES':<8} | {'W/BE/L':<12} | {'WIN RATE':<10} | {'NET PNL'}")
    print("-" * 90)

    for f in sorted(csv_files):
        t, bal, count, wr, init, w, b, l, tf = run_backtest(f)
        if count == 0 and bal == init: continue 
        wbel = f"{w}/{b}/{l}"
        print(f"{t:<10} | {tf:>2}m | {count:<8} | {wbel:<12} | {wr:>6.2f}%    | ${bal-init:,.2f}")
