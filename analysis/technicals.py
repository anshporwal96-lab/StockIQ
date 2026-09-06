"""
analysis/technicals.py
======================
Reads a price history and describes what has ALREADY happened.

A HARD RULE IN THIS FILE
------------------------
Technical indicators describe the past. They are not predictions. Every phrase
this module produces is written in the past or present tense ("price is above
its 200-day average"), never as a forecast ("price will rise"). The wording
matters: a beginner reading a dashboard should never come away thinking the
software knows what happens next.
"""

from utils.calculations import (
    adx, annualised_volatility, atr, macd, max_drawdown, nearest_levels,
    round_or_none, rsi, sma, stochastic, swing_levels,
)


def _series(candles):
    """Split candles into the four plain lists the maths functions want."""
    return (
        [c["close"] for c in candles],
        [c["high"] for c in candles],
        [c["low"] for c in candles],
        [c["volume"] for c in candles],
    )


def _trend_from_averages(price, ma_short, ma_medium, ma_long):
    """Classify a trend by where price sits relative to its moving averages.

    The rule is written out explicitly so a reader can check it, rather than
    hidden inside a scoring black box.
    """
    votes = 0
    checks = 0
    for average in (ma_short, ma_medium, ma_long):
        if average is None or price is None:
            continue
        checks += 1
        votes += 1 if price > average else -1
    if checks == 0:
        return None
    if votes == checks:
        return "uptrend"
    if votes == -checks:
        return "downtrend"
    return "mixed"


def analyze_technicals(history):
    """Compute every indicator and produce a plain-English conclusion."""
    candles = (history or {}).get("candles") or []

    # Most indicators need real history. Below 60 candles we say so rather than
    # printing a number that would be statistically meaningless.
    if len(candles) < 60:
        return {
            "available": False,
            "reason": (
                "Technical analysis needs at least 60 trading days of price history; "
                "only %d were returned." % len(candles)
            ),
            "source": (history or {}).get("source"),
            "is_demo": (history or {}).get("is_demo", False),
        }

    closes, highs, lows, volumes = _series(candles)
    price = closes[-1]

    # ---- moving averages -------------------------------------------------
    moving_averages = {}
    for period in (20, 50, 100, 200):
        series = sma(closes, period)
        moving_averages["dma_%d" % period] = round_or_none(series[-1] if series else None)

    # ---- momentum --------------------------------------------------------
    rsi_series = rsi(closes, 14)
    rsi_value = rsi_series[-1] if rsi_series else None

    macd_data = macd(closes)
    macd_value = macd_data["macd"][-1]
    signal_value = macd_data["signal"][-1]
    histogram_value = macd_data["histogram"][-1]

    adx_series = adx(highs, lows, closes, 14)
    adx_value = adx_series[-1] if adx_series else None

    stoch = stochastic(highs, lows, closes)
    stoch_k = stoch["k"][-1]

    # ---- trend across three horizons ------------------------------------
    short_trend = _trend_from_averages(price, moving_averages["dma_20"], None, None)
    medium_trend = _trend_from_averages(price, moving_averages["dma_50"], None, None)
    long_trend = _trend_from_averages(price, moving_averages["dma_200"], None, None)
    overall_trend = _trend_from_averages(
        price, moving_averages["dma_20"], moving_averages["dma_50"], moving_averages["dma_200"]
    )

    # ---- support and resistance -----------------------------------------
    swings = swing_levels(highs, lows, lookback=5)
    levels = nearest_levels(price, swings["peaks"], swings["troughs"])

    recent_high = max(highs[-60:])
    recent_low = min(lows[-60:])
    band = recent_high - recent_low
    # A "consolidation" is when price has been stuck in a narrow band. We call
    # narrow "less than 12% of the high", and state the threshold openly.
    consolidating = bool(recent_high) and (band / recent_high) < 0.12

    # ---- volume ----------------------------------------------------------
    average_volume_50 = sum(volumes[-50:]) / 50.0
    latest_volume = volumes[-1]
    volume_ratio = latest_volume / average_volume_50 if average_volume_50 else None

    # ---- overall view ----------------------------------------------------
    view, reasons = _build_view(
        price, moving_averages, rsi_value, macd_value, signal_value, adx_value, overall_trend
    )

    return {
        "available": True,
        "price": round_or_none(price),
        "as_of": candles[-1]["date"],
        "moving_averages": moving_averages,
        "price_vs_ma": {
            key: round_or_none((price - value) / value * 100) if value else None
            for key, value in moving_averages.items()
        },
        "rsi_14": round_or_none(rsi_value),
        "macd": {
            "macd": round_or_none(macd_value, 3),
            "signal": round_or_none(signal_value, 3),
            "histogram": round_or_none(histogram_value, 3),
            "crossover": (
                None if (macd_value is None or signal_value is None)
                else ("above signal" if macd_value > signal_value else "below signal")
            ),
        },
        "adx_14": round_or_none(adx_value),
        "stochastic_k": round_or_none(stoch_k),
        "trend": {
            "short_term": short_trend,
            "medium_term": medium_trend,
            "long_term": long_trend,
            "overall": overall_trend,
        },
        "levels": {
            "support": levels["support"],
            "resistance": levels["resistance"],
            "recent_high_60d": round_or_none(recent_high),
            "recent_low_60d": round_or_none(recent_low),
            "breakout_level": levels["resistance"][0] if levels["resistance"] else round_or_none(recent_high),
            "breakdown_level": levels["support"][0] if levels["support"] else round_or_none(recent_low),
            "consolidating": consolidating,
        },
        "volume": {
            "latest": latest_volume,
            "average_50d": int(average_volume_50),
            "ratio_vs_average": round_or_none(volume_ratio),
        },
        "volatility": {
            "atr_14": round_or_none(atr(highs, lows, closes)),
            "annualised_pct": round_or_none(annualised_volatility(closes)),
            "max_drawdown_pct": round_or_none(max_drawdown(closes)),
        },
        "view": view,
        "reasons": reasons,
        "disclaimer": (
            "Technical indicators describe price behaviour that has already happened. "
            "They are not forecasts and give no guarantee about future prices."
        ),
        "source": history.get("source"),
        "is_demo": history.get("is_demo", False),
    }


