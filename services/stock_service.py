"""
services/stock_service.py
=========================
Everything about identifying a stock and getting its price.

This sits BETWEEN the routes and the data provider:

    route  ->  stock_service  ->  cache  ->  provider  ->  external API

The route never touches the provider directly. That means caching, validation
and error handling are written once here instead of in every route.
"""

from utils import cache, validators
from services.providers import DataProviderError, get_provider
from services.stock_universe import ALL_ROWS, BY_BSE, BY_SYMBOL, get_peers


def search_stocks(query, limit=10):
    """Find companies by name, NSE symbol or BSE code.

    Handles all three of the search styles the brief asks for:
        "TCS"        -> exact NSE symbol
        "500325"     -> BSE scrip code
        "Reliance"   -> partial company name

    Results are ranked so exact matches come first, then names that START with
    the query, then names that merely contain it. That ordering is what makes
    typing "hdfc" put HDFC Bank at the top.
    """
    query = str(query or "").strip()
    if len(query) < 1:
        return []

    upper = query.upper()
    lower = query.lower()
    results = []

    # 1. Exact BSE code
    if validators.is_bse_code(upper) and upper in BY_BSE:
        results.append((0, BY_BSE[upper]))

    # 2. Exact NSE symbol
    if upper in BY_SYMBOL:
        results.append((0, BY_SYMBOL[upper]))

    for row in ALL_ROWS:
        name = row["company_name"].lower()
        symbol = row["symbol"]

        if symbol == upper or row["bse_code"] == upper:
            continue                      # already added above
        if symbol.startswith(upper):
            results.append((1, row))
        elif name.startswith(lower):
            results.append((2, row))
        elif lower in name:
            results.append((3, row))
        elif upper in symbol:
            results.append((4, row))

    results.sort(key=lambda pair: (pair[0], pair[1]["company_name"]))

    seen = set()
    output = []
    for _, row in results:
        if row["symbol"] in seen:
            continue
        seen.add(row["symbol"])
        output.append(dict(row))
        if len(output) >= limit:
            break
    return output


def resolve_symbol(raw):
    """Turn whatever the user typed into a canonical NSE symbol.

    Accepts "tcs", "TCS", "532540". Returns None if nothing matches, so the
    route can send a clean 404 instead of guessing.
    """
    text = str(raw or "").strip().upper()
    if not text:
        return None
    if text in BY_SYMBOL:
        return text
    if text in BY_BSE:
        return BY_BSE[text]["symbol"]
    matches = search_stocks(text, limit=1)
    return matches[0]["symbol"] if matches else None


def get_company_info(symbol):
    """Company profile, cached for 7 days by default."""
    cached = cache.get(symbol, "company")
    if cached:
        return cached
    data = get_provider().get_company_info(symbol)

    # Fill in the exchange identifiers from our own reference list when the
    # provider does not supply them (Yahoo, for example, has no BSE code).
    row = BY_SYMBOL.get(symbol.upper())
    if row:
        data.setdefault("bse_code", row["bse_code"])
        if not data.get("bse_code"):
            data["bse_code"] = row["bse_code"]
        if not data.get("sector"):
            data["sector"] = row["sector"]
        if not data.get("industry"):
            data["industry"] = row["industry"]

    return cache.set(symbol, "company", data)


def get_current_price(symbol):
    """Latest quote, cached for 60 seconds by default."""
    cached = cache.get(symbol, "price")
    if cached:
        return cached
    data = get_provider().get_current_price(symbol)

    # Data-quality check: attach the result so the UI can warn instead of
    # silently showing something odd.
    data["quality"] = validators.check_quality(data, required_fields=("price",))
    return cache.set(symbol, "price", data)


def get_historical_prices(symbol, period="1Y"):
    """Price candles for one of the chart's time buttons."""
    period = str(period or "1Y").upper()
    cache_key = "history_" + period
    cached = cache.get(symbol, cache_key)
    if cached:
        return cached

    data = get_provider().get_historical_prices(symbol, period)
    return cache.set(symbol, cache_key, data)


def get_market_overview():
    """NIFTY / SENSEX and the movers list for the homepage."""
    cached = cache.get("_MARKET_", "market")
    if cached:
        return cached
    data = get_provider().get_market_overview()
    return cache.set("_MARKET_", "market", data)


def get_peer_symbols(symbol, limit=4):
    """Companies in the same industry, for the Peers tab."""
    return get_peers(symbol, limit)


def get_stock_snapshot(symbol):
    """Company info + price in one call, used by the watchlist and compare
    pages where the full analysis would be overkill."""
    info = get_company_info(symbol)
    try:
        price = get_current_price(symbol)
    except DataProviderError as error:
        price = {"available": False, "reason": str(error)}
    return {"info": info, "price": price}
