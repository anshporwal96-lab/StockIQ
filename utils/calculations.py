"""
utils/calculations.py
=====================
Pure maths. No Flask, no database, no internet.

Every function here takes plain Python lists/numbers and returns plain Python
numbers. That makes them trivial to unit-test (see tests/test_technicals.py)
and means you can read them without knowing anything about web development.

Deliberately written WITHOUT numpy or pandas so the project installs anywhere.
"""

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def safe_divide(numerator, denominator):
    """Divide, but return None instead of crashing on a zero or missing value.

    Financial data is full of gaps, so this guard is used everywhere.
    """
    try:
        if numerator is None or denominator is None:
            return None
        denominator = float(denominator)
        if denominator == 0:
            return None
        return float(numerator) / denominator
    except (TypeError, ValueError):
        return None


def percent_change(new_value, old_value):
    """Percentage change from old to new. 110 vs 100 -> 10.0"""
    if old_value in (None, 0) or new_value is None:
        return None
    try:
        return (float(new_value) - float(old_value)) / abs(float(old_value)) * 100.0
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def cagr(final_value, initial_value, years):
    """Compound Annual Growth Rate, as a percentage.

    "Revenue grew from 100 to 200 over 5 years" -> what steady yearly rate
    would produce that? Formula: (final / initial) ** (1 / years) - 1

    Returns None when the maths is undefined (e.g. the company was loss-making
    at the start, so `initial_value` is negative).
    """
    try:
        final_value = float(final_value)
        initial_value = float(initial_value)
        years = float(years)
    except (TypeError, ValueError):
        return None
    if initial_value <= 0 or years <= 0 or final_value <= 0:
        return None
    return ((final_value / initial_value) ** (1.0 / years) - 1.0) * 100.0


def round_or_none(value, digits=2):
    """Round a number, passing None straight through."""
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def median(values):
    """Middle value of a list. Used for 'typical historical P/E'."""
    clean = sorted(v for v in values if v is not None)
    if not clean:
        return None
    middle = len(clean) // 2
    if len(clean) % 2 == 1:
        return clean[middle]
    return (clean[middle - 1] + clean[middle]) / 2.0


# ---------------------------------------------------------------------------
# Moving averages
# ---------------------------------------------------------------------------

def sma(values, period):
    """Simple Moving Average.

    A 20-day SMA is just "the average of the last 20 closing prices", moved
    forward one day at a time. It smooths out daily noise so the trend shows.

    Returns a list the same length as `values`, with None where there is not
    yet enough history to compute an average.
    """
    out = [None] * len(values)
    if period <= 0 or len(values) < period:
        return out
    running_total = sum(values[:period])
    out[period - 1] = running_total / period
    for i in range(period, len(values)):
        # Slide the window: add the new value, drop the oldest one.
        running_total += values[i] - values[i - period]
        out[i] = running_total / period
    return out


def ema(values, period):
    """Exponential Moving Average - like an SMA but recent prices count more.

    Each new point is:  price * k + previous_ema * (1 - k),  where k = 2/(n+1)
    """
    out = [None] * len(values)
    if period <= 0 or len(values) < period:
        return out
    k = 2.0 / (period + 1)
    previous = sum(values[:period]) / period  # seed with a simple average
    out[period - 1] = previous
    for i in range(period, len(values)):
        previous = values[i] * k + previous * (1 - k)
        out[i] = previous
    return out


# ---------------------------------------------------------------------------
# Momentum indicators
# ---------------------------------------------------------------------------

def rsi(closes, period=14):
    """Relative Strength Index (0-100), using Wilder smoothing.

    PLAIN ENGLISH: over the last 14 days, compare the size of up-moves with the
    size of down-moves. All up-days -> 100. All down-days -> 0.
    Above 70 is often called "overbought", below 30 "oversold".

    Those labels are descriptions of recent price behaviour, NOT predictions.
    """
    out = [None] * len(closes)
    if len(closes) <= period:
        return out

    gains, losses = [], []
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    def to_rsi(gain, loss):
        if loss == 0:
            return 100.0
        rs = gain / loss
        return 100.0 - (100.0 / (1.0 + rs))

    out[period] = to_rsi(avg_gain, avg_loss)

    for i in range(period + 1, len(closes)):
        change = closes[i] - closes[i - 1]
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        # Wilder smoothing: a weighted running average.
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        out[i] = to_rsi(avg_gain, avg_loss)

    return out


