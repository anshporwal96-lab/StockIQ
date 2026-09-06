"""
analysis/scoring.py
===================
The overall StockIQ score.

TRANSPARENCY IS THE POINT
-------------------------
A single number like "7.3/10" is only useful if you can see how it was built.
So every category below returns:

    score     the 0-10 result
    reason    the sentence explaining it
    inputs    the actual numbers used

and the UI prints all three. There is no hidden weighting and no machine
learning - just arithmetic you can check by hand.

A HIGH SCORE DOES NOT PREDICT RETURNS. It means more of our checks were met.
That warning is part of the returned data and is shown on screen.
"""


def _band(value, thresholds, reverse=False):
    """Map a number onto 0-10 using a list of (cutoff, score) pairs.

    With reverse=True a LOWER input scores higher (used for debt).
    """
    if value is None:
        return None
    for cutoff, score in thresholds:
        if (value <= cutoff) if reverse else (value >= cutoff):
            return score
    return 2


def score_stock(fundamentals, valuation, technicals, risk_result, company_info=None):
    """Produce the ten category scores plus a weighted overall score."""
    growth = (fundamentals or {}).get("growth") or {}
    profitability = (fundamentals or {}).get("profitability") or {}
    health = (fundamentals or {}).get("financial_health") or {}
    ratios = (valuation or {}).get("ratios") or {}
    categories = []

    def add(name, score, reason, inputs):
        categories.append({"category": name, "score": score, "reason": reason, "inputs": inputs})

    # 1. Business quality - proxied by return on capital employed.
    roce = profitability.get("roce_pct")
    add("Business Quality",
        _band(roce, [(25, 9), (20, 8), (15, 7), (12, 6), (9, 5), (6, 4)]),
        "Based on ROCE of %s percent. Companies that earn a high return on all the "
        "capital they use tend to be better businesses." % roce,
        {"roce_pct": roce})

    # 2. Growth - three-year revenue CAGR.
    revenue_cagr = growth.get("revenue_cagr_3y_pct")
    add("Growth",
        _band(revenue_cagr, [(20, 9), (15, 8), (11, 7), (8, 6), (5, 5), (2, 4)]),
        "Based on 3-year revenue CAGR of %s percent." % revenue_cagr,
        {"revenue_cagr_3y_pct": revenue_cagr, "revenue_yoy_pct": growth.get("revenue_yoy_pct")})

    # 3. Profitability - net margin.
    margin = profitability.get("pat_margin_pct")
    add("Profitability",
        _band(margin, [(20, 9), (15, 8), (11, 7), (8, 6), (5, 5), (2, 4)]),
        "Based on net profit margin of %s percent." % margin,
        {"pat_margin_pct": margin, "ebitda_margin_pct": profitability.get("ebitda_margin_pct")})

    # 4. Balance sheet - debt relative to equity (lower is better).
    d_e = health.get("debt_to_equity")
    add("Balance Sheet",
        _band(d_e, [(0.15, 9), (0.35, 8), (0.6, 7), (1.0, 6), (1.5, 4), (2.5, 3)], reverse=True),
        "Based on debt/equity of %s. Lower debt scores higher." % d_e,
        {"debt_to_equity": d_e, "interest_coverage": health.get("interest_coverage")})

    # 5. Cash flow - how much reported profit actually arrives as cash.
    conversion = health.get("cash_conversion")
    add("Cash Flow",
        _band(conversion, [(1.2, 9), (1.0, 8), (0.85, 7), (0.7, 6), (0.5, 4)]),
        "Based on operating cash flow divided by net profit (%s)." % conversion,
        {"cash_conversion": conversion, "free_cash_flow": health.get("free_cash_flow")})

    # 6. Management - proxied by ROE. This is a WEAK proxy and we say so,
    #    because there is no licensed governance dataset behind it.
    roe = profitability.get("roe_pct")
    add("Management",
        _band(roe, [(22, 8), (18, 7), (14, 6), (10, 5), (6, 4)]),
        "PROXY ONLY: based on ROE of %s percent. A real assessment of management needs "
        "capital-allocation history, related-party transactions and governance records, "
        "for which this app has no licensed source." % roe,
        {"roe_pct": roe, "is_proxy": True})

    # 7. Valuation - the classification from the valuation module.
    verdict = ((valuation or {}).get("verdict") or {}).get("label")
    valuation_scores = {
        "Undervalued": 9, "Fairly Valued": 7,
        "Moderately Expensive": 5, "Very Expensive": 3,
    }
    add("Valuation",
        valuation_scores.get(verdict),
        "Based on the valuation classification '%s' (P/E %s, EV/EBITDA %s)."
        % (verdict, ratios.get("pe_ratio"), ratios.get("ev_ebitda")),
        {"label": verdict, "pe_ratio": ratios.get("pe_ratio"), "peg_ratio": ratios.get("peg_ratio")})

    # 8. Industry - deliberately NOT scored. Judging an industry needs sector
    #    growth and market-share data we have no licensed source for.
    add("Industry", None,
        "NOT SCORED: industry attractiveness needs sector growth and market-share data "
        "that this app cannot access. Sector on file: %s."
        % ((company_info or {}).get("sector") or "unknown"),
        {"sector": (company_info or {}).get("sector")})

    # 9. Technicals - the technical view, deliberately given a small weight.
    technical_view = (technicals or {}).get("view")
    add("Technicals",
        {"BULLISH": 8, "NEUTRAL": 5, "BEARISH": 3}.get(technical_view),
        "Based on the technical view '%s' (RSI %s, ADX %s). This describes past price "
        "behaviour only." % (technical_view, (technicals or {}).get("rsi_14"),
                             (technicals or {}).get("adx_14")),
        {"view": technical_view})

    # 10. Risk - fewer severe flags scores higher.
    counts = (risk_result or {}).get("counts") or {}
    high = counts.get("high", 0)
    medium = counts.get("medium", 0)
    add("Risk",
        max(2, 9 - high * 2 - medium) if risk_result else None,
        "Based on %d high and %d medium risk flags. Each high flag costs 2 points and "
        "each medium flag 1, starting from 9." % (high, medium),
        {"high_flags": high, "medium_flags": medium})

    # ---- overall ---------------------------------------------------------
    # Weights are declared in the open. Fundamentals dominate on purpose: this
    # is a research tool, not a trading tool.
    weights = {
        "Business Quality": 1.5, "Growth": 1.5, "Profitability": 1.5,
        "Balance Sheet": 1.5, "Cash Flow": 1.5, "Management": 1.0,
        "Valuation": 1.5, "Industry": 0.0, "Technicals": 0.5, "Risk": 1.0,
    }

    weighted_total = 0.0
    weight_used = 0.0
    scored = 0
    for category in categories:
        weight = weights.get(category["category"], 0)
        if category["score"] is not None and weight:
            weighted_total += category["score"] * weight
            weight_used += weight
            scored += 1

    overall = round(weighted_total / weight_used, 1) if weight_used else None

    return {
        "available": overall is not None,
        "categories": categories,
        "weights": weights,
        "overall_score": overall,
        "scored_categories": scored,
        "methodology": (
            "Each category is scored 0-10 from the single metric named in its reason, then "
            "averaged using the weights shown. Categories with no data are excluded rather "
            "than filled in with a guess."
        ),
        "warning": (
            "This score summarises how many of our checks the company met, using the data we "
            "could obtain. It is not a prediction of future returns, and a higher score does "
            "not mean the stock will go up."
        ),
    }
