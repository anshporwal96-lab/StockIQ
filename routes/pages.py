"""
routes/pages.py
===============
The routes that return HTML pages (as opposed to JSON).

Flask's render_template() looks inside the templates/ folder, fills in any
{{ variables }} and returns the finished HTML to the browser. The pages then
call the JSON API with fetch() to load their data.

Why separate HTML routes from API routes? Because it keeps a clean line
between "what the user sees" and "what the data layer returns" - and it means
you could later replace all these pages with a React app without touching a
single API route.
"""

from flask import Blueprint, render_template, request, session

from config import Config
from services import stock_service
from utils.security import get_csrf_token

pages_bp = Blueprint("pages", __name__)


def _base_context():
    """Values every page needs. Passed into each template."""
    return {
        "csrf_token": get_csrf_token(),
        "logged_in": bool(session.get("user_id")),
        "username": session.get("username"),
        "using_demo_data": Config.using_demo_data(),
        "ai_enabled": Config.ai_enabled(),
        "data_provider": Config.DATA_PROVIDER,
    }


@pages_bp.route("/")
def home():
    """The homepage: hero, search, market overview."""
    return render_template("index.html", **_base_context())


@pages_bp.route("/markets")
def markets():
    """Market overview: indices, gainers, losers, most active."""
    return render_template("dashboard.html", **_base_context())


@pages_bp.route("/stock/<symbol>")
def stock_page(symbol):
    """The main event: the full stock dashboard with all its tabs."""
    resolved = stock_service.resolve_symbol(symbol)
    context = _base_context()
    context["symbol"] = resolved or str(symbol).upper()
    context["found"] = bool(resolved)
    return render_template("stock.html", **context)


@pages_bp.route("/compare")
def compare_page():
    """Side-by-side comparison of 2 to 5 stocks."""
    context = _base_context()
    context["preset"] = request.args.get("stocks", "")
    return render_template("compare.html", **context)


@pages_bp.route("/watchlist")
def watchlist_page():
    return render_template("watchlist.html", **_base_context())


@pages_bp.route("/learn")
def learn_page():
    """The glossary that powers Beginner Mode."""
    return render_template("learn.html", **_base_context())


@pages_bp.route("/login")
def login_page():
    return render_template("login.html", **_base_context())


@pages_bp.route("/register")
def register_page():
    return render_template("register.html", **_base_context())


@pages_bp.route("/profile")
def profile_page():
    return render_template("profile.html", **_base_context())
