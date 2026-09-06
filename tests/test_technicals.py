"""
tests/test_technicals.py
========================
Tests for the technical indicators and the valuation maths.

Each indicator is checked against a series whose answer we know by hand, so a
future change to the code cannot silently alter what the charts report.
"""

from analysis.technicals import analyze_technicals
from analysis.valuation import classify, compute_ratios
from utils.calculations import (
    adx, atr, ema, macd, max_drawdown, nearest_levels, rsi, sma, stochastic, swing_levels,
)


# ---------------------------------------------------------------------------
# Moving averages
# ---------------------------------------------------------------------------

def test_sma_is_a_plain_average_of_the_window():
    values = [1, 2, 3, 4, 5, 6]
    result = sma(values, 3)
    assert result[0] is None and result[1] is None   # not enough history yet
    assert result[2] == 2.0        # (1+2+3)/3
    assert result[5] == 5.0        # (4+5+6)/3


def test_sma_returns_all_none_when_the_series_is_too_short():
    assert sma([1, 2], 5) == [None, None]


def test_ema_reacts_faster_than_sma_to_a_jump():
    """A flat series with one big jump at the end.

    The SMA still averages in nine old values, so it barely moves. The EMA gives
    the newest value a much bigger weight, so it jumps further. That difference
    is the whole point of using an EMA.
    """
    prices = [100.0] * 30 + [200.0]
    assert ema(prices, 10)[-1] > sma(prices, 10)[-1]


# ---------------------------------------------------------------------------
# Momentum
# ---------------------------------------------------------------------------

def test_rsi_is_100_when_every_day_rises():
    """With no down-days at all the average loss is zero, so RSI pins at 100."""
    assert rsi(list(range(1, 40)), 14)[-1] == 100.0


def test_rsi_is_zero_when_every_day_falls():
    assert rsi(list(range(40, 1, -1)), 14)[-1] == 0.0


def test_rsi_stays_inside_zero_to_one_hundred():
    prices = [100 + (i % 9) * 3 - (i % 5) * 4 for i in range(120)]
    for value in rsi(prices, 14):
        if value is not None:
            assert 0 <= value <= 100


def test_macd_lines_line_up_with_the_input_length():
    prices = [100 + i * 0.5 for i in range(120)]
    result = macd(prices)
    assert len(result["macd"]) == len(prices)
    assert len(result["signal"]) == len(prices)
    # In a steadily rising series MACD must be positive.
    assert result["macd"][-1] > 0


def test_adx_stays_in_range():
    closes = [100 + i * 0.6 for i in range(120)]
    highs = [c + 1.5 for c in closes]
    lows = [c - 1.5 for c in closes]
    value = adx(highs, lows, closes, 14)[-1]
    assert value is not None and 0 <= value <= 100


def test_stochastic_reports_the_top_of_the_range():
    closes = list(range(1, 40))
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    # A series that only rises closes at the very top of its recent range.
    assert stochastic(highs, lows, closes)["k"][-1] > 90


# ---------------------------------------------------------------------------
# Levels and volatility
# ---------------------------------------------------------------------------

def test_swing_levels_finds_a_peak():
    highs = [10, 11, 12, 20, 12, 11, 10, 11, 12, 11, 10]
    lows = [h - 2 for h in highs]
    peaks = swing_levels(highs, lows, lookback=3)["peaks"]
    assert 20 in peaks


def test_nearest_levels_splits_above_and_below_the_price():
    levels = nearest_levels(100, peaks=[105, 120, 95], troughs=[90, 80, 110])
    assert all(r > 100 for r in levels["resistance"])
    assert all(s < 100 for s in levels["support"])


def test_max_drawdown_is_negative_after_a_fall():
    assert round(max_drawdown([100, 120, 60, 80]), 2) == -50.0   # 120 -> 60


def test_atr_needs_enough_history():
    assert atr([1, 2], [1, 2], [1, 2], 14) is None


# ---------------------------------------------------------------------------
# The technical analysis wrapper
# ---------------------------------------------------------------------------

def _fake_history(count, start=100.0, step=1.0):
    candles = []
    price = start
    for i in range(count):
        candles.append({
            "date": "2026-01-%02d" % ((i % 28) + 1),
            "open": price, "high": price + 2, "low": price - 2,
            "close": price, "volume": 100000,
        })
        price += step
    return {"candles": candles, "source": "test", "is_demo": False}


def test_technicals_refuses_to_analyse_a_short_series():
    """Fewer than 60 sessions must produce an honest refusal, not a number."""
    result = analyze_technicals(_fake_history(20))
    assert result["available"] is False
    assert "60" in result["reason"]


def test_technicals_call_a_steady_rise_bullish():
    result = analyze_technicals(_fake_history(300))
    assert result["available"] is True
    assert result["view"] == "BULLISH"
    assert result["trend"]["long_term"] == "uptrend"
    # The verdict must always ship with its reasoning.
    assert len(result["reasons"]) > 3


def test_technicals_call_a_steady_fall_bearish():
    result = analyze_technicals(_fake_history(300, start=400.0, step=-1.0))
    assert result["view"] == "BEARISH"


# ---------------------------------------------------------------------------
# Valuation
# ---------------------------------------------------------------------------

def test_compute_ratios_from_known_numbers():
    ratios = compute_ratios(
        {"price": 200.0},
        {"market_cap_cr": 20000, "shares_outstanding_cr": 100},
        {"annual": [{"period": "FY2026", "eps": 10.0, "equity": 10000, "revenue": 40000,
                     "ebitda": 5000, "total_debt": 2000, "cash": 1000, "net_profit": 1000}]},
    )
    assert ratios["pe_ratio"] == 20.0        # 200 / 10
    assert ratios["pb_ratio"] == 2.0         # 200 / (10000 / 100)
    # EV = 20000 + 2000 - 1000 = 21000; 21000 / 5000 = 4.2
    assert ratios["ev_ebitda"] == 4.2
    # Forward P/E must stay blank rather than being guessed.
    assert ratios["forward_pe"] is None


def test_compute_ratios_skips_pe_when_the_company_loses_money():
    ratios = compute_ratios(
        {"price": 200.0},
        {"market_cap_cr": 20000, "shares_outstanding_cr": 100},
        {"annual": [{"period": "FY2026", "eps": -5.0, "equity": 10000, "revenue": 40000,
                     "ebitda": 500, "total_debt": 0, "cash": 0, "net_profit": -500}]},
    )
    assert ratios["pe_ratio"] is None        # a negative P/E would be meaningless


def test_classify_flags_an_expensive_stock():
    ratios = {"available": True, "pe_ratio": 90.0, "peg_ratio": 4.0}
    band = {"available": True, "median": 30.0, "vs_median_pct": 200.0}
    result = classify(ratios, band)
    assert result["label"] == "Very Expensive"
    assert any("median" in reason for reason in result["reasons"])


def test_classify_always_explains_itself():
    result = classify({"available": True, "pe_ratio": 15.0}, {"available": False})
    assert result["label"] is not None
    assert any("Method:" in reason for reason in result["reasons"])
