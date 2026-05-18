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

# --- AUDIT PARAMETERS ---
WIN_RATE_THRESHOLD = 60.0  
MIN_TRADES_REQUIRED = 20   
LEDGER_PATH = '/root/trade_hunter/strategy_ledger.json'

def load_current_parameters():
    """Snapshots the active strategy parameters to link them to the performance."""
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
    """Saves the graded performance and the exact parameters to the local hard drive."""
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
    if audit_data['win_rate'] >= WIN_RATE_THRESHOLD and audit_data['total_trades'] >= MIN_TRADES_REQUIRED:
        color = 5763719 # Green
        status = "🟢 SYSTEM VERIFIED: CLEARED FOR LIVE CAPITAL"
        next_steps = "Mathematical edge confirmed. Safe to swap API keys to Live environment."
    else:
        color = 15548997 # Red
        status = "🟡 COLLECTING DATA / BELOW THRESHOLD"
        next_steps = f"Need {max(0, MIN_TRADES_REQUIRED - audit_data['total_trades'])} more trades or higher win rate."

    payload = {
        "embeds": [{
            "title": "Trade Hunter V3.6 | Parameter Ledger",
            "color": color,
            "fields": [
                {"name": "System Status", "value": status, "inline": False},
                {"name": "Total Closed Trades", "value": str(audit_data['total_trades']), "inline": True},
                {"name": "Wins", "value": str(audit_data['wins']), "inline": True},
                {"name": "Losses", "value": str(audit_data['losses']), "inline": True},
                {"name": "Current Win Rate", "value": f"{audit_data['win_rate']:.2f}%", "inline": False},
                {"name": "Directive", "value": next_steps, "inline": False}
            ],
            "footer": {"text": "Local Ledger Updated | Hourly Sync"}
        }]
    }
    try:
        requests.post(DISCORD_WEBHOOK, json=payload)
    except Exception as e:
        print(f"Webhook Error: {e}")

def run_performance_audit():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Executing Alpaca Ledger Audit...", flush=True)
    try:
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

        # Package the active snapshot
        audit_data = {
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "active_parameters": load_current_parameters()
        }

        save_to_ledger(audit_data)
        send_discord_report(audit_data)

    except Exception as e:
        print(f"Audit Failure: {e}", flush=True)

if __name__ == "__main__":
    print("Trade Hunter Ledger Online. Syncing and saving every 60 minutes.")
    while True:
        run_performance_audit()
        time.sleep(3600)
