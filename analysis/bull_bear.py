"""
analysis/bull_bear.py
=====================
The two sides of the argument, plus scenario analysis and the investment thesis.

Every point is built from a number that was actually computed, and every point
carries the number with it. That way a reader can disagree with the conclusion
while still seeing the evidence - which is the whole purpose of the app.
"""

from utils.calculations import round_or_none


def generate_bull_case(fundamentals, valuation, technicals, company_info=None):
    """Reasons the company could do well, ranked by how strong the evidence is."""
    points = []
    score = 0

    growth = (fundamentals or {}).get("growth") or {}
    profitability = (fundamentals or {}).get("profitability") or {}
    health = (fundamentals or {}).get("financial_health") or {}

    # ---- growth ----------------------------------------------------------
    cagr_5y = growth.get("revenue_cagr_5y_pct")
    if cagr_5y is not None and cagr_5y > 12:
        score += 2
        points.append({
            "point": "Sustained revenue growth",
            "evidence": "Revenue compounded at about %.1f%% a year over the available history." % cagr_5y,
            "strength": "strong",
        })
    elif cagr_5y is not None and cagr_5y > 7:
        score += 1
        points.append({
            "point": "Steady revenue growth",
            "evidence": "Revenue compounded at about %.1f%% a year." % cagr_5y,
            "strength": "moderate",
        })

    profit_cagr = growth.get("profit_cagr_3y_pct")
    if profit_cagr is not None and profit_cagr > (cagr_5y or 0) and profit_cagr > 10:
        score += 1
        points.append({
            "point": "Profit growing faster than sales",
            "evidence": "Profit compounded at about %.1f%% versus revenue at %.1f%%, which is "
                        "what operating leverage looks like." % (profit_cagr, cagr_5y or 0),
            "strength": "moderate",
        })

    # ---- profitability ---------------------------------------------------
    roe_value = profitability.get("roe_pct")
    if roe_value is not None and roe_value > 18:
        score += 2
        points.append({
            "point": "High return on equity",
            "evidence": "ROE of about %.1f%% means each rupee of shareholder capital is "
                        "producing strong profit." % roe_value,
            "strength": "strong",
        })
    elif roe_value is not None and roe_value > 13:
        score += 1
        points.append({
            "point": "Reasonable return on equity",
            "evidence": "ROE of about %.1f%%." % roe_value,
            "strength": "moderate",
        })

    roce_value = profitability.get("roce_pct")
    if roce_value is not None and roce_value > 18:
        score += 1
        points.append({
            "point": "Efficient use of total capital",
            "evidence": "ROCE of about %.1f%% - the business earns well on borrowed money "
                        "as well as on equity." % roce_value,
            "strength": "moderate",
        })

    if profitability.get("margin_trend") == "expanding":
        score += 1
        points.append({
            "point": "Margins are expanding",
            "evidence": "EBITDA margin improved by %.1f percentage points year on year."
                        % (profitability.get("margin_change_pp") or 0),
            "strength": "moderate",
        })

    # ---- balance sheet and cash -----------------------------------------
    d_e = health.get("debt_to_equity")
    if d_e is not None and d_e < 0.3:
        score += 2
        points.append({
            "point": "Strong balance sheet",
            "evidence": "Debt is only %.2f times equity, so the company is not dependent on "
                        "lenders staying friendly." % d_e,
            "strength": "strong",
        })
    elif d_e is not None and d_e < 0.7:
        score += 1
        points.append({
            "point": "Comfortable debt level",
            "evidence": "Debt is %.2f times equity." % d_e,
            "strength": "moderate",
        })

    fcf = health.get("free_cash_flow")
    if fcf is not None and fcf > 0:
        score += 1
        points.append({
            "point": "Generates free cash",
            "evidence": "Free cash flow of about Rs %.0f crore after capital spending." % fcf,
            "strength": "moderate",
        })

    # ---- valuation -------------------------------------------------------
    verdict = ((valuation or {}).get("verdict") or {}).get("label")
    if verdict == "Undervalued":
        score += 2
        points.append({
            "point": "Valuation looks undemanding",
            "evidence": "The valuation screen classes it as Undervalued on the multiples available.",
            "strength": "strong",
        })
    elif verdict == "Fairly Valued":
        score += 1
        points.append({
            "point": "Valuation is not stretched",
            "evidence": "The valuation screen classes it as Fairly Valued.",
            "strength": "moderate",
        })

    # ---- technicals ------------------------------------------------------
    if (technicals or {}).get("available") and technicals.get("view") == "BULLISH":
        score += 1
        points.append({
            "point": "Price trend is constructive",
            "evidence": "Price sits above its key moving averages. This describes what has "
                        "already happened, not what will happen next.",
            "strength": "weak",
        })

    if not points:
        points.append({
            "point": "No strong positives stood out in the available data",
            "evidence": "None of the bull-case rules were triggered by the metrics we could compute.",
            "strength": "weak",
        })

    bull_score = max(0, min(10, round(score * 10.0 / 12.0, 1)))
    return {
        "available": True,
        "points": points,
        "bull_score": bull_score,
        "score_raw": score,
        "score_max": 12,
        "methodology": (
            "Each rule above contributes 1 point (moderate evidence) or 2 points (strong "
            "evidence), out of a possible 12. The total is rescaled to 0-10. A high score "
            "means more of our positive checks were met, not that the stock will rise."
        ),
    }


