"""
routes/auth.py
==============
Registration, login, logout and profile.

HOW A FLASK BLUEPRINT WORKS
---------------------------
A Blueprint is a group of related routes. We build one here, then app.py
"registers" it with a URL prefix. So the route below written as

    @auth_bp.route("/register", methods=["POST"])

becomes the real URL /api/auth/register once app.py registers this blueprint
with url_prefix="/api/auth".

HOW LOGIN WORKS HERE
--------------------
On a successful login we put the user's id into `session`. Flask signs that
session with SECRET_KEY and stores it in a cookie. On the next request Flask
verifies the signature, so a user cannot edit the cookie to become someone
else. We never put the password (or its hash) in the session.
"""

from flask import Blueprint, jsonify, request, session

from database.db import db
from models.user import User
from utils.security import current_user, get_csrf_token, login_required, rate_limit, require_csrf
from utils.validators import validate_registration

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/csrf-token", methods=["GET"])
def csrf_token():
    """The frontend calls this once on page load and then sends the token back
    in the X-CSRF-Token header on every POST/DELETE."""
    return jsonify({"csrf_token": get_csrf_token()})


@auth_bp.route("/register", methods=["POST"])
@rate_limit("register", per_minute=6)
@require_csrf
def register():
    """Create a new account.

    Steps:
      1. Validate the input
      2. Check the username and email are not already taken
      3. Hash the password (never store the plaintext)
      4. Save the user and log them straight in
    """
    data = request.get_json(silent=True) or request.form or {}
    username = str(data.get("username", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    problems = validate_registration(username, email, password)
    if problems:
        return jsonify({"error": "validation_failed", "messages": problems}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "taken", "message": "That username is already registered."}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "taken", "message": "That email is already registered."}), 409

    user = User(username=username, email=email)
    user.set_password(password)     # hashes it - the plaintext is never stored

    try:
        db.session.add(user)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({
            "error": "database_error",
            "message": "We could not create your account right now. Please try again.",
        }), 500

    # Clearing the session first prevents "session fixation": an attacker who
    # somehow knew the visitor's old session id cannot reuse it once logged in.
    # Clearing also wipes the CSRF token, so we issue a fresh one and return it
    # for the frontend to store.
    session.clear()
    session["user_id"] = user.id
    session["username"] = user.username
    session.permanent = True

    return jsonify({
        "ok": True,
        "user": user.to_dict(),
        "csrf_token": get_csrf_token(),
    }), 201


@auth_bp.route("/login", methods=["POST"])
@rate_limit("login", per_minute=10)
@require_csrf
def login():
    """Sign in with username (or email) and password."""
    data = request.get_json(silent=True) or request.form or {}
    identifier = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    if not identifier or not password:
        return jsonify({
            "error": "missing_fields",
            "message": "Please enter both your username and password.",
        }), 400

    user = User.query.filter_by(username=identifier).first()
    if not user:
        user = User.query.filter_by(email=identifier.lower()).first()

    # The same message for "no such user" and "wrong password" on purpose:
    # a different message would tell an attacker which usernames exist.
    if not user or not user.check_password(password):
        return jsonify({
            "error": "invalid_credentials",
            "message": "Username or password is incorrect.",
        }), 401

    # A fresh session on login (see the note in register above), plus a fresh
    # CSRF token returned to the caller.
    session.clear()
    session["user_id"] = user.id
    session["username"] = user.username
    session.permanent = True

    return jsonify({
        "ok": True,
        "user": user.to_dict(),
        "csrf_token": get_csrf_token(),
    })


@auth_bp.route("/logout", methods=["POST"])
@require_csrf
def logout():
    """Clear the session. The cookie becomes useless immediately."""
    session.clear()
    # A logged-out visitor still needs a CSRF token to be able to log back in.
    return jsonify({"ok": True, "csrf_token": get_csrf_token()})


@auth_bp.route("/me", methods=["GET"])
def me():
    """Who is logged in? The frontend calls this to decide whether to show
    "Login" or the username in the header."""
    user = current_user()
    if not user:
        return jsonify({"logged_in": False})
    return jsonify({"logged_in": True, "user": user.to_dict()})


@auth_bp.route("/profile", methods=["GET"])
@login_required
def profile():
    """Account details plus a count of saved stocks."""
    user = current_user()
    return jsonify({
        "user": user.to_dict(),
        "watchlist_count": len(user.watchlist_items),
    })


@auth_bp.route("/change-password", methods=["POST"])
@login_required
@require_csrf
def change_password():
    """Change the password, after confirming the current one."""
    data = request.get_json(silent=True) or {}
    user = current_user()

    if not user.check_password(str(data.get("current_password", ""))):
        return jsonify({
            "error": "invalid_credentials",
            "message": "Your current password is incorrect.",
        }), 401

    new_password = str(data.get("new_password", ""))
    problems = validate_registration(user.username, user.email, new_password)
    password_problems = [p for p in problems if "Password" in p]
    if password_problems:
        return jsonify({"error": "validation_failed", "messages": password_problems}), 400

    user.set_password(new_password)
    db.session.commit()
    return jsonify({"ok": True, "message": "Password updated."})
