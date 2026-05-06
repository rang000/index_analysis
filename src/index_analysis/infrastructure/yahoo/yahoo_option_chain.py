from __future__ import annotations

import pandas as pd
import requests
import yfinance as yf


class YahooOptionChainClient:
    def load_option_chain(
        self,
        option_ticker: str,
        max_expiries: int,
    ) -> tuple[pd.DataFrame, float]:
        try:
            data, spot = self._load_option_chain_yfinance(option_ticker, max_expiries)
        except Exception:
            data, spot = pd.DataFrame(), float("nan")

        if data.empty or pd.isna(spot):
            data, spot = self._load_option_chain_yahoo_api(option_ticker, max_expiries)

        if data.empty:
            return pd.DataFrame(), spot

        data = data[
            [
                "contractSymbol",
                "optionType",
                "expiry",
                "daysToExpiry",
                "strike",
                "openInterest",
                "impliedVolatility",
            ]
        ].copy()
        data["openInterest"] = pd.to_numeric(data["openInterest"], errors="coerce").fillna(0)
        data["impliedVolatility"] = pd.to_numeric(data["impliedVolatility"], errors="coerce")
        data["strike"] = pd.to_numeric(data["strike"], errors="coerce")
        data = data.dropna(subset=["strike", "impliedVolatility"])
        data = data[
            (data["openInterest"] > 0)
            & (data["impliedVolatility"] > 0)
            & (data["daysToExpiry"] > 0)
        ]
        return data, spot

    def _load_option_chain_yfinance(
        self,
        option_ticker: str,
        max_expiries: int,
    ) -> tuple[pd.DataFrame, float]:
        ticker = yf.Ticker(option_ticker)
        history = ticker.history(period="5d", auto_adjust=False)
        if history.empty:
            return pd.DataFrame(), float("nan")

        spot = float(history["Close"].dropna().iloc[-1])
        expiries = list(ticker.options[:max_expiries])
        frames = []
        now = pd.Timestamp.utcnow().tz_localize(None)

        for expiry in expiries:
            chain = ticker.option_chain(expiry)
            for option_type, frame in (("call", chain.calls), ("put", chain.puts)):
                if frame.empty:
                    continue
                option_data = frame.copy()
                option_data["optionType"] = option_type
                option_data["expiry"] = pd.to_datetime(expiry)
                option_data["daysToExpiry"] = (option_data["expiry"] - now).dt.total_seconds() / 86400
                frames.append(option_data)

        if not frames:
            return pd.DataFrame(), spot

        return pd.concat(frames, ignore_index=True), spot

    def _load_option_chain_yahoo_api(
        self,
        option_ticker: str,
        max_expiries: int,
    ) -> tuple[pd.DataFrame, float]:
        base_url = f"https://query2.finance.yahoo.com/v7/finance/options/{option_ticker}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(base_url, headers=headers, timeout=15)
        response.raise_for_status()
        root = response.json().get("optionChain", {}).get("result", [])
        if not root:
            return pd.DataFrame(), float("nan")

        first_result = root[0]
        quote = first_result.get("quote", {})
        spot = quote.get("regularMarketPrice") or quote.get("postMarketPrice") or float("nan")
        expiries = first_result.get("expirationDates", [])[:max_expiries]
        frames = []

        for expiry_ts in expiries:
            chain_response = requests.get(f"{base_url}?date={expiry_ts}", headers=headers, timeout=15)
            chain_response.raise_for_status()
            chain_root = chain_response.json().get("optionChain", {}).get("result", [])
            if not chain_root:
                continue
            options = chain_root[0].get("options", [])
            if not options:
                continue
            option_set = options[0]
            expiry_date = pd.to_datetime(expiry_ts, unit="s")
            for option_type, key in (("call", "calls"), ("put", "puts")):
                frame = pd.DataFrame(option_set.get(key, []))
                if frame.empty:
                    continue
                frame["optionType"] = option_type
                frame["expiry"] = expiry_date
                frame["daysToExpiry"] = (
                    expiry_date - pd.Timestamp.utcnow().tz_localize(None)
                ).total_seconds() / 86400
                frames.append(frame)

        if not frames:
            return pd.DataFrame(), float(spot)

        return pd.concat(frames, ignore_index=True), float(spot)