def macd(closes, fast=12, slow=26, signal=9):
    """MACD - Moving Average Convergence Divergence.

    Three lines:
      macd_line   = EMA(12) - EMA(26)      momentum of the trend
      signal_line = EMA(9) of the macd line
      histogram   = macd_line - signal_line

    When the MACD line crosses above the signal line, short-term momentum has
    turned up relative to the medium term. Again: a description, not a forecast.
    """
    empty = [None] * len(closes)
    if len(closes) < slow + signal:
        return {"macd": empty, "signal": empty, "histogram": empty}

    fast_ema = ema(closes, fast)
    slow_ema = ema(closes, slow)

    macd_line = [
        (f - s) if (f is not None and s is not None) else None
        for f, s in zip(fast_ema, slow_ema)
    ]

    # The signal line is an EMA of the MACD line, so drop the leading Nones.
    valid = [v for v in macd_line if v is not None]
    signal_tail = ema(valid, signal)
    pad = len(macd_line) - len(signal_tail)
    signal_line = [None] * pad + signal_tail

    histogram = [
        (m - s) if (m is not None and s is not None) else None
        for m, s in zip(macd_line, signal_line)
    ]
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def stochastic(highs, lows, closes, period=14, smooth=3):
    """Stochastic oscillator (%K and %D).

    "Where is today's close inside the high/low range of the last 14 days?"
    100 = at the very top of the range, 0 = at the very bottom.
    """
    k_values = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        window_high = max(highs[i - period + 1 : i + 1])
        window_low = min(lows[i - period + 1 : i + 1])
        span = window_high - window_low
        k_values[i] = 50.0 if span == 0 else (closes[i] - window_low) / span * 100.0

    valid = [v for v in k_values if v is not None]
    d_tail = sma(valid, smooth)
    d_values = [None] * (len(k_values) - len(d_tail)) + d_tail
    return {"k": k_values, "d": d_values}


def adx(highs, lows, closes, period=14):
    """ADX - Average Directional Index (0-100).

    ADX measures how STRONG a trend is, not which way it points.
      below 20 -> no real trend, price is drifting sideways
      above 25 -> a genuine trend is in place (up or down)
    """
    length = len(closes)
    out = [None] * length
    if length < period * 2 + 1:
        return out

    plus_dm, minus_dm, true_range = [], [], []
    for i in range(1, length):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        plus_dm.append(up_move if (up_move > down_move and up_move > 0) else 0.0)
        minus_dm.append(down_move if (down_move > up_move and down_move > 0) else 0.0)
        true_range.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )

    def wilder_smooth(series):
        smoothed = [sum(series[:period])]
        for i in range(period, len(series)):
            smoothed.append(smoothed[-1] - smoothed[-1] / period + series[i])
        return smoothed

    tr_s = wilder_smooth(true_range)
    plus_s = wilder_smooth(plus_dm)
    minus_s = wilder_smooth(minus_dm)

    dx_values = []
    for tr, p, m in zip(tr_s, plus_s, minus_s):
        if tr == 0:
            dx_values.append(0.0)
            continue
        plus_di = 100.0 * p / tr
        minus_di = 100.0 * m / tr
        total = plus_di + minus_di
        dx_values.append(0.0 if total == 0 else 100.0 * abs(plus_di - minus_di) / total)

    if len(dx_values) < period:
        return out

    adx_value = sum(dx_values[:period]) / period
    first_index = period * 2 - 1
    if first_index < length:
        out[first_index] = adx_value
    for i in range(period, len(dx_values)):
        adx_value = (adx_value * (period - 1) + dx_values[i]) / period
        index = i + period
        if index < length:
            out[index] = adx_value
    return out


# ---------------------------------------------------------------------------
# Support, resistance and volatility
# ---------------------------------------------------------------------------

def swing_levels(highs, lows, lookback=5):
    """Find "swing highs" and "swing lows" in the price series.

    A swing high is a candle whose high is the highest within `lookback` bars
    on BOTH sides - in other words, a local peak. Traders treat clusters of
    such peaks as resistance, and clusters of troughs as support.
    """
    peaks, troughs = [], []
    for i in range(lookback, len(highs) - lookback):
        window_h = highs[i - lookback : i + lookback + 1]
        window_l = lows[i - lookback : i + lookback + 1]
        if highs[i] == max(window_h):
            peaks.append(highs[i])
        if lows[i] == min(window_l):
            troughs.append(lows[i])
    return {"peaks": peaks, "troughs": troughs}


