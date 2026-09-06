"""
models/user.py
==============
The `users` table plus password helpers.

SECURITY RULE: we never, ever store the plaintext password.
We store a one-way hash produced by Werkzeug (PBKDF2 with a random salt).
Given the hash you cannot work backwards to the password.
"""

from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from database.db import db


class User(db.Model):
    """One row per registered person."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # `watchlist_items` lets us write `user.watchlist_items` to get every saved
    # stock. cascade="all, delete-orphan" means deleting a user also deletes
    # their watchlist rows, so no orphaned data is left behind.
    watchlist_items = db.relationship(
        "WatchlistItem", back_populates="user", cascade="all, delete-orphan"
    )

    # ----- password helpers ------------------------------------------------
    def set_password(self, plain_password: str) -> None:
        """Hash the password and store only the hash."""
        self.password_hash = generate_password_hash(plain_password)

    def check_password(self, plain_password: str) -> bool:
        """Return True if the supplied password matches the stored hash."""
        return check_password_hash(self.password_hash, plain_password)

    # ----- serialisation ---------------------------------------------------
    def to_dict(self) -> dict:
        """Convert to a plain dictionary for a JSON response.

        Note there is deliberately no `password_hash` here - it must never be
        sent to the browser.
        """
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<User {self.username}>"
