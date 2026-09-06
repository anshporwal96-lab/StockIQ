"""
utils/validators.py
===================
Input checking and data-quality checking.

Two different jobs live here:

  1. Validating what the USER typed (symbols, usernames, emails, passwords).
     Never trust anything that arrives from a browser.

  2. Validating what a DATA PROVIDER returned (missing fields, impossible
     numbers, stale timestamps). Requirement 38 of the brief: we would rather
     show "Data unavailable" than show a number we do not trust.
"""

import re
from datetime import datetime, timezone

# A valid NSE symbol is letters, digits, "&", "-" (e.g. TCS, M&M, BAJAJ-AUTO).
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9&\-]{1,20}$")
BSE_CODE_PATTERN = re.compile(r"^\d{6}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.\-]{3,30}$")


def clean_symbol(raw):
    """Normalise a symbol the user typed. Returns "" if it looks invalid.

    Doing this in one place means every route treats "tcs", " TCS " and "TCS"
    as the same stock.
    """
    if not raw:
        return ""
    candidate = str(raw).strip().upper()
    if SYMBOL_PATTERN.match(candidate):
        return candidate
    return ""


def is_bse_code(raw):
    """True if the text looks like a 6-digit BSE scrip code, e.g. 532540."""
    return bool(BSE_CODE_PATTERN.match(str(raw).strip()))


def validate_registration(username, email, password):
    """Check sign-up input. Returns a list of human-readable problems.

    An empty list means everything is fine.
    """
    problems = []
    if not USERNAME_PATTERN.match(str(username or "").strip()):
        problems.append(
            "Username must be 3-30 characters: letters, numbers, dot, dash or underscore."
        )
    if not EMAIL_PATTERN.match(str(email or "").strip()):
        problems.append("Please enter a valid email address.")
    password = str(password or "")
    if len(password) < 8:
        problems.append("Password must be at least 8 characters long.")
    elif password.isdigit() or password.isalpha():
        problems.append("Password should mix letters and numbers.")
    return problems


# ---------------------------------------------------------------------------
# Data-quality helpers
# ---------------------------------------------------------------------------

def is_number(value):
    """True only for a real, finite number. Rejects None, "", NaN and text."""
    if value is None or isinstance(value, bool):
        return False
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    # NaN is the only value that is not equal to itself.
    return number == number and number not in (float("inf"), float("-inf"))


def safe_float(value, default=None):
    """Convert to float, or return `default` when that is not possible."""
    return float(value) if is_number(value) else default


def check_quality(payload, required_fields=(), max_age_seconds=None):
    """Inspect a provider response and report problems.

    Returns a dictionary like:
        {"ok": False, "issues": ["Missing field: revenue"], "stale": False}

    The routes attach this to the JSON response so the frontend can show a
    warning banner instead of silently displaying incomplete data.
    """
    issues = []

    if not isinstance(payload, dict):
        return {"ok": False, "issues": ["No data returned by the provider."], "stale": False}

    for field in required_fields:
        if payload.get(field) is None:
            issues.append(f"Missing field: {field}")

    stale = False
    as_of = payload.get("as_of")
    if max_age_seconds and as_of:
        try:
            stamp = datetime.fromisoformat(str(as_of))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - stamp).total_seconds()
            if age > max_age_seconds:
                stale = True
                issues.append(
                    f"Data is {int(age // 60)} minutes old and may be out of date."
                )
        except (ValueError, TypeError):
            issues.append("Provider timestamp could not be read.")

    return {"ok": len(issues) == 0, "issues": issues, "stale": stale}


def looks_implausible(metric_name, value):
    """Flag values that are almost certainly a data error rather than reality.

    We never silently "correct" a number - we only mark it so the UI can show
    it with a warning. Ranges are deliberately wide.
    """
    if not is_number(value):
        return False
    number = float(value)
    sane_ranges = {
        "pe_ratio": (-1000, 3000),
        "pb_ratio": (0, 200),
        "roe": (-200, 200),
        "roce": (-200, 200),
        "debt_to_equity": (0, 50),
        "dividend_yield": (0, 40),
        "rsi": (0, 100),
        "ebitda_margin": (-200, 100),
        "pat_margin": (-200, 100),
    }
    low, high = sane_ranges.get(metric_name, (float("-inf"), float("inf")))
    return not (low <= number <= high)
