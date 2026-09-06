"""
tests/test_routes.py
====================
End-to-end tests of the HTTP layer, using Flask's test client (a fake browser).

These cover the happy paths AND the error cases the brief asks for: an invalid
symbol, missing data, a failing provider, and requests without permission.
"""

import pytest

from services.providers import DataProviderError


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", [
    "/", "/markets", "/compare", "/watchlist", "/learn",
    "/login", "/register", "/profile", "/stock/TCS",
])
def test_every_page_loads(client, path):
    assert client.get(path).status_code == 200


def test_unknown_page_returns_404(client):
    assert client.get("/definitely-not-a-page").status_code == 404


def test_stock_page_for_an_unknown_symbol_is_still_friendly(client):
    """We render a helpful message rather than a crash or a blank page."""
    response = client.get("/stock/ZZZZINVALID")
    assert response.status_code == 200
    assert b"could not find" in response.data.lower()


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def test_search_by_symbol(client):
    results = client.get("/api/search?q=TCS").get_json()["results"]
    assert results[0]["symbol"] == "TCS"


def test_search_by_company_name(client):
    results = client.get("/api/search?q=reliance").get_json()["results"]
    assert any(r["symbol"] == "RELIANCE" for r in results)


def test_search_by_bse_code(client):
    results = client.get("/api/search?q=532540").get_json()["results"]
    assert results[0]["symbol"] == "TCS"


def test_search_with_no_match_explains_itself(client):
    data = client.get("/api/search?q=zzzzzzzz").get_json()
    assert data["results"] == []
    assert data["message"]          # a message, not a silent empty list


def test_empty_search_does_not_error(client):
    assert client.get("/api/search?q=").status_code == 200


# ---------------------------------------------------------------------------
# Stock data endpoints
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("endpoint", [
    "", "/price", "/history", "/financials", "/fundamentals", "/earnings",
    "/shareholding", "/technicals", "/valuation", "/news", "/analysis", "/score",
])
def test_stock_endpoints_return_data(client, endpoint):
    response = client.get("/api/stock/TCS" + endpoint)
    assert response.status_code == 200
    assert response.get_json() is not None


def test_symbol_lookup_is_case_insensitive(client):
    assert client.get("/api/stock/tcs/price").status_code == 200


def test_invalid_symbol_returns_404_with_a_message(client):
    response = client.get("/api/stock/ZZZZINVALID/price")
    assert response.status_code == 404
    assert "message" in response.get_json()


def test_invalid_chart_period_is_rejected(client):
    response = client.get("/api/stock/TCS/history?period=100Y")
    assert response.status_code == 400


def test_price_and_chart_agree(client):
    """A regression test for a real bug: the quoted price and the last candle
    on the chart must come from the same series."""
    price = client.get("/api/stock/TCS/price").get_json()["price"]
    candles = client.get("/api/stock/TCS/history?period=1Y").get_json()["candles"]
    assert candles[-1]["close"] == price


def test_analysis_contains_every_section(client):
    data = client.get("/api/stock/TCS/analysis").get_json()
    for section in ("fundamentals", "technicals", "valuation", "risks", "bull_case",
                    "bear_case", "scenarios", "thesis", "catalysts", "entry_scenarios",
                    "governance", "scores"):
        assert section in data, "missing section: " + section
    assert data["disclaimer"]


def test_demo_data_is_always_labelled(client):
    """Requirement 60: sample data must never be presented as real."""
    data = client.get("/api/stock/TCS").get_json()
    assert data["company"]["is_demo"] is True
    assert "DEMO" in data["company"]["source"].upper()


def test_scores_never_claim_to_predict_returns(client):
    scores = client.get("/api/stock/TCS/score").get_json()["scores"]
    assert "not a prediction" in scores["warning"].lower()
    # Industry is deliberately left unscored rather than guessed.
    industry = next(c for c in scores["categories"] if c["category"] == "Industry")
    assert industry["score"] is None


def test_compare_needs_at_least_two_stocks(client):
    assert client.get("/api/compare?stocks=TCS").status_code == 400


def test_compare_returns_a_row_per_stock(client):
    data = client.get("/api/compare?stocks=TCS,INFY,WIPRO").get_json()
    assert len(data["rows"]) == 3


def test_market_overview_has_a_timestamp(client):
    data = client.get("/api/market").get_json()
    assert data["as_of"]            # requirement 38: never invent a timestamp
    assert data["source"]


def test_status_never_leaks_the_api_key(client):
    body = client.get("/api/status").data.decode()
    assert "AI_API_KEY" not in body
    assert "x-api-key" not in body.lower()


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def test_register_login_and_logout(client, csrf):
    response = client.post("/api/auth/register",
                           json={"username": "alice", "email": "alice@example.com",
                                 "password": "goodpass123"},
                           headers={"X-CSRF-Token": csrf})
    assert response.status_code == 201
    token = response.get_json()["csrf_token"]

    assert client.get("/api/auth/me").get_json()["logged_in"] is True

    response = client.post("/api/auth/logout", headers={"X-CSRF-Token": token})
    token = response.get_json()["csrf_token"]
    assert client.get("/api/auth/me").get_json()["logged_in"] is False

    response = client.post("/api/auth/login",
                           json={"username": "alice", "password": "goodpass123"},
                           headers={"X-CSRF-Token": token})
    assert response.status_code == 200


