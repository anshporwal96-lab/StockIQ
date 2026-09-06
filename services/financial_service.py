"""
services/financial_service.py
=============================
Fetches financial statements and runs them through the analysis modules.

This is where the pipeline from the brief actually happens:

    provider -> raw statements -> Python calculations -> structured analysis

The AI never sees the raw provider response. It only ever sees the structured
analysis this module produces, which is exactly why it cannot invent a number.
"""

from analysis.bull_bear import (
    generate_bear_case, generate_bull_case, generate_investment_thesis, scenario_analysis,
)
from analysis.fundamentals import analyze_fundamentals
from analysis.risk import (
    analyze_shareholding_changes, assess_risks, entry_scenarios, governance_notes,
    identify_catalysts,
)
from analysis.scoring import score_stock
from analysis.technicals import analyze_technicals
from analysis.valuation import analyze_valuation, compute_ratios
from services.providers import DataProviderError, get_provider
from services.stock_service import (
    get_company_info, get_current_price, get_historical_prices, get_peer_symbols,
)
from utils import cache
from utils.calculations import percent_change, round_or_none


def get_financials(symbol):
    """Annual statements. Cached 24 hours - they change a few times a year."""
    cached = cache.get(symbol, "financials")
    if cached:
        return cached
    return cache.set(symbol, "financials", get_provider().get_financials(symbol))


def get_quarterly(symbol):
    """Quarterly results plus computed YoY and QoQ growth for each quarter."""
    cached = cache.get(symbol, "quarterly")
    if cached:
        return cached

    data = get_provider().get_quarterly_results(symbol)
    quarters = data.get("quarters") or []

    # QoQ compares with the previous quarter. YoY compares with the same
    # quarter a year earlier, which is four quarters back in the list.
    for index, quarter in enumerate(quarters):
        previous = quarters[index - 1] if index >= 1 else None
        year_ago = quarters[index - 4] if index >= 4 else None

        quarter["revenue_qoq_pct"] = round_or_none(
            percent_change(quarter.get("revenue"), previous.get("revenue")) if previous else None
        )
        quarter["revenue_yoy_pct"] = round_or_none(
            percent_change(quarter.get("revenue"), year_ago.get("revenue")) if year_ago else None
        )
        quarter["profit_qoq_pct"] = round_or_none(
            percent_change(quarter.get("net_profit"), previous.get("net_profit")) if previous else None
        )
        quarter["profit_yoy_pct"] = round_or_none(
            percent_change(quarter.get("net_profit"), year_ago.get("net_profit")) if year_ago else None
        )

    return cache.set(symbol, "quarterly", data)


def get_shareholding(symbol):
    """Ownership split by quarter, plus a description of how it changed."""
    cached = cache.get(symbol, "shareholding")
    if cached:
        return cached
    data = get_provider().get_shareholding(symbol)
    data["changes"] = analyze_shareholding_changes(data)
    return cache.set(symbol, "shareholding", data)


def get_fundamentals(symbol):
    """Ratios and growth, computed from the statements."""
    return analyze_fundamentals(get_financials(symbol), get_quarterly(symbol))


def get_technicals(symbol, period="1Y"):
    """Indicators computed from the price history."""
    return analyze_technicals(get_historical_prices(symbol, period))


def get_peer_pe_ratios(symbol):
    """The P/E of each peer, so valuation can be compared like for like.

    Each peer is wrapped in try/except: one failing peer must not break the page.
    """
    peer_pes = []
    for peer in get_peer_symbols(symbol):
        try:
            ratios = compute_ratios(
                get_current_price(peer), get_company_info(peer), get_financials(peer)
            )
            if ratios.get("available") and ratios.get("pe_ratio"):
                peer_pes.append(ratios["pe_ratio"])
        except Exception:
            continue
    return peer_pes


def get_valuation(symbol):
    """Valuation multiples, the historical band and the classification."""
    return analyze_valuation(
        get_current_price(symbol),
        get_company_info(symbol),
        get_financials(symbol),
        get_historical_prices(symbol, "5Y"),
        get_peer_pe_ratios(symbol),
    )


