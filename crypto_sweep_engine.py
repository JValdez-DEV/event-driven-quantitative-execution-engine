# /root/trade_hunter/crypto_sweep_engine.py
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

ROLLING_VOLUME = {}
ACTIVE_POSITIONS = {} 

def evaluate_live_bar(bar, params, client):
    global ROLLING_VOLUME, ACTIVE_POSITIONS
    sym = bar.symbol
    current_price = float(bar.close)
    
    # --- 1. LIVE POSITION STALKER ---
    if sym in ACTIVE_POSITIONS and ACTIVE_POSITIONS[sym] is not None:
        pos = ACTIVE_POSITIONS[sym]
        
        if current_price > pos["peak"]:
            pos["peak"] = current_price
            print(f"[TRAIL ADJUST] {sym} peaked at ${current_price:,.2f}. Stop raised to ${current_price * (1 - pos['trail_pct']):,.2f}", flush=True)
            
        stop_floor = pos["peak"] * (1 - pos["trail_pct"])
        
        if current_price <= stop_floor:
            try:
                exit_order = MarketOrderRequest(
                    symbol=sym,
                    qty=pos["qty"],
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.GTC
                )
                client.submit_order(order_data=exit_order)
                realized_pnl = (current_price - pos["entry"]) * pos["qty"]
                ACTIVE_POSITIONS[sym] = None
                
                return {
                    "title": f"Position Closed (CRYPTO TRAIL BREACH)",
                    "color": 15548997, 
                    "fields": {
                        "Ticker": sym,
                        "Action": "🔴 MARKET SELL (LOCAL SOFT TRAIL HIT)",
                        "Quantity Closed": pos["qty"],
                        "Net PnL Estimate": f"${realized_pnl:+,.2f}",
                        "Exit Price": f"${current_price:,.2f}",
                        "Peak Reached": f"${pos['peak']:,.2f}"
                    }
                }
            except Exception as e:
                print(f"⚠️ [CRITICAL EXIT ERROR] Failed to close crypto {sym}: {e}", flush=True)
        return None 

    # --- 2. DATA INGESTION ---
    if sym not in ROLLING_VOLUME:
        ROLLING_VOLUME[sym] = []
        
    ROLLING_VOLUME[sym].append(bar.volume)
    if len(ROLLING_VOLUME[sym]) > 10:
        ROLLING_VOLUME[sym].pop(0)
    if len(ROLLING_VOLUME[sym]) < 3:
        return None
        
    avg_volume = sum(ROLLING_VOLUME[sym][:-1]) / len(ROLLING_VOLUME[sym][:-1])
    if avg_volume == 0: avg_volume = 0.0001
    vol_multiplier = float(params.get('volume_multiplier', 1.5))
    
    # --- 3. ENTRY TRIGGER & FAIL-SAFE ---
    if bar.volume > (avg_volume * vol_multiplier):
        
        buffer_pct = float(params.get('stop_wick_buffer_pct', 0.005))
        stop_loss_delta = current_price * buffer_pct
        
        target_risk_usd = 100.0
        max_position_size = 3000.0 # LIVE ACCOUNT CAP
        
        # Initial sizing
        qty = round(target_risk_usd / stop_loss_delta, 4) if stop_loss_delta > 0 else 0
        
        # Override if too massive
        total_investment = qty * current_price
        if total_investment > max_position_size:
            qty = round(max_position_size / current_price, 4)
        
        if qty <= 0: return None

        # --- 4. LIVE EXECUTION ---
        try:
            entry_order = MarketOrderRequest(
                symbol=sym,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.GTC
            )
            client.submit_order(order_data=entry_order)
            
            ACTIVE_POSITIONS[sym] = {
                "qty": qty,
                "entry": current_price,
                "peak": current_price,
                "trail_pct": buffer_pct
            }
            
            action_text = "🟢 MARKET BUY (CAPPED LOCAL MONITORING)"
            color_hex = 5763719
        except Exception as e:
            action_text = f"🔴 ENTRY FAILED: {e}"
            color_hex = 15548997

        return {
            "title": f"Target Acquired (CRYPTO DYNAMIC)",
            "color": color_hex,
            "fields": {
                "Ticker": sym,
                "Action": action_text,
                "Quantity": qty,
                "Entry Price": f"${current_price:,.2f}",
                "Initial Stop": f"${current_price * (1 - buffer_pct):,.2f} (Trails Upward)",
                "Trigger": f"Vol Anomaly | Cur: {bar.volume:,.4f} vs Avg: {avg_volume:,.4f}"
            }
        }
    return None
