import pandas as pd
import pandas_ta as ta
import os

# --- PORTFOLIO CONFIGURATION ---
DATA_DIR = "/root/trade_hunter/massive_data"
ATR_RISK_MULTIPLIER = 1.5  
REWARD_MULTIPLIER = 4.0    

# The Concurrency Matrix
ROUTING_MATRIX = {
    "TSLA": 15,
    "X_ETHUSD": 15,
    "NVDA": 5,
    "X_BTCUSD": 5,
    "X_SOLUSD": 5,
    "AMD": 5
}

# Testing multiple compounding tiers to find the optimal production scale
ALLOCATION_TIERS = [0.05, 0.10, 0.15] 
# -------------------------------

def process_routed_asset(ticker, tf, allocation_pct):
    file_path = f"{DATA_DIR}/{ticker}_180d_{tf}m_massive.csv"
    
    if not os.path.exists(file_path):
        return ticker, 0, 0, 0.0, 0
        
    initial_capital = 10000 if ticker.startswith("X_") else 100000  
    df = pd.read_csv(file_path)
    
    df['SMA200'] = df['Close'].rolling(window=200).mean()
    df.ta.rsi(length=14, append=True)
    df.ta.atr(length=14, append=True)
    
    df.rename(columns={'RSI_14': 'RSI', 'ATRr_14': 'ATR'}, inplace=True)
    
    balance = initial_capital
    positions = 0
    trades = []
    wins = 0
    losses = 0
    
    entry_price = 0
    current_stop_loss = 0
    take_profit = 0
    breakeven_trigger = 0

    for i in range(200, len(df)):
        price = df.loc[i, 'Close']
        sma200 = df.loc[i, 'SMA200']
        rsi = df.loc[i, 'RSI']
        atr = df.loc[i, 'ATR']
        
        # BUY Condition
        if pd.notna(sma200) and pd.notna(rsi) and price > sma200 and rsi < 30 and positions == 0:
            
            # Realistic Compounding: Allocation based on current balance
            trade_value = balance * allocation_pct
            qty = round(trade_value / price, 4)
            
            positions = qty
            balance -= (qty * price)
            
            entry_price = price
            risk_distance = atr * ATR_RISK_MULTIPLIER
            
            current_stop_loss = entry_price - risk_distance
            take_profit = entry_price + (risk_distance * REWARD_MULTIPLIER)
            breakeven_trigger = entry_price + risk_distance 
            
            trades.append({'type': 'BUY', 'price': price, 'time': df.loc[i, 'timestamp']})
            
        # SELL Condition
        elif positions > 0:
            if price >= breakeven_trigger and current_stop_loss < entry_price:
                current_stop_loss = entry_price
                
            if price >= take_profit:
                balance += (positions * price)
                trades.append({'type': 'SELL', 'price': price, 'time': df.loc[i, 'timestamp']})
                positions = 0
                wins += 1
                
            elif price <= current_stop_loss:
                balance += (positions * price)
                trades.append({'type': 'SELL', 'price': price, 'time': df.loc[i, 'timestamp']})
                positions = 0
                if current_stop_loss >= entry_price:
                    pass 
                else:
                    losses += 1

    if positions > 0:
        final_price = df.iloc[-1]['Close']
        balance += (positions * final_price)
        if final_price > entry_price:
            wins += 1
        elif final_price < entry_price:
            losses += 1

    total_decisive_trades = wins + losses
    win_rate = (wins / total_decisive_trades * 100) if total_decisive_trades > 0 else 0.0
    total_executions = len(trades) // 2

    return ticker, balance, total_executions, win_rate, initial_capital

if __name__ == "__main__":
    for alloc in ALLOCATION_TIERS:
        print(f"\n[{'='*75}]")
        print(f"[*] Compounding Allocation Test: {int(alloc * 100)}% of Balance per Trade")
        print(f"[{'='*75}]")
        
        total_alpaca_pl = 0.0
        total_kraken_pl = 0.0
        
        for ticker, tf in ROUTING_MATRIX.items():
            t, bal, count, wr, init_cap = process_routed_asset(ticker, tf, alloc)
            profit = bal - init_cap
            
            if ticker.startswith("X_"):
                total_kraken_pl += profit
            else:
                total_alpaca_pl += profit
                
            print(f"Ticker: {t:<10} | Route: {tf:>2}m | Executions: {count:<4} | Win Rate: {wr:>5.1f}% | P/L: ${profit:>10,.2f}")

        print(f"\n[{'-'*75}]")
        print(f"[*] {int(alloc * 100)}% Allocation Portfolio Performance")
        print(f"    Alpaca (Equities) Net P/L : ${total_alpaca_pl:>10,.2f}")
        print(f"    Kraken (Crypto)   Net P/L : ${total_kraken_pl:>10,.2f}")
        print(f"    Combined System   Net P/L : ${(total_alpaca_pl + total_kraken_pl):>10,.2f}")
