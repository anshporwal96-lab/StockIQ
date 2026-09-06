"""
analysis/risk.py
================
Ranked risks, possible catalysts, governance observations, and the
"when could this be attractive / when should I be careful" scenarios.

TONE RULE
---------
Governance is the most sensitive area in Indian equity research. This module
never accuses anyone of anything. It reports what the disclosed numbers show
(for example "promoter holding fell 3 percentage points over four quarters")
and tells the reader where to verify it. Interpretation is always flagged as
interpretation.
"""

from utils.calculations import percent_change, round_or_none


def _add(risks, level, title, explanation):
    risks.append({"level": level, "title": title, "explanation": explanation})


def assess_risks(fundamentals, valuation, technicals, shareholding):
    """Build a risk list ranked High / Medium / Lower.

    Every entry states the NUMBER that triggered it, so the reader can disagree
    with our threshold and still see the underlying fact.
    """
    risks = []

    health = (fundamentals or {}).get("financial_health") or {}
    growth = (fundamentals or {}).get("growth") or {}
    profitability = (fundamentals or {}).get("profitability") or {}
    quality = (fundamentals or {}).get("earnings_quality") or {}

    # ---- balance sheet ---------------------------------------------------
    d_e = health.get("debt_to_equity")
    if d_e is not None:
        if d_e > 2:
            _add(risks, "High", "High leverage",
                 "Debt is %.2f times equity. Heavily indebted companies are far more "
                 "exposed to rising interest rates and to a weak year of trading." % d_e)
        elif d_e > 1:
            _add(risks, "Medium", "Meaningful debt",
                 "Debt is %.2f times equity. Manageable while profits hold up, but it "
                 "reduces the margin for error." % d_e)

    coverage = health.get("interest_coverage")
    if coverage is not None and coverage < 3:
        _add(risks, "High" if coverage < 1.5 else "Medium", "Thin interest cover",
             "Operating profit covers the interest bill only %.1f times. Below about 2 "
             "this becomes uncomfortable if earnings dip." % coverage)

    ratio = health.get("current_ratio")
    if ratio is not None and ratio < 1:
        _add(risks, "Medium", "Short-term liquidity",
             "Current assets are only %.2f times current liabilities, so short-term "
             "bills exceed short-term resources." % ratio)

    # ---- cash flow -------------------------------------------------------
    fcf = health.get("free_cash_flow")
    if fcf is not None and fcf < 0:
        _add(risks, "High", "Negative free cash flow",
             "The business consumed Rs %.0f crore of cash after capital spending in the "
             "latest year. That is normal during a big expansion, but it has to be "
             "funded from debt or fresh equity." % abs(fcf))

    conversion = health.get("cash_conversion")
    if conversion is not None and conversion < 0.6:
        _add(risks, "Medium", "Profit is not turning into cash",
             "Operating cash flow was only %.0f%% of reported profit. Check receivables "
             "and inventory in the annual report." % (conversion * 100))

    # ---- growth and margins ---------------------------------------------
    revenue_growth = growth.get("revenue_yoy_pct")
    if revenue_growth is not None and revenue_growth < 0:
        _add(risks, "High", "Revenue is shrinking",
             "Revenue fell %.1f%% year on year. Falling sales make every other ratio "
             "harder to sustain." % abs(revenue_growth))
    elif revenue_growth is not None and revenue_growth < 5:
        _add(risks, "Medium", "Slow growth",
             "Revenue grew only %.1f%% year on year, which is below typical nominal "
             "GDP growth in India." % revenue_growth)

    if profitability.get("margin_trend") == "compressing":
        _add(risks, "Medium", "Margins are compressing",
             "EBITDA margin fell %.1f percentage points versus the previous year. "
             "Sustained compression usually points to cost or pricing pressure."
             % abs(profitability.get("margin_change_pp") or 0))

    # ---- valuation -------------------------------------------------------
    verdict = ((valuation or {}).get("verdict") or {}).get("label")
    if verdict == "Very Expensive":
        _add(risks, "High", "Demanding valuation",
             "The valuation screen classes the stock as Very Expensive. When a lot of "
             "future growth is already in the price, even good results can disappoint.")
    elif verdict == "Moderately Expensive":
        _add(risks, "Medium", "Full valuation",
             "The stock is not obviously cheap on the metrics available, so returns "
             "depend more on earnings delivering than on the multiple re-rating.")

    # ---- technical -------------------------------------------------------
    if (technicals or {}).get("available"):
        if technicals.get("view") == "BEARISH":
            _add(risks, "Medium", "Weak price trend",
                 "Price is below its key moving averages. That is a description of "
                 "recent behaviour, not a forecast, but it does mean recent buyers are "
                 "sitting on losses.")
        volatility = (technicals.get("volatility") or {}).get("annualised_pct")
        if volatility is not None and volatility > 40:
            _add(risks, "Lower", "High volatility",
                 "Annualised volatility is about %.0f%%. Expect large swings in both "
                 "directions." % volatility)
        drawdown = (technicals.get("volatility") or {}).get("max_drawdown_pct")
        if drawdown is not None and drawdown < -35:
            _add(risks, "Lower", "History of deep falls",
                 "The largest peak-to-trough fall in this price window was %.0f%%. "
                 "A repeat is always possible." % drawdown)

    # ---- ownership -------------------------------------------------------
    ownership = analyze_shareholding_changes(shareholding)
    for observation in ownership.get("flags", []):
        _add(risks, "Medium", "Shareholding change", observation)

    # ---- earnings quality ------------------------------------------------
    for flag in quality.get("flags", []):
        _add(risks, "Medium", "Earnings quality observation", flag)

    if not risks:
        _add(risks, "Lower", "No specific flags from the available data",
             "Nothing in the metrics we could compute triggered a risk rule. That is "
             "not the same as 'low risk' - it reflects the limits of the data we have.")

    order = {"High": 0, "Medium": 1, "Lower": 2}
    risks.sort(key=lambda r: order.get(r["level"], 3))
    for index, risk in enumerate(risks, start=1):
        risk["rank"] = index

    return {
        "available": True,
        "risks": risks,
        "counts": {
            "high": sum(1 for r in risks if r["level"] == "High"),
            "medium": sum(1 for r in risks if r["level"] == "Medium"),
            "lower": sum(1 for r in risks if r["level"] == "Lower"),
        },
    }


