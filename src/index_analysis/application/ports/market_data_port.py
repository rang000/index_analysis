from __future__ import annotations

from typing import Protocol

import pandas as pd


class MarketDataPort(Protocol):
    def load_daily_prices(
        self,
        ticker: str,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        ...
