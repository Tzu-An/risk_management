"""
Manage risk based on the trading record analysis
"""
import os
import argparse
import pandas as pd

import common

def get_args():
    parser = argparse.ArgumentParser("Trade record analysis.")
    parser.add_argument("--dir", dest="data_dir", default="./test_data")
    parser.add_argument("-s", dest="start_date", required=True, help="Start date in YYYY/MM/DD")
    parser.add_argument("-e", dest="end_date", required=True, help="End date in YYYY/MM/DD")
    args = parser.parse_args()
    return args

class RiskManager:
    def __init__(self, data_dir):
        self.data = self.load_data_to_dataframe(os.path.join(data_dir, "trade_record.csv"))
        self.configs = common.load_json(os.path.join(data_dir, "configs.json"))

    @staticmethod
    def load_data_to_dataframe(fname):
        df = pd.read_csv(fname)
        df['net_earning'] = df['earning'] - df['cost']
        df['date'] = df[['year', 'month', 'day']].apply(lambda row: common.parse_date(f"{row.year}/{row.month:0>2}/{row.day:0>2}"), axis=1)
        return df[['date', 'net_earning', 'invest']]

    @staticmethod
    def extract_extremes(pl_array):
        ret_gain, ret_loss = 0, 0
        for pl in pl_array:
            if pl > ret_gain:
                ret_gain = pl
            elif pl < ret_loss:
                ret_loss = pl
        return -ret_loss, ret_gain

    @staticmethod
    def extract_max_accum_profit(pl_array):
        ret = 0
        prev = float("-inf")
        for idx, pl in enumerate(pl_array):
            if prev < 0:
                prev = pl
            else:
                prev += pl

            if pl > 0:
                ret = max(prev, ret)

        return ret

    @staticmethod
    def extract_max_accum_loss(pl_array):
        ret = 0
        prev = float("inf")
        start, span = 0, None
        for idx, pl in enumerate(pl_array):
            if prev > 0:
                prev = pl
                start = idx
            else:
                prev += pl

            if pl < 0:
                if prev < ret:
                    span = (start, idx)
                    ret = prev

        return -ret, span

    def extract_metrics(self, start, end):
        selected = self.data[(self.data.date >= start) & (self.data.date <= end)]
        num_transactions = max(selected.shape[0], 1)
        earliest_datelatest_date = selected['date'].min(), selected['date'].max()
        pl_array = selected['net_earning'].to_list()
        trade_volume = sum(selected['invest'])
        maximum_invest = max(selected['invest'])
        avg_invest = trade_volume / num_transactions
        profit_loss = sum(pl_array)

        max_accum_profit = self.extract_max_accum_profit(pl_array)
        max_accum_loss, n_span = self.extract_max_accum_loss(pl_array)
        max_loss, max_profit = self.extract_extremes(pl_array)

        div = 1 if max_accum_loss == 0 else max_accum_loss
        avg_invest_during_losing = selected.loc[n_span[0]: n_span[1], 'invest'].mean()
        roi = profit_loss / avg_invest
        rot = profit_loss / trade_volume

        ret = {
            "Allow Investment Volume": int(
                self.configs['capital'] *\
                self.configs['risk_taking_ratio'] *\
                avg_invest_during_losing / div
            ),
            "Average Invest": avg_invest,
            "P&L": profit_loss,
            "Profit-Risk ratio": profit_loss / div,
            "Risk-Invest Ratio": max_accum_loss / avg_invest_during_losing,
            "Overall Risk-Invest Ratio": max_accum_loss / avg_invest,
            "ROI": f"{roi*100:.2f}%",
            "ROT": f"{rot*100:.2f}%",
            "_details": {
                "ROI": roi,
                "ROT": rot,
                "Max Accumulated Loss": max_accum_loss,
                "Max Accumulated Profit": max_accum_profit,
                "Max Single Loss": max_loss,
                "Max Single Profit": max_profit,
                "Trade Volume": trade_volume,
                "Maximum Invest": maximum_invest,
                "Real Date Range": (
                    common.form_date_string(selected['date'].min()),
                    common.form_date_string(selected['date'].max())
                )
            },
        }
        return ret

    def query(self, start_date, end_date):
        start = common.parse_date(start_date)
        end = common.parse_date(end_date)
        metrics = self.extract_metrics(start, end)
        common.show_result(metrics, title="Metrics")

if __name__ == '__main__':
    args = get_args()
    agent = RiskManager(data_dir=args.data_dir)
    agent.query(args.start_date, args.end_date)
