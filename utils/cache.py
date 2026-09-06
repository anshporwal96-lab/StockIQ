"""
utils/cache.py
==============
A very small two-layer cache.

WHY CACHE AT ALL?
-----------------
External data APIs are slow and usually rate-limited. If ten people open the
TCS page in the same minute we should fetch the price once, not ten times.

TWO LAYERS
----------
  1. In-memory dictionary  - fastest, but lost when the server restarts.
  2. `cached_data` table   - slower, but survives a restart.

Lookup order is memory -> database -> (miss, so fetch fresh).

CACHE LIFETIMES (set in .env, documented in the README)
-------------------------------------------------------
  price        60 s        prices move constantly
  history      15 min      historical candles barely change intraday
  financials   24 h        annual reports change a few times a year
  news         15 min
  company      7 days      sector / industry almost never change
  ai           1 h         AI narratives cost money, so reuse them
"""

import json
import time

from config import Config

# The in-memory layer: {"TCS:price": (expires_at_epoch, payload)}
_memory_cache = {}


def _key(symbol, data_type):
    return f"{str(symbol).upper()}:{data_type}"


def ttl_for(data_type):
    """How long this kind of data stays fresh, in seconds."""
    return Config.CACHE_TTL.get(data_type, 300)


def get(symbol, data_type):
    """Return cached data, or None if there is nothing fresh."""
    key = _key(symbol, data_type)

    # --- Layer 1: memory ---------------------------------------------------
    entry = _memory_cache.get(key)
    if entry:
        expires_at, payload = entry
        if time.time() < expires_at:
            return payload
        del _memory_cache[key]  # expired

    # --- Layer 2: database -------------------------------------------------
    # Imported here (not at the top of the file) so this module can also be
    # used in plain unit tests that never start Flask.
    try:
        from models.stock import CachedData

        row = (
            CachedData.query.filter_by(
                stock_symbol=str(symbol).upper(), data_type=data_type
            ).first()
        )
        if row and row.age_seconds() < ttl_for(data_type):
            payload = row.payload()
            if payload is not None:
                # Promote it back into memory so the next hit is instant.
                _memory_cache[key] = (
                    time.time() + ttl_for(data_type) - row.age_seconds(),
                    payload,
                )
                return payload
    except Exception:
        # A cache miss must never break the page. If the database is not
        # available we simply behave as if nothing was cached.
        pass

    return None


def set(symbol, data_type, payload):
    """Store data in both cache layers. Returns the payload unchanged so you
    can write:  return cache.set(symbol, "price", fetch_price(symbol))"""
    key = _key(symbol, data_type)
    _memory_cache[key] = (time.time() + ttl_for(data_type), payload)

    try:
        from database.db import db
        from models.stock import CachedData

        row = CachedData.query.filter_by(
            stock_symbol=str(symbol).upper(), data_type=data_type
        ).first()
        text = json.dumps(payload, default=str)
        if row:
            row.data = text
            from datetime import datetime, timezone

            row.timestamp = datetime.now(timezone.utc)
        else:
            db.session.add(
                CachedData(
                    stock_symbol=str(symbol).upper(),
                    data_type=data_type,
                    data=text,
                )
            )
        db.session.commit()
    except Exception:
        try:
            from database.db import db

            db.session.rollback()
        except Exception:
            pass

    return payload


def clear(symbol=None):
    """Empty the cache. With no argument it clears everything."""
    global _memory_cache
    if symbol is None:
        _memory_cache = {}
    else:
        prefix = f"{str(symbol).upper()}:"
        for key in [k for k in _memory_cache if k.startswith(prefix)]:
            del _memory_cache[key]
