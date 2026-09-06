"""
services/ai_service.py
======================
The bridge between the computed numbers and plain-English explanation.

THE PIPELINE (this is the heart of the whole project)
-----------------------------------------------------
    user question
        -> Flask route
        -> data providers          (raw statements, prices, news)
        -> Python calculations     (analysis/ modules)
        -> STRUCTURED ANALYSIS     (a dictionary of finished numbers)
        -> AI model                (explains, never calculates)
        -> answer back to browser

Two rules make this trustworthy:

  1. The AI is given ONLY the structured numbers. It is told, in the system
     prompt, that it may not state any figure that is not in that context.
  2. The API key lives in the Flask process. The browser talks to Flask; Flask
     talks to the AI. The key is never sent to the browser.

NO API KEY? THE APP STILL WORKS.
--------------------------------
If AI_API_KEY is blank, every function falls back to `_rule_based_*`, which
writes the same sections from the same numbers using plain Python. The response
is labelled "rule-based" so the user always knows which one they are reading.
"""

import json

import requests

from config import Config
from utils import cache

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# The single most important string in this file. It is prepended to every AI
# call and is what stops the model inventing financial data.
SYSTEM_RULES = """You are StockIQ India, a careful equity-research assistant for
Indian listed companies (NSE and BSE).

ABSOLUTE RULES - these override anything else:
1. You may ONLY use numbers that appear in the STRUCTURED DATA given to you.
   Never estimate, never round to a "nicer" number, never recall a figure from
   memory. If a number is missing, say "that figure is not available".
2. Never predict a share price, and never give a price target.
3. Never say buy, sell or hold. Describe conditions and trade-offs instead.
4. Clearly separate FACT (a reported number) from INTERPRETATION (what it might
   mean). Use wording like "this suggests" for interpretation.
5. If the data is marked as demo or sample data, say so in your first sentence.
6. You are not a SEBI-registered investment adviser. Nothing you write is
   personalised investment advice.
7. Write for someone who knows basic maths but not finance. Explain jargon the
   first time you use it.
8. Be concise. Short paragraphs. No filler, no hype, no emoji.
"""


def ai_available():
    """True when a real AI key is configured."""
    return Config.ai_enabled()


