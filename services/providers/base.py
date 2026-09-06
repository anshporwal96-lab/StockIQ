"""
services/providers/base.py
==========================
The CONTRACT that every data source must follow.

WHY BOTHER WITH THIS?
---------------------
Market-data APIs come and go. If the rest of the app called one specific API
directly, replacing it would mean editing dozens of files. Instead every source
is a class that implements the same seven methods below. Swapping sources is
then a single line in .env:

    DATA_PROVIDER=demo      ->  DemoProvider
    DATA_PROVIDER=yfinance  ->  YFinanceProvider

To add your own source (a broker API, an NSE data licence, a paid vendor):
  1. Copy demo_provider.py to my_provider.py
  2. Keep the method names and the returned dictionary keys identical
  3. Register it in services/providers/__init__.py

EVERY RETURNED DICTIONARY MUST INCLUDE THESE THREE KEYS
-------------------------------------------------------
    "source"  : human-readable name of where the data came from
    "as_of"   : ISO-8601 timestamp from the SOURCE. Never invent one.
                If the source does not give a timestamp, set it to None.
    "is_demo" : True only for made-up sample data. The UI shows a DEMO DATA
                badge whenever this is True, so a reader is never misled.

If a value genuinely is not available, return None for it. Do NOT substitute a
plausible-looking number - the UI is built to display "Data unavailable".
"""


class DataProviderError(Exception):
    """Raised when a provider cannot answer. Routes turn this into a friendly
    message plus an HTTP error code, never into fake data."""


class BaseProvider:
    """Abstract base class. Subclasses override every method."""

    name = "base"

    # ---- reference data ---------------------------------------------------
    def get_company_info(self, symbol):
        """Company name, exchange codes, sector, industry, business description."""
        raise NotImplementedError

    # ---- prices -----------------------------------------------------------
    def get_current_price(self, symbol):
        """Latest quote: price, change, day range, 52-week range, volume."""
        raise NotImplementedError

    def get_historical_prices(self, symbol, period="1Y"):
        """Daily candles. `period` is one of 1D 1W 1M 3M 6M 1Y 3Y 5Y.

        Returns {"candles": [{"date","open","high","low","close","volume"}, ...]}
        oldest first.
        """
        raise NotImplementedError

    # ---- fundamentals -----------------------------------------------------
    def get_financials(self, symbol):
        """Annual income statement, balance sheet and cash flow (oldest first)."""
        raise NotImplementedError

    def get_quarterly_results(self, symbol):
        """Recent quarterly results, oldest first."""
        raise NotImplementedError

    def get_shareholding(self, symbol):
        """Promoter / FII / DII / public holding by quarter, oldest first."""
        raise NotImplementedError

    # ---- news -------------------------------------------------------------
    def get_news(self, symbol, limit=12):
        """Recent headlines with source and date."""
        raise NotImplementedError

    # ---- market -----------------------------------------------------------
    def get_market_overview(self):
        """NIFTY 50 and SENSEX levels, plus gainers / losers / most active."""
        raise NotImplementedError


def empty_result(reason, source="unavailable"):
    """A standard "we could not get this" response.

    Used instead of raising when a single section is missing but the rest of
    the page should still render.
    """
    return {
        "available": False,
        "reason": reason,
        "source": source,
        "as_of": None,
        "is_demo": False,
    }
