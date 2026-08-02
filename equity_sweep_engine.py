from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
# /root/event-driven-quantitative-execution-engine/equity_sweep_engine.py
from alpaca.trading.requests import MarketOrderRequest, TakeProfitRequest, StopLossRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass

ROLLING_VOLUME = {}

def evaluate_live_bar(bar, params, client):
    global ROLLING_VOLUME
    sym = bar.symbol
    
    # --- 1. DATA INGESTION & BASELINE ---
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
    
    # --- 2. THE TRIGGER ENGINE ---
    if bar.volume > (avg_volume * vol_multiplier):
        try:
            client.get_open_position(sym)
            return None 
        except Exception:
            pass
            
        # --- 3. DYNAMIC TARGET MATRIX & BROKER LIQUIDITY CHECK ---
        entry_price = float(bar.close)
        buffer_pct = float(params.get('stop_wick_buffer_pct', 0.005))
        rr = float(params.get('reward_risk', 2.0))
        
        stop_loss = round(entry_price * (1 - buffer_pct), 2)
        risk_per_share = entry_price - stop_loss
        take_profit = round(entry_price + (risk_per_share * rr), 2)
        
        target_risk_usd = 100.0
        STRATEGIC_MAX_CAP = 3000.0 
        
        # Pull exact available broker liquidity dynamically
        try:
            account = client.get_account()
            available_buying_power = float(account.buying_power)
        except Exception:
            available_buying_power = 0.0
            
        # Hard cap is the lesser of our $3k strategy limit or actual broker cash left
        effective_cap = min(STRATEGIC_MAX_CAP, available_buying_power)
        
        # Initial sizing attempt
        qty = round(target_risk_usd / risk_per_share, 0) if risk_per_share > 0 else 0
        
        # Dynamic down-scale override
        total_investment = qty * entry_price
        if total_investment > effective_cap:
            qty = round(effective_cap / entry_price, 0)
            
        if qty <= 0:
            print(f"⚠️ [SKIPPED] {sym} ignored. Effective buying power cap (${effective_cap:.2f}) insufficient for 1 share.", flush=True)
            return None

        # --- 4. SUBMIT HARD BRACKET ORDER TO EXCHANGE ---
        try:
            order_data = MarketOrderRequest(
                symbol=sym,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.GTC,
                order_class=OrderClass.BRACKET,
                take_profit=TakeProfitRequest(limit_price=take_profit),
                stop_loss=StopLossRequest(stop_price=stop_loss)
            )
            client.submit_order(order_data=order_data)
            action_text = f"🟢 MARKET BUY (DYNAMIC CAP: ${effective_cap:,.2f})"
            color_hex = 5763719
        except Exception as e:
            action_text = f"🔴 EQUITY REJECTED: {e}"
            color_hex = 15548997

        return {
            "title": f"Target Acquired (EQUITY HARD BRACKET)",
            "color": color_hex,
            "fields": {
                "Ticker": sym,
                "Action": action_text,
                "Quantity": int(qty),
                "Entry Price": f"${entry_price:,.2f}",
                "Hard Stop (1R)": f"${stop_loss:,.2f}",
                f"Take Profit ({rr}R)": f"${take_profit:,.2f}",
                "Trigger": f"Vol Anomaly | Cur: {bar.volume:,.0f} vs Avg: {avg_volume:,.0f}"
            }
        }
    return None
