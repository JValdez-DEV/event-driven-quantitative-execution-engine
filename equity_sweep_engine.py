# /root/trade_hunter/equity_sweep_engine.py
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
            
        # --- 3. MATHEMATICAL TARGET MATRIX & FAIL-SAFE ---
        entry_price = float(bar.close)
        buffer_pct = float(params.get('stop_wick_buffer_pct', 0.005))
        rr = float(params.get('reward_risk', 2.0))
        
        stop_loss = round(entry_price * (1 - buffer_pct), 2)
        risk_per_share = entry_price - stop_loss
        take_profit = round(entry_price + (risk_per_share * rr), 2)
        
        target_risk_usd = 100.0
        max_position_size = 3000.0 # LIVE ACCOUNT CAP
        
        # Initial sizing attempt
        qty = round(target_risk_usd / risk_per_share, 0) if risk_per_share > 0 else 0
        
        # Override if position size is too massive
        total_investment = qty * entry_price
        if total_investment > max_position_size:
            qty = round(max_position_size / entry_price, 0)
            
        if qty <= 0: return None

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
            action_text = "🟢 MARKET BUY (CAPPED BRACKET OCO)"
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
                "Take Profit ({rr}R)": f"${take_profit:,.2f}",
                "Trigger": f"Vol Anomaly | Cur: {bar.volume:,.0f} vs Avg: {avg_volume:,.0f}"
            }
        }
    return None
