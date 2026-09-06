"""
routes/watchlist.py
===================
The user's saved stocks. Every route requires a login, because a watchlist
belongs to one person.

Notice that every query filters by `user_id=session["user_id"]`. That is what
stops one user from reading or deleting another user's rows - never trust a
user id sent from the browser.
"""

from flask import Blueprint, jsonify, request, session

from database.db import db
from models.watchlist import WatchlistItem
from services import financial_service, stock_service
from utils.security import login_required, require_csrf

watchlist_bp = Blueprint("watchlist", __name__)


@watchlist_bp.route("/watchlist", methods=["GET"])
@login_required
def get_watchlist():
    """GET /api/watchlist - saved stocks with live price and scores.

    `?full=1` also computes the AI score and the fundamental/technical views.
    That is slower, so the default is the light version.
    """
    items = (
        WatchlistItem.query
        .filter_by(user_id=session["user_id"])
        .order_by(WatchlistItem.created_at.desc())
        .all()
    )
    want_full = request.args.get("full") in ("1", "true", "yes")

    rows = []
    for item in items:
        row = item.to_dict()
        try:
            info = stock_service.get_company_info(item.stock_symbol)
            price = stock_service.get_current_price(item.stock_symbol)
            row["company_name"] = info.get("company_name")
            row["sector"] = info.get("sector")
            row["price"] = price.get("price")
            row["change_pct"] = price.get("change_pct")
            row["is_demo"] = info.get("is_demo", False)

            if want_full:
                analysis = financial_service.build_full_analysis(item.stock_symbol)
                row["score"] = (analysis.get("scores") or {}).get("overall_score")
                row["fundamental_view"] = (analysis.get("thesis") or {}).get("overall_view")
                row["technical_view"] = (analysis.get("technicals") or {}).get("view")
        except Exception as error:
            # One bad symbol must not empty the whole watchlist.
            row["error"] = "Could not load live data (%s)" % error

        rows.append(row)

    return jsonify({"count": len(rows), "items": rows})


@watchlist_bp.route("/watchlist", methods=["POST"])
@login_required
@require_csrf
def add_to_watchlist():
    """POST /api/watchlist  body: {"symbol": "TCS", "note": "optional"}"""
    body = request.get_json(silent=True) or {}
    symbol = stock_service.resolve_symbol(body.get("symbol", ""))
    if not symbol:
        return jsonify({
            "error": "not_found",
            "message": "We could not find that stock. Check the symbol and try again.",
        }), 404

    existing = WatchlistItem.query.filter_by(
        user_id=session["user_id"], stock_symbol=symbol
    ).first()
    if existing:
        return jsonify({
            "ok": True,
            "already_present": True,
            "message": symbol + " is already on your watchlist.",
            "item": existing.to_dict(),
        })

    item = WatchlistItem(
        user_id=session["user_id"],
        stock_symbol=symbol,
        note=str(body.get("note", ""))[:255],
    )
    try:
        db.session.add(item)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({
            "error": "database_error",
            "message": "We could not save that right now. Please try again.",
        }), 500

    return jsonify({"ok": True, "item": item.to_dict()}), 201


@watchlist_bp.route("/watchlist/<symbol>", methods=["DELETE"])
@login_required
@require_csrf
def remove_from_watchlist(symbol):
    """DELETE /api/watchlist/TCS"""
    item = WatchlistItem.query.filter_by(
        user_id=session["user_id"], stock_symbol=str(symbol).upper()
    ).first()
    if not item:
        return jsonify({
            "error": "not_found",
            "message": symbol + " is not on your watchlist.",
        }), 404

    try:
        db.session.delete(item)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "database_error", "message": "Could not remove it."}), 500

    return jsonify({"ok": True, "removed": str(symbol).upper()})


@watchlist_bp.route("/watchlist/check/<symbol>", methods=["GET"])
@login_required
def check_watchlist(symbol):
    """GET /api/watchlist/check/TCS - is this already saved?

    Used to draw the star on the stock page filled or hollow.
    """
    resolved = stock_service.resolve_symbol(symbol) or str(symbol).upper()
    exists = WatchlistItem.query.filter_by(
        user_id=session["user_id"], stock_symbol=resolved
    ).first() is not None
    return jsonify({"symbol": resolved, "in_watchlist": exists})
