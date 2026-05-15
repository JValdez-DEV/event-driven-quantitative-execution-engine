from backtesting import Backtest, Strategy
import pandas as pd
import pandas_ta as ta
import requests

# 1. Fetch Historical Data (Last 720 minutes/hours)
def get_hist_data(pair="XBTUSD", interval=60):
    url = f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval={interval}"
    response = requests.get(url).json()
    pair_key = list(response['result'].keys())[0]
    data = response['result'][pair_key]
    df = pd.DataFrame(data, columns=['Time', 'Open', 'High', 'Low', 'Close', 'VWAP', 'Volume', 'Count'])
    df['Time'] = pd.to_datetime(df['Time'], unit='s')
    df = df.set_index('Time')
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        df[col] = df[col].astype(float)
    return df

# 2. Define the RSI Strategy
class RsiStrategy(Strategy):
    def init(self):
        # Pre-calculate RSI using pandas_ta
        self.rsi = self.I(ta.rsi, pd.Series(self.data.Close), length=14)

    def next(self):
        # Entry Logic: RSI drops below 30
        if self.rsi[-1] < 30:
            # Entry price is current close, Stop-Loss is 2% below
            price = self.data.Close[-1]
            self.buy(sl=price * 0.98, tp=price * 1.06) # 1:3 Risk/Reward

# 3. Run the Backtest
data = get_hist_data()
bt = Backtest(data, RsiStrategy, cash=10000, commission=.002)
stats = bt.run()

print(stats)
# bt.plot() # Uncomment this if you have a desktop environment to see the chart
