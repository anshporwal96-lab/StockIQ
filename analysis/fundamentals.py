"""
analysis/fundamentals.py
========================
Turns raw financial statements into the ratios an investor actually looks at.

DESIGN RULE FOR THIS WHOLE FOLDER
---------------------------------
Python does the ARITHMETIC. The AI only EXPLAINS the result.
That is why every number the AI ever sees is computed here first - it cannot
invent a growth rate, because the growth rate is handed to it.

Every function returns None (never 0, never a guess) when the input data is
missing, and the UI prints "Data unavailable" for None.
"""

from utils.calculations import (
    cagr, current_ratio, debt_to_equity, ebitda_margin, free_cash_flow,
    interest_coverage, pat_margin, percent_change, roa, roce, roe,
    round_or_none, safe_divide,
)


def _latest_and_previous(rows):
    """Grab the newest year and the one before it. Statements arrive oldest
    first, so the newest is the last item."""
    if not rows:
        return None, None
    latest = rows[-1]
    previous = rows[-2] if len(rows) > 1 else None
    return latest, previous


def analyze_growth(annual_rows):
    """Revenue and profit growth: latest year, plus 3- and 5-year CAGR."""
    latest, previous = _latest_and_previous(annual_rows)
    if not latest:
        return {"available": False, "reason": "No annual financial data."}

    revenues = [r.get("revenue") for r in annual_rows]
    profits = [r.get("net_profit") for r in annual_rows]

    def growth_over(series, years):
        """CAGR across `years` full years, if we have that much history."""
        if len(series) < years + 1:
            return None
        return cagr(series[-1], series[-(years + 1)], years)

    return {
        "available": True,
        "latest_period": latest.get("period"),
        "revenue": latest.get("revenue"),
        "revenue_yoy_pct": round_or_none(
            percent_change(latest.get("revenue"), previous.get("revenue")) if previous else None
        ),
        "revenue_cagr_3y_pct": round_or_none(growth_over(revenues, 3)),
        "revenue_cagr_5y_pct": round_or_none(growth_over(revenues, 4)),
        "profit": latest.get("net_profit"),
        "profit_yoy_pct": round_or_none(
            percent_change(latest.get("net_profit"), previous.get("net_profit")) if previous else None
        ),
        "profit_cagr_3y_pct": round_or_none(growth_over(profits, 3)),
        "profit_cagr_5y_pct": round_or_none(growth_over(profits, 4)),
        "eps": latest.get("eps"),
        "eps_yoy_pct": round_or_none(
            percent_change(latest.get("eps"), previous.get("eps")) if previous else None
        ),
        "history": [
            {
                "period": row.get("period"),
                "revenue": row.get("revenue"),
                "net_profit": row.get("net_profit"),
                "eps": row.get("eps"),
            }
            for row in annual_rows
        ],
    }


def analyze_profitability(annual_rows):
    """Margins and returns on capital - is this a GOOD business, not just a
    big one?"""
    latest, previous = _latest_and_previous(annual_rows)
    if not latest:
        return {"available": False, "reason": "No annual financial data."}

    current_ebitda_margin = ebitda_margin(latest.get("ebitda"), latest.get("revenue"))
    previous_ebitda_margin = (
        ebitda_margin(previous.get("ebitda"), previous.get("revenue")) if previous else None
    )

    margin_trend = None
    if current_ebitda_margin is not None and previous_ebitda_margin is not None:
        difference = current_ebitda_margin - previous_ebitda_margin
        if difference > 0.5:
            margin_trend = "expanding"
        elif difference < -0.5:
            margin_trend = "compressing"
        else:
            margin_trend = "stable"

    return {
        "available": True,
        "latest_period": latest.get("period"),
        "ebitda": latest.get("ebitda"),
        "ebitda_margin_pct": round_or_none(current_ebitda_margin),
        "ebit": latest.get("ebit"),
        "pat": latest.get("net_profit"),
        "pat_margin_pct": round_or_none(pat_margin(latest.get("net_profit"), latest.get("revenue"))),
        "eps": latest.get("eps"),
        "margin_trend": margin_trend,
        "margin_change_pp": round_or_none(
            current_ebitda_margin - previous_ebitda_margin
            if (current_ebitda_margin is not None and previous_ebitda_margin is not None)
            else None
        ),
        "roe_pct": round_or_none(roe(latest.get("net_profit"), latest.get("equity"))),
        "roce_pct": round_or_none(
            roce(latest.get("ebit"), latest.get("total_debt"), latest.get("equity"))
        ),
        "roa_pct": round_or_none(roa(latest.get("net_profit"), latest.get("total_assets"))),
        "margin_history": [
            {
                "period": row.get("period"),
                "ebitda_margin_pct": round_or_none(
                    ebitda_margin(row.get("ebitda"), row.get("revenue"))
                ),
                "pat_margin_pct": round_or_none(
                    pat_margin(row.get("net_profit"), row.get("revenue"))
                ),
            }
            for row in annual_rows
        ],
    }


