"""
analysis/valuation.py
=====================
How expensive is the stock relative to what the business earns and owns?

Valuation is the most easily abused part of stock analysis, so this module is
deliberately conservative:

  * Every ratio is computed from figures the provider actually returned.
  * Anything we cannot compute is None - never estimated, never "roughly".
  * The historical P/E band is clearly labelled an APPROXIMATION, because it
    uses today's earnings against past prices. The UI repeats that caveat.
"""

from utils.calculations import (
    cagr, enterprise_value, median, percent_change, round_or_none, safe_divide,
)


def compute_ratios(price_data, company_info, financials):
    """The core valuation multiples for the latest reported year."""
    annual_rows = (financials or {}).get("annual") or []
    if not annual_rows or not price_data:
        return {"available": False, "reason": "Not enough data to value this company."}

    latest = annual_rows[-1]
    price = price_data.get("price")
    market_cap = (company_info or {}).get("market_cap_cr")
    shares = (company_info or {}).get("shares_outstanding_cr")

    # Derive market cap only when we genuinely have both inputs.
    if market_cap is None and price and shares:
        market_cap = price * shares

    eps = latest.get("eps")
    book_value_per_share = safe_divide(latest.get("equity"), shares) if shares else None

    pe_ratio = safe_divide(price, eps) if (price and eps and eps > 0) else None
    pb_ratio = safe_divide(price, book_value_per_share) if book_value_per_share else None
    ps_ratio = safe_divide(market_cap, latest.get("revenue"))

    ev = enterprise_value(market_cap, latest.get("total_debt"), latest.get("cash"))
    ev_ebitda = safe_divide(ev, latest.get("ebitda"))

    # PEG compares the P/E with the earnings growth rate. Near 1 is the classic
    # rule of thumb for "growth roughly justifies the price".
    profits = [row.get("net_profit") for row in annual_rows]
    profit_growth = cagr(profits[-1], profits[-4], 3) if len(profits) >= 4 else None
    peg = None
    if pe_ratio and profit_growth and profit_growth > 0:
        peg = safe_divide(pe_ratio, profit_growth)

    dividend_per_share = latest.get("dividend_per_share")
    dividend_yield = None
    if dividend_per_share and price:
        dividend_yield = safe_divide(dividend_per_share, price) * 100

    return {
        "available": True,
        "price": price,
        "period": latest.get("period"),
        "market_cap_cr": round_or_none(market_cap, 1),
        "enterprise_value_cr": round_or_none(ev, 1),
        "pe_ratio": round_or_none(pe_ratio),
        "pb_ratio": round_or_none(pb_ratio),
        "ps_ratio": round_or_none(ps_ratio),
        "ev_ebitda": round_or_none(ev_ebitda),
        "peg_ratio": round_or_none(peg),
        "earnings_growth_3y_pct": round_or_none(profit_growth),
        "dividend_yield_pct": round_or_none(dividend_yield),
        "eps": eps,
        "book_value_per_share": round_or_none(book_value_per_share),
        "forward_pe": None,
        "forward_pe_note": (
            "Forward P/E needs consensus analyst estimates, which this app has no "
            "licensed source for. It is left blank rather than guessed."
        ),
    }


def historical_pe_band(history, financials, current_pe):
    """Approximate where today's P/E sits within its own recent range.

    METHOD, stated openly: we divide past closing prices by the LATEST reported
    EPS. A precise version would use the EPS that was known on each past date.
    This one shows the shape of the range, nothing more.
    """
    candles = (history or {}).get("candles") or []
    annual_rows = (financials or {}).get("annual") or []
    if len(candles) < 200 or not annual_rows:
        return {"available": False, "reason": "Not enough price history for a P/E band."}

    eps = annual_rows[-1].get("eps")
    if not eps or eps <= 0:
        return {"available": False, "reason": "No positive EPS to value against."}

    pe_series = [candle["close"] / eps for candle in candles]
    low, high = min(pe_series), max(pe_series)
    typical = median(pe_series)

    position = None
    if current_pe and high > low:
        position = (current_pe - low) / (high - low) * 100

    return {
        "available": True,
        "low": round_or_none(low),
        "median": round_or_none(typical),
        "high": round_or_none(high),
        "current": round_or_none(current_pe),
        "percentile_in_range": round_or_none(position),
        "vs_median_pct": round_or_none(percent_change(current_pe, typical)),
        "method_note": (
            "APPROXIMATION: past closing prices divided by the latest reported EPS."
        ),
    }