def analyze_shareholding_changes(shareholding):
    """Describe how ownership has moved, without jumping to conclusions.

    A promoter selling is NOT automatically bearish (it can be estate planning,
    a pledge release, or an offer for sale to meet listing rules). An FII
    increase is NOT automatically bullish. We report the movement and say what
    to check.
    """
    quarters = (shareholding or {}).get("quarters") or []
    if len(quarters) < 2:
        return {
            "available": False,
            "reason": (shareholding or {}).get("reason")
                      or "Shareholding data is not available from the current provider.",
            "flags": [],
            "changes": [],
        }

    first, last = quarters[0], quarters[-1]
    changes = []
    for key, label in (
        ("promoter", "Promoter"), ("fii", "FII"), ("dii", "DII"), ("public", "Public"),
    ):
        if first.get(key) is None or last.get(key) is None:
            continue
        delta = last[key] - first[key]
        changes.append({
            "category": label,
            "from_pct": first[key],
            "to_pct": last[key],
            "change_pp": round_or_none(delta),
            "direction": "up" if delta > 0.05 else ("down" if delta < -0.05 else "flat"),
        })

    flags = []
    promoter_change = next((c for c in changes if c["category"] == "Promoter"), None)
    if promoter_change and promoter_change["change_pp"] is not None:
        if promoter_change["change_pp"] <= -2:
            flags.append(
                "Promoter holding fell from %.2f%% to %.2f%% across the last %d disclosed "
                "quarters. There are many legitimate reasons for this. Check the exchange "
                "filings for the stated reason before drawing a conclusion."
                % (promoter_change["from_pct"], promoter_change["to_pct"], len(quarters))
            )
        elif promoter_change["change_pp"] >= 2:
            flags.append(
                "Promoter holding rose from %.2f%% to %.2f%%. Promoters buying is often "
                "read positively, but check whether it came from open-market purchases, "
                "a preferential issue or a warrant conversion."
                % (promoter_change["from_pct"], promoter_change["to_pct"])
            )

    pledge = last.get("promoter_pledge_pct")
    if pledge is not None and pledge > 15:
        flags.append(
            "About %.1f%% of the promoter stake is disclosed as pledged. High pledging "
            "can force selling if the share price falls sharply." % pledge
        )

    return {
        "available": True,
        "changes": changes,
        "flags": flags,
        "latest": last,
        "note": (
            "Ownership changes are facts from exchange filings. Whether a change is good "
            "or bad depends on the reason behind it, which the filing itself usually gives."
        ),
    }


