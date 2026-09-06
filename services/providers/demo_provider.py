"""
services/providers/demo_provider.py
===================================
                        *** DEMO DATA - NOT REAL ***

This provider generates a complete, internally-consistent SAMPLE dataset so
that every screen, chart and calculation in StockIQ India can be built and
tested without a paid market-data licence.

READ THIS CAREFULLY
-------------------
Nothing this file produces is real market information. The numbers are
generated from a random-number generator seeded by the ticker symbol, which is
why TCS always looks the same each time you reload - it is reproducible, but it
is still invented.

Every dictionary returned sets  "is_demo": True  and
"source": "DEMO DATA (generated sample - not real market data)".
The frontend paints an orange DEMO DATA badge whenever it sees that flag, and
the AI prompts state plainly that the figures are sample data.

TO USE REAL DATA
----------------
Set DATA_PROVIDER=yfinance in .env (and pip install yfinance), or write your
own provider against the contract in base.py. See README -> "Switching to real
data" for the exact steps and where each API call belongs.
"""

import random
from datetime import date, datetime, timedelta, timezone

from services.providers.base import BaseProvider, DataProviderError
from services.stock_universe import BY_SYMBOL

DEMO_SOURCE = "DEMO DATA (generated sample - not real market data)"

# How many trading days each period button covers.
PERIOD_DAYS = {
    "1D": 1, "1W": 5, "1M": 22, "3M": 66,
    "6M": 126, "1Y": 252, "3Y": 756, "5Y": 1260,
}


def _seed_for(symbol):
    """Turn a ticker into a stable number, so the same symbol always produces
    the same sample data. Reproducibility makes the app easier to test."""
    return sum(ord(character) * (index + 7) for index, character in enumerate(symbol))


