import asyncio
import os
import sqlite3
import aiohttp
import ccxt.async_support as ccxt_async
from alpaca.trading.client import TradingClient
from dotenv import load_dotenv

load_dotenv()

DB_FILE = "/root/trade_hunter/active_trades.db"
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

ROUTING_MATRIX = [
    "TSLA", "NVDA", "AMD",
    "BTC/USD", "ETH/USD", "SOL/USD"
]

async def send_critical_alert():
    if not WEBHOOK_URL: return
    payload = {
        "embeds": [{
            "title": "🚨 SYSTEM LIQUIDATION INITIATED 🚨",
            "description": "The Emergency Kill Switch was manually triggered. All positions closed. State wiped.",
            "color": 16711680, # Pure Red
            "footer": {"text": "Trade Hunter V3.4 | Panic Protocol"}
        }]
    }
    async with aiohttp.ClientSession() as session:
        await session.post(WEBHOOK_URL, json=payload)

def wipe_database():
    print("[*] Wiping local state database...")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM trades')
    conn.commit()
    conn.close()
    print("[+] Database wiped.")

async def liquidate_kraken():
    print("[*] Liquidating Kraken positions...")
    kraken = ccxt_async.kraken({'apiKey': os.getenv('KRAKEN_KEY'), 'secret': os.getenv('KRAKEN_SECRET')})
    try:
        balance = await kraken.fetch_balance()
        for symbol in [s for s in ROUTING_MATRIX if '/' in s]:
            base_currency = symbol.split('/')[0]
            avail_qty = balance['free'].get(base_currency, 0)
            if avail_qty > 0.0001:  # Filter out dust
                print(f"    -> Market Selling {avail_qty} {symbol}")
                await kraken.create_market_sell_order(symbol, avail_qty)
        print("[+] Kraken liquidation complete.")
    except Exception as e:
        print(f"[!] Kraken Liquidation Error: {e}")
    finally:
        await kraken.close()

def liquidate_alpaca():
    print("[*] Liquidating Alpaca positions and cancelling pending orders...")
    try:
        client = TradingClient(os.getenv('ALPACA_KEY'), os.getenv('ALPACA_SECRET'), paper=True)
        cancel_statuses = client.close_all_positions(cancel_orders=True)
        for order in cancel_statuses:
            print(f"    -> Order dispatched for {order.symbol}")
        print("[+] Alpaca liquidation complete.")
    except Exception as e:
        print(f"[!] Alpaca Liquidation Error: {e}")

async def main():
    print(f"[{'!'*60}]")
    print(f"[!] INITIATING EMERGENCY PANIC PROTOCOL")
    print(f"[{'!'*60}]\n")
    
    # 1. Fire webhook immediately
    await send_critical_alert()
    
    # 2. Liquidate Exchanges Concurrent/Sync
    liquidate_alpaca()
    await liquidate_kraken()
    
    # 3. Wipe State
    wipe_database()
    
    print(f"\n[{'='*60}]")
    print("[+] PANIC PROTOCOL COMPLETE. ALL SYSTEMS HALTED.")

if __name__ == "__main__":
    asyncio.run(main())
