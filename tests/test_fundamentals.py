"""
tests/test_fundamentals.py
==========================
Tests for the financial maths. These need no Flask app and no internet - they
are plain functions with plain numbers, which is exactly why the calculations
were kept in utils/ and analysis/ rather than inside the routes.
"""

from analysis.fundamentals import analyze_fundamentals, analyze_growth
from utils.calculations import (
    cagr, debt_to_equity, ebitda_margin, free_cash_flow, interest_coverage,
    percent_change, roce, roe, safe_divide,
)


# ---------------------------------------------------------------------------
# The individual formulas
# ---------------------------------------------------------------------------

def test_safe_divide_handles_zero_and_none():
    """Division must never crash the page, however bad the data is."""
    assert safe_divide(10, 2) == 5
    assert safe_divide(10, 0) is None        # not ZeroDivisionError
    assert safe_divide(None, 5) is None
    assert safe_divide(10, None) is None
    assert safe_divide("abc", 2) is None


def test_percent_change():
    assert percent_change(110, 100) == 10.0
    assert percent_change(90, 100) == -10.0
    assert percent_change(100, 0) is None    # cannot grow from zero


def test_cagr_matches_hand_calculation():
    """Doubling over 5 years is about 14.87% a year: 1.1487 ** 5 = 2."""
    assert round(cagr(200, 100, 5), 2) == 14.87
    assert cagr(200, 0, 5) is None           # undefined from zero
    assert cagr(-50, 100, 5) is None         # undefined for a negative end value


def test_margins_and_returns():
    assert ebitda_margin(200, 1000) == 20.0
    assert roe(150, 1000) == 15.0
    # ROCE uses debt + equity as the capital employed: 250 / (400 + 600) = 25%
    assert roce(250, 400, 600) == 25.0
    assert roe(150, 0) is None


def test_debt_and_coverage():
    assert debt_to_equity(500, 1000) == 0.5
    assert debt_to_equity(0, 1000) == 0.0
    assert interest_coverage(300, 50) == 6.0
    assert interest_coverage(300, 0) is None


def test_free_cash_flow_treats_capex_as_an_outflow():
    """Capex may arrive positive or negative depending on the source, so the
    function takes its absolute value either way."""
    assert free_cash_flow(1000, 300) == 700
    assert free_cash_flow(1000, -300) == 700
    assert free_cash_flow(None, 300) is None


# ---------------------------------------------------------------------------
# The analysis layer
# ---------------------------------------------------------------------------

SAMPLE_YEARS = [
    {"period": "FY2022", "revenue": 1000, "net_profit": 100, "eps": 10, "ebitda": 200,
     "ebit": 160, "equity": 800, "total_debt": 200, "interest_expense": 20,
     "operating_cash_flow": 130, "capex": 40, "cash": 150, "total_assets": 1400,
     "current_assets": 600, "current_liabilities": 300, "receivables": 150},
    {"period": "FY2023", "revenue": 1200, "net_profit": 130, "eps": 13, "ebitda": 250,
     "ebit": 200, "equity": 900, "total_debt": 180, "interest_expense": 18,
     "operating_cash_flow": 160, "capex": 45, "cash": 180, "total_assets": 1500,
     "current_assets": 650, "current_liabilities": 320, "receivables": 170},
]


def test_growth_uses_the_latest_year():
    growth = analyze_growth(SAMPLE_YEARS)
    assert growth["available"] is True
    assert growth["latest_period"] == "FY2023"
    assert growth["revenue"] == 1200
    assert growth["revenue_yoy_pct"] == 20.0     # 1000 -> 1200
    assert growth["profit_yoy_pct"] == 30.0      # 100 -> 130


def test_analyze_fundamentals_reports_missing_data_honestly():
    """With no statements the result must say so, not invent zeros."""
    result = analyze_fundamentals({"annual": []})
    assert result["available"] is False
    assert "reason" in result


def test_analyze_fundamentals_computes_every_section():
    result = analyze_fundamentals({"annual": SAMPLE_YEARS, "units": "Rs crore"})
    assert result["available"] is True

    health = result["financial_health"]
    assert health["debt_to_equity"] == 0.2       # 180 / 900
    assert health["free_cash_flow"] == 115       # 160 - 45

    profitability = result["profitability"]
    assert profitability["ebitda_margin_pct"] == round(250 / 1200 * 100, 2)
    assert profitability["margin_trend"] == "expanding"   # 20.0% -> 20.83%
