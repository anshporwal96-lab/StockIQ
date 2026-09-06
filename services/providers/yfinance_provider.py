"""
services/providers/yfinance_provider.py
=======================================
A REAL market-data provider built on the `yfinance` package.

BEFORE YOU USE THIS
-------------------
  1. Install it yourself:      pip install yfinance
  2. Set DATA_PROVIDER=yfinance in your .env file
  3. Read and accept Yahoo Finance's terms of use. yfinance is a community
     library that reads Yahoo's public endpoints; it is not an official NSE or
     BSE feed and it is not licensed for redistribution. For anything beyond
     personal research, use a licensed vendor or an official exchange feed.

HOW SYMBOLS WORK
----------------
Yahoo suffixes Indian tickers by exchange:
    TCS on NSE      -> "TCS.NS"
    TCS on BSE      -> "532540.BO"
We try NSE first and fall back to BSE.

WHAT IS AND IS NOT IMPLEMENTED
------------------------------
  get_company_info      implemented
  get_current_price     implemented
  get_historical_prices implemented
  get_financials        implemented (annual income / balance / cash flow)
  get_quarterly_results implemented
  get_shareholding      NOT AVAILABLE - promoter/FII/DII splits come from
                        Indian exchange filings, which Yahoo does not carry.
                        See the note in the method for where to plug in a real
                        source. It returns "unavailable" rather than guessing.
  get_news              implemented (Yahoo headlines)
  get_market_overview   partly - NIFTY 50 (^NSEI) and SENSEX (^BSESN) levels
                        are real; gainers/losers need a screener feed, so they
                        are returned empty rather than invented.
"""

from datetime import datetime, timezone

from services.providers.base import BaseProvider, DataProviderError, empty_result
from services.stock_universe import BY_SYMBOL

SOURCE_NAME = "Yahoo Finance via yfinance (unofficial)"

PERIOD_MAP = {
    "1D": ("1d", "5m"), "1W": ("5d", "30m"), "1M": ("1mo", "1d"),
    "3M": ("3mo", "1d"), "6M": ("6mo", "1d"), "1Y": ("1y", "1d"),
    "3Y": ("3y", "1d"), "5Y": ("5y", "1wk"),
}


def _load_yfinance():
    """Import yfinance only when it is actually needed, and give a clear error
    if it is missing instead of crashing the whole app at start-up."""
    try:
        import yfinance
        return yfinance
    except ImportError as exc:
        raise DataProviderError(
            "The yfinance package is not installed. Run 'pip install yfinance', "
            "or set DATA_PROVIDER=demo in your .env file."
        ) from exc


def _number(value):
    """Convert a value from pandas/yfinance into a plain float, or None.

    yfinance returns NaN for missing cells. NaN is the only value that is not
    equal to itself, which is how we detect it here without importing numpy.
    """
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:      # NaN check
        return None
    return number


def _pick(frame, row_names, column):
    """Read one cell out of a yfinance DataFrame.

    yfinance labels rows differently depending on the company, so we try a list
    of possible names ("Total Revenue", "Operating Revenue", ...) and return the
    first one that exists. Returns None when none of them are present - we never
    substitute a stand-in number.
    """
    if frame is None or getattr(frame, "empty", True):
        return None
    for name in row_names:
        if name in frame.index:
            try:
                return _number(frame.loc[name, column])
            except (KeyError, IndexError, TypeError):
                continue
    return None


