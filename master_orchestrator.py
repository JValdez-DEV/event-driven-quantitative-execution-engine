#!/usr/bin/env python3

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
import os
import json
import threading
import time
import requests
from dotenv import load_dotenv
from alpaca.data.live import StockDataStream, CryptoDataStream
from alpaca.data.models import Bar
from alpaca.trading.client import TradingClient

ENV_PATH = str(BASE_DIR / ".env")
load_dotenv(ENV_PATH)
API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_API_SECRET")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")

if not API_KEY or not SECRET_KEY:
    raise SystemExit("[CRITICAL] Credentials missing from .env")

# --- INITIALIZE CORE CLIENTS ---
trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)

# --- LOAD CONFIGURATIONS ---
with open(str(BASE_DIR / "crypto_config.json"), 'r') as f:
    CRYPTO_CONFIG = json.load(f)

try:
    with open(str(BASE_DIR / "equity_config.json"), 'r') as f:
        EQUITY_CONFIG = json.load(f)
except FileNotFoundError:
    EQUITY_CONFIG = {}

# --- IMPORT SECURE PRODUCTION ENGINE STACKS ---
import crypto_sweep_engine
import equity_sweep_engine

# Safely extract target ticker arrays from configuration parameters
EQUITY_TICKERS = EQUITY_CONFIG.get("symbols", ["AMD", "MSFT", "TSLA", "QQQ", "SPY", "COIN", "PLTR"])
if "MSFT" not in EQUITY_TICKERS:
    EQUITY_TICKERS.append("MSFT")

CRYPTO_TICKERS = CRYPTO_CONFIG.get("symbols", ["BTC/USD", "ETH/USD"])

print(f"\n{'='*60}\nEVENT-DRIVEN QUANTITATIVE EXECUTION ENGINE V1.4 - MULTI-THREADED ROUTER ONLINE\n{'='*60}", flush=True)

def send_rich_discord_alert(payload):
    if not DISCORD_WEBHOOK or not payload: return
    embed = {
        "title": payload.get('title', 'System Alert'),
        "color": payload.get('color', 0), 
        "fields": []
    }
    for key, val in payload.get('fields', {}).items():
        embed["fields"].append({"name": key, "value": str(val), "inline": False})
    embed["footer"] = {"text": "Event-Driven Quantitative Execution Engine V3.9 | Dynamic Telemetry Stack"}
    try:
        requests.post(DISCORD_WEBHOOK, json={"embeds": [embed]})
    except Exception as e:
        print(f"[ALERT ERROR] Webhook failed: {e}", flush=True)

# --- ASYNC HANDLERS (Required by Alpaca SDK) ---
async def process_equity_tick(bar: Bar):
    params = EQUITY_CONFIG.get(bar.symbol, EQUITY_CONFIG)
    try:
        payload = equity_sweep_engine.evaluate_live_bar(bar, params, trading_client)
        if payload: send_rich_discord_alert(payload)
    except Exception as e:
        print(f"⚠️ [STOCK ENGINE ERROR]: {e}", flush=True)

async def process_crypto_tick(bar: Bar):
    config_key = f"X_{bar.symbol.replace('/', '')}"
    params = CRYPTO_CONFIG.get(config_key, CRYPTO_CONFIG)
    try:
        payload = crypto_sweep_engine.evaluate_live_bar(bar, params, trading_client)
        if payload: send_rich_discord_alert(payload)
    except Exception as e:
        print(f"⚠️ [CRYPTO ENGINE ERROR]: {e}", flush=True)

# --- ISOLATED THREAD RUNNERS ---
def run_equity_stream():
    while True:
        try:
            print("[THREAD-1] Initializing Equity WebSocket...", flush=True)
            stock_stream = StockDataStream(API_KEY, SECRET_KEY)
            stock_stream.subscribe_bars(process_equity_tick, *EQUITY_TICKERS)
            stock_stream.run() # Blocking call for this thread
        except Exception as e:
            print(f"[THREAD-1 FATAL] Equity Stream Crashed: {e}. Reconnecting in 5s...", flush=True)
            time.sleep(5)

def run_crypto_stream():
    while True:
        try:
            print("[THREAD-2] Initializing Crypto WebSocket...", flush=True)
            crypto_stream = CryptoDataStream(API_KEY, SECRET_KEY)
            crypto_stream.subscribe_bars(process_crypto_tick, *CRYPTO_TICKERS)
            crypto_stream.run() # Blocking call for this thread
        except Exception as e:
            print(f"[THREAD-2 FATAL] Crypto Stream Crashed: {e}. Reconnecting in 5s...", flush=True)
            time.sleep(5)

if __name__ == "__main__":
    startup_payload = {
        "title": "🟢 Event-Driven Quantitative Execution Engine V1.4 Orchestrator Online",
        "color": 5763719,
        "fields": {"Status": "Live Multi-Threaded Sockets Armed", "Active Hunters": "Crypto Matrix, Equity Matrix"}
    }
    send_rich_discord_alert(startup_payload)
    
    # Ignite isolated background threads
    t1 = threading.Thread(target=run_equity_stream, daemon=True)
    t2 = threading.Thread(target=run_crypto_stream, daemon=True)
    
    t1.start()
    t2.start()

    try:
        # Keep main thread alive so background daemons don't die
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nOrchestrator terminated cleanly.")