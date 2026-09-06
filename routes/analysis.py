"""
routes/analysis.py
==================
The analysis and AI endpoints.

The important one is POST /api/ai/chat. Notice what it does:

    1. Build the FULL structured analysis for the stock (all Python maths)
    2. Pass that structured data to the AI together with the question
    3. Return the AI's answer

The browser never talks to the AI provider, and never sees the API key. It only
ever talks to Flask.
"""

from flask import Blueprint, jsonify, request

from config import Config
from services import ai_service, financial_service, news_service, stock_service
from services.providers import DataProviderError
from utils.security import rate_limit, require_csrf

analysis_bp = Blueprint("analysis", __name__)


def _resolve(raw_symbol):
    return stock_service.resolve_symbol(raw_symbol)


def _not_found(raw_symbol):
    return jsonify({
        "error": "not_found",
        "message": "We could not find a stock matching '%s'." % raw_symbol,
    }), 404


@analysis_bp.route("/stock/<symbol>/analysis", methods=["GET"])
@rate_limit("analysis", per_minute=40)
def full_analysis(symbol):
    """GET /api/stock/TCS/analysis

    Everything the Python side computed: fundamentals, technicals, valuation,
    risks, bull case, bear case, scenarios, thesis, catalysts, governance and
    the score. No AI involved - this is pure arithmetic.
    """
    resolved = _resolve(symbol)
    if not resolved:
        return _not_found(symbol)
    try:
        return jsonify(financial_service.build_full_analysis(resolved))
    except DataProviderError as error:
        return jsonify({
            "error": "provider_error",
            "message": "We could not build the analysis: " + str(error),
        }), 503
    except Exception as error:
        return jsonify({
            "error": "server_error",
            "message": "Something went wrong while building the analysis.",
            "detail": str(error),
        }), 500


@analysis_bp.route("/stock/<symbol>/ai/<section>", methods=["GET"])
@rate_limit("ai", per_minute=Config.RATE_LIMIT_AI_PER_MINUTE)
def ai_section(symbol, section):
    """GET /api/stock/TCS/ai/summary

    Valid sections: fundamental, technical, valuation, bull, bear, quarterly,
    beginner, summary.

    Each one is written by the AI from the structured numbers - or by the
    app's own rule-based writer when no AI key is set. The response says which.
    """
    resolved = _resolve(symbol)
    if not resolved:
        return _not_found(symbol)

    writers = {
        "fundamental": ai_service.analyze_fundamentals_ai,
        "technical": ai_service.analyze_technicals_ai,
        "valuation": ai_service.analyze_valuation_ai,
        "bull": ai_service.generate_bull_case_ai,
        "bear": ai_service.generate_bear_case_ai,
        "quarterly": ai_service.analyze_quarterly_ai,
        "beginner": ai_service.explain_for_beginner_ai,
        "summary": ai_service.generate_final_summary,
    }
    if section not in writers:
        return jsonify({
            "error": "bad_section",
            "message": "Section must be one of: " + ", ".join(sorted(writers)),
        }), 400

    try:
        analysis = financial_service.build_full_analysis(resolved)
        return jsonify(writers[section](analysis))
    except DataProviderError as error:
        return jsonify({"error": "provider_error", "message": str(error)}), 503
    except Exception as error:
        return jsonify({
            "error": "ai_error",
            "message": "The analysis could not be generated. Please try again.",
            "detail": str(error),
        }), 500


@analysis_bp.route("/ai/chat", methods=["POST"])
@rate_limit("ai", per_minute=Config.RATE_LIMIT_AI_PER_MINUTE)
@require_csrf
def ai_chat():
    """POST /api/ai/chat

    Body: {"symbol": "TCS", "question": "What are the biggest risks?",
           "history": [{"role": "user", "content": "..."}]}

    The `history` is optional and lets the chat remember the last few turns.
    """
    body = request.get_json(silent=True) or {}
    raw_symbol = body.get("symbol", "")
    question = str(body.get("question", "")).strip()
    history = body.get("history") or []

    if not question:
        return jsonify({"error": "no_question", "message": "Please type a question."}), 400

    resolved = _resolve(raw_symbol)
    if not resolved:
        return _not_found(raw_symbol)

    try:
        analysis = financial_service.build_full_analysis(resolved)
        result = ai_service.chat(resolved, question, analysis, history)
        result["symbol"] = resolved
        return jsonify(result)
    except DataProviderError as error:
        return jsonify({"error": "provider_error", "message": str(error)}), 503
    except Exception as error:
        return jsonify({
            "error": "ai_error",
            "message": "The assistant could not answer right now. Please try again.",
            "detail": str(error),
        }), 500


@analysis_bp.route("/stock/<symbol>/score", methods=["GET"])
def stock_score(symbol):
    """GET /api/stock/TCS/score - just the scorecard and its methodology."""
    resolved = _resolve(symbol)
    if not resolved:
        return _not_found(symbol)
    try:
        analysis = financial_service.build_full_analysis(resolved)
        return jsonify({
            "symbol": resolved,
            "scores": analysis["scores"],
            "thesis": analysis["thesis"],
        })
    except Exception as error:
        return jsonify({"error": "server_error", "detail": str(error)}), 500


@analysis_bp.route("/status", methods=["GET"])
def status():
    """GET /api/status - what the app is currently configured to use.

    The frontend reads this to decide whether to show the DEMO DATA badge and
    whether the AI banner should say "AI" or "rule-based". No secrets are
    included: we report only WHETHER a key is set, never the key itself.
    """
    return jsonify({
        "data_provider": Config.DATA_PROVIDER,
        "using_demo_data": Config.using_demo_data(),
        "ai_enabled": Config.ai_enabled(),
        "ai_model": Config.AI_MODEL if Config.ai_enabled() else None,
        "news_api_configured": bool(Config.NEWS_API_KEY),
        "cache_ttl_seconds": Config.CACHE_TTL,
        "disclaimer": (
            "StockIQ India is for educational and research purposes only. AI-generated "
            "analysis may contain errors and is not personalised investment advice. "
            "Verify information independently and consider your own financial situation, "
            "investment horizon and risk tolerance before making investment decisions."
        ),
    })
