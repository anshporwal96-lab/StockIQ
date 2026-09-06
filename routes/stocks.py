"""
routes/stocks.py
================
The stock data API: search, company info, price, history, financials,
quarterly results, shareholding, technicals, valuation and compare.

EVERY ROUTE FOLLOWS THE SAME SHAPE
----------------------------------
    1. Validate / resolve the symbol the user asked for
    2. Call a service function (which handles caching and the provider)
    3. Return JSON, or a friendly error - never fake numbers

Errors are caught here rather than in the services so that each service stays
easy to unit-test without Flask.
"""

from flask import Blueprint, jsonify, request

from services import financial_service, stock_service
from services.providers import DataProviderError
from utils.security import rate_limit
from utils.validators import clean_symbol

stocks_bp = Blueprint("stocks", __name__)

VALID_PERIODS = ["1D", "1W", "1M", "3M", "6M", "1Y", "3Y", "5Y"]


def _resolve_or_404(raw_symbol):
    """Turn user input into a known symbol, or return an error response.

    Returns (symbol, None) on success or (None, response) on failure, so the
    caller can write:  symbol, error = _resolve_or_404(x)
    """
    symbol = stock_service.resolve_symbol(raw_symbol)
    if not symbol:
        return None, (jsonify({
            "error": "not_found",
            "message": "We could not find a stock matching '%s'. Try an NSE symbol such as "
                       "TCS, a BSE code such as 532540, or a company name." % raw_symbol,
        }), 404)
    return symbol, None


def _handle(fetch):
    """Run a data fetch and translate any failure into a friendly message.

    Requirement 40 of the brief: show a user-friendly message, never a stack
    trace and never invented data.
    """
    try:
        return jsonify(fetch())
    except DataProviderError as error:
        return jsonify({
            "error": "provider_error",
            "message": "We could not retrieve that data right now. " + str(error),
        }), 503
    except Exception as error:
        return jsonify({
            "error": "server_error",
            "message": "Something went wrong while preparing this data. Please try again.",
            "detail": str(error),
        }), 500


@stocks_bp.route("/search", methods=["GET"])
@rate_limit("search")
def search():
    """GET /api/search?q=TCS - company name, NSE symbol or BSE code."""
    query = request.args.get("q", "")
    if len(str(query).strip()) < 1:
        return jsonify({"results": [], "message": "Type at least one character to search."})
    results = stock_service.search_stocks(query, limit=int(request.args.get("limit", 10)))
    return jsonify({
        "query": query,
        "count": len(results),
        "results": results,
        "message": None if results else "No matching company found. Check the spelling, or "
                                        "the company may not be in our reference list yet.",
    })


@stocks_bp.route("/stock/<symbol>", methods=["GET"])
def stock_detail(symbol):
    """GET /api/stock/TCS - company profile plus the latest price."""
    resolved, error = _resolve_or_404(symbol)
    if error:
        return error
    return _handle(lambda: {
        "symbol": resolved,
        "company": stock_service.get_company_info(resolved),
        "price": stock_service.get_current_price(resolved),
        "peers": stock_service.get_peer_symbols(resolved),
    })


@stocks_bp.route("/stock/<symbol>/price", methods=["GET"])
def stock_price(symbol):
    """GET /api/stock/TCS/price - just the quote. Cached for 60 seconds."""
    resolved, error = _resolve_or_404(symbol)
    if error:
        return error
    return _handle(lambda: stock_service.get_current_price(resolved))


@stocks_bp.route("/stock/<symbol>/history", methods=["GET"])
def stock_history(symbol):
    """GET /api/stock/TCS/history?period=1Y - candles for the chart."""
    resolved, error = _resolve_or_404(symbol)
    if error:
        return error

    period = str(request.args.get("period", "1Y")).upper()
    if period not in VALID_PERIODS:
        return jsonify({
            "error": "bad_period",
            "message": "Period must be one of: " + ", ".join(VALID_PERIODS),
        }), 400

    return _handle(lambda: stock_service.get_historical_prices(resolved, period))


@stocks_bp.route("/stock/<symbol>/financials", methods=["GET"])
def stock_financials(symbol):
    """GET /api/stock/TCS/financials - income statement, balance sheet, cash flow."""
    resolved, error = _resolve_or_404(symbol)
    if error:
        return error
    return _handle(lambda: financial_service.get_financials(resolved))


@stocks_bp.route("/stock/<symbol>/fundamentals", methods=["GET"])
def stock_fundamentals(symbol):
    """GET /api/stock/TCS/fundamentals - the computed ratios."""
    resolved, error = _resolve_or_404(symbol)
    if error:
        return error
    return _handle(lambda: financial_service.get_fundamentals(resolved))


@stocks_bp.route("/stock/<symbol>/earnings", methods=["GET"])
def stock_earnings(symbol):
    """GET /api/stock/TCS/earnings - quarterly results with YoY and QoQ growth."""
    resolved, error = _resolve_or_404(symbol)
    if error:
        return error
    return _handle(lambda: financial_service.get_quarterly(resolved))


@stocks_bp.route("/stock/<symbol>/shareholding", methods=["GET"])
def stock_shareholding(symbol):
    """GET /api/stock/TCS/shareholding - promoter / FII / DII / public split."""
    resolved, error = _resolve_or_404(symbol)
    if error:
        return error
    return _handle(lambda: financial_service.get_shareholding(resolved))


@stocks_bp.route("/stock/<symbol>/technicals", methods=["GET"])
def stock_technicals(symbol):
    """GET /api/stock/TCS/technicals - moving averages, RSI, MACD, ADX, levels."""
    resolved, error = _resolve_or_404(symbol)
    if error:
        return error
    period = str(request.args.get("period", "1Y")).upper()
    if period not in VALID_PERIODS:
        period = "1Y"
    return _handle(lambda: financial_service.get_technicals(resolved, period))


@stocks_bp.route("/stock/<symbol>/valuation", methods=["GET"])
def stock_valuation(symbol):
    """GET /api/stock/TCS/valuation - multiples, historical band, classification."""
    resolved, error = _resolve_or_404(symbol)
    if error:
        return error
    return _handle(lambda: financial_service.get_valuation(resolved))


@stocks_bp.route("/compare", methods=["GET"])
@rate_limit("compare", per_minute=30)
def compare():
    """GET /api/compare?stocks=TCS,INFY,HCLTECH - 2 to 5 stocks side by side."""
    raw = request.args.get("stocks", "")
    requested = [clean_symbol(part) for part in str(raw).split(",") if clean_symbol(part)]

    resolved = []
    for item in requested:
        symbol = stock_service.resolve_symbol(item)
        if symbol and symbol not in resolved:
            resolved.append(symbol)

    if len(resolved) < 2:
        return jsonify({
            "error": "need_two",
            "message": "Give at least two valid stocks, for example ?stocks=TCS,INFY",
        }), 400

    return _handle(lambda: {
        "symbols": resolved[:5],
        "rows": financial_service.compare_stocks(resolved[:5]),
    })


@stocks_bp.route("/market", methods=["GET"])
def market():
    """GET /api/market - NIFTY 50, SENSEX, gainers, losers, most active."""
    return _handle(stock_service.get_market_overview)
