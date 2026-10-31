import pandas as pd
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class Trade:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    direction: str  # "long" or "short"
    sl_price: float
    tp_price: float
    hit_sl: bool
    hit_tp: bool
    pnl: float


class Backtester:
    def __init__(self, data: pd.DataFrame, sl_distance: float, tp_distance: float):
        """
        :param data: DataFrame with columns ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        :param sl_distance: distance from entry price to stop loss (absolute price units)
        :param tp_distance: distance from entry price to take profit (absolute price units)
        """
        self.data = data.sort_values('timestamp').reset_index(drop=True)
        self.sl_distance = sl_distance
        self.tp_distance = tp_distance
        self.trades: List[Trade] = []

    def _generate_signal(self, idx: int) -> Optional[str]:
        """
        Simple placeholder strategy: go long if close > open, short otherwise.
        """
        row = self.data.loc[idx]
        if row['close'] > row['open']:
            return 'long'
        elif row['close'] < row['open']:
            return 'short'
        return None

    def _calculate_sl_tp(self, entry_price: float, direction: str) -> Tuple[float, float]:
        if direction == 'long':
            sl_price = entry_price - self.sl_distance
            tp_price = entry_price + self.tp_distance
        else:  # short
            sl_price = entry_price + self.sl_distance
            tp_price = entry_price - self.tp_distance
        return sl_price, tp_price

    def run(self):
        i = 0
        while i < len(self.data) - 1:
            signal = self._generate_signal(i)
            if signal is None:
                i += 1
                continue

            entry_row = self.data.loc[i]
            entry_price = entry_row['close']  # use close price of entry candle
            sl_price, tp_price = self._calculate_sl_tp(entry_price, signal)

            # Scan forward to find first hit of SL or TP
            hit_sl = hit_tp = False
            exit_price = entry_price
            exit_time = entry_row['timestamp']
            for j in range(i + 1, len(self.data)):
                future_row = self.data.loc[j]
                high = future_row['high']
                low = future_row['low']

                if signal == 'long':
                    if low <= sl_price:
                        hit_sl = True
                        exit_price = sl_price
                        exit_time = future_row['timestamp']
                        break
                    if high >= tp_price:
                        hit_tp = True
                        exit_price = tp_price
                        exit_time = future_row['timestamp']
                        break
                else:  # short
                    if high >= sl_price:
                        hit_sl = True
                        exit_price = sl_price
                        exit_time = future_row['timestamp']
                        break
                    if low <= tp_price:
                        hit_tp = True
                        exit_price = tp_price
                        exit_time = future_row['timestamp']
                        break

            pnl = (exit_price - entry_price) if signal == 'long' else (entry_price - exit_price)
            trade = Trade(
                entry_time=entry_row['timestamp'],
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=exit_price,
                direction=signal,
                sl_price=sl_price,
                tp_price=tp_price,
                hit_sl=hit_sl,
                hit_tp=hit_tp,
                pnl=pnl
            )
            self.trades.append(trade)

            # Skip to the candle after the exit to avoid overlapping trades
            i = self.data.index[self.data['timestamp'] == exit_time][0] + 1

    def get_results(self) -> pd.DataFrame:
        return pd.DataFrame([t.__dict__ for t in self.trades])


# Example usage (commented out – remove comments to run):
# if __name__ == "__main__":
#     df = pd.read_csv("candles.csv", parse_dates=['timestamp'])
#     bt = Backtester(df, sl_distance=0.5, tp_distance=1.0)
#     bt.run()
#     results = bt.get_results()
#     print(results)