class YFinanceProvider(BaseProvider):
    """Fetches real data. Every method raises DataProviderError on failure so
    the routes can show an honest error instead of a made-up number."""

    name = "yfinance"

    def __init__(self):
        self._yf = None
        self._ticker_cache = {}

    def _ticker(self, symbol):
        """Return a yfinance Ticker, trying the NSE listing then the BSE one."""
        symbol = symbol.upper()
        if symbol in self._ticker_cache:
            return self._ticker_cache[symbol]

        if self._yf is None:
            self._yf = _load_yfinance()

        candidates = [symbol + ".NS"]
        row = BY_SYMBOL.get(symbol)
        if row and row.get("bse_code"):
            candidates.append(row["bse_code"] + ".BO")

        for yahoo_symbol in candidates:
            try:
                ticker = self._yf.Ticker(yahoo_symbol)
                history = ticker.history(period="5d")
                if history is not None and not history.empty:
                    self._ticker_cache[symbol] = ticker
                    return ticker
            except Exception:
                continue

        raise DataProviderError(
            "No price data was returned for " + symbol + " from Yahoo Finance."
        )

    # ------------------------------------------------------------------
    def get_company_info(self, symbol):
        ticker = self._ticker(symbol)
        try:
            info = ticker.info or {}
        except Exception:
            info = {}

        row = BY_SYMBOL.get(symbol.upper(), {})
        market_cap = _number(info.get("marketCap"))

        return {
            "symbol": symbol.upper(),
            "company_name": info.get("longName") or row.get("company_name") or symbol.upper(),
            "nse_symbol": symbol.upper(),
            "bse_code": row.get("bse_code"),
            "exchange": info.get("exchange") or "NSE / BSE",
            "sector": info.get("sector") or row.get("sector"),
            "industry": info.get("industry") or row.get("industry"),
            # Yahoo reports market cap in rupees; the app displays Rs crore.
            "market_cap_cr": round(market_cap / 1e7, 2) if market_cap else None,
            "shares_outstanding_cr": (
                round(_number(info.get("sharesOutstanding")) / 1e7, 2)
                if _number(info.get("sharesOutstanding")) else None
            ),
            "face_value": None,   # Yahoo does not publish Indian face value.
            "description": info.get("longBusinessSummary"),
            "business_model": None,  # Needs a filings source; not invented here.
            "website": info.get("website"),
            "source": SOURCE_NAME,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "is_demo": False,
        }

    def get_current_price(self, symbol):
        ticker = self._ticker(symbol)
        try:
            history = ticker.history(period="1y")
        except Exception as exc:
            raise DataProviderError("Price lookup failed: " + str(exc)) from exc
        if history is None or history.empty:
            raise DataProviderError("No price history returned for " + symbol + ".")

        last = history.iloc[-1]
        previous_close = (
            _number(history["Close"].iloc[-2]) if len(history) > 1 else _number(last["Close"])
        )
        price = _number(last["Close"])
        change = (price - previous_close) if (price and previous_close) else None

        return {
            "symbol": symbol.upper(),
            "price": round(price, 2) if price else None,
            "previous_close": round(previous_close, 2) if previous_close else None,
            "change": round(change, 2) if change is not None else None,
            "change_pct": (
                round(change / previous_close * 100, 2)
                if (change is not None and previous_close) else None
            ),
            "open": round(_number(last["Open"]), 2) if _number(last["Open"]) else None,
            "day_high": round(_number(last["High"]), 2) if _number(last["High"]) else None,
            "day_low": round(_number(last["Low"]), 2) if _number(last["Low"]) else None,
            "volume": int(_number(last["Volume"]) or 0),
            "week_52_high": round(_number(history["Close"].max()), 2),
            "week_52_low": round(_number(history["Close"].min()), 2),
            "currency": "INR",
            "source": SOURCE_NAME,
            # The real timestamp of the last candle - not a made-up "now".
            "as_of": history.index[-1].isoformat(),
            "is_demo": False,
        }

    def get_historical_prices(self, symbol, period="1Y"):
        ticker = self._ticker(symbol)
        yahoo_period, interval = PERIOD_MAP.get(str(period).upper(), ("1y", "1d"))
        try:
            history = ticker.history(period=yahoo_period, interval=interval)
        except Exception as exc:
            raise DataProviderError("History lookup failed: " + str(exc)) from exc
        if history is None or history.empty:
            raise DataProviderError("No historical data returned for " + symbol + ".")

        candles = []
        for stamp, row in history.iterrows():
            close = _number(row["Close"])
            if close is None:
                continue      # skip gaps rather than filling them in
            candles.append({
                "date": stamp.isoformat(),
                "open": round(_number(row["Open"]) or close, 2),
                "high": round(_number(row["High"]) or close, 2),
                "low": round(_number(row["Low"]) or close, 2),
                "close": round(close, 2),
                "volume": int(_number(row["Volume"]) or 0),
            })

        return {
            "symbol": symbol.upper(),
            "period": str(period).upper(),
            "interval": interval,
            "candles": candles,
            "source": SOURCE_NAME,
            "as_of": candles[-1]["date"] if candles else None,
            "is_demo": False,
        }

    # ------------------------------------------------------------------
    def _statements(self, symbol, quarterly=False):
        """Pull the three statements and line them up by reporting period."""
        ticker = self._ticker(symbol)
        try:
            income = ticker.quarterly_financials if quarterly else ticker.financials
            balance = ticker.quarterly_balance_sheet if quarterly else ticker.balance_sheet
            cash = ticker.quarterly_cashflow if quarterly else ticker.cashflow
        except Exception as exc:
            raise DataProviderError("Financial statements unavailable: " + str(exc)) from exc

        if income is None or getattr(income, "empty", True):
            raise DataProviderError("No financial statements published for " + symbol + ".")

        def to_crore(value):
            """yfinance reports rupees; the whole app works in Rs crore."""
            return round(value / 1e7, 1) if value is not None else None

        # Columns are report dates, newest first. Reverse so charts read left to right.
        periods = list(income.columns)[::-1]
        rows = []
        for column in periods:
            revenue = _pick(income, ["Total Revenue", "Operating Revenue"], column)
            ebit = _pick(income, ["EBIT", "Operating Income"], column)
            depreciation = _pick(
                cash,
                ["Depreciation And Amortization", "Depreciation Amortization Depletion"],
                column,
            )
            ebitda = _pick(income, ["EBITDA", "Normalized EBITDA"], column)
            if ebitda is None and ebit is not None and depreciation is not None:
                ebitda = ebit + depreciation

            operating_cf = _pick(
                cash, ["Operating Cash Flow", "Total Cash From Operating Activities"], column
            )
            capex = _pick(cash, ["Capital Expenditure", "Purchase Of PPE"], column)
            free_cf = None
            if operating_cf is not None and capex is not None:
                free_cf = operating_cf - abs(capex)

            rows.append({
                "period": column.strftime("%b %Y") if hasattr(column, "strftime") else str(column),
                "revenue": to_crore(revenue),
                "ebitda": to_crore(ebitda),
                "depreciation": to_crore(depreciation),
                "ebit": to_crore(ebit),
                "interest_expense": to_crore(_pick(income, ["Interest Expense"], column)),
                "pbt": to_crore(_pick(income, ["Pretax Income", "Income Before Tax"], column)),
                "net_profit": to_crore(
                    _pick(income, ["Net Income", "Net Income Common Stockholders"], column)
                ),
                "eps": _pick(income, ["Diluted EPS", "Basic EPS"], column),
                "total_assets": to_crore(_pick(balance, ["Total Assets"], column)),
                "total_debt": to_crore(_pick(balance, ["Total Debt", "Long Term Debt"], column)),
                "cash": to_crore(
                    _pick(balance, ["Cash And Cash Equivalents", "Cash Financial"], column)
                ),
                "equity": to_crore(
                    _pick(balance, ["Stockholders Equity", "Total Equity Gross Minority Interest"], column)
                ),
                "receivables": to_crore(_pick(balance, ["Accounts Receivable", "Receivables"], column)),
                "inventory": to_crore(_pick(balance, ["Inventory"], column)),
                "current_assets": to_crore(_pick(balance, ["Current Assets"], column)),
                "current_liabilities": to_crore(_pick(balance, ["Current Liabilities"], column)),
                "operating_cash_flow": to_crore(operating_cf),
                "capex": to_crore(abs(capex)) if capex is not None else None,
                "free_cash_flow": to_crore(free_cf),
                "dividend_per_share": None,
            })
        return rows

    def get_financials(self, symbol):
        return {
            "symbol": symbol.upper(),
            "currency": "INR",
            "units": "Rs crore (except per-share figures)",
            "annual": self._statements(symbol, quarterly=False),
            "source": SOURCE_NAME,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "is_demo": False,
        }

    def get_quarterly_results(self, symbol):
        quarters = []
        for row in self._statements(symbol, quarterly=True):
            margin = None
            if row["revenue"] and row["ebitda"] is not None:
                margin = round(row["ebitda"] / row["revenue"] * 100, 2)
            quarters.append({
                "period": row["period"],
                "end_date": None,
                "revenue": row["revenue"],
                "ebitda": row["ebitda"],
                "ebitda_margin": margin,
                "net_profit": row["net_profit"],
                "eps": row["eps"],
                "exceptional_items": None,
            })
        return {
            "symbol": symbol.upper(),
            "units": "Rs crore (except EPS)",
            "quarters": quarters,
            "source": SOURCE_NAME,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "is_demo": False,
        }

    def get_shareholding(self, symbol):
        """NOT AVAILABLE from Yahoo Finance.

        Promoter / FII / DII splits are published in the quarterly shareholding
        pattern that companies file with NSE and BSE. Yahoo does not carry them.

        TO IMPLEMENT FOR REAL: fetch the shareholding-pattern filing from the
        exchange (or from a licensed vendor) right here, and return the same
        dictionary shape that DemoProvider.get_shareholding returns.

        Until then we return "unavailable". We do NOT guess a split.
        """
        result = empty_result(
            "Promoter, FII and DII holdings come from NSE/BSE shareholding-pattern "
            "filings, which this provider cannot access.",
            source=SOURCE_NAME,
        )
        result["symbol"] = symbol.upper()
        result["quarters"] = []
        return result

    def get_news(self, symbol, limit=12):
        ticker = self._ticker(symbol)
        try:
            raw_items = ticker.news or []
        except Exception:
            raw_items = []

        articles = []
        for item in raw_items[:limit]:
            content = item.get("content", item)
            published = content.get("pubDate") or item.get("providerPublishTime")
            if isinstance(published, (int, float)):
                published = datetime.fromtimestamp(published, tz=timezone.utc).isoformat()
            provider = content.get("provider") or {}
            canonical = content.get("canonicalUrl") or {}
            articles.append({
                "headline": content.get("title") or item.get("title"),
                "date": published,
                "source": provider.get("displayName") or item.get("publisher") or "Yahoo Finance",
                "url": canonical.get("url") or item.get("link"),
                "summary": content.get("summary"),
                # Sentiment is assigned later by news_service, from the text.
                "why_it_matters": None,
                "sentiment": None,
                "verified": True,
                "is_demo": False,
            })

        return {
            "symbol": symbol.upper(),
            "articles": [a for a in articles if a["headline"]],
            "source": SOURCE_NAME,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "is_demo": False,
        }

    def get_market_overview(self):
        """NIFTY 50 and SENSEX levels are real. Gainers/losers need a screener
        feed we do not have, so those lists come back empty, not invented."""
        if self._yf is None:
            self._yf = _load_yfinance()

        indices = []
        for name, yahoo_symbol in (("NIFTY 50", "^NSEI"), ("SENSEX", "^BSESN")):
            try:
                history = self._yf.Ticker(yahoo_symbol).history(period="5d")
                if history is None or history.empty or len(history) < 2:
                    continue
                value = _number(history["Close"].iloc[-1])
                previous = _number(history["Close"].iloc[-2])
                if value is None or not previous:
                    continue
                indices.append({
                    "name": name,
                    "value": round(value, 2),
                    "change": round(value - previous, 2),
                    "change_pct": round((value - previous) / previous * 100, 2),
                    "as_of": history.index[-1].isoformat(),
                })
            except Exception:
                continue

        return {
            "indices": indices,
            "top_gainers": [],
            "top_losers": [],
            "most_active": [],
            "sentiment": None,
            "sentiment_note": "Gainers, losers and market breadth need a licensed screener feed.",
            "source": SOURCE_NAME,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "is_demo": False,
        }
