"""
database/db.py
==============
Creates the single SQLAlchemy object that the whole application shares.

WHAT IS SQLAlchemy?
-------------------
It is an ORM ("Object Relational Mapper"). Instead of writing SQL strings like

    INSERT INTO users (username) VALUES ('ansh')

you write Python:

    db.session.add(User(username="ansh"))
    db.session.commit()

Two big wins:
  1. It is much harder to write an SQL-injection bug, because values are always
     sent as parameters and never glued into the query text.
  2. Swapping SQLite for PostgreSQL later is a one-line change in .env.
"""

from flask_sqlalchemy import SQLAlchemy

# One shared database object. Models import this and Flask "binds" it to the
# app inside init_db() below. Creating it here (instead of inside app.py)
# avoids circular imports between app.py and the model files.
db = SQLAlchemy()


def init_db(app):
    """Attach the database to a Flask app and make sure all tables exist.

    Called once from app.py during start-up.
    """
    db.init_app(app)

    # Importing the model modules registers the table classes with SQLAlchemy.
    # Without these imports, create_all() would not know the tables exist.
    from models import stock, user, watchlist  # noqa: F401  (imported for side effect)

    # app_context() gives the database access to the app's configuration
    # (specifically SQLALCHEMY_DATABASE_URI).
    with app.app_context():
        db.create_all()          # Creates any missing tables. Safe to re-run.
        stock.seed_stock_universe()  # Fills the `stocks` table on first run.
