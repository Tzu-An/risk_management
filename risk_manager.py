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
    parser.add_argument("--keep-privacy", action="store_true", dest="keep_privacy", help="avoid returning data with privacy issue")
    args = parser.parse_args()
    return args


class RiskManager:
    def __init__(self, data_dir):
        self.data = self.load_data_to_dataframe(os.path.join(data_dir, "trade_record.csv"))
        self.configs = common.load_json(os.path.join(data_dir, "configs.json"))

    @staticmethod
    def load_data_to_dataframe(fname):
        df = pd.read_csv(fname)
        if df.shape[0] == 0:
            raise ValueError("No Transaction Data")

        df["net_earning"] = df["earning"] - df["cost"]
        df["entry_date"] = df[["entry_year", "entry_month", "entry_day"]].apply(
            lambda row: common.parse_date(f"{row.entry_year}/{row.entry_month:0>2}/{row.entry_day:0>2}"),
            axis=1
        )
        df["close_date"] = df[["close_year", "close_month", "close_day"]].apply(
            lambda row: common.parse_date(f"{row.close_year}/{row.close_month:0>2}/{row.close_day:0>2}"),
            axis=1
        )
        df["holding_days"] = (df["close_date"] - df["entry_date"]).apply(lambda dur: dur.days + 1)
        return df[["entry_date", "close_date", "holding_days", "net_earning", "invest"]]

    @staticmethod
    def select_data_in_drange(data, start_date, end_date):
        start = common.parse_date(start_date)
        end = common.parse_date(end_date)
        selected = data[(data.entry_date >= start) & (data.close_date <= end)]
        selected.index = range(selected.shape[0])
        return selected

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

    def extract_gross_numbers(self, selected_data):
        ret = dict()
        ret["Number of the Trades"] = selected_data.shape[0]
        ret["Amount of the Transactions"] = sum(selected_data["invest"])
        ret["Maximum Invest"] = max(selected_data["invest"])
        if ret["Number of the Trades"] > 0:
            ret["Average Invest"] = ret["Amount of the Transactions"] / ret["Number of the Trades"]
        else:
            ret["Average Invest"] = 0

        pl_array = selected_data["net_earning"].to_list()
        ret["Net Profit"] = sum(pl_array)
        ret["Max Accumulated Profit"] = self.extract_max_accum_profit(pl_array)
        ret["Max Drawdown"], ret["n_span"] = self.extract_max_accum_loss(pl_array)
        ret["Max Loss"] = - min(min(pl_array), 0)
        ret["Max Profit"] = max(max(pl_array), 0)
        ret["Average Holding Days"] = selected_data["holding_days"].mean()
        ret["Max Holding Days"] = selected_data["holding_days"].max()
        return ret

    def extract_common_ratios(self, selected_data, gross_numbers):
        ret = dict()
        wins = (selected_data["net_earning"] > 0).tolist()
        loses = (selected_data["net_earning"] < 0).tolist()

        if sum(loses) > 0:
            ret["Win Ratio"] = float(sum(wins) / selected_data.shape[0])
            ret["Profit Factor"] = abs(sum(selected_data["net_earning"][wins]) / sum(selected_data["net_earning"][loses]))
            ret["Profit Loss Ratio"] = abs(selected_data["net_earning"][wins].mean() / selected_data["net_earning"][loses].mean())
        else:
            ret["Win Ratio"] = float("inf") if sum(wins) > 0 else float("nan")
            ret["Profit Factor"] = float("inf") if sum(selected_data["net_earning"][wins]) > 0 else float("nan")
            ret["Profit Loss Ratio"] = float("inf") if sum(selected_data["net_earning"][wins]) > 0 else float("nan")

        ret["ROA"] = gross_numbers["Net Profit"] / self.configs["capital"]
        ret["ROI"] = gross_numbers["Net Profit"] / gross_numbers["Maximum Invest"]
        return ret

    def extract_udf_ratios(self, selected_data, gross_numbers):
        ret = dict()
        if gross_numbers["Net Profit"] != 0:
            ret["Return on the Average Investment"] = gross_numbers["Net Profit"] / gross_numbers["Average Invest"]
            ret["Return on Trades"] = gross_numbers["Net Profit"] / gross_numbers["Amount of the Transactions"]
        else:
            ret["Return on the Average Investment"] = 0
            ret["Return on Trades"] = 0

        n_span = gross_numbers.pop("n_span")
        if n_span is None:
            avg_invest_during_losing = 1 # for computation convenience
        elif n_span[0] == n_span[1]:
            avg_invest_during_losing = selected_data.loc[n_span[0], "invest"]
        else:
            avg_invest_during_losing = selected_data.loc[n_span[0]: n_span[1], "invest"].mean()

        potential_max_loss_ratio = gross_numbers["Max Drawdown"] / avg_invest_during_losing

        if potential_max_loss_ratio == 0:
            ret["Allowed Investing Capital"] = self.configs["capital"]
        else:
            ret["Allowed Investing Capital"] = int(self.configs["capital"] * self.configs["risk_taking_ratio"] / potential_max_loss_ratio)

        ret["Risk-Invest Ratio"] = potential_max_loss_ratio
        ret["Profit-Risk Ratio"] = float(gross_numbers["Net Profit"] / gross_numbers["Max Drawdown"]) if gross_numbers["Max Drawdown"] != 0 else float("inf")
        ret["Overall Risk-Invest Ratio"] = float(gross_numbers["Max Drawdown"] / gross_numbers["Average Invest"]) if gross_numbers["Average Invest"] > 0 else float("inf")
        ret["Max Drawdown Percentage"] = gross_numbers["Max Drawdown"] / self.configs["capital"]
        return ret

    def extract_metrics(self, selected_data):
        gross_numbers = self.extract_gross_numbers(selected_data)
        common_ratios = self.extract_common_ratios(selected_data, gross_numbers)
        udf_ratios = self.extract_udf_ratios(selected_data, gross_numbers)
        ret = {
            "Gross Numbers": gross_numbers,
            "Common Ratios": common_ratios,
            "User Defined Ratios": udf_ratios,
            "Real Date Range": (
                common.form_date_string(selected_data["entry_date"].min()),
                common.form_date_string(selected_data["close_date"].max())
                ),
            "Expecting ROA": udf_ratios["Allowed Investing Capital"] * common_ratios["ROI"] / self.configs["capital"]
        }
        return ret

    def format_metrics(self, metrics, keep_privacy):
        metrics["Common Ratios"]["ROI"] = common.format_perc_string(metrics["Common Ratios"]["ROI"])
        metrics["Common Ratios"]["ROA"] = common.format_perc_string(metrics["Common Ratios"]["ROA"])
        metrics["Common Ratios"]["Win Ratio"] = common.format_perc_string(metrics["Common Ratios"]["Win Ratio"])
        metrics["User Defined Ratios"]["Return on the Average Investment"] = common.format_perc_string(metrics["User Defined Ratios"]["Return on the Average Investment"])
        metrics["User Defined Ratios"]["Risk-Invest Ratio"] = common.format_perc_string(metrics["User Defined Ratios"]["Risk-Invest Ratio"])
        metrics["User Defined Ratios"]["Overall Risk-Invest Ratio"] = common.format_perc_string(metrics["User Defined Ratios"]["Overall Risk-Invest Ratio"])
        metrics["User Defined Ratios"]["Return on Trades"] = common.format_perc_string(metrics["User Defined Ratios"]["Return on Trades"])
        metrics["User Defined Ratios"]["Max Drawdown Percentage"] = common.format_perc_string(metrics["User Defined Ratios"]["Max Drawdown Percentage"])
        metrics["Expecting ROA"] = common.format_perc_string(metrics["Expecting ROA"])

        if keep_privacy:
            ret = {
                "Profit-Risk Ratio": metrics["User Defined Ratios"]["Profit-Risk Ratio"],
                "Risk-Invest Ratio": metrics["User Defined Ratios"]["Risk-Invest Ratio"],
                "Overall Risk-Invest Ratio": metrics["User Defined Ratios"]["Overall Risk-Invest Ratio"],
                "Win Ratio": metrics["Common Ratios"]["Win Ratio"],
                "ROI": metrics["Common Ratios"]["ROI"],
                "Expecting ROA": metrics["Expecting ROA"],
                "Return on Trades": metrics["User Defined Ratios"]["Return on Trades"],
                "Max Drawdown Percentage": metrics["User Defined Ratios"]["Max Drawdown Percentage"],
                "Profit Factor": metrics["Common Ratios"]["Profit Factor"],
                "Profit Loss Ratio": metrics["Common Ratios"]["Profit Loss Ratio"],
                "Max Holding Days": metrics["Gross Numbers"]["Max Holding Days"],
                "Average Holding Days": metrics["Gross Numbers"]["Average Holding Days"]
            }
            return ret
        return metrics

    def query(self, start_date, end_date, keep_privacy):
        selected_data = self.select_data_in_drange(self.data, start_date, end_date)
        if selected_data.shape[0] == 0:
            raise ValueError(f"No Transaction Data in date range {start_date} - {end_date}")
        metrics = self.extract_metrics(selected_data)
        metrics = self.format_metrics(metrics, keep_privacy)
        common.show_result(metrics, title="Metrics")

if __name__ == "__main__":
    args = get_args()
    agent = RiskManager(data_dir=args.data_dir)
    agent.query(args.start_date, args.end_date, args.keep_privacy)