def test_password_is_never_stored_or_returned(app, client, csrf):
    response = client.post("/api/auth/register",
                           json={"username": "bob", "email": "bob@example.com",
                                 "password": "goodpass123"},
                           headers={"X-CSRF-Token": csrf})
    body = response.data.decode()
    assert "goodpass123" not in body
    assert "password_hash" not in body

    # Reading the database directly needs an application context.
    with app.app_context():
        from models.user import User
        user = User.query.filter_by(username="bob").first()
        assert user.password_hash != "goodpass123"       # stored as a hash
        assert user.check_password("goodpass123") is True
        assert user.check_password("wrong") is False


def test_registration_rejects_weak_input(client, csrf):
    response = client.post("/api/auth/register",
                           json={"username": "x", "email": "not-an-email", "password": "123"},
                           headers={"X-CSRF-Token": csrf})
    assert response.status_code == 400
    assert len(response.get_json()["messages"]) == 3


def test_duplicate_username_is_refused(client, logged_in):
    response = client.post("/api/auth/register",
                           json={"username": "tester", "email": "other@example.com",
                                 "password": "goodpass123"},
                           headers=logged_in)
    assert response.status_code == 409


def test_wrong_password_gives_a_vague_message(client, logged_in):
    """The message must not reveal whether the username exists."""
    client.post("/api/auth/logout", headers=logged_in)
    token = client.get("/api/auth/csrf-token").get_json()["csrf_token"]
    response = client.post("/api/auth/login",
                           json={"username": "tester", "password": "wrongpass"},
                           headers={"X-CSRF-Token": token})
    assert response.status_code == 401
    assert "incorrect" in response.get_json()["message"].lower()


def test_state_changing_requests_need_a_csrf_token(client):
    """Without the token the request must be refused - this is the CSRF guard."""
    response = client.post("/api/auth/register",
                           json={"username": "mallory", "email": "m@example.com",
                                 "password": "goodpass123"})
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------

def test_watchlist_requires_login(client):
    assert client.get("/api/watchlist").status_code == 401
    assert client.post("/api/watchlist", json={"symbol": "TCS"}).status_code in (401, 403)


def test_watchlist_add_list_and_remove(client, logged_in):
    assert client.post("/api/watchlist", json={"symbol": "TCS"},
                       headers=logged_in).status_code == 201

    # A BSE code must resolve to the same canonical NSE symbol.
    response = client.post("/api/watchlist", json={"symbol": "500325"}, headers=logged_in)
    assert response.get_json()["item"]["symbol"] == "RELIANCE"

    items = client.get("/api/watchlist").get_json()["items"]
    assert {item["symbol"] for item in items} == {"TCS", "RELIANCE"}
    assert items[0]["price"] is not None      # a live price is attached

    assert client.delete("/api/watchlist/TCS", headers=logged_in).status_code == 200
    assert client.get("/api/watchlist/check/TCS").get_json()["in_watchlist"] is False


def test_watchlist_ignores_a_duplicate(client, logged_in):
    client.post("/api/watchlist", json={"symbol": "TCS"}, headers=logged_in)
    response = client.post("/api/watchlist", json={"symbol": "TCS"}, headers=logged_in)
    assert response.get_json()["already_present"] is True


def test_watchlist_rejects_an_unknown_symbol(client, logged_in):
    assert client.post("/api/watchlist", json={"symbol": "ZZZZINVALID"},
                       headers=logged_in).status_code == 404


def test_removing_something_not_saved_returns_404(client, logged_in):
    assert client.delete("/api/watchlist/INFY", headers=logged_in).status_code == 404


# ---------------------------------------------------------------------------
# AI endpoints
# ---------------------------------------------------------------------------

def test_ai_chat_answers_without_an_api_key(client, csrf):
    """With no AI key the rule-based writer must still produce a real answer."""
    response = client.post("/api/ai/chat",
                           json={"symbol": "TCS", "question": "What are the biggest risks?"},
                           headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    data = response.get_json()
    assert data["generated_by"] == "rule-based"
    assert len(data["answer"]) > 50
    assert data["disclaimer"]


def test_ai_chat_needs_a_question(client, csrf):
    response = client.post("/api/ai/chat", json={"symbol": "TCS", "question": "  "},
                           headers={"X-CSRF-Token": csrf})
    assert response.status_code == 400


def test_ai_chat_rejects_an_unknown_symbol(client, csrf):
    response = client.post("/api/ai/chat",
                           json={"symbol": "ZZZZINVALID", "question": "Tell me about it"},
                           headers={"X-CSRF-Token": csrf})
    assert response.status_code == 404


@pytest.mark.parametrize("section", [
    "fundamental", "technical", "valuation", "bull", "bear",
    "quarterly", "beginner", "summary",
])
def test_every_ai_section_produces_text(client, section):
    response = client.get("/api/stock/TCS/ai/" + section)
    assert response.status_code == 200
    assert len(response.get_json()["text"]) > 50


def test_unknown_ai_section_is_rejected(client):
    assert client.get("/api/stock/TCS/ai/nonsense").status_code == 400


# ---------------------------------------------------------------------------
# Provider failure
# ---------------------------------------------------------------------------

def test_a_failing_provider_produces_a_friendly_error(client, monkeypatch):
    """When the data source dies we must return a clear message and a 503 -
    never a stack trace, and never made-up numbers."""
    from routes import stocks

    def explode(symbol):
        raise DataProviderError("The upstream API is unavailable.")

    monkeypatch.setattr(stocks.stock_service, "get_current_price", explode)

    response = client.get("/api/stock/TCS/price")
    assert response.status_code == 503
    message = response.get_json()["message"]
    assert "could not retrieve" in message.lower()
    assert "Traceback" not in message
