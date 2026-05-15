import pandas as pd
import glob
import os
import json
import gc
from datetime import datetime, timedelta

# --- CONFIGURATION ---
DATA_DIR = "/root/trade_hunter/massive_data"
TIMEFRAMES = ["1min", "3min", "5min", "15min", "1h"]
RISK_PCT = 0.01
REWARD_MULT = 4.0
LOOKBACK_DAYS = 30 # 30-Day Lookback Limit for 1GB RAM Environments
# ---------------------

# Mock pandas_ta if not available
try:
    import pandas_ta as ta
except ImportError:
    import sys
    from unittest.mock import MagicMock
    sys.modules['pandas_ta'] = MagicMock()
    import pandas_ta as ta

def run_backtest_tf(file_path, tf):
    filename = os.path.basename(file_path)
    ticker = filename.split('_1m_master')[0]
    
    initial_capital = 10000 if ticker.startswith("X_") or "USD" in ticker else 100000
    
    # 1. Load 1m Raw Data
    try:
        # Use chunking or just read and immediately filter to save memory
        df_1m = pd.read_csv(file_path)
    except Exception:
        return None

    time_col = next((c for c in df_1m.columns if c.lower() in ['timestamp', 'time', 'date']), None)
    if not time_col:
        del df_1m
        return None
    
    df_1m[time_col] = pd.to_datetime(df_1m[time_col])
    df_1m.set_index(time_col, inplace=True)
    df_1m.sort_index(inplace=True)
    
    # --- MEMORY OPTIMIZATION: 6 MONTH LOOKBACK LIMIT ---
    cutoff_date = df_1m.index.max() - timedelta(days=LOOKBACK_DAYS)
    df_1m = df_1m[df_1m.index >= cutoff_date]
    
    if df_1m.empty:
        del df_1m
        return None

    df_1m.columns = [c.capitalize() for c in df_1m.columns]

    # 2. Resample to Target Timeframe
    df_tf = df_1m.resample(tf).agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna()

    if len(df_tf) < 200:
        del df_1m
        del df_tf
        return None

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

    df_1m['tf_group'] = df_1m.index.floor(tf)
    tf_delta = pd.to_timedelta(tf)

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
    net_pnl = balance - initial_capital
    
    result = {
        "ticker": ticker,
        "tf": tf,
        "net_pnl": net_pnl,
        "win_rate": wr,
        "trades": total
    }
    
    # --- MEMORY PRUNING ---
    del df_1m
    del df_tf
    gc.collect()
    
    return result

def optimize():
    csv_files = glob.glob(os.path.join(DATA_DIR, "*_1m_master.csv"))
    if not csv_files:
        print(f"No data found in {DATA_DIR}")
        return
        
    results = []
    print(f"Optimizing {len(csv_files)} assets across {len(TIMEFRAMES)} timeframes...")
    print(f"Mode: SEQUENTIAL EXECUTION | Lookback: {LOOKBACK_DAYS} Days")
    
    # --- SEQUENTIAL EXECUTION ---
    # Process exactly one ticker/timeframe pair at a time. The finally block
    # guarantees cleanup after every iteration, including failed runs.
    for f in csv_files:
        for tf in TIMEFRAMES:
            res = None
            try:
                print(f"Processing {os.path.basename(f)} @ {tf}...")
                res = run_backtest_tf(f, tf)
                if res:
                    results.append(res)
            finally:
                del res
                gc.collect()

    # Find optimal TF per ticker
    config = {}
    ticker_results = {}
    for r in results:
        t = r['ticker']
        if t not in ticker_results:
            ticker_results[t] = []
        ticker_results[t].append(r)

    print(f"\n{'TICKER':<10} | {'BEST TF':<8} | {'NET PNL':<12} | {'WIN RATE'}")
    print("-" * 50)
    
    for t, res_list in ticker_results.items():
        best = sorted(res_list, key=lambda x: (x['net_pnl'], x['win_rate']), reverse=True)[0]
        tf_str = best['tf']
        if 'min' in tf_str:
            tf_val = int(tf_str.replace('min', ''))
        elif 'h' in tf_str:
            tf_val = int(tf_str.replace('h', '')) * 60
        else:
            tf_val = 5
            
        config[t] = tf_val
        print(f"{t:<10} | {tf_str:<8} | ${best['net_pnl']:,.2f} | {best['win_rate']:.2f}%")

    with open('ticker_config.json', 'w') as f:
        json.dump(config, f, indent=4)
    print(f"\nOptimization complete. Config saved to ticker_config.json")

if __name__ == "__main__":
    optimize()