def compare_stocks(symbols):
    """Side-by-side metrics for 2-5 stocks, for the Compare page."""
    rows = []
    for symbol in symbols[:5]:
        try:
            info = get_company_info(symbol)
            price = get_current_price(symbol)
            fundamentals = get_fundamentals(symbol)
            valuation = get_valuation(symbol)
            technicals = get_technicals(symbol)

            growth = fundamentals.get("growth") or {}
            profitability = fundamentals.get("profitability") or {}
            health = fundamentals.get("financial_health") or {}
            ratios = valuation.get("ratios") or {}

            rows.append({
                "symbol": symbol,
                "company_name": info.get("company_name"),
                "sector": info.get("sector"),
                "price": price.get("price"),
                "change_pct": price.get("change_pct"),
                "market_cap_cr": info.get("market_cap_cr"),
                "revenue_growth_pct": growth.get("revenue_yoy_pct"),
                "profit_growth_pct": growth.get("profit_yoy_pct"),
                "revenue_cagr_3y_pct": growth.get("revenue_cagr_3y_pct"),
                "ebitda_margin_pct": profitability.get("ebitda_margin_pct"),
                "pat_margin_pct": profitability.get("pat_margin_pct"),
                "roe_pct": profitability.get("roe_pct"),
                "roce_pct": profitability.get("roce_pct"),
                "debt_to_equity": health.get("debt_to_equity"),
                "free_cash_flow": health.get("free_cash_flow"),
                "pe_ratio": ratios.get("pe_ratio"),
                "pb_ratio": ratios.get("pb_ratio"),
                "ev_ebitda": ratios.get("ev_ebitda"),
                "dividend_yield_pct": ratios.get("dividend_yield_pct"),
                "valuation_label": (valuation.get("verdict") or {}).get("label"),
                "technical_view": technicals.get("view"),
                "is_demo": info.get("is_demo", False),
                "error": None,
            })
        except DataProviderError as error:
            rows.append({"symbol": symbol, "error": str(error)})
        except Exception as error:
            rows.append({"symbol": symbol, "error": "Could not load %s (%s)" % (symbol, error)})
    return rows


def build_full_analysis(symbol):
    """Run EVERY analysis module and return one structured dictionary.

    This single object is:
      * what GET /api/stock/<symbol>/analysis returns
      * the entire factual context the AI service is given

    Sections that fail are marked unavailable. One broken section never takes
    the whole page down.
    """
    info = get_company_info(symbol)
    price = get_current_price(symbol)
    financials = get_financials(symbol)
    quarterly = get_quarterly(symbol)
    shareholding = get_shareholding(symbol)

    fundamentals = analyze_fundamentals(financials, quarterly)
    technicals = get_technicals(symbol)
    valuation = get_valuation(symbol)
    risks = assess_risks(fundamentals, valuation, technicals, shareholding)
    bull = generate_bull_case(fundamentals, valuation, technicals, info)
    bear = generate_bear_case(fundamentals, valuation, technicals, risks)

    return {
        "symbol": symbol,
        "company": info,
        "price": price,
        "fundamentals": fundamentals,
        "financials": financials,
        "quarterly": quarterly,
        "shareholding": shareholding,
        "technicals": technicals,
        "valuation": valuation,
        "risks": risks,
        "bull_case": bull,
        "bear_case": bear,
        "scenarios": scenario_analysis(fundamentals, valuation),
        "thesis": generate_investment_thesis(fundamentals, valuation, technicals, bull, bear, info),
        "catalysts": identify_catalysts(fundamentals, valuation, technicals, info),
        "entry_scenarios": entry_scenarios(fundamentals, valuation, technicals),
        "governance": governance_notes(shareholding, fundamentals, info),
        "scores": score_stock(fundamentals, valuation, technicals, risks, info),
        "peers": get_peer_symbols(symbol),
        "is_demo": info.get("is_demo", False),
        "data_sources": {
            "company": info.get("source"),
            "price": price.get("source"),
            "financials": financials.get("source"),
            "shareholding": shareholding.get("source"),
        },
        "disclaimer": (
            "For education and research only. Not investment advice. StockIQ India is not a "
            "SEBI-registered investment adviser. Verify every figure against the company's "
            "own filings before acting on it."
        ),
    }
