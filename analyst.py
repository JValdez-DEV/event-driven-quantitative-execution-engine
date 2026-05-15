import pandas as pd
import numpy as np
from datetime import datetime

class AnalystAgent:
    def __init__(self, exchange, symbol='BTC/USDT'):
        """
        Initializes the Analyst Agent.
        Requires the active ccxt exchange instance passed from the Sentinel.
        """
        self.exchange = exchange
        self.symbol = symbol

    def _calculate_rsi(self, df, period=14):
        """
        Calculates the 14-period RSI using Pandas.
        Uses the Wilder's smoothing method (standard for crypto).
        """
        delta = df['close'].diff()
        
        # Make two series: one for lower closes and one for higher closes
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        
        # Calculate the Exponential Moving Average (Wilder's Smoothing)
        ema_up = up.ewm(com=period - 1, adjust=False).mean()
        ema_down = down.ewm(com=period - 1, adjust=False).mean()
        
        rs = ema_up / ema_down
        df['RSI'] = 100 - (100 / (1 + rs))
        return df

    def analyze_target(self, df, current_price):
        """
        Executes the 100-Point Scoring Engine on the flagged asset.
        """
        print(f"\n[{datetime.now()}] Analyst Agent: Evaluating {self.symbol} at ${current_price:.2f}")
        total_score = 0
        
        # ---------------------------------------------------------
        # 1. Volume Confirmation (+30 Points)
        # ---------------------------------------------------------
        df['MA_Volume_20'] = df['volume'].rolling(window=20).mean()
        
        current_vol = df['volume'].iloc[-1]
        avg_vol = df['MA_Volume_20'].iloc[-1]
        
        if current_vol > avg_vol:
            total_score += 30
            print(f" [+] Volume Check: PASS (Current: {current_vol:.2f} > Avg: {avg_vol:.2f}) -> +30 Pts")
        else:
            print(f" [-] Volume Check: FAIL (Current: {current_vol:.2f} <= Avg: {avg_vol:.2f}) -> 0 Pts")

        # ---------------------------------------------------------
        # 2. RSI Health (+30 Points)
        # ---------------------------------------------------------
        df = self._calculate_rsi(df, period=14)
        current_rsi = df['RSI'].iloc[-1]
        
        if 40 <= current_rsi <= 60:
            total_score += 30
            print(f" [+] RSI Check: PASS (Value: {current_rsi:.2f}) -> +30 Pts")
        else:
            print(f" [-] RSI Check: FAIL (Value: {current_rsi:.2f} is outside 40-60 range) -> 0 Pts")

        # ---------------------------------------------------------
        # 3. Order Book Depth (+40 Points)
        # ---------------------------------------------------------
        try:
            # Fetch the order book. Limit 100 is usually enough for a 1% spread on high liquidity pairs.
            order_book = self.exchange.fetch_order_book(self.symbol, limit=100)
            bids = order_book['bids']  
            asks = order_book['asks']  

            lower_bound = current_price * 0.99
            upper_bound = current_price * 1.01

            # Iterate using index positions to avoid unpacking errors from unexpected list lengths
            bid_volume_1pct = 0
            for bid in bids:
                price = bid[0]
                size = bid[1]
                if price >= lower_bound:
                    bid_volume_1pct += size

            ask_volume_1pct = 0
            for ask in asks:
                price = ask[0]
                size = ask[1]
                if price <= upper_bound:
                    ask_volume_1pct += size

            if bid_volume_1pct > ask_volume_1pct:
                total_score += 40
                print(f" [+] Order Book Check: PASS (Bids: {bid_volume_1pct:.2f} > Asks: {ask_volume_1pct:.2f}) -> +40 Pts")
            else:
                print(f" [-] Order Book Check: FAIL (Bids: {bid_volume_1pct:.2f} <= Asks: {ask_volume_1pct:.2f}) -> 0 Pts")
                
        except Exception as e:
            print(f" [-] Order Book Error: {e} -> 0 Pts")

        # ---------------------------------------------------------
        # Execution Rules & Threshold Logic
        # ---------------------------------------------------------
        print("-" * 45)
        if total_score > 75:
            # ANSI \033[92m is Green text
            print(f"\033[92m[TRADE AUTHORIZED: Score {total_score}/100]\033[0m")
            print(">>> Passing execution parameters to the Risk Warden... <<<")
            return True, total_score
        else:
            # ANSI \033[93m is Yellow text
            print(f"\033[93m[TRADE REJECTED: Insufficient Confidence (Score {total_score}/100)]\033[0m")
            print(">>> Returning control to Sentinel for continued scanning... <<<")
            return False, total_score

# =====================================================================
# Handoff Implementation Example (How to link it to the Sentinel)
# =====================================================================
if __name__ == "__main__":
    import ccxt
    
    # Mocking the ccxt instance (Kraken) from the Sentinel
    exchange = ccxt.kraken({'enableRateLimit': True})
    
    # Initialize the Analyst Agent, passing the exchange instance
    analyst = AnalystAgent(exchange, symbol='BTC/USDT')
    
    # -----------------------------------------------------------------
    # MOCK SCENARIO: Sentinel has just triggered the 0.1% MA20 threshold.
    # -----------------------------------------------------------------
    print("Sentinel Triggered! Fetching data for Analyst testing...")
    
    # Fetching real data to test the logic
    ohlcv = exchange.fetch_ohlcv('BTC/USDT', timeframe='5m', limit=100)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    current_price = df['close'].iloc[-1]
    
    # Trigger the Analyst
    trade_authorized, final_score = analyst.analyze_target(df, current_price)