def generate_bear_case(fundamentals, valuation, technicals, risk_result=None):
    """Reasons the company could disappoint. Same evidence-first structure."""
    points = []
    score = 0

    growth = (fundamentals or {}).get("growth") or {}
    profitability = (fundamentals or {}).get("profitability") or {}
    health = (fundamentals or {}).get("financial_health") or {}

    verdict = ((valuation or {}).get("verdict") or {}).get("label")
    if verdict == "Very Expensive":
        score += 3
        points.append({
            "point": "Demanding valuation",
            "evidence": "The valuation screen classes it as Very Expensive, so a lot of future "
                        "growth is already reflected in the price.",
            "strength": "strong",
        })
    elif verdict == "Moderately Expensive":
        score += 2
        points.append({
            "point": "Full valuation",
            "evidence": "The valuation screen classes it as Moderately Expensive.",
            "strength": "moderate",
        })

    revenue_growth = growth.get("revenue_yoy_pct")
    if revenue_growth is not None and revenue_growth < 0:
        score += 3
        points.append({
            "point": "Revenue is falling",
            "evidence": "Revenue declined %.1f%% year on year." % abs(revenue_growth),
            "strength": "strong",
        })
    elif revenue_growth is not None and revenue_growth < 6:
        score += 1
        points.append({
            "point": "Slow growth",
            "evidence": "Revenue grew only %.1f%% year on year." % revenue_growth,
            "strength": "moderate",
        })

    if profitability.get("margin_trend") == "compressing":
        score += 2
        points.append({
            "point": "Margins are compressing",
            "evidence": "EBITDA margin fell %.1f percentage points year on year."
                        % abs(profitability.get("margin_change_pp") or 0),
            "strength": "moderate",
        })

    d_e = health.get("debt_to_equity")
    if d_e is not None and d_e > 1.5:
        score += 3
        points.append({
            "point": "High debt",
            "evidence": "Debt is %.2f times equity, which amplifies both good and bad years." % d_e,
            "strength": "strong",
        })
    elif d_e is not None and d_e > 0.8:
        score += 1
        points.append({
            "point": "Meaningful debt",
            "evidence": "Debt is %.2f times equity." % d_e,
            "strength": "moderate",
        })

    coverage = health.get("interest_coverage")
    if coverage is not None and coverage < 3:
        score += 2
        points.append({
            "point": "Thin interest cover",
            "evidence": "Operating profit covers interest only %.1f times." % coverage,
            "strength": "moderate",
        })

    fcf = health.get("free_cash_flow")
    if fcf is not None and fcf < 0:
        score += 2
        points.append({
            "point": "Negative free cash flow",
            "evidence": "The business consumed about Rs %.0f crore of cash after capital "
                        "spending." % abs(fcf),
            "strength": "moderate",
        })

    conversion = health.get("cash_conversion")
    if conversion is not None and conversion < 0.7:
        score += 1
        points.append({
            "point": "Profit is not fully converting into cash",
            "evidence": "Operating cash flow was %.0f%% of reported profit." % (conversion * 100),
            "strength": "moderate",
        })

    roe_value = profitability.get("roe_pct")
    if roe_value is not None and roe_value < 10:
        score += 1
        points.append({
            "point": "Low return on equity",
            "evidence": "ROE of about %.1f%% is modest relative to what a saver can earn "
                        "elsewhere in India." % roe_value,
            "strength": "moderate",
        })

    if (technicals or {}).get("available") and technicals.get("view") == "BEARISH":
        score += 1
        points.append({
            "point": "Weak price trend",
            "evidence": "Price is below its key moving averages.",
            "strength": "weak",
        })

    # Competition and disruption are qualitative and cannot be measured from a
    # balance sheet, so we raise them as questions rather than as findings.
    points.append({
        "point": "Competitive and regulatory risk cannot be read off the numbers",
        "evidence": "New entrants, pricing pressure, technology change and policy shifts do "
                    "not appear in past financials. Read the annual report's risk section "
                    "and management discussion for these.",
        "strength": "context",
    })

    if risk_result:
        high_risks = [r for r in risk_result.get("risks", []) if r["level"] == "High"]
        if high_risks:
            score += min(2, len(high_risks))

    risk_score = max(0, min(10, round(score * 10.0 / 14.0, 1)))
    return {
        "available": True,
        "points": points,
        "risk_score": risk_score,
        "score_raw": score,
        "score_max": 14,
        "methodology": (
            "Each concern contributes 1 to 3 points depending on how strong the evidence is, "
            "out of a possible 14, rescaled to 0-10. A higher risk score means more of our "
            "warning checks fired - it is not a probability of loss."
        ),
    }


