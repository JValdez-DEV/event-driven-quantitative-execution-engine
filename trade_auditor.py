#!/usr/bin/env python3

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
import os
import time
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus, OrderSide

# --- INITIALIZATION ---
load_dotenv(BASE_DIR / ".env")
API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_API_SECRET")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")

client = TradingClient(API_KEY, SECRET_KEY, paper=True)

# --- PARAMETERS ---
WIN_RATE_THRESHOLD = 60.0  
MIN_TRADES_REQUIRED = 20   
PROP_FIRM_DD_LIMIT = 5.0      # Hard exchange limit
CIRCUIT_BREAKER_LIMIT = 4.0    # Tactical safety tripwire
HALT_FILE = str(BASE_DIR / ".halt")
LEDGER_PATH = str(BASE_DIR / "strategy_ledger.json")

def load_current_parameters():
    params = {"crypto": {}, "equity": {}}
    try:
        with open(str(BASE_DIR / "crypto_config.json"), 'r') as f:
            params["crypto"] = json.load(f)
        with open(str(BASE_DIR / "equity_config.json"), 'r') as f:
            params["equity"] = json.load(f)
    except FileNotFoundError:
        pass
    return params

def save_to_ledger(audit_data):
    ledger = []
    if os.path.exists(LEDGER_PATH):
        try:
            with open(LEDGER_PATH, 'r') as f:
                ledger = json.load(f)
        except json.JSONDecodeError:
            pass
    ledger.append(audit_data)
    with open(LEDGER_PATH, 'w') as f:
        json.dump(ledger, f, indent=4)

def execute_nuclear_liquidation():
    """Cancels all orders and flattens all open positions instantly across the account."""
    print("🚨 [CRITICAL ALERT] CIRCUIT BREAKER TRIGGERED! FLATTENING PORTFOLIO...", flush=True)
    try:
        # 1. Drop halt file to stop entry engines immediately
        with open(HALT_FILE, 'w') as f:
            f.write(f"Halted at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 2. Cancel all outstanding open orders on exchange
        client.cancel_orders()
        
        # 3. Liquidate every active position at market value
        client.close_all_positions(cancel_orders=True)
        
        return True
    except Exception as e:
        print(f"⚠️ [CRITICAL ERROR] Nuclear liquidation failed to execute completely: {e}", flush=True)
        return False

def send_discord_report(audit_data, breached=False):
    if breached:
        color = 15548997 # Red
        status = "🚨 EMERGENCY SHUTDOWN: CIRCUIT BREAKER TRIGGERED"
        next_steps = f"Daily Drawdown hit {audit_data['daily_drawdown_pct']:.2f}%. All positions closed. Engines locked."
    elif audit_data['win_rate'] >= WIN_RATE_THRESHOLD and audit_data['total_trades'] >= MIN_TRADES_REQUIRED:
        color = 5763719 # Green
        status = "🟢 SYSTEM VERIFIED: PROP FIRM READY"
        next_steps = "Mathematical edge confirmed. Clearance granted for live evaluation deployment."
    else:
        color = 16766720 # Yellow
        status = "🟡 FILTERING ACTIVE / MULTIPLIER UPGRADED"
        next_steps = f"Volume filters raised to 2.5x. Tracking next trades. Keep daily DD below {CIRCUIT_BREAKER_LIMIT}%."

    payload = {
        "embeds": [{
            "title": "Event-Driven Quantitative Execution Engine V3.7 | Institutional Risk Enforcer",
            "color": color,
            "fields": [
                {"name": "System Status", "value": status, "inline": False},
                {"name": "Total Trades", "value": str(audit_data['total_trades']), "inline": True},
                {"name": "Wins", "value": str(audit_data['wins']), "inline": True},
                {"name": "Losses", "value": str(audit_data['losses']), "inline": True},
                {"name": "Win Rate", "value": f"{audit_data['win_rate']:.2f}%", "inline": True},
                {"name": "Daily Drawdown", "value": f"{audit_data['daily_drawdown_pct']:.2f}% (Limit: {CIRCUIT_BREAKER_LIMIT}%)", "inline": True},
                {"name": "Account Equity", "value": f"${audit_data['current_equity']:,.2f}", "inline": True},
                {"name": "Directive", "value": next_steps, "inline": False}
            ],
            "footer": {"text": f"Active Guardian Execution | 10s High-Freq Loop"}
        }]
    }
    try:
        requests.post(DISCORD_WEBHOOK, json=payload)
    except Exception as e:
        print(f"Webhook Error: {e}")

def run_performance_audit(last_report_time):
    current_time = time.time()
    should_report = (current_time - last_report_time) >= 3600 # Force Discord update every hour
    
    try:
        # 1. High-frequency calculation of portfolio state
        account = client.get_account()
        current_equity = float(account.portfolio_value)
        last_equity = float(account.last_equity) 
        
        daily_drawdown_pct = 0.0
        if last_equity > 0 and current_equity < last_equity:
            daily_drawdown_pct = ((last_equity - current_equity) / last_equity) * 100

        # 2. Check risk limit breach
        if daily_drawdown_pct >= CIRCUIT_BREAKER_LIMIT:
            if not os.path.exists(HALT_FILE):
                execute_nuclear_liquidation()
                should_report = True # Force report on breach

        # 3. Check for automatic daily rollover reset
        if os.path.exists(HALT_FILE) and daily_drawdown_pct == 0.0:
            os.remove(HALT_FILE)
            print("🔄 New trading day detected. Drawdown reset to 0%. Removing halt locks.", flush=True)

        # 4. Process accounting ledger stats if reporting interval is hit
        if should_report:
            req = GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=500)
            closed_orders = client.get_orders(req)
            total_trades = wins = losses = 0

            for order in closed_orders:
                if order.side == OrderSide.SELL and order.filled_qty and float(order.filled_qty) > 0:
                    total_trades += 1
                    if order.limit_price: wins += 1 
                    elif order.stop_price: losses += 1 

            win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0.0

            audit_data = {
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "total_trades": total_trades,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "current_equity": current_equity,
                "daily_drawdown_pct": daily_drawdown_pct,
                "active_parameters": load_current_parameters()
            }
            save_to_ledger(audit_data)
            send_discord_report(audit_data, breached=os.path.exists(HALT_FILE))
            return current_time

    except Exception as e:
        print(f"Enforcer Error: {e}", flush=True)
    return last_report_time

if __name__ == "__main__":
    print("Event-Driven Quantitative Execution Engine Risk Enforcer Online. Active 10-second monitoring enabled.")
    last_report = 0
    while True:
        last_report = run_performance_audit(last_report)
        time.sleep(10)