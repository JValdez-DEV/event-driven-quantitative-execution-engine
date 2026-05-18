#!/usr/bin/env python3
import os
import json
import asyncio
from dotenv import load_dotenv
from alpaca.data.live import StockDataStream, CryptoDataStream
from alpaca.data.models import Bar
from alpaca.trading.client import TradingClient

# --- ENVIRONMENT LOAD ---
ENV_PATH = '/root/trade_hunter/.env'
load_dotenv(ENV_PATH)
API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_API_SECRET")

if not API_KEY or not SECRET_KEY:
    raise SystemExit("[CRITICAL] Alpaca credentials missing from .env")

# --- INITIALIZE CLIENTS ---
trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
stock_stream = StockDataStream(API_KEY, SECRET_KEY)
crypto_stream = CryptoDataStream(API_KEY, SECRET_KEY)

# --- LOAD CONFIGURATIONS ---
with open('/root/trade_hunter/crypto_config.json', 'r') as f:
    CRYPTO_CONFIG = json.load(f)

# Note: Equities config loading would go here
EQUITY_TICKERS = ["AMD", "MSFT", "TSLA", "QQQ", "SPY", "COIN", "PLTR"]
CRYPTO_TICKERS = list(CRYPTO_CONFIG.keys())

print(f"\n{'='*60}\nTRADE HUNTER V1 - MASTER ORCHESTRATOR INITIALIZED\n{'='*60}", flush=True)

# --- ROUTING LOGIC ---
async def process_equity_tick(bar: Bar):
    # Route to v3_velocity_engine
    print(f"[EQUITY TICK] {bar.symbol} | Close: {bar.close} | Vol: {bar.volume}", flush=True)

async def process_crypto_tick(bar: Bar):
    # Convert Alpaca's live format "BTC/USD" back to our config format "X_BTCUSD"
    config_key = f"X_{bar.symbol.replace('/', '')}"
    params = CRYPTO_CONFIG.get(config_key, {})
    print(f"[CRYPTO TICK] {bar.symbol} | Close: {bar.close} | Params: {params}", flush=True)

# --- ASYNC WEBSOCKET DAEMON ---
async def main():
    print(f"[-] Subscribing to Equity Streams: {EQUITY_TICKERS}", flush=True)
    stock_stream.subscribe_bars(process_equity_tick, *EQUITY_TICKERS)
    
    # Alpaca crypto stream requires stripping the 'X_' and 'USD' for the live socket
    formatted_crypto = [t.replace('X_', '').replace('USD', '/USD') for t in CRYPTO_TICKERS]
    print(f"[-] Subscribing to Crypto Streams: {formatted_crypto}", flush=True)
    crypto_stream.subscribe_bars(process_crypto_tick, *formatted_crypto)

    print("\n[+] WebSockets Active. Listening for institutional volume spikes...\n", flush=True)
    
    # Run both streams concurrently
    await asyncio.gather(
        stock_stream._run_forever(),
        crypto_stream._run_forever()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Orchestrator manually terminated. Shutting down WebSockets.")