def identify_catalysts(fundamentals, valuation, technicals, company_info):
    """Things that could plausibly change the story, in either direction.

    These are POSSIBILITIES derived from the company's own situation, not
    predictions and not insider knowledge.
    """
    catalysts = []
    health = (fundamentals or {}).get("financial_health") or {}
    growth = (fundamentals or {}).get("growth") or {}
    industry = (company_info or {}).get("industry") or "this industry"

    catalysts.append({
        "catalyst": "Next quarterly results",
        "what_could_happen": "Revenue, margin and any management commentary are updated.",
        "why_it_matters": "It is the most regular checkpoint on whether the trend so far continues.",
        "potential_impact": "High",
        "direction": "either",
    })

    if (health.get("debt_to_equity") or 0) > 1:
        catalysts.append({
            "catalyst": "Debt reduction",
            "what_could_happen": "Repayment or refinancing lowers the interest bill.",
            "why_it_matters": "With debt at %.2f times equity, less interest flows straight to profit."
                              % health["debt_to_equity"],
            "potential_impact": "High",
            "direction": "positive",
        })

    if (growth.get("revenue_yoy_pct") or 0) < 5:
        catalysts.append({
            "catalyst": "Return to faster growth",
            "what_could_happen": "New orders, products or capacity lift revenue growth.",
            "why_it_matters": "Growth was only %s%% last year, so any acceleration would be noticed."
                              % growth.get("revenue_yoy_pct"),
            "potential_impact": "High",
            "direction": "positive",
        })

    catalysts.append({
        "catalyst": "Policy and regulation affecting %s" % industry,
        "what_could_happen": "Government policy, tariffs, taxation or sector rules change.",
        "why_it_matters": "Regulation can reset the economics of an entire sector at short notice.",
        "potential_impact": "Medium",
        "direction": "either",
    })

    catalysts.append({
        "catalyst": "Interest-rate direction",
        "what_could_happen": "The RBI shifts policy rates.",
        "why_it_matters": "Rates change both the cost of the company's debt and the multiple "
                          "investors are willing to pay for future earnings.",
        "potential_impact": "Medium",
        "direction": "either",
    })

    if (technicals or {}).get("available"):
        levels = technicals.get("levels") or {}
        if levels.get("breakout_level"):
            catalysts.append({
                "catalyst": "Move through Rs %s" % levels["breakout_level"],
                "what_could_happen": "Price clears the nearest resistance level identified from past peaks.",
                "why_it_matters": "Chart watchers treat that area as a decision point. It is a "
                                  "description of past price behaviour, not a target.",
                "potential_impact": "Low",
                "direction": "positive",
            })

    return {"available": True, "catalysts": catalysts}


