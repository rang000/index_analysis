from __future__ import annotations

import pandas as pd
import yfinance as yf


class YahooMarketDataClient:
    def load_daily_prices(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        data = yf.download(
            ticker,
            start=start,
            end=end,
            interval="1d",
            auto_adjust=False,
            progress=False,
        )
        if data.empty:
            return data

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        data = data.reset_index()
        data["Date"] = pd.to_datetime(data["Date"])
        return data[["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume"]]
