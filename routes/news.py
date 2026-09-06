"""
routes/news.py
==============
News endpoints. Paginated, because loading 50 articles at once would make the
page slow for no benefit.
"""

from flask import Blueprint, jsonify, request

from services import ai_service, news_service, stock_service
from utils.security import rate_limit

news_bp = Blueprint("news", __name__)


@news_bp.route("/stock/<symbol>/news", methods=["GET"])
@rate_limit("news", per_minute=40)
def stock_news(symbol):
    """GET /api/stock/TCS/news?page=1

    Each article carries: headline, date, source, summary, why it matters and
    a sentiment label. Anything whose wording suggests it is unconfirmed is
    flagged `unverified` so the UI can mark it.
    """
    resolved = stock_service.resolve_symbol(symbol)
    if not resolved:
        return jsonify({
            "error": "not_found",
            "message": "We could not find a stock matching '%s'." % symbol,
        }), 404

    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1

    try:
        payload = news_service.get_news(resolved, page=page)
        payload["sentiment_summary"] = news_service.summarise_sentiment(payload["articles"])
        if not payload["articles"]:
            payload["message"] = (
                "No news was available for this stock from the configured sources. "
                "We show nothing rather than filling the space with unrelated articles."
            )
        return jsonify(payload)
    except Exception as error:
        return jsonify({
            "error": "news_error",
            "message": "We could not load the news right now. Please try again later.",
            "detail": str(error),
        }), 503


@news_bp.route("/stock/<symbol>/news/summary", methods=["GET"])
@rate_limit("ai", per_minute=12)
def news_summary(symbol):
    """GET /api/stock/TCS/news/summary - an AI (or rule-based) read of the news."""
    resolved = stock_service.resolve_symbol(symbol)
    if not resolved:
        return jsonify({"error": "not_found"}), 404

    try:
        # per_page is large here so the summary considers every article,
        # not just the first page.
        payload = news_service.get_news(resolved, per_page=50)
        return jsonify(ai_service.analyze_news_ai(resolved, payload))
    except Exception as error:
        return jsonify({
            "error": "news_error",
            "message": "We could not summarise the news right now.",
            "detail": str(error),
        }), 503
