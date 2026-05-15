import pandas as pd
import pandas_ta as ta
import glob
import os

# --- V3.6 ROUTING, RISK & ANALYST CONFIG ---
DATA_DIR = "/root/trade_hunter/massive_data"
RISK_PCT = 0.01
REWARD_MULTIPLIER = 4.0

OPTIMAL_ROUTING = {
    "NVDA": 5, "TSLA": 5, "AMD": 5, "MSFT": 5,
    "X_BTCUSD": 5,  # Dropping Crypto to 5m to increase trade frequency
    "X_ETHUSD": 5, 
    "X_SOLUSD": 5
}
# -------------------------------------------

def run_backtest(file_path):
    filename = os.path.basename(file_path)
    ticker = filename.split('_1m_master.csv')[0]
    target_tf = OPTIMAL_ROUTING.get(ticker, 5)
    resample_rule = f"{target_tf}min"
    
    is_crypto = ticker.startswith("X_")
    initial_capital = 10000.0 if is_crypto else 100000.0  
    
    df = pd.read_csv(file_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)

    df_res = df.resample(resample_rule, label='right', closed='right').agg({
        'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'
    }).dropna()

    df_res['SMA200'] = ta.sma(df_res['Close'], length=200)
    df_res['RSI'] = ta.rsi(df_res['Close'], length=14)
    df_res['Vol_MA20'] = ta.sma(df_res['Volume'], length=20)
    
    df_res['Recent_High'] = df_res['High'].rolling(window=10).max().shift(1)
    df_res['ChoCH'] = df_res['Close'] > df_res['Recent_High']
    df_res['Trend_Up'] = df_res['Close'] > df_res['SMA200']

    df_res['c1_High'] = df_res['High'].shift(2)
    df_res['c2_Low'] = df_res['Low'].shift(1)
    df_res['FVG_Bullish'] = df_res['Low'] > df_res['c1_High']
    df_res['FVG_Mid'] = (df_res['Low'] + df_res['c1_High']) / 2
    df_res['FVG_Stop'] = df_res['c2_Low']

    # Analyst Scoring
    df_res['Score_Vol'] = (df_res['Volume'] > df_res['Vol_MA20']).astype(int) * 30
    df_res['Score_RSI'] = ((df_res['RSI'] >= 40) & (df_res['RSI'] <= 70)).astype(int) * 30
    
    signals = df_res[['Trend_Up', 'ChoCH', 'FVG_Bullish', 'FVG_Mid', 'FVG_Stop', 'c1_High', 'Score_Vol', 'Score_RSI']]
    signals = signals.reindex(df.index, method='ffill').shift(1)
    df = df.join(signals)
    
    balance, positions = initial_capital, 0
    trades, wins, losses = [], 0, 0
    entry_price, current_sl, tp, be_trigger = 0, 0, 0, 0

    for current_time, row in df.iterrows():
        price, low_p = row['Close'], row['Low']
        
        if positions == 0:
            if pd.notna(row['Trend_Up']) and row['Trend_Up'] and row['ChoCH'] and row['FVG_Bullish']:
                
                # INTELLIGENCE UPGRADE: Setting threshold to 60 (Mandates BOTH Vol + RSI)
                analyst_score = row['Score_Vol'] + row['Score_RSI']
                if analyst_score < 60: continue 

                if low_p <= row['FVG_Mid'] and price >= row['c1_High']:
                    entry_p = min(price, row['FVG_Mid']) 
                    sl = row['FVG_Stop']
                    if sl >= entry_p: sl = entry_p * 0.99 
                    risk_dist = entry_p - sl
                    qty = (balance * RISK_PCT) / risk_dist
                    
                    cost = qty * entry_p
                    if is_crypto:
                        if cost > balance: qty = balance / entry_p
                    else:
                        if cost > (balance * 2): qty = (balance * 2) / entry_p
                    
                    if qty <= 0: continue
                    positions = qty
                    balance -= (positions * entry_p)
                    entry_price, current_sl = entry_p, sl
                    tp = entry_p + (risk_dist * REWARD_MULTIPLIER)
                    be_trigger = entry_p + risk_dist 
                    trades.append({'type': 'BUY', 'price': entry_p, 'time': current_time})
                
        elif positions > 0:
            if price >= be_trigger and current_sl < entry_price:
                current_sl = entry_price 
            if price >= tp:
                balance += (positions * tp) 
                trades.append({'type': 'SELL', 'price': tp, 'time': current_time})
                positions, wins = 0, wins + 1
            elif low_p <= current_sl:
                balance += (positions * current_sl) 
                trades.append({'type': 'SELL', 'price': current_sl, 'time': current_time})
                positions = 0
                if current_sl < entry_price: losses += 1

    total_t = wins + losses
    win_rate = (wins / total_t * 100) if total_t > 0 else 0.0
    return ticker, target_tf, balance, total_t, win_rate, initial_capital

if __name__ == "__main__":
    search_pattern = f"{DATA_DIR}/*_1m_master.csv"
    csv_files = sorted(glob.glob(search_pattern))
    print(f"\n{'='*80}\n[*] V3.6 TIGHTENED ANALYST (Score 60) | Master 1m Backtest\n{'='*80}")
    
    if not csv_files:
        print(f"  -> No data found in {DATA_DIR}.")
    else:
        for f in csv_files:
            t, tf, bal, count, wr, init_cap = run_backtest(f)
            print(f"Ticker: {t:<10} | Route: {tf:>2}m | Trades: {count:<4} | Win Rate: {wr:>5.1f}% | P/L: ${bal-init_cap:>9,.2f}")
