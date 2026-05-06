from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from index_analysis.config.loader import load_settings
from index_analysis.infrastructure.yahoo.yahoo_market_data import YahooMarketDataClient
from index_analysis.infrastructure.yahoo.yahoo_option_chain import YahooOptionChainClient
from index_analysis.presentation.streamlit.app import main


if __name__ == "__main__":
    main(
        settings=load_settings(),
        market_data_client=YahooMarketDataClient(),
        option_chain_client=YahooOptionChainClient(),
    )
