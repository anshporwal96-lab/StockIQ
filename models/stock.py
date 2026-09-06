"""
models/stock.py
===============
Two tables:

  * `stocks`      - the searchable index of listed companies
  * `cached_data` - a simple key/value store so we do not re-fetch the same
                    data from an external API over and over again

Storing the cache in the database (rather than only in memory) means the cache
survives a restart of the Flask server.
"""

import json
from datetime import datetime, timezone

from database.db import db


class Stock(db.Model):
    """One row per listed company."""

    __tablename__ = "stocks"

    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(30), unique=True, nullable=False, index=True)
    company_name = db.Column(db.String(255), nullable=False, index=True)
    bse_code = db.Column(db.String(20), index=True)
    exchange = db.Column(db.String(20), default="NSE/BSE")
    sector = db.Column(db.String(100))
    industry = db.Column(db.String(100))
    updated_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "company_name": self.company_name,
            "nse_symbol": self.symbol,
            "bse_code": self.bse_code,
            "exchange": self.exchange,
            "sector": self.sector,
            "industry": self.industry,
        }

    def __repr__(self):
        return f"<Stock {self.symbol}>"


class CachedData(db.Model):
    """A cached API response.

    `data` holds JSON as text. SQLite has no native JSON column, so we convert
    with json.dumps / json.loads in the helper methods below.
    """

    __tablename__ = "cached_data"

    id = db.Column(db.Integer, primary_key=True)
    stock_symbol = db.Column(db.String(30), nullable=False, index=True)
    data_type = db.Column(db.String(50), nullable=False, index=True)
    data = db.Column(db.Text, nullable=False)
    timestamp = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        db.UniqueConstraint("stock_symbol", "data_type", name="uq_symbol_type"),
    )

    def payload(self):
        """Turn the stored JSON text back into a Python dictionary."""
        try:
            return json.loads(self.data)
        except (ValueError, TypeError):
            return None

    def age_seconds(self):
        """How many seconds ago this row was written."""
        stored = self.timestamp
        if stored.tzinfo is None:
            # SQLite gives back naive datetimes; treat them as UTC.
            stored = stored.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - stored).total_seconds()

    def __repr__(self):
        return f"<CachedData {self.stock_symbol}/{self.data_type}>"


def seed_stock_universe():
    """Copy the reference company list into the `stocks` table.

    Runs on every start-up but only inserts rows that are missing, so it is
    safe and fast to call repeatedly.
    """
    from services.stock_universe import ALL_ROWS

    existing = {row[0] for row in db.session.query(Stock.symbol).all()}
    added = 0
    for row in ALL_ROWS:
        if row["symbol"] in existing:
            continue
        db.session.add(
            Stock(
                symbol=row["symbol"],
                company_name=row["company_name"],
                bse_code=row["bse_code"],
                exchange=row["exchange"],
                sector=row["sector"],
                industry=row["industry"],
            )
        )
        added += 1
    if added:
        db.session.commit()
    return added
