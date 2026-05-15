import json

class RiskWarden:
    def __init__(self, portfolio_balance):
        self.balance = portfolio_balance
        self.max_risk_pct = 0.02  # 2% of total equity
        self.stop_loss_pct = 0.01 # 1% below entry
        self.take_profit_pct = 0.03 # 3% above entry (1:3 R:R)

    def calculate_position(self, entry_price):
        """
        Calculates position size strictly based on the 2% max loss rule.
        """
        # 1. Calculate max allowable loss in USD
        capital_at_risk = self.balance * self.max_risk_pct
        
        # 2. Calculate exact SL and TP prices
        sl_price = entry_price * (1 - self.stop_loss_pct)
        tp_price = entry_price * (1 + self.take_profit_pct)
        
        # 3. Calculate position size
        # Risk per 1 full BTC = Entry Price - Stop Loss Price
        risk_per_btc = entry_price - sl_price
        
        # How many BTC can we buy so that if it drops to SL, we only lose exactly $20?
        position_size = capital_at_risk / risk_per_btc
        
        total_trade_cost = position_size * entry_price

        return {
            "entry_price": entry_price,
            "position_size": position_size,
            "sl_price": sl_price,
            "tp_price": tp_price,
            "capital_at_risk": capital_at_risk,
            "total_trade_cost": total_trade_cost
        }

class Executioner:
    @staticmethod
    def format_ccxt_oco_payload(symbol, trade_params):
        """
        Formats the dictionary payload for ccxt.create_order() 
        using unified OCO parameters.
        """
        payload = {
            "symbol": symbol,
            "type": "limit",
            "side": "buy",
            "amount": round(trade_params["position_size"], 8),
            "price": round(trade_params["entry_price"], 2),
            "params": {
                "stopLossPrice": round(trade_params["sl_price"], 2),
                "takeProfitPrice": round(trade_params["tp_price"], 2),
                # Some exchanges require a specific flag for OCO functionality via ccxt
                "ocoOrder": True 
            }
        }
        return payload

if __name__ == "__main__":
    # --- 1. MOCK ENVIRONMENT SETUP ---
    MOCK_BALANCE = 1000.00
    MOCK_ENTRY_PRICE = 82000.00
    SYMBOL = "BTC/USDT"

    print(f"\n\033[94m[SYSTEM ALERT] Signal Received from Analyst: TRADE AUTHORIZED\033[0m")
    print("-" * 50)
    
    # --- 2. RISK WARDEN PROCESSING ---
    warden = RiskWarden(portfolio_balance=MOCK_BALANCE)
    trade_data = warden.calculate_position(entry_price=MOCK_ENTRY_PRICE)
    
    print("\033[95m[ RISK WARDEN: MATHEMATICAL CLEARANCE ]\033[0m")
    print(f"Total Portfolio Equity: ${MOCK_BALANCE:,.2f}")
    print(f"Max Capital at Risk:    ${trade_data['capital_at_risk']:,.2f} (2%)")
    print(f"Entry Price:            ${trade_data['entry_price']:,.2f}")
    print(f"Stop-Loss (1% drop):    ${trade_data['sl_price']:,.2f}")
    print(f"Take-Profit (3% rise):  ${trade_data['tp_price']:,.2f}")
    print(f"Authorized Size (BTC):  {trade_data['position_size']:.8f} BTC")
    
    # Note on margin: Since $20 is 2% of $1000, and the SL is 1%, 
    # the total cost of the position will actually be $2000. 
    # This automatically implies a 2x margin requirement.
    if trade_data['total_trade_cost'] > MOCK_BALANCE:
        margin_required = trade_data['total_trade_cost'] / MOCK_BALANCE
        print(f"\n\033[93m* WARDEN NOTE: Total position cost is ${trade_data['total_trade_cost']:,.2f}. "
              f"This requires ~{margin_required:.1f}x margin execution.\033[0m")

    print("-" * 50)

    # --- 3. EXECUTIONER PROCESSING ---
    print("\033[91m[ EXECUTIONER: CCXT PAYLOAD GENERATED (MOCK MODE) ]\033[0m")
    ccxt_payload = Executioner.format_ccxt_oco_payload(SYMBOL, trade_data)
    
    # Print the exact dictionary that would be passed to exchange.create_order(**ccxt_payload)
    print(json.dumps(ccxt_payload, indent=4))
    print("-" * 50)