class DemoProvider(BaseProvider):
    """Generates the offline sample dataset."""

    name = "demo"

    def __init__(self):
        # One generated price series per symbol, built on first use.
        self._candle_cache = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _profile(self, symbol):
        """Look up the company and derive its sample "personality" - starting
        price, growth rate, margins and so on - from the seeded generator."""
        row = BY_SYMBOL.get(symbol.upper())
        if not row:
            raise DataProviderError(f"{symbol} is not in the demo stock universe.")

        rng = random.Random(_seed_for(symbol.upper()))

        # Different sectors get different plausible-looking characteristics so
        # the demo dataset is varied rather than 112 identical companies.
        sector_traits = {
            "Information Technology": (2200, 0.10, 25.0, 18.0, 0.05),
            "Financials":             (1100, 0.14, 30.0, 20.0, 0.90),
            "Energy":                 (1400, 0.07, 18.0, 8.0, 0.55),
            "Utilities":              (280, 0.08, 28.0, 13.0, 1.20),
            "Materials":              (900, 0.09, 20.0, 11.0, 0.45),
            "Consumer Staples":       (1600, 0.09, 22.0, 15.0, 0.12),
            "Consumer Discretionary": (2400, 0.12, 16.0, 9.0, 0.30),
            "Healthcare":             (1300, 0.11, 24.0, 15.0, 0.20),
            "Industrials":            (1900, 0.13, 15.0, 9.0, 0.35),
            "Communication Services": (1000, 0.10, 33.0, 10.0, 0.80),
        }
        base_price, growth, margin, net_margin, leverage = sector_traits.get(
            row["sector"], (1000, 0.10, 20.0, 12.0, 0.40)
        )

        return {
            "row": row,
            "rng": rng,
            "base_price": round(base_price * rng.uniform(0.35, 2.4), 2),
            "growth": growth * rng.uniform(0.4, 1.7),
            "ebitda_margin": margin * rng.uniform(0.7, 1.3),
            "pat_margin": net_margin * rng.uniform(0.6, 1.35),
            "leverage": leverage * rng.uniform(0.2, 1.8),
            "shares_crore": round(rng.uniform(30, 900), 2),
        }

    def _master_candles(self, symbol):
        """Build ONE long price series per symbol, roughly seven years of it.

        WHY ONE SERIES?
        ---------------
        Every other method slices this list. If each call generated its own
        random walk, the quote on the header and the line on the 1Y chart would
        be two different prices for the same stock. Generating once and slicing
        keeps every screen internally consistent - and because the seed comes
        only from the symbol, reloading the page shows the same numbers again.
        """
        symbol = symbol.upper()
        if symbol in self._candle_cache:
            return self._candle_cache[symbol]

        profile = self._profile(symbol)
        rng = random.Random(_seed_for(symbol))
        days = 2600                       # about 7 calendar years

        price = profile["base_price"] * 0.65  # start lower so there is a trend
        drift = profile["growth"] / 252.0
        shock = 0.014 + profile["leverage"] * 0.004  # daily volatility

        candles = []
        today = date.today()
        for offset in range(days, 0, -1):
            day = today - timedelta(days=offset)
            if day.weekday() >= 5:      # skip Saturdays and Sundays
                continue
            move = rng.gauss(drift, shock)
            open_price = price
            close_price = max(1.0, price * (1 + move))
            high = max(open_price, close_price) * (1 + abs(rng.gauss(0, 0.004)))
            low = min(open_price, close_price) * (1 - abs(rng.gauss(0, 0.004)))
            volume = int(abs(rng.gauss(1, 0.35)) * 900_000) + 40_000
            candles.append({
                "date": day.isoformat(),
                "open": round(open_price, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(close_price, 2),
                "volume": volume,
            })
            price = close_price

        # Rescale so the final close equals the profile price. Without this the
        # random walk could drift anywhere and a "Rs 2,200 stock" might end at
        # Rs 400, which would make the demo dataset confusing to read.
        if candles:
            scale = profile["base_price"] / candles[-1]["close"]
            for candle in candles:
                for key in ("open", "high", "low", "close"):
                    candle[key] = round(candle[key] * scale, 2)

        self._candle_cache[symbol] = candles
        return candles

    def _candles(self, symbol, days):
        """The most recent `days` trading sessions from the master series."""
        master = self._master_candles(symbol)
        return master[-days:] if days < len(master) else master

    # ------------------------------------------------------------------
    # Public methods (the contract from base.py)
    # ------------------------------------------------------------------
    def get_company_info(self, symbol):
        profile = self._profile(symbol)
        row = profile["row"]
        rng = profile["rng"]
        candles = self._candles(symbol, 30)
        last_price = candles[-1]["close"]
        shares = profile["shares_crore"]

        return {
            "symbol": row["symbol"],
            "company_name": row["company_name"],
            "nse_symbol": row["nse_symbol"],
            "bse_code": row["bse_code"],
            "exchange": "NSE / BSE",
            "sector": row["sector"],
            "industry": row["industry"],
            # market cap in Rs crore = price (Rs) x shares (crore)
            "market_cap_cr": round(last_price * shares, 2),
            "shares_outstanding_cr": shares,
            "face_value": rng.choice([1, 1, 2, 5, 10]),
            "description": (
                f"{row['company_name']} operates in the {row['industry']} industry "
                f"within the {row['sector']} sector. This description is part of the "
                f"demo dataset and is not sourced from company filings."
            ),
            "business_model": {
                "what_it_sells": f"Products and services in {row['industry']}.",
                "who_buys": "Enterprise and retail customers across India and abroad.",
                "revenue_sources": ["Core operations", "Services", "Other income"],
                "geography": {"India": 62, "Americas": 21, "Europe": 12, "Others": 5},
                "segments": [
                    {"name": "Core business", "share_pct": 71},
                    {"name": "Adjacent services", "share_pct": 20},
                    {"name": "Others", "share_pct": 9},
                ],
                "moat": "Scale, brand recognition and customer switching costs.",
            },
            "source": DEMO_SOURCE,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "is_demo": True,
        }

    def get_current_price(self, symbol):
        candles = self._candles(symbol, 400)
        latest, previous = candles[-1], candles[-2]
        closes = [c["close"] for c in candles]
        change = latest["close"] - previous["close"]

        return {
            "symbol": symbol.upper(),
            "price": latest["close"],
            "previous_close": previous["close"],
            "change": round(change, 2),
            "change_pct": round(change / previous["close"] * 100, 2),
            "open": latest["open"],
            "day_high": latest["high"],
            "day_low": latest["low"],
            "volume": latest["volume"],
            "week_52_high": round(max(closes[-252:]), 2),
            "week_52_low": round(min(closes[-252:]), 2),
            "currency": "INR",
            "source": DEMO_SOURCE,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "is_demo": True,
        }

    def get_historical_prices(self, symbol, period="1Y"):
        period = str(period).upper()
        if period not in PERIOD_DAYS:
            period = "1Y"

        # PERIOD_DAYS counts TRADING sessions, and the master series already has
        # weekends removed, so we can slice it directly. A minimum of two keeps
        # the chart from being a single dot on the 1D button.
        wanted = max(2, PERIOD_DAYS[period])
        candles = self._candles(symbol, wanted)

        note = None
        if period in ("1D", "1W"):
            note = ("This provider only produces daily candles, so the 1D and 1W views "
                    "show recent daily closes rather than intraday ticks.")

        return {
            "symbol": symbol.upper(),
            "period": period,
            "interval": "1d",
            "candles": candles,
            "note": note,
            "source": DEMO_SOURCE,
            "as_of": candles[-1]["date"] if candles else None,
            "is_demo": True,
        }

    def get_financials(self, symbol):
        """Five years of annual statements, built so the numbers agree with
        each other (profit ties to margins, cash flow ties to profit)."""
        profile = self._profile(symbol)
        rng = random.Random(_seed_for(symbol.upper()) + 99)

        market_cap = profile["base_price"] * profile["shares_crore"]
        revenue = market_cap / rng.uniform(1.4, 4.5)   # sales in Rs crore
        current_year = date.today().year

        years = []
        for step in range(5):
            year_revenue = revenue / ((1 + profile["growth"]) ** (4 - step))
            year_revenue *= rng.uniform(0.97, 1.03)
            ebitda = year_revenue * (profile["ebitda_margin"] / 100) * rng.uniform(0.94, 1.06)
            depreciation = ebitda * rng.uniform(0.12, 0.24)
            ebit = ebitda - depreciation
            equity = year_revenue * rng.uniform(0.55, 1.4)
            debt = equity * profile["leverage"] * rng.uniform(0.8, 1.2)
            interest = debt * rng.uniform(0.06, 0.10)
            pbt = ebit - interest
            net_profit = year_revenue * (profile["pat_margin"] / 100) * rng.uniform(0.93, 1.07)
            operating_cf = net_profit * rng.uniform(0.85, 1.35) + depreciation
            capex = year_revenue * rng.uniform(0.03, 0.11)

            years.append({
                "period": f"FY{current_year - 4 + step}",
                "revenue": round(year_revenue, 1),
                "ebitda": round(ebitda, 1),
                "depreciation": round(depreciation, 1),
                "ebit": round(ebit, 1),
                "interest_expense": round(interest, 1),
                "pbt": round(pbt, 1),
                "net_profit": round(net_profit, 1),
                "eps": round(net_profit / profile["shares_crore"], 2),
                "total_assets": round((equity + debt) * rng.uniform(1.2, 1.6), 1),
                "total_debt": round(debt, 1),
                "cash": round(year_revenue * rng.uniform(0.05, 0.28), 1),
                "equity": round(equity, 1),
                "receivables": round(year_revenue * rng.uniform(0.10, 0.24), 1),
                "inventory": round(year_revenue * rng.uniform(0.02, 0.20), 1),
                "current_assets": round(year_revenue * rng.uniform(0.35, 0.75), 1),
                "current_liabilities": round(year_revenue * rng.uniform(0.20, 0.50), 1),
                "operating_cash_flow": round(operating_cf, 1),
                "capex": round(capex, 1),
                "free_cash_flow": round(operating_cf - capex, 1),
                "dividend_per_share": round(
                    net_profit / profile["shares_crore"] * rng.uniform(0.1, 0.45), 2
                ),
            })

        return {
            "symbol": symbol.upper(),
            "currency": "INR",
            "units": "Rs crore (except per-share figures)",
            "annual": years,
            "source": DEMO_SOURCE,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "is_demo": True,
        }

    def get_quarterly_results(self, symbol):
        """Eight quarters, derived from the annual figures so the two views do
        not contradict each other."""
        profile = self._profile(symbol)
        financials = self.get_financials(symbol)
        latest_year = financials["annual"][-1]
        rng = random.Random(_seed_for(symbol.upper()) + 7)

        quarterly_revenue = latest_year["revenue"] / 4.0
        quarters = []
        today = date.today()
        # Indian companies report Apr-Mar financial years: Q1 = Apr-Jun.
        for step in range(8):
            months_back = (7 - step) * 3
            end_month = today.month - months_back
            year = today.year + (end_month - 1) // 12
            month = (end_month - 1) % 12 + 1
            fiscal_quarter = ((month - 4) % 12) // 3 + 1
            fiscal_year = year if month >= 4 else year - 1

            seasonal = 1 + 0.05 * rng.uniform(-1, 1)
            growth_so_far = (1 + profile["growth"] / 4) ** (step - 7)
            revenue = quarterly_revenue * seasonal * growth_so_far
            ebitda = revenue * (profile["ebitda_margin"] / 100) * rng.uniform(0.9, 1.1)
            net_profit = revenue * (profile["pat_margin"] / 100) * rng.uniform(0.88, 1.12)
            exceptional = round(net_profit * rng.uniform(-0.05, 0.05), 1)

            quarters.append({
                "period": "Q%d FY%s" % (fiscal_quarter, str(fiscal_year + 1)[-2:]),
                "end_date": date(year, month, 28).isoformat(),
                "revenue": round(revenue, 1),
                "ebitda": round(ebitda, 1),
                "ebitda_margin": round(ebitda / revenue * 100, 2),
                "net_profit": round(net_profit, 1),
                "eps": round(net_profit / profile["shares_crore"], 2),
                "exceptional_items": exceptional if rng.random() < 0.3 else 0.0,
            })

        return {
            "symbol": symbol.upper(),
            "units": "Rs crore (except EPS)",
            "quarters": quarters,
            "source": DEMO_SOURCE,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "is_demo": True,
        }

    def get_shareholding(self, symbol):
        """Four quarters of the ownership split. The four categories always add
        up to 100 percent, as they must in a real filing."""
        rng = random.Random(_seed_for(symbol.upper()) + 21)
        promoter = rng.uniform(0, 75)
        fii = rng.uniform(3, min(30, 95 - promoter))
        dii = rng.uniform(3, min(28, 98 - promoter - fii))

        quarters = []
        today = date.today()
        for step in range(4):
            drift = (step - 3) * rng.uniform(-0.4, 0.4)
            p = max(0.0, min(75.0, promoter + drift))
            f = max(0.0, fii - drift * 0.6)
            d = max(0.0, dii + drift * 0.3)
            public = max(0.0, 100.0 - p - f - d)
            months_back = (3 - step) * 3
            end_month = today.month - months_back
            year = today.year + (end_month - 1) // 12
            month = (end_month - 1) % 12 + 1

            quarters.append({
                "period": date(year, month, 28).strftime("%b %Y"),
                "promoter": round(p, 2),
                "fii": round(f, 2),
                "dii": round(d, 2),
                "public": round(public, 2),
                "promoter_pledge_pct": round(rng.uniform(0, 4), 2),
            })

        return {
            "symbol": symbol.upper(),
            "quarters": quarters,
            "source": DEMO_SOURCE,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "is_demo": True,
        }

    def get_news(self, symbol, limit=12):
        """Sample headlines. Every item is flagged is_demo so the UI can label
        it, and none of them are presented as verified reporting."""
        row = BY_SYMBOL.get(symbol.upper())
        if not row:
            raise DataProviderError(symbol + " is not in the demo stock universe.")
        rng = random.Random(_seed_for(symbol.upper()) + 5)
        name = row["company_name"]

        templates = [
            ("{n} reports quarterly results", "Exchange filing", "positive",
             "Quarterly numbers were filed with the exchanges."),
            ("{n} announces capacity expansion plan", "Company announcement", "positive",
             "Management outlined a multi-year capital expenditure plan."),
            ("Brokerages update estimates on {n}", "Financial media", "neutral",
             "Analyst estimates were revised after the latest disclosures."),
            ("{n} board approves dividend", "Exchange filing", "positive",
             "A dividend was recommended, subject to shareholder approval."),
            ("Input cost pressure noted in the {n} sector", "Financial media", "negative",
             "Sector-wide raw material costs were reported to be rising."),
            ("{n} discloses change in shareholding", "Exchange filing", "neutral",
             "A routine disclosure of a change in the shareholding pattern."),
            ("Regulatory update affects the {n} industry", "Regulator", "neutral",
             "A policy change was announced that touches this industry."),
            ("{n} signs new customer agreement", "Company announcement", "positive",
             "A new multi-year contract was announced."),
            ("{n} faces increased competition", "Financial media", "negative",
             "Competitors were reported to be expanding in the same markets."),
        ]

        articles = []
        today = datetime.now(timezone.utc)
        for index in range(min(limit, len(templates))):
            headline, source, sentiment, summary = templates[index]
            published = today - timedelta(days=index * 2, hours=rng.randint(0, 20))
            articles.append({
                "headline": "[DEMO] " + headline.format(n=name),
                "date": published.isoformat(),
                "source": source + " (demo)",
                "url": None,
                "summary": summary,
                "why_it_matters": "Illustrative only - the demo feed contains no real news.",
                "sentiment": sentiment,
                "verified": False,
                "is_demo": True,
            })

        return {
            "symbol": symbol.upper(),
            "articles": articles,
            "source": DEMO_SOURCE,
            "as_of": today.isoformat(),
            "is_demo": True,
        }

    def get_market_overview(self):
        """Sample index levels and movers."""
        rng = random.Random(int(date.today().strftime("%Y%m%d")))
        now = datetime.now(timezone.utc).isoformat()

        def index_block(name, base):
            change_pct = rng.uniform(-1.4, 1.4)
            value = base * (1 + change_pct / 100)
            return {
                "name": name,
                "value": round(value, 2),
                "change": round(value - base, 2),
                "change_pct": round(change_pct, 2),
            }

        symbols = list(BY_SYMBOL.keys())
        rng.shuffle(symbols)

        def movers(pool, positive):
            out = []
            for sym in pool:
                pct = rng.uniform(1.5, 7.5) * (1 if positive else -1)
                row = BY_SYMBOL[sym]
                out.append({
                    "symbol": sym,
                    "company_name": row["company_name"],
                    "price": round(self._profile(sym)["base_price"], 2),
                    "change_pct": round(pct, 2),
                })
            return sorted(out, key=lambda r: r["change_pct"], reverse=positive)

        return {
            "indices": [index_block("NIFTY 50", 24000), index_block("SENSEX", 79000)],
            "top_gainers": movers(symbols[:5], True),
            "top_losers": movers(symbols[5:10], False),
            "most_active": movers(symbols[10:15], True),
            "sentiment": None,
            "sentiment_note": "Market breadth needs licensed data, so sentiment is not shown.",
            "source": DEMO_SOURCE,
            "as_of": now,
            "is_demo": True,
        }