def entry_scenarios(fundamentals, valuation, technicals):
    """"When could this become attractive?" - written as CONDITIONS, never as
    a buy signal.

    The brief is explicit: the app must not print BUY / SELL / HOLD. Instead we
    describe what would have to be true, so the reader forms their own view and
    can check later whether it actually happened.
    """
    attractive, wait, avoid = [], [], []

    verdict = ((valuation or {}).get("verdict") or {}).get("label")
    ratios = (valuation or {}).get("ratios") or {}
    band = (valuation or {}).get("historical_band") or {}
    health = (fundamentals or {}).get("financial_health") or {}
    growth = (fundamentals or {}).get("growth") or {}

    # ---- conditions that would make it more attractive -------------------
    if band.get("available") and band.get("median") and ratios.get("pe_ratio"):
        if ratios["pe_ratio"] > band["median"]:
            attractive.append(
                "The P/E falls back towards its own recent median of about %s "
                "(it is %s today)." % (band["median"], ratios["pe_ratio"])
            )
        else:
            attractive.append(
                "Earnings keep growing while the P/E stays near its recent median of %s, "
                "so the multiple is supported by profits rather than by optimism."
                % band["median"]
            )

    if (growth.get("revenue_yoy_pct") or 0) < 8:
        attractive.append("Revenue growth re-accelerates for two or more consecutive quarters.")
    else:
        attractive.append(
            "Revenue growth of about %s percent is sustained rather than a one-year spike."
            % growth.get("revenue_yoy_pct")
        )

    if (health.get("free_cash_flow") or 0) <= 0:
        attractive.append("Free cash flow turns positive and stays positive.")
    else:
        attractive.append("Free cash flow stays positive while capital spending continues.")

    if (technicals or {}).get("available"):
        levels = technicals.get("levels") or {}
        if levels.get("support"):
            attractive.append(
                "Price holds the nearest support area around Rs %s, which has held before."
                % levels["support"][0]
            )
        if technicals.get("view") == "BEARISH":
            attractive.append(
                "The price trend stabilises - for example price reclaiming its 200-day "
                "average of Rs %s." % (technicals.get("moving_averages") or {}).get("dma_200")
            )

    # ---- conditions that argue for waiting -------------------------------
    if verdict in ("Very Expensive", "Moderately Expensive"):
        wait.append(
            "The valuation stays in the '%s' bucket while earnings growth does not "
            "improve to match it." % verdict
        )
    if (growth.get("profit_yoy_pct") or 0) < 0:
        wait.append("Profit is still falling year on year, so earnings visibility is poor.")
    if (technicals or {}).get("available") and technicals.get("view") == "NEUTRAL":
        wait.append(
            "The price trend is directionless (ADX %s), so there is no hurry."
            % technicals.get("adx_14")
        )
    if not wait:
        wait.append(
            "The position would be larger than you could hold calmly through a 30 percent "
            "fall. That is a reason to wait regardless of what the analysis says."
        )

    # ---- conditions that argue for caution -------------------------------
    if (health.get("debt_to_equity") or 0) > 1.5:
        avoid.append("Debt rises further from the current %.2f times equity."
                     % health["debt_to_equity"])
    else:
        avoid.append("Debt starts rising materially without a matching rise in profit.")

    avoid.append("Operating cash flow keeps falling short of reported profit for several years.")
    avoid.append("Margins compress for three or more consecutive quarters with no explanation.")
    avoid.append(
        "Auditors qualify the accounts, senior management resign unexpectedly, or promoter "
        "pledging rises sharply."
    )
    avoid.append(
        "The reason you were interested in the first place stops being true. That is what "
        "a broken thesis looks like."
    )

    return {
        "available": True,
        "attractive_if": attractive,
        "wait_if": wait,
        "avoid_if": avoid,
        "disclaimer": (
            "These are educational scenarios, not personalised investment advice and not a "
            "recommendation to buy or sell. StockIQ India is not a SEBI-registered "
            "investment adviser."
        ),
    }


def governance_notes(shareholding, fundamentals, company_info):
    """Publicly-checkable governance observations, phrased carefully."""
    notes = []
    ownership = analyze_shareholding_changes(shareholding)

    if ownership.get("available"):
        latest = ownership.get("latest") or {}
        if latest.get("promoter") is not None:
            notes.append({
                "topic": "Promoter ownership",
                "observation": "Promoters hold about %.2f percent as per the latest disclosed quarter."
                               % latest["promoter"],
                "how_to_verify": "Shareholding pattern filed with NSE and BSE each quarter.",
            })
        if latest.get("promoter_pledge_pct") is not None:
            notes.append({
                "topic": "Pledged shares",
                "observation": "About %.1f percent of the promoter holding is disclosed as pledged."
                               % latest["promoter_pledge_pct"],
                "how_to_verify": "Pledge disclosures filed with the exchanges under SEBI rules.",
            })
        for flag in ownership.get("flags", []):
            notes.append({
                "topic": "Change in holding",
                "observation": flag,
                "how_to_verify": "Compare the last four quarterly shareholding patterns.",
            })

    quality = (fundamentals or {}).get("earnings_quality") or {}
    for flag in quality.get("flags", []):
        notes.append({
            "topic": "Reported numbers",
            "observation": flag,
            "how_to_verify": "Notes to accounts and the auditor report in the annual report.",
        })

    return {
        "available": True,
        "notes": notes,
        "not_covered": [
            "Related-party transactions",
            "Board independence and committee composition",
            "Auditor changes and qualifications",
            "Insider trading disclosures",
            "Buybacks and capital-allocation history",
        ],
        "not_covered_note": (
            "These require reading the annual report and exchange filings directly. This app "
            "has no licensed structured source for them, so it says nothing about them "
            "rather than guessing."
        ),
        "disclaimer": (
            "Nothing here is an allegation about any company, promoter or director. These are "
            "observations drawn from disclosed figures, with pointers to the primary "
            "documents where you can check them yourself."
        ),
    }