def _compare(first, second, scale):
    """Compare two numbers, treating a negligible gap as "level".

    WHY THIS EXISTS
    ---------------
    Floating-point arithmetic leaves noise. On a perfectly steady series the
    MACD line and its signal line came out as 7.0 and 7.000000000000002 - a
    difference of about 0.0000000000000018, which is nothing at all. Without a
    tolerance the code read that as "momentum is negative" and marked a rising
    stock bearish.

    So anything smaller than one millionth of the price scale counts as level.
    Returns 1 (first is higher), -1 (lower) or 0 (level).
    """
    tolerance = max(abs(scale) * 1e-6, 1e-9)
    difference = first - second
    if difference > tolerance:
        return 1
    if difference < -tolerance:
        return -1
    return 0


def _build_view(price, moving_averages, rsi_value, macd_value, signal_value, adx_value, trend):
    """Turn the indicators into BULLISH / NEUTRAL / BEARISH, transparently.

    Each check is worth one point, positive or negative. The individual reasons
    are returned alongside the verdict so the user can see exactly what drove
    it - no hidden weighting.
    """
    score = 0
    reasons = []

    dma_200 = moving_averages.get("dma_200")
    dma_50 = moving_averages.get("dma_50")

    if dma_200:
        direction = _compare(price, dma_200, price)
        score += direction
        reasons.append({
            1: "Price is above the 200-day moving average (long-term uptrend intact).",
            -1: "Price is below the 200-day moving average (long-term trend is weak).",
            0: "Price is sitting on its 200-day moving average.",
        }[direction])

    if dma_50:
        direction = _compare(price, dma_50, price)
        score += direction
        reasons.append({
            1: "Price is above the 50-day moving average.",
            -1: "Price is below the 50-day moving average.",
            0: "Price is sitting on its 50-day moving average.",
        }[direction])

    if dma_50 and dma_200:
        direction = _compare(dma_50, dma_200, price)
        score += direction
        reasons.append({
            1: "The 50-day average sits above the 200-day average.",
            -1: "The 50-day average sits below the 200-day average.",
            0: "The 50-day and 200-day averages are level with each other.",
        }[direction])

    if rsi_value is not None:
        if rsi_value > 70:
            reasons.append(
                "RSI is %.0f, above 70. Recent buying has been strong; this is often "
                "described as overbought, which says nothing about what happens next."
                % rsi_value
            )
        elif rsi_value < 30:
            reasons.append(
                "RSI is %.0f, below 30. Recent selling has been heavy; this is often "
                "described as oversold." % rsi_value
            )
        elif rsi_value > 55:
            score += 1
            reasons.append("RSI is %.0f, in the upper half of its range." % rsi_value)
        elif rsi_value < 45:
            score -= 1
            reasons.append("RSI is %.0f, in the lower half of its range." % rsi_value)

    if macd_value is not None and signal_value is not None:
        # A crossover only means something when the two lines genuinely differ.
        # See _compare above for why a plain > test is not good enough here.
        direction = _compare(macd_value, signal_value, price)
        score += direction
        reasons.append({
            1: "MACD is above its signal line (short-term momentum is positive).",
            -1: "MACD is below its signal line (short-term momentum is negative).",
            0: "MACD is level with its signal line, so momentum is flat.",
        }[direction])

    if adx_value is not None:
        if adx_value >= 25:
            reasons.append(
                "ADX is %.0f, so the current move has real strength behind it." % adx_value
            )
        else:
            reasons.append(
                "ADX is %.0f, below 25, so there is no strong trend - price is drifting."
                % adx_value
            )

    if score >= 3:
        view = "BULLISH"
    elif score <= -3:
        view = "BEARISH"
    else:
        view = "NEUTRAL"

    reasons.append(
        "Verdict method: each check above adds or removes one point. "
        "3 or more is BULLISH, -3 or less is BEARISH, anything between is NEUTRAL. "
        "This score reached %+d." % score
    )
    return view, reasons


def summarise_for_ai(technicals):
    """A compact dictionary handed to the AI service.

    We pass only computed numbers. The AI writes prose about them; it never
    calculates anything itself.
    """
    if not technicals.get("available"):
        return {"available": False, "reason": technicals.get("reason")}
    return {
        "available": True,
        "price": technicals["price"],
        "trend": technicals["trend"],
        "rsi_14": technicals["rsi_14"],
        "macd_crossover": technicals["macd"]["crossover"],
        "adx_14": technicals["adx_14"],
        "moving_averages": technicals["moving_averages"],
        "support": technicals["levels"]["support"],
        "resistance": technicals["levels"]["resistance"],
        "view": technicals["view"],
        "volatility_pct": technicals["volatility"]["annualised_pct"],
    }