def nearest_levels(current_price, peaks, troughs, count=3):
    """Pick the closest resistance levels above and support levels below.

    Resistance = past peaks sitting ABOVE today's price.
    Support    = past troughs sitting BELOW today's price.
    """
    resistance = sorted({round(p, 2) for p in peaks if p > current_price})[:count]
    support = sorted({round(t, 2) for t in troughs if t < current_price}, reverse=True)[
        :count
    ]
    return {"support": support, "resistance": resistance}


def atr(highs, lows, closes, period=14):
    """Average True Range - the average size of a daily move, in rupees.

    Useful for saying "this stock typically moves about Rs 45 a day", which is
    a far more honest statement than any price prediction.
    """
    if len(closes) <= period:
        return None
    true_ranges = []
    for i in range(1, len(closes)):
        true_ranges.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )
    return sum(true_ranges[-period:]) / period


def annualised_volatility(closes):
    """Standard deviation of daily returns, scaled to a yearly percentage.

    Roughly: "how much does this stock bounce around in a typical year?"
    Uses 252, the usual number of trading days in a year.
    """
    if len(closes) < 30:
        return None
    returns = []
    for i in range(1, len(closes)):
        if closes[i - 1]:
            returns.append((closes[i] - closes[i - 1]) / closes[i - 1])
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return (variance ** 0.5) * (252 ** 0.5) * 100.0


def max_drawdown(closes):
    """Largest peak-to-trough fall, as a percentage.

    Answers "if I had bought at the worst possible moment in this period, how
    far down would I have been?"
    """
    if not closes:
        return None
    peak = closes[0]
    worst = 0.0
    for price in closes:
        peak = max(peak, price)
        if peak:
            drawdown = (price - peak) / peak * 100.0
            worst = min(worst, drawdown)
    return worst


# ---------------------------------------------------------------------------
# Fundamental ratios
# ---------------------------------------------------------------------------
# Each of these is a one-line formula, kept as a named function so the analysis
# modules read like English and so each one can be unit-tested on its own.

def ebitda_margin(ebitda, revenue):
    """What share of every rupee of sales survives as operating profit."""
    value = safe_divide(ebitda, revenue)
    return value * 100.0 if value is not None else None


def pat_margin(net_profit, revenue):
    """Net profit as a percentage of revenue - profit after everything."""
    value = safe_divide(net_profit, revenue)
    return value * 100.0 if value is not None else None


def roe(net_profit, shareholders_equity):
    """Return on Equity: profit earned per rupee the owners have in the business."""
    value = safe_divide(net_profit, shareholders_equity)
    return value * 100.0 if value is not None else None


def roce(ebit, total_debt, shareholders_equity):
    """Return on Capital Employed: profit per rupee of ALL capital used
    (owners' money plus borrowed money). Harder to flatter with debt than ROE."""
    capital_employed = None
    if total_debt is not None and shareholders_equity is not None:
        capital_employed = float(total_debt) + float(shareholders_equity)
    value = safe_divide(ebit, capital_employed)
    return value * 100.0 if value is not None else None


def roa(net_profit, total_assets):
    """Return on Assets: profit per rupee of everything the company owns."""
    value = safe_divide(net_profit, total_assets)
    return value * 100.0 if value is not None else None


def debt_to_equity(total_debt, shareholders_equity):
    """Borrowed money divided by owners' money. 0 = debt-free."""
    return safe_divide(total_debt, shareholders_equity)


def interest_coverage(ebit, interest_expense):
    """How many times over operating profit covers the interest bill.
    Below about 2 is usually considered uncomfortable."""
    return safe_divide(ebit, interest_expense)


def current_ratio(current_assets, current_liabilities):
    """Short-term assets vs short-term bills. Below 1 can mean a cash squeeze."""
    return safe_divide(current_assets, current_liabilities)


def free_cash_flow(operating_cash_flow, capex):
    """Cash left after paying to maintain and grow the business.
    `capex` is passed in as a positive number here."""
    if operating_cash_flow is None or capex is None:
        return None
    return float(operating_cash_flow) - abs(float(capex))


def enterprise_value(market_cap, total_debt, cash):
    """What it would cost to buy the whole company: market value plus the debt
    you inherit, minus the cash you get to keep."""
    if market_cap is None:
        return None
    return float(market_cap) + float(total_debt or 0) - float(cash or 0)
