"""
services/news_service.py
========================
Fetches headlines and labels them, without ever inventing one.

THREE SOURCES, IN ORDER OF PREFERENCE
-------------------------------------
  1. The configured data provider (exchange filings when it has them)
  2. NewsAPI.org, if NEWS_API_KEY is set in .env
  3. Nothing - we return an honest "no news available" rather than filler

SENTIMENT
---------
Sentiment is assigned by simple keyword matching, NOT by the AI, so it is
cheap, instant and inspectable. The word lists are right here in the file, so
you can see exactly why an article was labelled negative and change it.
"""

import requests

from config import Config
from services.providers import get_provider
from utils import cache

# Keywords that push an article positive or negative. Deliberately short and
# readable - you can audit and edit this list.
POSITIVE_WORDS = [
    "profit rises", "profit jumps", "record", "beats", "upgrade", "expansion",
    "new order", "wins contract", "dividend", "buyback", "approval", "growth",
    "surge", "rally", "strong", "outperform", "margin expansion", "acquisition",
]
NEGATIVE_WORDS = [
    "profit falls", "loss", "decline", "downgrade", "probe", "penalty", "fine",
    "resign", "fraud", "default", "delay", "cut", "weak", "slump", "plunge",
    "lawsuit", "recall", "margin pressure", "impairment", "qualification",
]

# Words that mark an item as unconfirmed. These get flagged in the UI so a
# rumour is never displayed as though it were a filing.
RUMOUR_WORDS = ["reportedly", "rumour", "rumor", "sources say", "speculation", "may consider"]

# Sources we treat as primary and authoritative, in the priority order the
# brief asks for.
PRIMARY_SOURCES = [
    "exchange filing", "nse", "bse", "sebi", "company announcement",
    "annual report", "investor presentation", "earnings call",
]


def classify_sentiment(text):
    """Score an article as positive / negative / neutral by counting keywords.

    Returns the label and the words that caused it, so the UI can show its
    reasoning instead of asking the user to trust a black box.
    """
    if not text:
        return "neutral", []

    lowered = text.lower()
    hits_positive = [word for word in POSITIVE_WORDS if word in lowered]
    hits_negative = [word for word in NEGATIVE_WORDS if word in lowered]

    if len(hits_positive) > len(hits_negative):
        return "positive", hits_positive
    if len(hits_negative) > len(hits_positive):
        return "negative", hits_negative
    return "neutral", hits_positive + hits_negative


def is_unverified(text):
    """True when the wording suggests the item is a rumour, not a fact."""
    lowered = (text or "").lower()
    return any(word in lowered for word in RUMOUR_WORDS)


def source_priority(source_name):
    """Lower number = more authoritative. Used to sort the news list so
    exchange filings appear above general commentary."""
    lowered = (source_name or "").lower()
    for index, primary in enumerate(PRIMARY_SOURCES):
        if primary in lowered:
            return index
    return len(PRIMARY_SOURCES) + 1


def _fetch_from_newsapi(company_name, limit):
    """Optional second source. Returns [] on any problem - never raises, and
    never falls back to invented articles."""
    if not Config.NEWS_API_KEY:
        return []
    try:
        response = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": company_name,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": limit,
            },
            headers={"X-Api-Key": Config.NEWS_API_KEY},
            timeout=8,
        )
        if response.status_code != 200:
            return []
        articles = []
        for item in response.json().get("articles", []):
            articles.append({
                "headline": item.get("title"),
                "date": item.get("publishedAt"),
                "source": (item.get("source") or {}).get("name") or "NewsAPI",
                "url": item.get("url"),
                "summary": item.get("description"),
                "why_it_matters": None,
                "sentiment": None,
                "verified": True,
                "is_demo": False,
            })
        return [a for a in articles if a["headline"]]
    except requests.RequestException:
        return []


