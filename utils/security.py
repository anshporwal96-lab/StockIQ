"""
utils/security.py
=================
Small security helpers used by the routes:

  * CSRF protection for state-changing requests
  * A simple per-IP rate limiter
  * A @login_required decorator

WHAT IS CSRF?
-------------
Cross-Site Request Forgery. Another website could quietly make your browser
send a POST to our app while you are logged in - your cookie goes along
automatically, so the request looks genuine.

The fix: we keep a random token in the session, hand it to our own pages, and
require it back on every POST/DELETE. A different website cannot read our
session, so it cannot supply the token.
"""

import secrets
import time
from functools import wraps

from flask import jsonify, request, session

from config import Config

CSRF_SESSION_KEY = "_csrf_token"
CSRF_HEADER = "X-CSRF-Token"

# {"1.2.3.4:ai": [timestamp, timestamp, ...]} - in memory, resets on restart.
# Fine for a single-server learning project; use Redis if you ever run several.
_request_log = {}


def get_csrf_token():
    """Return this session's CSRF token, creating one on first use."""
    if CSRF_SESSION_KEY not in session:
        session[CSRF_SESSION_KEY] = secrets.token_urlsafe(32)
    return session[CSRF_SESSION_KEY]


def csrf_is_valid():
    """Check the token the browser sent against the one in the session.

    secrets.compare_digest compares in constant time, so an attacker cannot
    learn the token by measuring how long the comparison takes.
    """
    expected = session.get(CSRF_SESSION_KEY)
    if not expected:
        return False
    supplied = request.headers.get(CSRF_HEADER) or (request.form.get("csrf_token") if request.form else None)
    if not supplied and request.is_json:
        supplied = (request.get_json(silent=True) or {}).get("csrf_token")
    return bool(supplied) and secrets.compare_digest(str(supplied), str(expected))


def require_csrf(view):
    """Decorator: reject a state-changing request without a valid token."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and not csrf_is_valid():
            return jsonify({
                "error": "csrf_failed",
                "message": "Your session expired. Please refresh the page and try again.",
            }), 403
        return view(*args, **kwargs)
    return wrapper


def login_required(view):
    """Decorator: the caller must be signed in.

    Returns JSON 401 (not a redirect) because our frontend calls these
    endpoints with fetch() and needs a machine-readable answer.
    """
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({
                "error": "not_logged_in",
                "message": "Please log in to use this feature.",
            }), 401
        return view(*args, **kwargs)
    return wrapper


def rate_limit(bucket, per_minute=None):
    """Decorator: allow only N requests per minute per IP address.

    Protects the AI endpoint (which costs money per call) and stops one client
    from hammering the data provider and getting us rate-limited upstream.
    """
    limit = per_minute or Config.RATE_LIMIT_API_PER_MINUTE

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            # Tests fire hundreds of requests from one address in seconds, which
            # is exactly what this limiter exists to stop. Turn it off there.
            from flask import current_app
            if current_app.config.get("TESTING"):
                return view(*args, **kwargs)

            client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
            client_ip = client_ip.split(",")[0].strip()
            key = client_ip + ":" + bucket
            now = time.time()

            # Keep only the timestamps from the last 60 seconds.
            recent = [t for t in _request_log.get(key, []) if now - t < 60]
            if len(recent) >= limit:
                return jsonify({
                    "error": "rate_limited",
                    "message": "Too many requests. Please wait a minute and try again.",
                }), 429

            recent.append(now)
            _request_log[key] = recent
            return view(*args, **kwargs)
        return wrapper
    return decorator


def current_user():
    """Return the logged-in User row, or None."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    from database.db import db
    from models.user import User
    # db.session.get() is the SQLAlchemy 2.x way; User.query.get() is deprecated.
    return db.session.get(User, user_id)
