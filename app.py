"""
app.py
======
The starting point of the whole application.

RUN IT WITH:
    python app.py
then open http://127.0.0.1:5000 in your browser.

WHAT FLASK ACTUALLY DOES
------------------------
Flask is a web framework. It listens for HTTP requests from a browser, matches
the URL against a list of routes, runs the matching Python function, and sends
back whatever that function returns (HTML or JSON).

That is the entire idea. Everything else in this project is ordinary Python
sitting behind those routes.

THE APPLICATION FACTORY
-----------------------
Instead of creating the app at import time we build it inside create_app().
That makes testing easy: a test can build a fresh app with a throwaway
database, and it does not interfere with the real one.
"""

from datetime import timedelta

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from config import Config
from database.db import init_db


def create_app(config_object=Config):
    """Build and return a configured Flask application."""

    app = Flask(__name__)
    app.config.from_object(config_object)

    # How long a login lasts before the user has to sign in again.
    app.permanent_session_lifetime = timedelta(days=14)

    # CORS lets a page served from a different origin call our API. We keep it
    # limited to /api/* and allow credentials so the session cookie still works.
    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

    # ----- database -------------------------------------------------------
    # Creates the SQLite file and the tables if they do not exist yet, then
    # seeds the stock reference list.
    init_db(app)

    # ----- register the routes -------------------------------------------
    # Each blueprint is a group of related routes. url_prefix is glued onto
    # the front of every route inside it.
    from routes.analysis import analysis_bp
    from routes.auth import auth_bp
    from routes.news import news_bp
    from routes.pages import pages_bp
    from routes.stocks import stocks_bp
    from routes.watchlist import watchlist_bp

    app.register_blueprint(pages_bp)                              # /, /stock/TCS, ...
    app.register_blueprint(stocks_bp, url_prefix="/api")          # /api/search, /api/stock/...
    app.register_blueprint(analysis_bp, url_prefix="/api")        # /api/stock/TCS/analysis
    app.register_blueprint(news_bp, url_prefix="/api")            # /api/stock/TCS/news
    app.register_blueprint(watchlist_bp, url_prefix="/api")       # /api/watchlist
    app.register_blueprint(auth_bp, url_prefix="/api/auth")       # /api/auth/login

    # ----- error handlers -------------------------------------------------
    # Requirement 40: friendly messages, never a stack trace in the browser.

    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith("/api/"):
            return jsonify({
                "error": "not_found",
                "message": "That endpoint does not exist. See the README for the API list.",
            }), 404
        return render_template("error.html", code=404,
                               message="We could not find that page."), 404

    @app.errorhandler(429)
    def too_many(error):
        return jsonify({
            "error": "rate_limited",
            "message": "Too many requests. Please wait a minute and try again.",
        }), 429

    @app.errorhandler(500)
    def server_error(error):
        if request.path.startswith("/api/"):
            return jsonify({
                "error": "server_error",
                "message": "Something went wrong on our side. Please try again.",
            }), 500
        return render_template("error.html", code=500,
                               message="Something went wrong on our side."), 500

    # ----- security headers ----------------------------------------------
    @app.after_request
    def add_security_headers(response):
        """A few standard headers that cost nothing and prevent common attacks."""
        response.headers["X-Content-Type-Options"] = "nosniff"   # no MIME sniffing
        response.headers["X-Frame-Options"] = "SAMEORIGIN"       # no clickjacking
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    return app


# Created at import time so `flask run` and WSGI servers such as gunicorn can
# find it as `app:app`.
app = create_app()


if __name__ == "__main__":
    print("")
    print("  StockIQ India")
    print("  -------------")
    print("  Data provider : %s%s" % (
        Config.DATA_PROVIDER,
        "   *** DEMO DATA - not real market data ***" if Config.using_demo_data() else "",
    ))
    print("  AI            : %s" % (
        Config.AI_MODEL if Config.ai_enabled()
        else "no key set - using the built-in rule-based writer"
    ))
    print("  Database      : %s" % Config.SQLALCHEMY_DATABASE_URI)
    print("")
    print("  Open http://127.0.0.1:5000 in your browser. Press CTRL+C to stop.")
    print("")

    # debug=True reloads the server whenever you save a file, and shows a
    # detailed error page. Never use it on a public server.
    app.run(host="127.0.0.1", port=5000, debug=Config.DEBUG)
