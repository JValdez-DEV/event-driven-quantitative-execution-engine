import os
import logging
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta
from alpaca_trade_api.rest import REST, TimeFrame
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(message)s')
load_dotenv()

class VelocityBacktester:
    def __init__(self):
        # Maps exact keys used by your Live Engine
        api_key = os.getenv('ALPACA_API_KEY')
        api_secret = os.getenv('ALPACA_API_SECRET')
        base_url = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
        
        if not api_key or not api_secret:
            logging.error("[CRITICAL] ALPACA_API_KEY or ALPACA_API_SECRET missing from .env")
            exit(1)
            
        self.api = REST(api_key, api_secret, base_url, api_version='v2')
        self.capital_baseline = 10000.0
        self.risk_pct = 0.01
        self.reward_mult = 4.0

    def fetch_historical_1m(self, symbol: str, days_back: int) -> pd.DataFrame:
        end = datetime.now()
        start = end - timedelta(days=days_back)
        start_str = start.strftime('%Y-%m-%d')
        end_str = end.strftime('%Y-%m-%d')
        
        try:
            if 'USD' in symbol:
                df = self.api.get_crypto_bars(symbol, TimeFrame.Minute, start_str, end_str).df
            else:
                df = self.api.get_bars(symbol, TimeFrame.Minute, start_str, end_str).df
                
            if df.empty: return df
            if isinstance(df.index, pd.MultiIndex):
                df = df.xs(symbol, level=1)
                
            df.index = pd.to_datetime(df.index)
            return df
        except Exception as e:
            logging.error(f"[!] Data Fetch Error for {symbol}: {e}")
            return pd.DataFrame()

    def generate_5m_signals(self, df_1m: pd.DataFrame) -> pd.DataFrame:
        df_5m = df_1m.resample('5min').agg({
            'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
        }).dropna()
        
        if len(df_5m) < 200: return pd.DataFrame()

        df_5m['SMA200'] = ta.sma(df_5m['close'], length=200)
        df_5m['RSI'] = ta.rsi(df_5m['close'], length=14)
        df_5m['Vol_MA20'] = ta.sma(df_5m['volume'], length=20)
        df_5m['Recent_High'] = df_5m['high'].rolling(window=10).max().shift(1)
        df_5m['ChoCH'] = df_5m['close'] > df_5m['Recent_High']
        
        df_5m = df_5m.dropna(subset=['SMA200'])
        df_5m['Trend_Up'] = df_5m['close'] > df_5m['SMA200']

        df_5m['c1_High'] = df_5m['high'].shift(2)
        df_5m['c2_Low'] = df_5m['low'].shift(1)
        df_5m['FVG_Bullish'] = df_5m['low'] > df_5m['c1_High']
        df_5m['FVG_Mid'] = (df_5m['low'] + df_5m['c1_High']) / 2
        df_5m['FVG_Stop'] = df_5m['c2_Low']

        score_vol = (df_5m['volume'] > df_5m['Vol_MA20']).astype(int) * 30
        score_rsi = ((df_5m['RSI'] >= 40) & (df_5m['RSI'] <= 70)).astype(int) * 30
        df_5m['Score'] = score_vol + score_rsi

        df_5m['Signal'] = df_5m['Trend_Up'] & df_5m['ChoCH'] & df_5m['FVG_Bullish'] & (df_5m['Score'] >= 60)
        return df_5m

    def run_simulation(self, df_1m: pd.DataFrame, df_5m: pd.DataFrame) -> dict:
        capital = self.capital_baseline
        trades = []
        in_trade = False
        
        entry_price = sl_price = tp_price = initial_risk = qty = 0.0
        risk_eliminated = False

        df_1m['5m_time'] = df_1m.index.floor('5min')

        for idx, row in df_1m.iterrows():
            current_5m_period = row['5m_time']
            last_closed_5m = current_5m_period - timedelta(minutes=5)

            if in_trade:
                if not risk_eliminated and row['high'] >= (entry_price + initial_risk):
                    risk_eliminated = True
                    sl_price = entry_price 

                if row['low'] <= sl_price:
                    pnl = (sl_price - entry_price) * qty
                    capital += pnl
                    trades.append({'pnl': pnl, 'win': 1 if pnl > 0 else 0, 'be': 1 if pnl == 0 else 0})
                    in_trade = False
                elif row['high'] >= tp_price:
                    pnl = (tp_price - entry_price) * qty
                    capital += pnl
                    trades.append({'pnl': pnl, 'win': 1, 'be': 0})
                    in_trade = False

            if not in_trade and last_closed_5m in df_5m.index:
                signal_row = df_5m.loc[last_closed_5m]
                
                if signal_row['Signal']:
                    if row['low'] <= signal_row['FVG_Mid'] and row['close'] >= signal_row['c1_High']:
                        in_trade = True
                        entry_price = row['close']
                        sl_price = signal_row['FVG_Stop']
                        
                        if sl_price >= entry_price:
                            sl_price = entry_price * 0.99
                            
                        initial_risk = entry_price - sl_price
                        qty = (capital * self.risk_pct) / initial_risk
                        tp_price = entry_price + (initial_risk * self.reward_mult)
                        risk_eliminated = False

        total_trades = len(trades)
        wins = sum(1 for t in trades if t['win'] == 1 and t['be'] == 0)
        bes = sum(1 for t in trades if t['be'] == 1)
        losses = total_trades - wins - bes
        
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0

        return {
            'trades': total_trades,
            'wins': wins,
            'bes': bes,
            'losses': losses,
            'win_rate': win_rate,
            'total_pnl': capital - self.capital_baseline
        }

    def batch_audit(self, symbols: list, days_back: int = 14):
        logging.info("="*80)
        logging.info("V3.6 VELOCITY ARCHITECTURE - 1m DATA PRECISION BACKTEST")
        logging.info("="*80)
        logging.info(f"{'SYMBOL':<10} | {'TRADES':<8} | {'W/BE/L':<12} | {'WIN RATE':<10} | {'NET PNL'}")
        logging.info("-" * 80)

        for symbol in symbols:
            df_1m = self.fetch_historical_1m(symbol, days_back)
            if df_1m.empty: continue
            
            df_5m = self.generate_5m_signals(df_1m)
            if df_5m.empty: continue
            
            res = self.run_simulation(df_1m, df_5m)
            
            wbel = f"{res['wins']}/{res['bes']}/{res['losses']}"
            logging.info(f"{symbol:<10} | {res['trades']:<8} | {wbel:<12} | {res['win_rate']:>6.2f}%    | ${res['total_pnl']:>.2f}")

if __name__ == "__main__":
    tester = VelocityBacktester()
    target_symbols = ['NVDA', 'TSLA', 'BTC/USD', 'ETH/USD']
    tester.batch_audit(target_symbols, days_back=14)
