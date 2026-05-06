from __future__ import annotations

from typing import Protocol

import pandas as pd


class OptionChainPort(Protocol):
    def load_option_chain(
        self,
        option_ticker: str,
        max_expiries: int,
    ) -> tuple[pd.DataFrame, float]:
        ...
