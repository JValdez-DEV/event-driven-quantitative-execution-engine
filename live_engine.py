import os
import time
import json
import csv
import ccxt
import requests
import pandas as pd
import pandas_ta as ta
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# --- V3.6 PRODUCTION CONFIGURATION ---
OPTIMAL_ROUTING = {
    "NVDA": 5, "TSLA": 5, "AMD": 5, "MSFT": 5,
    "X_BTCUSD": 5, "X_ETHUSD": 5, "X_SOLUSD": 5
}
RISK_PCT = 0.01
REWARD_MULTIPLIER = 4.0
DISCORD_URL = os.getenv("DISCORD_WEBHOOK_URL")

# --- SYSTEM FILES ---
STATS_FILE = "/root/trade_hunter/daily_stats.json"
LEDGER_FILE = "/root/trade_hunter/kraken_paper_ledger.json"
ACTIVE_TRADES_FILE = "/root/trade_hunter/active_trades.json"
MASTER_CSV_FILE = "/root/trade_hunter/master_trade_log.csv"
# -------------------------------------

def notify_discord(title, fields, color=5763719, description=None):
    if not DISCORD_URL:
        return
        
    embed = {
        "title": title,
        "color": color,
        "fields": [{"name": k, "value": str(v), "inline": False if k in ["Trigger Logic", "Action"] else True} for k, v in fields.items()],
        "footer": {"text": f"Trade Hunter V3.6 | Dynamic Telemetry | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}
    }
    if description:
        embed["description"] = description
        
    try:
        requests.post(DISCORD_URL, json={"embeds": [embed]}, timeout=5)
    except Exception:
        pass

def log_to_master_csv(ticker, mode, action, entry_p, close_p, qty, pnl, trigger, risk_elim):
    file_exists = os.path.exists(MASTER_CSV_FILE)
    
    with open(MASTER_CSV_FILE, 'a', newline='') as csvfile:
        fieldnames = ['timestamp', 'ticker', 'mode', 'action', 'entry_price', 'close_price', 'quantity', 'net_pnl', 'trigger_logic', 'risk_eliminated']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()
            
        writer.writerow({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'ticker': ticker,
            'mode': mode,
            'action': action,
            'entry_price': round(entry_p, 4),
            'close_price': round(close_p, 4) if close_p else 0.0,
            'quantity': round(qty, 6),
            'net_pnl': round(pnl, 4),
            'trigger_logic': trigger,
            'risk_eliminated': risk_elim
        })

def update_daily_stats(pnl=0.0):
    stats = {"total_pnl": 0.0, "trades": 0, "date": str(datetime.now().date())}
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r') as f:
                stats = json.load(f)
            if stats.get("date") != str(datetime.now().date()):
                stats = {"total_pnl": 0.0, "trades": 0, "date": str(datetime.now().date())}
        except Exception:
            pass
    
    stats["total_pnl"] += pnl
    if pnl != 0:
        stats["trades"] += 1
    
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f)
        
    return stats["total_pnl"]