def get_news(symbol, limit=12, page=1, per_page=6):
    """Fetch, label, sort and paginate the news for one stock.

    Pagination keeps the page light: the frontend asks for six at a time
    instead of downloading everything.
    """
    cached = cache.get(symbol, "news")
    if cached is None:
        articles = []
        provider_source = None

        # --- source 1: the configured data provider -----------------------
        try:
            provider_result = get_provider().get_news(symbol, limit)
            articles.extend(provider_result.get("articles") or [])
            provider_source = provider_result.get("source")
        except Exception:
            pass

        # --- source 2: NewsAPI, only if a key is configured ---------------
        from services.stock_service import get_company_info
        try:
            company_name = get_company_info(symbol).get("company_name") or symbol
        except Exception:
            company_name = symbol
        articles.extend(_fetch_from_newsapi(company_name, limit))

        # --- label every article -----------------------------------------
        for article in articles:
            text = " ".join(
                filter(None, [article.get("headline"), article.get("summary")])
            )
            if not article.get("sentiment"):
                label, keywords = classify_sentiment(text)
                article["sentiment"] = label
                article["sentiment_keywords"] = keywords
            article["unverified"] = is_unverified(text)
            article["source_rank"] = source_priority(article.get("source"))
            if not article.get("why_it_matters"):
                article["why_it_matters"] = _why_it_matters(article)

        # Most authoritative source first, then newest first.
        articles.sort(key=lambda a: (a.get("source_rank", 99), str(a.get("date") or "")), reverse=False)
        articles.sort(key=lambda a: str(a.get("date") or ""), reverse=True)
        articles.sort(key=lambda a: a.get("source_rank", 99))

        payload = {
            "symbol": symbol,
            "articles": articles,
            "source": provider_source,
            "is_demo": any(a.get("is_demo") for a in articles),
            "note": (
                "Sentiment is assigned by keyword matching, not by an AI, and is a rough "
                "signal only. Items flagged unverified use tentative wording and should "
                "not be treated as confirmed."
            ),
        }
        cached = cache.set(symbol, "news", payload)

    # --- paginate ---------------------------------------------------------
    all_articles = cached.get("articles") or []
    page = max(1, int(page))
    start = (page - 1) * per_page
    total_pages = max(1, -(-len(all_articles) // per_page))  # ceiling division

    result = dict(cached)
    result["articles"] = all_articles[start:start + per_page]
    result["pagination"] = {
        "page": page,
        "per_page": per_page,
        "total": len(all_articles),
        "total_pages": total_pages,
    }
    return result


def _why_it_matters(article):
    """A one-line explanation, chosen from the article's own sentiment and
    source. Kept deliberately generic - we do not pretend to know more about
    an article than its headline tells us."""
    sentiment = article.get("sentiment")
    rank = article.get("source_rank", 99)

    if rank <= 2:
        base = "This comes from a primary exchange or regulatory filing, so the facts in it are official."
    elif rank <= len(PRIMARY_SOURCES):
        base = "This is a company announcement, so it reflects what management chose to disclose."
    else:
        base = "This is media coverage, so weigh it against the company's own filings."

    if article.get("unverified"):
        return base + " The wording suggests it is not yet confirmed."
    if sentiment == "positive":
        return base + " On the face of it this is favourable, but check whether it is already in the price."
    if sentiment == "negative":
        return base + " This is a negative development. Check whether it is one-off or structural."
    return base


def summarise_sentiment(articles):
    """Count the sentiment labels, for the small summary bar on the News tab."""
    counts = {"positive": 0, "negative": 0, "neutral": 0}
    for article in articles:
        label = article.get("sentiment") or "neutral"
        counts[label] = counts.get(label, 0) + 1
    total = sum(counts.values()) or 1
    return {
        "counts": counts,
        "positive_pct": round(counts["positive"] / total * 100, 1),
        "negative_pct": round(counts["negative"] / total * 100, 1),
        "total": sum(counts.values()),
        "note": "Counts of keyword-matched labels. Not a market prediction.",
    }