def analyze_financial_health(annual_rows):
    """Balance sheet and cash flow: can the company survive a bad year?"""
    latest, _ = _latest_and_previous(annual_rows)
    if not latest:
        return {"available": False, "reason": "No annual financial data."}

    fcf = latest.get("free_cash_flow")
    if fcf is None:
        fcf = free_cash_flow(latest.get("operating_cash_flow"), latest.get("capex"))

    # "Cash conversion" compares reported profit with cash actually collected.
    # A company can book a sale as profit long before the cash arrives, so a
    # ratio well below 1 for several years is worth a closer look.
    cash_conversion = safe_divide(latest.get("operating_cash_flow"), latest.get("net_profit"))

    net_debt = None
    if latest.get("total_debt") is not None and latest.get("cash") is not None:
        net_debt = latest["total_debt"] - latest["cash"]

    return {
        "available": True,
        "latest_period": latest.get("period"),
        "total_debt": latest.get("total_debt"),
        "cash": latest.get("cash"),
        "net_debt": round_or_none(net_debt, 1),
        "equity": latest.get("equity"),
        "debt_to_equity": round_or_none(
            debt_to_equity(latest.get("total_debt"), latest.get("equity"))
        ),
        "interest_coverage": round_or_none(
            interest_coverage(latest.get("ebit"), latest.get("interest_expense"))
        ),
        "current_ratio": round_or_none(
            current_ratio(latest.get("current_assets"), latest.get("current_liabilities"))
        ),
        "operating_cash_flow": latest.get("operating_cash_flow"),
        "capex": latest.get("capex"),
        "free_cash_flow": round_or_none(fcf, 1),
        "cash_conversion": round_or_none(cash_conversion),
        "history": [
            {
                "period": row.get("period"),
                "total_debt": row.get("total_debt"),
                "cash": row.get("cash"),
                "operating_cash_flow": row.get("operating_cash_flow"),
                "free_cash_flow": row.get("free_cash_flow"),
                "debt_to_equity": round_or_none(
                    debt_to_equity(row.get("total_debt"), row.get("equity"))
                ),
            }
            for row in annual_rows
        ],
    }


def analyze_earnings_quality(annual_rows, quarterly_rows=None):
    """Look for gaps between reported profit and actual cash.

    IMPORTANT: these are OBSERVATIONS, not accusations. A profit/cash gap has
    many innocent explanations (a fast-growing company funds more receivables
    and inventory). We describe what the numbers show and say what to check.
    """
    observations = []
    flags = []

    if annual_rows:
        latest = annual_rows[-1]

        conversion = safe_divide(latest.get("operating_cash_flow"), latest.get("net_profit"))
        if conversion is not None:
            if conversion < 0.6:
                flags.append(
                    "Operating cash flow was only %.0f%% of reported net profit in %s. "
                    "Worth checking receivables, inventory and any one-off items in the notes."
                    % (conversion * 100, latest.get("period"))
                )
            elif conversion > 1.1:
                observations.append(
                    "Operating cash flow exceeded reported profit, which usually points to "
                    "healthy cash collection."
                )

        # Receivables growing much faster than sales can mean customers are
        # paying more slowly.
        if len(annual_rows) >= 2:
            previous = annual_rows[-2]
            receivable_growth = percent_change(latest.get("receivables"), previous.get("receivables"))
            revenue_growth = percent_change(latest.get("revenue"), previous.get("revenue"))
            if (
                receivable_growth is not None
                and revenue_growth is not None
                and receivable_growth > revenue_growth + 15
            ):
                flags.append(
                    "Receivables grew %.1f%% while revenue grew %.1f%%. Customers may be "
                    "paying more slowly. Check the ageing schedule in the annual report."
                    % (receivable_growth, revenue_growth)
                )

    # Exceptional items distort a quarter, so the headline number can flatter
    # or understate the underlying business.
    if quarterly_rows:
        for quarter in quarterly_rows[-4:]:
            exceptional = quarter.get("exceptional_items")
            profit = quarter.get("net_profit")
            if exceptional and profit and abs(exceptional) > abs(profit) * 0.08:
                flags.append(
                    "%s included an exceptional item of about Rs %.1f crore. Compare the "
                    "underlying profit, not just the headline number."
                    % (quarter.get("period"), exceptional)
                )

    return {
        "available": bool(annual_rows),
        "observations": observations,
        "flags": flags,
        "note": (
            "These are observations drawn from the reported figures, not conclusions "
            "about accounting practices. Always read the auditor report and the notes "
            "to accounts before drawing your own."
        ),
    }


def analyze_fundamentals(financials, quarterly=None):
    """The single entry point used by the routes and the AI service.

    Combines growth, profitability, financial health and earnings quality into
    one dictionary.
    """
    annual_rows = (financials or {}).get("annual") or []
    quarterly_rows = (quarterly or {}).get("quarters") or []

    if not annual_rows:
        return {
            "available": False,
            "reason": "No annual financial statements were returned for this company.",
            "source": (financials or {}).get("source"),
            "is_demo": (financials or {}).get("is_demo", False),
        }

    return {
        "available": True,
        "growth": analyze_growth(annual_rows),
        "profitability": analyze_profitability(annual_rows),
        "financial_health": analyze_financial_health(annual_rows),
        "earnings_quality": analyze_earnings_quality(annual_rows, quarterly_rows),
        "units": financials.get("units"),
        "source": financials.get("source"),
        "as_of": financials.get("as_of"),
        "is_demo": financials.get("is_demo", False),
    }