def load_active_trades():
    if not os.path.exists(ACTIVE_TRADES_FILE):
        return []
    try:
        with open(ACTIVE_TRADES_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return []

def save_active_trades(trades):
    with open(ACTIVE_TRADES_FILE, 'w') as f:
        json.dump(trades, f, indent=4)

class LiveVelocityEngine:
    def __init__(self, ticker):
        self.ticker = ticker
        self.tf = OPTIMAL_ROUTING.get(ticker, 5)
        
        if ticker.startswith("X_"):
            self.exchange_id = 'kraken'
            self.symbol = ticker.replace("X_", "").replace("USD", "/USD")
        else:
            self.exchange_id = 'alpaca'
            self.symbol = f"{ticker}/USD"

        exchange_class = getattr(ccxt, self.exchange_id)
        api_key = os.getenv(f'{self.exchange_id.upper()}_API_KEY')
        api_secret = os.getenv(f'{self.exchange_id.upper()}_API_SECRET')

        exchange_params = {'enableRateLimit': True}
        if api_key and api_secret:
            exchange_params['apiKey'] = api_key
            exchange_params['secret'] = api_secret
        elif self.exchange_id == 'alpaca':
            raise ValueError(f"[!] MISSING CREDENTIALS for ALPACA.")

        self.exchange = exchange_class(exchange_params)
        if self.exchange_id == 'alpaca':
            self.exchange.urls['api'] = self.exchange.urls['test']
            
        self.exchange.load_markets()

    def fetch_data(self):
        try:
            ohlcv_tf = self.exchange.fetch_ohlcv(self.symbol, timeframe=f'{self.tf}m', limit=250)
            ohlcv_1m = self.exchange.fetch_ohlcv(self.symbol, timeframe='1m', limit=5)
            
            if not ohlcv_tf or not ohlcv_1m:
                return None, None
            
            df_tf = pd.DataFrame(ohlcv_tf, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df_tf['timestamp'] = pd.to_datetime(df_tf['timestamp'], unit='ms')
            df_tf.set_index('timestamp', inplace=True)

            df_1m = pd.DataFrame(ohlcv_1m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df_1m['timestamp'] = pd.to_datetime(df_1m['timestamp'], unit='ms')
            df_1m.set_index('timestamp', inplace=True)
            
            return df_tf, df_1m
        except Exception:
            return None, None

    def manage_telemetry(self, current_price):
        all_trades = load_active_trades()
        my_trades = [t for t in all_trades if t['ticker'] == self.ticker]
        
        for t in my_trades:
            # 1. RISK ELIMINATED PROTOCOL (1R Hit)
            if not t['risk_eliminated'] and current_price >= (t['entry'] + t['initial_risk']):
                t['risk_eliminated'] = True
                t['sl'] = t['entry']
                
                if t['mode'] == 'LIVE':
                    try:
                        self.exchange.cancel_all_orders(self.symbol)
                        self.exchange.create_order(
                            symbol=self.symbol, type='limit', side='sell', amount=t['qty'], price=t['tp'],
                            params={'stopLossPrice': round(t['sl'], 2), 'ocoOrder': True}
                        )
                    except Exception as e:
                        print(f"[!] Alpaca Hard Stop Update Failed: {e}")

                save_active_trades(all_trades)
                desc = "Price secured 1R distance. Server bracket stop moved to breakeven."
                notify_discord("🛡️ Risk Eliminated", {"Ticker": self.ticker, "New Stop Level": f"${t['sl']:,.2f}"}, color=16705372, description=desc)

            # 2. EXIT PROTOCOLS
            if current_price <= t['sl'] or current_price >= t['tp']:
                trigger = "STOP LOSS (SOFT) HIT" if current_price <= t['sl'] else "TAKE PROFIT (SOFT) HIT"
                if t['mode'] == 'LIVE':
                    trigger = trigger.replace("SOFT", "HARD")
                
                close_price = t['sl'] if current_price <= t['sl'] else t['tp']
                pnl = (close_price - t['entry']) * t['qty']
                realized_today = update_daily_stats(pnl)
                
                fields = {
                    "Ticker": self.ticker,
                    "Action": f"🔴 MARKET SELL ({t['mode']})",
                    "Quantity Closed": f"{t['qty']:.4f}",
                    "Net PnL": f"${pnl:,.2f}",
                    "Close Price": f"${close_price:,.2f}",
                    "Realized Today": f"{'🔴' if realized_today < 0 else '🟢'} ${realized_today:,.2f}",
                    "Trigger Logic": trigger
                }
                notify_discord(f"Position Closed ({t['mode']})", fields, color=15548997)
                
                log_to_master_csv(self.ticker, t['mode'], "EXIT", t['entry'], close_price, t['qty'], pnl, trigger, t['risk_eliminated'])
                
                all_trades.remove(t)
                save_active_trades(all_trades)

    def analyze_and_execute(self):
        df_tf, df_1m = self.fetch_data()
        
        if df_tf is None or len(df_tf) < 200:
            return
        
        current_price = df_1m['close'].iloc[-1]
        self.manage_telemetry(current_price)

        df_tf['SMA200'] = ta.sma(df_tf['close'], length=200)
        df_tf['RSI'] = ta.rsi(df_tf['close'], length=14)
        df_tf['Vol_MA20'] = ta.sma(df_tf['volume'], length=20)
        df_tf['Recent_High'] = df_tf['high'].rolling(window=10).max().shift(1)
        df_tf['ChoCH'] = df_tf['close'] > df_tf['Recent_High']
        
        df_tf = df_tf.dropna(subset=['SMA200'])
        if df_tf.empty:
            return
            
        df_tf['Trend_Up'] = df_tf['close'] > df_tf['SMA200']

        df_tf['c1_High'] = df_tf['high'].shift(2)
        df_tf['c2_Low'] = df_tf['low'].shift(1)
        df_tf['FVG_Bullish'] = df_tf['low'] > df_tf['c1_High']
        df_tf['FVG_Mid'] = (df_tf['low'] + df_tf['c1_High']) / 2
        df_tf['FVG_Stop'] = df_tf['c2_Low']

        last = df_tf.iloc[-1]
        score_vol = 30 if last['volume'] > last['Vol_MA20'] else 0
        score_rsi = 30 if 40 <= last['RSI'] <= 70 else 0
        score = score_vol + score_rsi

        if self.exchange_id == 'kraken' or (datetime.now().second % 30 == 0):
             print(f"[{datetime.now().strftime('%H:%M:%S')}] {self.ticker:<10} | Score: {score}/60 | Price: {last['close']:.2f}")

        active = [t for t in load_active_trades() if t['ticker'] == self.ticker]
        if active:
            return 

        if last['Trend_Up'] and last['ChoCH'] and last['FVG_Bullish'] and score >= 60:
            if df_1m['low'].iloc[-1] <= last['FVG_Mid'] and current_price >= last['c1_High']:
                self.fire_warden_order(last, current_price, score)

    def fire_warden_order(self, signal_row, entry_p, score):
        try:
            is_kraken_paper = (self.exchange_id == 'kraken' and os.getenv("KRAKEN_MODE") == "PAPER")
            mode = "PAPER" if is_kraken_paper else "LIVE"
            
            if is_kraken_paper:
                balance = float(os.getenv("KRAKEN_PAPER_BAL", 10000.0))
            else:
                balance_data = self.exchange.fetch_balance()
                balance = float(balance_data['total'].get('USD', 0.0))
                
            if balance < 1.0:
                return
            
            sl = signal_row['FVG_Stop']
            if sl >= entry_p:
                sl = entry_p * 0.99
                
            risk_dist = entry_p - sl
            qty = (balance * RISK_PCT) / risk_dist
            tp = entry_p + (risk_dist * REWARD_MULTIPLIER)

            if not is_kraken_paper:
                self.exchange.create_order(
                    symbol=self.symbol, type='limit', side='buy', amount=qty, price=entry_p,
                    params={'stopLossPrice': round(sl, 2), 'takeProfitPrice': round(tp, 2), 'ocoOrder': True}
                )
            
            all_trades = load_active_trades()
            all_trades.append({
                "ticker": self.ticker, "mode": mode, "qty": qty, "entry": entry_p,
                "sl": sl, "tp": tp, "initial_risk": risk_dist, "risk_eliminated": False
            })
            save_active_trades(all_trades)

            log_to_master_csv(self.ticker, mode, "ENTRY", entry_p, 0.0, qty, 0.0, "SCORE 60", False)

            fields = {
                "Ticker": self.ticker,
                "Action": f"🟢 SIMULATED BUY (LOCAL)" if is_kraken_paper else "🟢 BUY (LIVE)",
                "Quantity": f"{qty:.4f}",
                "Entry Price": f"${entry_p:,.2f}",
                f"{'Soft' if is_kraken_paper else 'Hard'} Stop (1R)": f"${sl:,.2f}",
                f"{'Soft' if is_kraken_paper else 'Hard'} TP (4R)": f"${tp:,.2f}"
            }
            notify_discord(f"Target Acquired ({mode})", fields, color=5763719)

        except Exception as e:
            notify_discord("Execution Error", {"Ticker": self.ticker, "Error": str(e)}, color=15548997)

if __name__ == "__main__":
    print(f"\n{'='*60}\nV3.6 VELOCITY | TELEMETRY + DAEMON ACTIVE\n{'='*60}")
    engines = [LiveVelocityEngine(t) for t in OPTIMAL_ROUTING.keys()]
    
    update_daily_stats(0.0)

    while True:
        for engine in engines: 
            engine.analyze_and_execute()
            time.sleep(1.5)