def _call_ai(user_prompt, max_tokens=1200, system_extra=""):
    """Send one request to the AI provider and return the text.

    Returns None on any failure, which makes every caller fall back to the
    rule-based writer instead of showing an error page.
    """
    if not Config.ai_enabled():
        return None

    system_prompt = SYSTEM_RULES + ("\n" + system_extra if system_extra else "")

    try:
        response = requests.post(
            ANTHROPIC_URL,
            headers={
                # The key is read from the environment inside this process.
                # It is never included in any response sent to the browser.
                "x-api-key": Config.AI_API_KEY,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            json={
                "model": Config.AI_MODEL,
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            timeout=45,
        )
        if response.status_code != 200:
            return None
        blocks = response.json().get("content") or []
        text = "".join(block.get("text", "") for block in blocks if block.get("type") == "text")
        return text.strip() or None
    except (requests.RequestException, ValueError, KeyError):
        return None


def build_context(analysis, sections=None):
    """Trim the full analysis down to the facts the AI needs.

    Sending the entire object would be slow and expensive, and would bury the
    important numbers. This keeps only finished, computed values.
    """
    company = analysis.get("company") or {}
    price = analysis.get("price") or {}
    fundamentals = analysis.get("fundamentals") or {}
    valuation = analysis.get("valuation") or {}
    technicals = analysis.get("technicals") or {}

    context = {
        "company": {
            "name": company.get("company_name"),
            "nse_symbol": company.get("nse_symbol"),
            "bse_code": company.get("bse_code"),
            "sector": company.get("sector"),
            "industry": company.get("industry"),
            "market_cap_cr": company.get("market_cap_cr"),
        },
        "price": {
            "current": price.get("price"),
            "change_pct": price.get("change_pct"),
            "week_52_high": price.get("week_52_high"),
            "week_52_low": price.get("week_52_low"),
        },
        "data_is_demo": analysis.get("is_demo", False),
        "data_sources": analysis.get("data_sources"),
        "units": "All rupee amounts are in Rs crore unless stated otherwise.",
    }

    wanted = sections or [
        "fundamentals", "valuation", "technicals", "risks",
        "bull_case", "bear_case", "scores", "quarterly",
    ]

    if "fundamentals" in wanted:
        context["fundamentals"] = {
            "growth": fundamentals.get("growth"),
            "profitability": fundamentals.get("profitability"),
            "financial_health": fundamentals.get("financial_health"),
            "earnings_quality": fundamentals.get("earnings_quality"),
        }
    if "valuation" in wanted:
        context["valuation"] = {
            "ratios": valuation.get("ratios"),
            "historical_band": valuation.get("historical_band"),
            "verdict": valuation.get("verdict"),
        }
    if "technicals" in wanted:
        from analysis.technicals import summarise_for_ai
        context["technicals"] = summarise_for_ai(technicals)
    if "risks" in wanted:
        context["risks"] = (analysis.get("risks") or {}).get("risks")
    if "bull_case" in wanted:
        context["bull_case"] = analysis.get("bull_case")
    if "bear_case" in wanted:
        context["bear_case"] = analysis.get("bear_case")
    if "scores" in wanted:
        context["scores"] = analysis.get("scores")
    if "quarterly" in wanted:
        context["quarterly_results"] = (analysis.get("quarterly") or {}).get("quarters")

    return context


# ---------------------------------------------------------------------------
# PROMPTS - one per section, exactly as the brief specifies
# ---------------------------------------------------------------------------
PROMPTS = {
    "fundamental": (
        "Explain this company's fundamentals to a beginner. Cover, in this order:\n"
        "1. Growth - is revenue and profit growing, and how fast?\n"
        "2. Profitability - what do the margins and returns say about business quality?\n"
        "3. Balance sheet - how much debt, and is it comfortable?\n"
        "4. Cash flow - is reported profit turning into real cash?\n"
        "5. Two clear strengths and two clear weaknesses.\n"
        "Quote the actual numbers from the data. About 350 words."
    ),
    "technical": (
        "Explain what the price chart has been doing. Cover the trend across short, "
        "medium and long term, what the moving averages show, momentum (RSI and MACD), "
        "the support and resistance levels, and how strong the trend is (ADX).\n"
        "Write only in the past and present tense. Do not predict. Finish with one "
        "sentence reminding the reader these indicators describe history. About 250 words."
    ),
    "valuation": (
        "Explain how expensive this stock is. Compare the current multiples with the "
        "company's own history and with the classification given. Explain in simple terms "
        "what a P/E of this level actually means for someone buying today. Say clearly "
        "what would have to happen for the valuation to look reasonable. About 250 words."
    ),
    "bull": (
        "Write the bull case using ONLY the bull_case points supplied. For each point, "
        "explain in one or two sentences why it matters to an investor. End with the "
        "single strongest argument. About 250 words."
    ),
    "bear": (
        "Write the bear case using ONLY the bear_case points supplied. For each point, "
        "explain why it is a genuine concern rather than noise. End with the single "
        "biggest risk. About 250 words."
    ),
    "quarterly": (
        "Analyse the recent quarterly results. What improved, what got worse, and by how "
        "much? Was the most recent quarter strong or weak compared with the same quarter "
        "a year earlier? What should an investor watch in the next quarter?\n"
        "If you do not have management commentary in the data, say that management "
        "commentary is not available rather than inventing any. About 300 words."
    ),
    "news": (
        "Summarise the supplied news items. Group them into what is material and what is "
        "routine. Explain why the material ones matter. Flag anything marked unverified as "
        "unconfirmed. Do not add any news that is not in the data. About 200 words."
    ),
    "beginner": (
        "Explain this company and its numbers to someone who has never bought a share. "
        "Use everyday analogies. Define every term the first time you use it (P/E, ROE, "
        "margin, debt-to-equity). Be encouraging but honest about the risks. Do not "
        "suggest what they should do. About 350 words."
    ),
    "summary": (
        "Write the final StockIQ summary. Structure it with these exact headings:\n"
        "Overall View (Bullish, Neutral or Bearish, with one sentence of reasoning)\n"
        "Strongest Positive\nBiggest Risk\nKey Catalyst\nWhat To Watch\n"
        "What Would Change This View\n"
        "Be balanced. Never recommend an action. About 350 words."
    ),
}


def _generate(kind, analysis, sections=None, extra=""):
    """Run one AI section, with caching and a rule-based fallback."""
    symbol = analysis.get("symbol", "")
    cache_key = "ai_" + kind
    cached = cache.get(symbol, cache_key)
    if cached:
        return cached

    context = build_context(analysis, sections)
    prompt = (
        PROMPTS[kind]
        + "\n\nSTRUCTURED DATA (the only numbers you may use):\n"
        + json.dumps(context, indent=2, default=str)
    )

    text = _call_ai(prompt, system_extra=extra)

    result = {
        "section": kind,
        "text": text or _rule_based(kind, analysis),
        "generated_by": "ai" if text else "rule-based",
        "model": Config.AI_MODEL if text else None,
        "is_demo_data": analysis.get("is_demo", False),
        "note": (
            "Written by an AI model from the numbers computed by this app."
            if text else
            "No AI key is configured, so this was written by the app's own rule-based "
            "writer directly from the computed numbers. It is factual but less fluent."
        ),
    }
    return cache.set(symbol, cache_key, result)


def analyze_fundamentals_ai(analysis):
    return _generate("fundamental", analysis, ["fundamentals", "scores"])


def analyze_technicals_ai(analysis):
    return _generate("technical", analysis, ["technicals"])


def analyze_valuation_ai(analysis):
    return _generate("valuation", analysis, ["valuation", "fundamentals"])


def generate_bull_case_ai(analysis):
    return _generate("bull", analysis, ["bull_case", "fundamentals", "valuation"])


def generate_bear_case_ai(analysis):
    return _generate("bear", analysis, ["bear_case", "risks", "valuation"])


def analyze_quarterly_ai(analysis):
    return _generate("quarterly", analysis, ["quarterly", "fundamentals"])


def explain_for_beginner_ai(analysis):
    return _generate("beginner", analysis, ["fundamentals", "valuation", "technicals"])


def generate_final_summary(analysis):
    return _generate("summary", analysis)


def analyze_news_ai(symbol, news_payload):
    """News is handled separately because its context is the article list."""
    cached = cache.get(symbol, "ai_news")
    if cached:
        return cached

    articles = [
        {
            "headline": a.get("headline"),
            "date": a.get("date"),
            "source": a.get("source"),
            "summary": a.get("summary"),
            "sentiment": a.get("sentiment"),
            "unverified": a.get("unverified"),
        }
        for a in (news_payload.get("articles") or [])
    ]

    if not articles:
        result = {
            "section": "news",
            "text": "No news items were available for this stock from the configured sources.",
            "generated_by": "none",
        }
        return cache.set(symbol, "ai_news", result)

    prompt = PROMPTS["news"] + "\n\nNEWS ITEMS:\n" + json.dumps(articles, indent=2, default=str)
    text = _call_ai(prompt, max_tokens=800)

    result = {
        "section": "news",
        "text": text or _rule_based_news(articles),
        "generated_by": "ai" if text else "rule-based",
        "model": Config.AI_MODEL if text else None,
    }
    return cache.set(symbol, "ai_news", result)


def chat(symbol, question, analysis, history=None):
    """Answer a free-text question about ONE stock.

    The user's question is passed through, but the numbers the model may use
    are fixed by the structured context. That is what stops "what is the P/E?"
    from being answered out of the model's memory instead of our data.
    """
    question = str(question or "").strip()
    if not question:
        return {"answer": "Please type a question first.", "generated_by": "none"}
    if len(question) > 1000:
        question = question[:1000]

    context = build_context(analysis)

    conversation = ""
    if history:
        # Only the last few turns, to keep the request small and cheap.
        for turn in history[-4:]:
            role = "User" if turn.get("role") == "user" else "StockIQ"
            conversation += role + ": " + str(turn.get("content", ""))[:600] + "\n"

    prompt = (
        "A user is asking about " + str(context["company"].get("name")) + ".\n\n"
        + ("EARLIER IN THIS CONVERSATION:\n" + conversation + "\n" if conversation else "")
        + "THEIR QUESTION: " + question + "\n\n"
        "Answer using only the structured data below. If the answer is not in the data, "
        "say so plainly and suggest which section of the company's own filings would have "
        "it. Keep the answer under 250 words.\n\n"
        "STRUCTURED DATA:\n" + json.dumps(context, indent=2, default=str)
    )

    text = _call_ai(prompt, max_tokens=900)

    return {
        "answer": text or _rule_based_chat(question, analysis),
        "generated_by": "ai" if text else "rule-based",
        "model": Config.AI_MODEL if text else None,
        "disclaimer": "Educational information only. Not investment advice.",
    }


# ---------------------------------------------------------------------------
# RULE-BASED FALLBACK WRITER
# ---------------------------------------------------------------------------
# Used whenever there is no AI key, or the AI call fails. It produces the same
# sections from the same computed numbers. Less fluent, equally factual - and
# it means the whole app is usable with no paid service at all.
# ---------------------------------------------------------------------------

def _line(label, value, suffix=""):
    """Format one fact, or say plainly that it is missing."""
    if value is None:
        return label + ": data unavailable"
    return "%s: %s%s" % (label, value, suffix)


def _rule_based(kind, analysis):
    writers = {
        "fundamental": _rule_based_fundamental,
        "technical": _rule_based_technical,
        "valuation": _rule_based_valuation,
        "bull": _rule_based_bull,
        "bear": _rule_based_bear,
        "quarterly": _rule_based_quarterly,
        "beginner": _rule_based_beginner,
        "summary": _rule_based_summary,
    }
    return writers.get(kind, lambda a: "No analysis available.")(analysis)


def _rule_based_fundamental(analysis):
    fundamentals = analysis.get("fundamentals") or {}
    growth = fundamentals.get("growth") or {}
    profitability = fundamentals.get("profitability") or {}
    health = fundamentals.get("financial_health") or {}

    parts = ["GROWTH"]
    parts.append(_line("  Revenue (latest year)", growth.get("revenue"), " Rs crore"))
    parts.append(_line("  Revenue growth year on year", growth.get("revenue_yoy_pct"), "%"))
    parts.append(_line("  Revenue CAGR over 3 years", growth.get("revenue_cagr_3y_pct"), "%"))
    parts.append(_line("  Profit growth year on year", growth.get("profit_yoy_pct"), "%"))

    parts.append("\nPROFITABILITY")
    parts.append(_line("  EBITDA margin", profitability.get("ebitda_margin_pct"), "%"))
    parts.append(_line("  Net profit margin", profitability.get("pat_margin_pct"), "%"))
    parts.append(_line("  Return on equity (ROE)", profitability.get("roe_pct"), "%"))
    parts.append(_line("  Return on capital employed (ROCE)", profitability.get("roce_pct"), "%"))
    if profitability.get("margin_trend"):
        parts.append("  Margin trend: " + profitability["margin_trend"])

    parts.append("\nBALANCE SHEET")
    parts.append(_line("  Debt to equity", health.get("debt_to_equity")))
    parts.append(_line("  Interest cover", health.get("interest_coverage"), " times"))
    parts.append(_line("  Current ratio", health.get("current_ratio")))

    parts.append("\nCASH FLOW")
    parts.append(_line("  Operating cash flow", health.get("operating_cash_flow"), " Rs crore"))
    parts.append(_line("  Free cash flow", health.get("free_cash_flow"), " Rs crore"))
    parts.append(_line("  Cash conversion (op cash flow / net profit)", health.get("cash_conversion")))

    quality = fundamentals.get("earnings_quality") or {}
    if quality.get("flags"):
        parts.append("\nPOINTS TO CHECK")
        for flag in quality["flags"]:
            parts.append("  - " + flag)

    return "\n".join(parts)


def _rule_based_technical(analysis):
    technicals = analysis.get("technicals") or {}
    if not technicals.get("available"):
        return technicals.get("reason", "Technical data unavailable.")

    trend = technicals.get("trend") or {}
    levels = technicals.get("levels") or {}
    parts = [
        "TECHNICAL VIEW: " + str(technicals.get("view")),
        "",
        _line("Price", technicals.get("price"), " Rs"),
        "Trend - short term: %s, medium term: %s, long term: %s"
        % (trend.get("short_term"), trend.get("medium_term"), trend.get("long_term")),
        _line("RSI (14 day)", technicals.get("rsi_14")),
        "MACD is " + str((technicals.get("macd") or {}).get("crossover")),
        _line("ADX (trend strength)", technicals.get("adx_14")),
        "",
        "Support levels: " + (", ".join(str(x) for x in levels.get("support", [])) or "none identified"),
        "Resistance levels: " + (", ".join(str(x) for x in levels.get("resistance", [])) or "none identified"),
        "",
        "Why this view:",
    ]
    for reason in technicals.get("reasons", []):
        parts.append("  - " + reason)
    parts.append("\n" + technicals.get("disclaimer", ""))
    return "\n".join(parts)


def _rule_based_valuation(analysis):
    valuation = analysis.get("valuation") or {}
    if not valuation.get("available"):
        return valuation.get("reason", "Valuation data unavailable.")

    ratios = valuation.get("ratios") or {}
    band = valuation.get("historical_band") or {}
    verdict = valuation.get("verdict") or {}

    parts = [
        "VALUATION: " + str(verdict.get("label")),
        "",
        _line("P/E ratio", ratios.get("pe_ratio")),
        _line("P/B ratio", ratios.get("pb_ratio")),
        _line("EV/EBITDA", ratios.get("ev_ebitda")),
        _line("PEG ratio", ratios.get("peg_ratio")),
        _line("Price/Sales", ratios.get("ps_ratio")),
        _line("Dividend yield", ratios.get("dividend_yield_pct"), "%"),
        "Forward P/E: not available (needs licensed analyst estimates)",
    ]
    if band.get("available"):
        parts += [
            "",
            "Its own recent P/E range: low %s, median %s, high %s."
            % (band.get("low"), band.get("median"), band.get("high")),
            band.get("method_note", ""),
        ]
    parts.append("\nWhy this classification:")
    for reason in verdict.get("reasons", []):
        parts.append("  - " + reason)
    return "\n".join(parts)


def _rule_based_bull(analysis):
    bull = analysis.get("bull_case") or {}
    parts = ["BULL CASE - score %s out of 10" % bull.get("bull_score"), ""]
    for point in bull.get("points", []):
        parts.append("- %s (%s evidence)" % (point["point"], point["strength"]))
        parts.append("    " + point["evidence"])
    parts.append("\nHow the score works: " + str(bull.get("methodology")))
    return "\n".join(parts)


def _rule_based_bear(analysis):
    bear = analysis.get("bear_case") or {}
    parts = ["BEAR CASE - risk score %s out of 10" % bear.get("risk_score"), ""]
    for point in bear.get("points", []):
        parts.append("- %s (%s evidence)" % (point["point"], point["strength"]))
        parts.append("    " + point["evidence"])
    parts.append("\nHow the score works: " + str(bear.get("methodology")))
    return "\n".join(parts)


def _rule_based_quarterly(analysis):
    quarters = (analysis.get("quarterly") or {}).get("quarters") or []
    if not quarters:
        return "No quarterly results were available from the data provider."

    latest = quarters[-1]
    parts = [
        "LATEST QUARTER: " + str(latest.get("period")),
        _line("  Revenue", latest.get("revenue"), " Rs crore"),
        _line("  Revenue growth year on year", latest.get("revenue_yoy_pct"), "%"),
        _line("  Revenue growth quarter on quarter", latest.get("revenue_qoq_pct"), "%"),
        _line("  EBITDA", latest.get("ebitda"), " Rs crore"),
        _line("  EBITDA margin", latest.get("ebitda_margin"), "%"),
        _line("  Net profit", latest.get("net_profit"), " Rs crore"),
        _line("  Profit growth year on year", latest.get("profit_yoy_pct"), "%"),
        _line("  EPS", latest.get("eps")),
        "",
    ]

    yoy = latest.get("revenue_yoy_pct")
    profit_yoy = latest.get("profit_yoy_pct")
    if yoy is not None and profit_yoy is not None:
        if yoy > 0 and profit_yoy > yoy:
            parts.append("WHAT IMPROVED: profit grew faster than revenue, so margins widened.")
        elif yoy > 0 and profit_yoy < 0:
            parts.append("WHAT DETERIORATED: revenue rose but profit fell, so costs outpaced sales.")
        elif yoy < 0:
            parts.append("WHAT DETERIORATED: revenue fell versus the same quarter last year.")
        else:
            parts.append("The quarter was broadly in line with the same quarter a year earlier.")

    if latest.get("exceptional_items"):
        parts.append(
            "NOTE: this quarter included an exceptional item of about Rs %s crore, so the "
            "headline profit is not directly comparable." % latest["exceptional_items"]
        )

    parts.append(
        "\nMANAGEMENT COMMENTARY: not available. This app has no licensed source for "
        "earnings-call transcripts, so nothing is quoted rather than invented."
    )
    parts.append(
        "WHAT TO WATCH NEXT QUARTER: whether the revenue trend continues, whether the "
        "margin holds, and whether operating cash flow keeps pace with reported profit."
    )
    return "\n".join(parts)


def _rule_based_beginner(analysis):
    company = analysis.get("company") or {}
    fundamentals = analysis.get("fundamentals") or {}
    profitability = fundamentals.get("profitability") or {}
    growth = fundamentals.get("growth") or {}
    health = fundamentals.get("financial_health") or {}
    ratios = (analysis.get("valuation") or {}).get("ratios") or {}

    name = company.get("company_name", "This company")
    return "\n".join([
        "%s works in %s, inside the %s sector."
        % (name, company.get("industry"), company.get("sector")),
        "",
        "IS IT GROWING?",
        "  Last year it sold Rs %s crore worth of goods and services, %s percent more than "
        "the year before. Growing sales usually means more customers or higher prices."
        % (growth.get("revenue"), growth.get("revenue_yoy_pct")),
        "",
        "DOES IT MAKE MONEY?",
        "  Out of every Rs 100 of sales, about Rs %s stayed as final profit. That is what "
        "'net profit margin' means." % profitability.get("pat_margin_pct"),
        "  ROE of %s percent means that for every Rs 100 the owners have tied up in the "
        "business, it earned that much profit in a year." % profitability.get("roe_pct"),
        "",
        "DOES IT OWE MONEY?",
        "  Debt-to-equity is %s. Read it as: for every Rs 1 the owners put in, the company "
        "borrowed that much. Lower is safer." % health.get("debt_to_equity"),
        "",
        "IS THE SHARE EXPENSIVE?",
        "  The P/E ratio is %s. If a company earns Rs 10 per share and the share costs "
        "Rs 200, its P/E is 20 - you are paying Rs 20 for every Rs 1 of yearly earnings. "
        "A higher number means paying more for the same earnings, usually because buyers "
        "expect growth." % ratios.get("pe_ratio"),
        "",
        "WHAT THIS DOES NOT TELL YOU",
        "  Past numbers do not decide future ones. Nothing here is advice about whether to "
        "buy. Read the company's annual report and think about your own situation first.",
    ])


def _rule_based_summary(analysis):
    scores = analysis.get("scores") or {}
    thesis = analysis.get("thesis") or {}
    bull = analysis.get("bull_case") or {}
    risks = (analysis.get("risks") or {}).get("risks") or []
    catalysts = (analysis.get("catalysts") or {}).get("catalysts") or []

    parts = ["STOCKIQ SUMMARY", ""]
    for category in scores.get("categories", []):
        score = category["score"]
        shown = "not scored" if score is None else "%s/10" % score
        parts.append("  %-20s %s" % (category["category"], shown))
    parts.append("  %-20s %s" % ("OVERALL", scores.get("overall_score")))
    parts.append("")
    parts.append("OVERALL VIEW: " + str(thesis.get("overall_view")))
    parts.append("  " + str(thesis.get("view_method")))

    if bull.get("points"):
        top = bull["points"][0]
        parts.append("\nSTRONGEST POSITIVE")
        parts.append("  " + top["point"] + " - " + top["evidence"])
    if risks:
        parts.append("\nBIGGEST RISK")
        parts.append("  " + risks[0]["title"] + " - " + risks[0]["explanation"])
    if catalysts:
        parts.append("\nKEY CATALYST")
        parts.append("  " + catalysts[0]["catalyst"] + " - " + catalysts[0]["why_it_matters"])

    parts.append("\nWHAT TO WATCH")
    for item in (thesis.get("what_must_go_right") or [])[:4]:
        parts.append("  - " + item)

    parts.append("\nWHAT WOULD CHANGE THIS VIEW")
    for item in (thesis.get("what_would_prove_it_wrong") or [])[:4]:
        parts.append("  - " + item)

    parts.append("\n" + str(scores.get("warning")))
    return "\n".join(parts)


def _rule_based_news(articles):
    parts = ["NEWS SUMMARY", ""]
    for article in articles[:8]:
        flag = " [UNVERIFIED]" if article.get("unverified") else ""
        parts.append("- [%s]%s %s" % (article.get("sentiment"), flag, article.get("headline")))
        parts.append("    Source: %s | Date: %s" % (article.get("source"), article.get("date")))
    parts.append("\nSentiment labels come from keyword matching, not from a model.")
    return "\n".join(parts)


def _rule_based_chat(question, analysis):
    """Answer common questions by looking up the computed numbers directly.

    Deliberately simple keyword routing. It cannot handle everything, and when
    it cannot it says so rather than making something up.
    """
    lowered = question.lower()
    fundamentals = analysis.get("fundamentals") or {}
    profitability = fundamentals.get("profitability") or {}
    health = fundamentals.get("financial_health") or {}
    growth = fundamentals.get("growth") or {}
    ratios = (analysis.get("valuation") or {}).get("ratios") or {}

    if any(word in lowered for word in ("risk", "worry", "danger", "concern", "bear")):
        return _rule_based_bear(analysis)
    if any(word in lowered for word in ("bull", "positive", "why buy", "strength")):
        return _rule_based_bull(analysis)
    if any(word in lowered for word in ("p/e", "pe ratio", "expensive", "cheap", "valuation", "valued")):
        return _rule_based_valuation(analysis)
    if any(word in lowered for word in ("debt", "balance sheet", "loan", "borrow")):
        return (
            "Debt to equity is %s and interest cover is %s times. Total debt is Rs %s crore "
            "against cash of Rs %s crore."
            % (health.get("debt_to_equity"), health.get("interest_coverage"),
               health.get("total_debt"), health.get("cash"))
        )
    if any(word in lowered for word in ("profit", "margin", "roe", "profitable")):
        return (
            "Net profit margin is %s percent, EBITDA margin is %s percent, ROE is %s percent "
            "and ROCE is %s percent. Profit changed %s percent year on year."
            % (profitability.get("pat_margin_pct"), profitability.get("ebitda_margin_pct"),
               profitability.get("roe_pct"), profitability.get("roce_pct"),
               growth.get("profit_yoy_pct"))
        )
    if any(word in lowered for word in ("technical", "chart", "rsi", "trend", "fall", "fell", "drop")):
        return _rule_based_technical(analysis)
    if any(word in lowered for word in ("quarter", "result", "earning")):
        return _rule_based_quarterly(analysis)
    if any(word in lowered for word in ("beginner", "simple", "explain like")):
        return _rule_based_beginner(analysis)
    if any(word in lowered for word in ("summary", "overall", "verdict")):
        return _rule_based_summary(analysis)

    return (
        "No AI key is configured, so I can only answer from a fixed set of topics: risks, "
        "the bull case, valuation, debt, profitability, technicals, quarterly results, or a "
        "beginner explanation. Try rephrasing around one of those, or add an AI_API_KEY to "
        "your .env file for full conversational answers.\n\n"
        "Here are the headline numbers I do have:\n"
        + _line("  Price", (analysis.get("price") or {}).get("price"), " Rs") + "\n"
        + _line("  P/E", ratios.get("pe_ratio")) + "\n"
        + _line("  ROE", profitability.get("roe_pct"), " percent") + "\n"
        + _line("  Debt/equity", health.get("debt_to_equity"))
    )
