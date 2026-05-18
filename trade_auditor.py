#!/usr/bin/env python3
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
load_dotenv('/root/trade_hunter/.env')
API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_API_SECRET")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")

client = TradingClient(API_KEY, SECRET_KEY, paper=True)

# --- AUDIT & PROP FIRM PARAMETERS ---
WIN_RATE_THRESHOLD = 60.0  
MIN_TRADES_REQUIRED = 20   
PROP_FIRM_DD_LIMIT = 5.0 # Max 5% Daily Drawdown
LEDGER_PATH = '/root/trade_hunter/strategy_ledger.json'

def load_current_parameters():
    params = {"crypto": {}, "equity": {}}
    try:
        with open('/root/trade_hunter/crypto_config.json', 'r') as f:
            params["crypto"] = json.load(f)
        with open('/root/trade_hunter/equity_config.json', 'r') as f:
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
    print(f"[{audit_data['timestamp']}] Ledger Updated. Data saved to disk.")

def send_discord_report(audit_data):
    if audit_data['daily_drawdown_pct'] >= PROP_FIRM_DD_LIMIT:
        color = 15548997 # Red (Fatal Fail)
        status = "🔴 EVALUATION FAILED: 5% DRAWDOWN BREACHED"
        next_steps = "Halt trading immediately. Strategy requires strict risk scaling."
    elif audit_data['win_rate'] >= WIN_RATE_THRESHOLD and audit_data['total_trades'] >= MIN_TRADES_REQUIRED:
        color = 5763719 # Green (Pass)
        status = "🟢 SYSTEM VERIFIED: PROP FIRM READY"
        next_steps = "Mathematical edge confirmed. Safe to deploy to Evaluation Server."
    else:
        color = 16766720 # Yellow (Pending)
        status = "🟡 COLLECTING DATA / BELOW THRESHOLD"
        next_steps = f"Need {max(0, MIN_TRADES_REQUIRED - audit_data['total_trades'])} more trades. Keep DD below 5%."

    payload = {
        "embeds": [{
            "title": "Trade Hunter V3.7 | Institutional Ledger",
            "color": color,
            "fields": [
                {"name": "System Status", "value": status, "inline": False},
                {"name": "Total Trades", "value": str(audit_data['total_trades']), "inline": True},
                {"name": "Wins", "value": str(audit_data['wins']), "inline": True},
                {"name": "Losses", "value": str(audit_data['losses']), "inline": True},
                {"name": "Win Rate", "value": f"{audit_data['win_rate']:.2f}%", "inline": True},
                {"name": "Daily Drawdown", "value": f"{audit_data['daily_drawdown_pct']:.2f}% (Max 5%)", "inline": True},
                {"name": "Account Equity", "value": f"${audit_data['current_equity']:,.2f}", "inline": True},
                {"name": "Directive", "value": next_steps, "inline": False}
            ],
            "footer": {"text": "Prop Firm Audit | Hourly Sync"}
        }]
    }
    try:
        requests.post(DISCORD_WEBHOOK, json=payload)
    except Exception as e:
        print(f"Webhook Error: {e}")

def run_performance_audit():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Executing Prop Firm Audit...", flush=True)
    try:
        account = client.get_account()
        current_equity = float(account.portfolio_value)
        last_equity = float(account.last_equity) 
        
        daily_drawdown_pct = 0.0
        if last_equity > 0 and current_equity < last_equity:
            daily_drawdown_pct = ((last_equity - current_equity) / last_equity) * 100

        req = GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=500)
        closed_orders = client.get_orders(req)
        
        total_trades = 0
        wins = 0
        losses = 0

        for order in closed_orders:
            if order.side == OrderSide.SELL and order.filled_qty and float(order.filled_qty) > 0:
                total_trades += 1
                avg_fill_price = float(order.filled_avg_price) if order.filled_avg_price else 0.0
                
                if avg_fill_price > 0:
                    if order.limit_price: 
                        wins += 1 
                    elif order.stop_price:
                        losses += 1 

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
        send_discord_report(audit_data)

    except Exception as e:
        print(f"Audit Failure: {e}", flush=True)

if __name__ == "__main__":
    print("Trade Hunter Prop Firm Ledger Online. Syncing every 60 minutes.")
    while True:
        run_performance_audit()
        time.sleep(3600)
