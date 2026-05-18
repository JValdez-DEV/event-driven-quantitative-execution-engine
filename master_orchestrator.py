#!/usr/bin/env python3
import os
import json
import asyncio
import requests
from dotenv import load_dotenv
from alpaca.data.live import StockDataStream, CryptoDataStream
from alpaca.data.models import Bar
from alpaca.trading.client import TradingClient

# --- ENVIRONMENT LOAD ---
ENV_PATH = '/root/trade_hunter/.env'
load_dotenv(ENV_PATH)
API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_API_SECRET")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")

if not API_KEY or not SECRET_KEY:
    raise SystemExit("[CRITICAL] Alpaca credentials missing from .env")

# --- INITIALIZE CLIENTS ---
trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
stock_stream = StockDataStream(API_KEY, SECRET_KEY)
crypto_stream = CryptoDataStream(API_KEY, SECRET_KEY)

# --- LOAD CONFIGURATIONS ---
with open('/root/trade_hunter/crypto_config.json', 'r') as f:
    CRYPTO_CONFIG = json.load(f)

EQUITY_TICKERS = ["AMD", "MSFT", "TSLA", "QQQ", "SPY", "COIN", "PLTR"]
CRYPTO_TICKERS = list(CRYPTO_CONFIG.keys())

print(f"\n{'='*60}\nTRADE HUNTER V1 - MASTER ORCHESTRATOR [IMMEDIATE ALERTS ARMED]\n{'='*60}", flush=True)

# --- TRACKERS TO PREVENT TELEMETRY FLOODING ---
crypto_test_fired = False
equity_test_fired = False

# --- DISCORD ALERT ENGINE ---
def send_discord_alert(message):
    if DISCORD_WEBHOOK:
        try:
            requests.post(DISCORD_WEBHOOK, json={"content": message})
        except Exception as e:
            print(f"[ALERT ERROR] Failed to send Discord ping: {e}", flush=True)

# --- ROUTING LOGIC ---
async def process_equity_tick(bar: Bar):
    global equity_test_fired
    print(f"[EQUITY TICK] {bar.symbol} | Close: {bar.close} | Vol: {bar.volume}", flush=True)
    
    # --- LIVE DATA VERIFICATION FROM MARKET ---
    if not equity_test_fired:
        test_msg = f"🔥 **LIVE EQUITY MARKET DATA RECEIVED** 🔥\n**Asset:** {bar.symbol}\n**Live Price:** ${bar.close}\n**Status:** Stream verified functional."
        send_discord_alert(test_msg)
        equity_test_fired = True

async def process_crypto_tick(bar: Bar):
    global crypto_test_fired
    
    # [HOTFIX RETAINED] Convert Alpaca's live format "BTC/USD" back to our config format "X_BTCUSD"
    config_key = f"X_{bar.symbol.replace('/', '')}"
    params = CRYPTO_CONFIG.get(config_key, {})
    
    print(f"[CRYPTO TICK] {bar.symbol} | Close: {bar.close} | Params: {params}", flush=True)
    
    # --- LIVE DATA VERIFICATION FROM MARKET ---
    if not crypto_test_fired:
        test_msg = f"🔥 **LIVE CRYPTO MARKET DATA RECEIVED** 🔥\n**Asset:** {bar.symbol}\n**Live Price:** ${bar.close}\n**Params Dynamic Load:** `{json.dumps(params)}`"
        send_discord_alert(test_msg)
        crypto_test_fired = True

# --- ASYNC WEBSOCKET DAEMON ---
async def main():
    print(f"[-] Subscribing to Equity Streams: {EQUITY_TICKERS}", flush=True)
    stock_stream.subscribe_bars(process_equity_tick, *EQUITY_TICKERS)
    
    formatted_crypto = [t.replace('X_', '').replace('USD', '/USD') for t in CRYPTO_TICKERS]
    print(f"[-] Subscribing to Crypto Streams: {formatted_crypto}", flush=True)
    crypto_stream.subscribe_bars(process_crypto_tick, *formatted_crypto)

    print("\n[+] Executing Immediate Connection Tests...", flush=True)
    
    # --- IMMEDIATE TELEMETRY PINGS ---
    send_discord_alert("🟢 **Trade Hunter V1 Orchestrator Online** - Initializing Pipeline Daemon.")
    
    mock_crypto_key = "X_BTCUSD"
    mock_crypto_params = CRYPTO_CONFIG.get(mock_crypto_key, {})
    
    immediate_equity_msg = f"📈 **EQUITY CONNECTION TEST (IMMEDIATE)** 📈\n**Status:** Webhook Integration Operational.\n**Target Matrix:** {EQUITY_TICKERS}"
    immediate_crypto_msg = f"🪙 **CRYPTO CONNECTION TEST (IMMEDIATE)** 📈\n**Status:** Webhook Integration Operational.\n**Sample Config Vector ({mock_crypto_key}):** `{json.dumps(mock_crypto_params)}`"
    
    send_discord_alert(immediate_equity_msg)
    send_discord_alert(immediate_crypto_msg)

    print("[+] WebSockets Active. TELEMETRY MONITORING LIVE...\n", flush=True)
    
    await asyncio.gather(
        stock_stream._run_forever(),
        crypto_stream._run_forever()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Orchestrator manually terminated. Shutting down WebSockets.")
        send_discord_alert("🔴 **Trade Hunter V1 Orchestrator Offline** - Manual Shutdown.")