def scenario_analysis(fundamentals, valuation):
    """Bull / Base / Bear scenarios built from EXPLICIT assumptions.

    IMPORTANT: these are ASSUMPTIONS, not forecasts. Every input is printed on
    screen next to the output so the reader can change it in their head, and the
    label "Assumption" is attached to each one.
    """
    growth = (fundamentals or {}).get("growth") or {}
    ratios = (valuation or {}).get("ratios") or {}

    base_growth = growth.get("revenue_cagr_3y_pct")
    if base_growth is None:
        base_growth = growth.get("revenue_yoy_pct")
    eps = ratios.get("eps")
    pe = ratios.get("pe_ratio")

    if eps is None or pe is None or base_growth is None:
        return {
            "available": False,
            "reason": "Scenario analysis needs EPS, P/E and a growth rate. At least one is "
                      "unavailable, so no scenario is shown rather than an invented one.",
        }

    def build(name, growth_rate, multiple, notes):
        # Three years of compounding at the assumed growth rate.
        future_eps = eps * ((1 + growth_rate / 100.0) ** 3)
        implied_price = future_eps * multiple
        return {
            "scenario": name,
            "assumptions": notes,
            "assumed_eps_growth_pct": round_or_none(growth_rate),
            "assumed_exit_pe": round_or_none(multiple),
            "implied_eps_year_3": round_or_none(future_eps),
            "illustrative_price_year_3": round_or_none(implied_price),
            "vs_today_pct": round_or_none(
                (implied_price - ratios["price"]) / ratios["price"] * 100
            ) if ratios.get("price") else None,
        }

    return {
        "available": True,
        "label": "Assumption-driven scenarios",
        "base_inputs": {
            "current_eps": eps,
            "current_pe": pe,
            "historical_growth_used_pct": round_or_none(base_growth),
        },
        "scenarios": [
            build("Bull", base_growth * 1.5 + 3, pe * 1.15, [
                "Revenue growth runs above the recent trend",
                "Margins expand as scale improves",
                "The industry grows and the company gains share",
                "Investors are willing to pay a slightly higher multiple",
            ]),
            build("Base", base_growth, pe, [
                "Growth continues at roughly the recent three-year rate",
                "Margins stay broadly where they are",
                "The valuation multiple is unchanged",
            ]),
            build("Bear", max(-10.0, base_growth * 0.3 - 4), pe * 0.75, [
                "Growth slows sharply",
                "Margins compress under competition or cost pressure",
                "Investors pay a lower multiple for the same earnings",
            ]),
        ],
        "disclaimer": (
            "These are illustrations of arithmetic, not forecasts. Change any assumption and "
            "the output changes completely. Nothing here is a price target."
        ),
    }


def generate_investment_thesis(fundamentals, valuation, technicals, bull, bear, company_info=None):
    """The summary an investor would actually write for themselves."""
    name = (company_info or {}).get("company_name") or (company_info or {}).get("symbol") or "This company"

    likes = [p["point"] + " - " + p["evidence"] for p in bull.get("points", [])[:5]]
    dislikes = [p["point"] + " - " + p["evidence"] for p in bear.get("points", [])[:5]]

    growth = (fundamentals or {}).get("growth") or {}
    health = (fundamentals or {}).get("financial_health") or {}

    must_go_right = [
        "Revenue growth of at least the recent %s%% rate has to continue."
        % (growth.get("revenue_cagr_3y_pct") or growth.get("revenue_yoy_pct")),
        "Margins must hold, so cost inflation has to be passed on to customers.",
        "Operating cash flow must keep tracking reported profit.",
    ]
    if (health.get("debt_to_equity") or 0) > 0.8:
        must_go_right.append("Debt has to come down, or at least not rise further.")
    if ((valuation or {}).get("verdict") or {}).get("label") in ("Very Expensive", "Moderately Expensive"):
        must_go_right.append(
            "Earnings have to grow into the current valuation, because the multiple is "
            "unlikely to expand from here."
        )

    would_break_it = [
        "Two or three consecutive quarters of falling revenue.",
        "EBITDA margin compressing without a clear, temporary explanation.",
        "Operating cash flow diverging further from reported profit.",
        "A sharp rise in debt, or in the share of promoter holding that is pledged.",
        "An auditor qualification, an unexpected CFO or CEO exit, or a governance event.",
        "A structural change in the industry that makes the company's advantage irrelevant.",
    ]

    bull_score = bull.get("bull_score") or 0
    risk_score = bear.get("risk_score") or 0
    if bull_score - risk_score >= 3:
        stance = "Bullish"
    elif risk_score - bull_score >= 3:
        stance = "Bearish"
    else:
        stance = "Neutral"

    return {
        "available": True,
        "company": name,
        "overall_view": stance,
        "view_method": (
            "Bull score %.1f minus risk score %.1f. A gap of 3 or more either way sets the "
            "stance; anything closer is Neutral." % (bull_score, risk_score)
        ),
        "why_investors_may_like": likes,
        "why_investors_may_avoid": dislikes,
        "what_must_go_right": must_go_right,
        "what_would_prove_it_wrong": would_break_it,
        "disclaimer": (
            "This is an educational summary of computed metrics. It is not investment advice, "
            "not a recommendation, and not a forecast."
        ),
    }