def classify(ratios, band, peer_pes=None):
    """Label the valuation and show the reasoning behind the label.

    Four buckets: Undervalued / Fairly Valued / Moderately Expensive /
    Very Expensive.
    """
    if not ratios.get("available"):
        return {"label": None, "reasons": ["Not enough data to classify the valuation."]}

    score = 0        # positive = cheap, negative = expensive
    reasons = []

    # --- versus its own history -------------------------------------------
    if band.get("available") and band.get("vs_median_pct") is not None:
        difference = band["vs_median_pct"]
        if difference < -20:
            score += 2
            reasons.append(
                "P/E of %s is about %.0f percent below its own recent median of %s."
                % (ratios["pe_ratio"], abs(difference), band["median"])
            )
        elif difference < -5:
            score += 1
            reasons.append("P/E is modestly below its own recent median.")
        elif difference > 40:
            score -= 2
            reasons.append(
                "P/E of %s is about %.0f percent above its own recent median of %s."
                % (ratios["pe_ratio"], difference, band["median"])
            )
        elif difference > 12:
            score -= 1
            reasons.append("P/E is somewhat above its own recent median.")
        else:
            reasons.append("P/E is close to its own recent median.")

    # --- versus peers ------------------------------------------------------
    if peer_pes:
        peer_median = median([p for p in peer_pes if p])
        if peer_median and ratios.get("pe_ratio"):
            gap = percent_change(ratios["pe_ratio"], peer_median)
            if gap is not None and gap < -20:
                score += 1
                reasons.append("It trades at a discount to the peer median P/E of %s." % round(peer_median, 1))
            elif gap is not None and gap > 25:
                score -= 1
                reasons.append("It trades at a premium to the peer median P/E of %s." % round(peer_median, 1))
            elif gap is not None:
                reasons.append("Its P/E is broadly in line with peers.")

    # --- growth-adjusted ---------------------------------------------------
    peg = ratios.get("peg_ratio")
    if peg is not None and peg < 1:
        score += 1
        reasons.append("PEG of %s is below 1: recent earnings growth more than covers the P/E." % peg)
    elif peg is not None and peg > 2.5:
        score -= 1
        reasons.append("PEG of %s is above 2.5: the price implies growth beyond the recent record." % peg)

    # --- absolute sanity check --------------------------------------------
    pe = ratios.get("pe_ratio")
    if pe is not None and pe > 70:
        score -= 1
        reasons.append("An absolute P/E above 70 leaves little room for disappointment.")
    elif pe is not None and pe < 12:
        score += 1
        reasons.append("An absolute P/E below 12 is low. Worth asking why the market is cautious.")

    if score >= 3:
        label = "Undervalued"
    elif score >= 1:
        label = "Fairly Valued"
    elif score >= -1:
        label = "Moderately Expensive"
    else:
        label = "Very Expensive"

    reasons.append(
        "Method: each comparison adds or subtracts points. Score %+d maps to '%s'. "
        "A cheap stock can stay cheap and an expensive one can keep rising - this "
        "describes the price being paid for the earnings, it is not a signal."
        % (score, label)
    )
    return {"label": label, "score": score, "reasons": reasons}


def analyze_valuation(price_data, company_info, financials, history=None, peer_pes=None):
    """Entry point used by the routes and the AI service."""
    ratios = compute_ratios(price_data, company_info, financials)
    if not ratios.get("available"):
        return ratios

    band = historical_pe_band(history, financials, ratios.get("pe_ratio"))
    verdict = classify(ratios, band, peer_pes)

    return {
        "available": True,
        "ratios": ratios,
        "historical_band": band,
        "verdict": verdict,
        "source": (financials or {}).get("source"),
        "is_demo": (financials or {}).get("is_demo", False),
    }
