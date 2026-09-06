"""
models/watchlist.py
===================
The `watchlist` table: which stocks a user has starred.
"""

from datetime import datetime, timezone

from database.db import db


class WatchlistItem(db.Model):
    """One row = one stock saved by one user."""

    __tablename__ = "watchlist"

    id = db.Column(db.Integer, primary_key=True)

    # ForeignKey ties this row to a row in the `users` table.
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    stock_symbol = db.Column(db.String(30), nullable=False)
    note = db.Column(db.String(255), default="")
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    user = db.relationship("User", back_populates="watchlist_items")

    # A person should not be able to add the same stock twice.
    __table_args__ = (
        db.UniqueConstraint("user_id", "stock_symbol", name="uq_user_symbol"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "symbol": self.stock_symbol,
            "note": self.note or "",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<WatchlistItem {self.stock_symbol} for user {self.user_id}>"
