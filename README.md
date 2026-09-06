# StockIQ India

### Your AI Research Analyst for Indian Stocks

A full-stack web application for researching companies listed on the **NSE**
(National Stock Exchange) and **BSE** (Bombay Stock Exchange).

Type `TCS` and you get a complete research report: what the company does, whether
it is growing, whether it is profitable, how healthy its balance sheet is, how
expensive the stock is, what the charts show, what the risks are, and what would
have to change for the story to break.

**It never tells you to buy or sell.** It shows you the evidence and the
reasoning so you can decide for yourself.

---

## Table of contents

1. [What this project does](#1-what-this-project-does)
2. [Technologies used](#2-technologies-used)
3. [Folder structure](#3-folder-structure)
4. [How Flask works](#4-how-flask-works)
5. [How the frontend and backend talk](#5-how-the-frontend-and-backend-talk)
6. [How the AI pipeline works](#6-how-the-ai-pipeline-works)
7. [Setup, step by step](#7-setup-step-by-step)
8. [Running the application](#8-running-the-application)
9. [Running the tests](#9-running-the-tests)
10. [Switching to real data](#10-switching-to-real-data)
11. [Adding another data provider](#11-adding-another-data-provider)
12. [Modifying the UI](#12-modifying-the-ui)
13. [The API reference](#13-the-api-reference)
14. [Deploying it](#14-deploying-it)
15. [Data quality rules](#15-data-quality-rules)
16. [Legal and disclaimer](#16-legal-and-disclaimer)

---

## 1. What this project does

Search any of about 112 well-known Indian listed companies and get:

| Section | What you see |
|---|---|
| **Overview** | Price, chart with moving averages, StockIQ score, profile, shareholding |
| **Fundamentals** | Revenue growth, CAGR, margins, ROE, ROCE, debt, cash flow, earnings quality |
| **Financials** | Income statement, balance sheet and cash flow for up to five years |
| **Technicals** | 20/50/100/200 DMA, RSI, MACD, ADX, stochastic, support and resistance |
| **Valuation** | P/E, P/B, EV/EBITDA, PEG, versus its own history and versus peers |
| **Earnings** | Quarterly results with YoY and QoQ growth, plus what changed |
| **News** | Headlines with source, sentiment and why each one matters |
| **Bull / Bear** | Both cases with evidence, ranked risks, catalysts, governance, thesis |
| **Peers** | Side by side with companies in the same industry |
| **AI Analyst** | A chatbot that answers using only this app's computed numbers |

Plus user accounts, a watchlist, dark mode, a beginner mode that explains every
term inline, and a Learn page that defines all of it.

### Three things this app deliberately will not do

1. **It never prints BUY, SELL or HOLD.** It shows the conditions under which a
   stock could become attractive, when to wait, and when to be cautious.
2. **It never invents a number.** If a figure is unavailable it says
   "Data unavailable". No placeholder zeros, no plausible-looking estimates.
3. **It never predicts a price.** Scenario analysis shows the arithmetic that
   follows from stated assumptions, clearly labelled as assumptions.

---

## 2. Technologies used

**Backend**

| Tool | Why it is here |
|---|---|
| Python 3.10+ | The language |
| Flask | The web framework: turns a URL into a Python function |
| Flask-SQLAlchemy | Talks to the database using Python classes instead of SQL |
| SQLite | The database. One file, no server to install |
| python-dotenv | Reads secrets from `.env` so they stay out of the code |
| requests | Makes HTTP calls to external APIs |
| Werkzeug | Secure password hashing (ships with Flask) |

**Frontend**

Plain HTML, CSS and JavaScript. No React, no build step, no `npm install`.
Open any `.js` file and it runs exactly as written. Chart.js is loaded from a
CDN for the charts.

**Everything is pure Python** - no numpy, no pandas, no C compiler needed. Every
moving average, RSI and MACD is written out longhand in `utils/calculations.py`
so you can read the formula and check it by hand.

---

## 3. Folder structure

```
stockiq-india/
|
|-- app.py                  START HERE. Builds the Flask app and runs the server.
|-- config.py               Every setting, read once from .env
|-- requirements.txt        The Python packages to install
|-- .env                    YOUR SECRETS (never committed to Git)
|-- .env.example            A template to copy into .env
|-- .gitignore              Tells Git to ignore .env, the database and venv/
|-- README.md               This file
|
|-- routes/                 URL -> Python function. Thin: they validate and delegate.
|   |-- pages.py            The HTML pages (/, /stock/TCS, /compare, ...)
|   |-- stocks.py           Stock data API (/api/search, /api/stock/TCS/price, ...)
|   |-- analysis.py         Analysis and AI API (/api/stock/TCS/analysis, /api/ai/chat)
|   |-- news.py             News API
|   |-- auth.py             Register, login, logout, profile
|   |-- watchlist.py        The saved-stocks API
|
|-- services/               The middle layer: caching, provider calls, orchestration
|   |-- providers/          ONE FILE PER DATA SOURCE
|   |   |-- base.py             The contract every provider must implement
|   |   |-- demo_provider.py    Offline sample data (the default)
|   |   |-- yfinance_provider.py Real data via yfinance
|   |   |-- __init__.py         Picks the provider based on .env
|   |-- stock_universe.py   The searchable list of NSE/BSE companies
|   |-- stock_service.py    Search, company info, prices
|   |-- financial_service.py Statements plus every analysis module
|   |-- news_service.py     News fetching and sentiment labelling
|   |-- ai_service.py       Prompts, the AI call, and the rule-based fallback
|
|-- analysis/               PURE MATHS. No Flask, no database, no internet.
|   |-- fundamentals.py     Growth, margins, returns, financial health
|   |-- technicals.py       Trend, indicators, support/resistance, the verdict
|   |-- valuation.py        Multiples, historical band, the classification
|   |-- risk.py             Ranked risks, catalysts, governance, entry scenarios
|   |-- bull_bear.py        Bull case, bear case, scenarios, investment thesis
|   |-- scoring.py          The overall StockIQ score
|
|-- models/                 Database tables as Python classes
|   |-- user.py             users
|   |-- stock.py            stocks + cached_data
|   |-- watchlist.py        watchlist
|
|-- database/db.py          Creates the shared SQLAlchemy object
|
|-- utils/
|   |-- calculations.py     Every formula: SMA, EMA, RSI, MACD, ADX, ratios, CAGR
|   |-- validators.py       Input checking and data-quality checking
|   |-- cache.py            Two-layer cache (memory + database)
|   |-- security.py         CSRF, rate limiting, @login_required
|
|-- templates/              HTML pages (Jinja2)
|-- static/css/             Stylesheets
|-- static/js/              Frontend JavaScript
|-- tests/                  pytest suite (92 tests)
```

### The one rule that keeps this readable

Data flows in **one direction**:

```
routes  ->  services  ->  providers  ->  external API
   |            |
   |            +-->  analysis/   (pure maths)
   |
   +-->  templates/  (HTML)
```

A route never calls a provider directly. The analysis modules never touch Flask
or the database. That is exactly why every formula can be tested with plain
numbers and no web server.

---

## 4. How Flask works

Flask is small. Here is the whole idea:

```python
@app.route("/hello")        # when a browser asks for /hello ...
def hello():                # ... run this function ...
    return "Hi there"       # ... and send back whatever it returns.
```

That is it. Everything else is detail.

**Three things Flask adds that this project uses:**

**1. Blueprints** group related routes. `routes/stocks.py` builds one:

```python
stocks_bp = Blueprint("stocks", __name__)

@stocks_bp.route("/stock/<symbol>/price")
def stock_price(symbol):
    return jsonify(stock_service.get_current_price(symbol))
```

Then `app.py` attaches it with a prefix:

```python
app.register_blueprint(stocks_bp, url_prefix="/api")
```

so the real URL becomes `/api/stock/TCS/price`. The `<symbol>` part of the URL
arrives as the `symbol` argument.

**2. Templates.** `render_template("stock.html", symbol="TCS")` loads
`templates/stock.html`, replaces every `{{ symbol }}` with `TCS`, and returns
the finished HTML.

**3. Sessions.** `session["user_id"] = 5` stores a value in a cookie that Flask
**cryptographically signs** with your `SECRET_KEY`. A user cannot edit the
cookie to become someone else, because they cannot forge the signature. This is
how login works, and it is why `SECRET_KEY` must be secret and random.

---

## 5. How the frontend and backend talk

The browser never contacts a stock API or the AI directly. It only ever talks to
your Flask server:

```
Browser  --fetch('/api/stock/TCS/price')-->  Flask  --HTTPS-->  Data provider
Browser  <---------- JSON ----------------  Flask  <---------  Data provider
```

**In the browser** (`static/js/main.js`):

```javascript
async function api(path, options = {}) {
  const response = await fetch(path, config);   // ask our own server
  const data = await response.json();           // read the JSON back
  if (!response.ok) throw new ApiError(data.message, response.status);
  return data;
}
```

**In Flask** (`routes/stocks.py`):

```python
@stocks_bp.route("/stock/<symbol>/price")
def stock_price(symbol):
    return jsonify(stock_service.get_current_price(symbol))
```

Every single network call in the frontend goes through that one `api()` helper,
so error handling and the CSRF header are written once rather than twenty times.

**Why route everything through Flask?** Because the API keys live on the server.
If the browser called the AI provider directly, anyone could open DevTools and
steal your key. This way the key never leaves the Python process.

---

## 6. How the AI pipeline works

This is the most important design decision in the project.

The AI is **never** asked "analyse TCS". It would happily make up numbers if it
were. Instead:

```
User asks a question
        |
        v
Flask route
        |
        v
Data providers          raw statements, prices, filings
        |
        v
Python calculations     analysis/*.py - every ratio computed in code
        |
        v
STRUCTURED ANALYSIS     { "roe_pct": 24.03, "debt_to_equity": 0.06,
        |                 "pe_ratio": 11.06, "rsi_14": 47.2, ... }
        v
AI model                explains those numbers, calculates nothing
        |
        v
Answer back to the browser
```

The system prompt in `services/ai_service.py` states the rules explicitly:

> 1. You may ONLY use numbers that appear in the STRUCTURED DATA given to you.
>    Never estimate, never round to a "nicer" number, never recall a figure from
>    memory. If a number is missing, say "that figure is not available".
> 2. Never predict a share price, and never give a price target.
> 3. Never say buy, sell or hold.

**No API key? The app still works.** With `AI_API_KEY` blank, every section falls
back to `_rule_based_*` functions that write the same analysis from the same
numbers in plain Python. Less fluent, equally factual, and the UI labels which
one you are reading. You can run and learn from this entire project without
paying for anything.

---

## 7. Setup, step by step

### 7.1 Install Python

Download Python 3.10 or newer from [python.org/downloads](https://www.python.org/downloads/).

**On Windows, tick "Add Python to PATH" on the first screen of the installer.**
If you miss it, the `python` command will not be found later.

Check it worked:

```bash
python --version
```

You should see something like `Python 3.12.4`. (On some Macs and Linux systems
the command is `python3`.)

### 7.2 Create a virtual environment

A virtual environment is a private folder of packages just for this project.
Without one, installing Flask here could break a different project on your
machine that needs a different version.

```bash
cd stockiq-india
python -m venv venv
```

That creates a `venv/` folder. Now **activate** it:

**Windows (PowerShell):**
```bash
venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```bash
venv\Scripts\activate.bat
```

**macOS / Linux:**
```bash
source venv/bin/activate
```

Your prompt now starts with `(venv)`. That is how you know it worked. You need
to activate it again every time you open a new terminal.

> **PowerShell blocks the script?** Run this once, then try again:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### 7.3 Install the requirements

```bash
pip install -r requirements.txt
```

This reads `requirements.txt` and downloads Flask, SQLAlchemy and the rest into
`venv/`. It takes about 30 seconds. Everything listed is pure Python, so there
is nothing to compile.

### 7.4 Create your .env file

`.env` holds your secrets. It is listed in `.gitignore`, so it never reaches
GitHub.

**Windows:**
```bash
copy .env.example .env
```

**macOS / Linux:**
```bash
cp .env.example .env
```

Then open `.env` and set a real `SECRET_KEY`. Generate one with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Paste the output after `SECRET_KEY=`. **You can leave every other value as it
is** - the app runs perfectly with demo data and no API keys at all.

### 7.5 Where the API keys go

| Key | What it unlocks | Needed? |
|---|---|---|
| `SECRET_KEY` | Signs login cookies | **Yes** - generate one |
| `AI_API_KEY` | Real AI-written analysis | No - falls back to the rule-based writer |
| `NEWS_API_KEY` | Real headlines from NewsAPI.org | No - falls back to the demo feed |
| `DATA_PROVIDER` | `demo` or `yfinance` | No - defaults to `demo` |

**Security rules this project follows, and you should too:**

- Keys live **only** in `.env`, which is in `.gitignore`.
- Keys are read **only** by `config.py`, inside the Python process.
- No key is ever sent to the browser. `/api/status` reports *whether* a key is
  set, never the key itself - and there is a test that checks this.
- Never paste a key into a `.js` file. Anyone can read those.

### 7.6 Initialise the database

**There is nothing to do.** `app.py` calls `init_db()` at start-up, which
creates the SQLite file, builds all four tables and fills the stock list on the
first run. Starting the app is enough.

The file appears at `instance/stockiq.db`. Flask puts a relative SQLite path in
its `instance/` folder, which `.gitignore` already excludes.

To wipe everything and start fresh, just delete that folder:

```bash
rm -rf instance
```

---

## 8. Running the application

```bash
python app.py
```

You will see:

```
  StockIQ India
  -------------
  Data provider : demo   *** DEMO DATA - not real market data ***
  AI            : no key set - using the built-in rule-based writer
  Database      : sqlite:///stockiq.db

  Open http://127.0.0.1:5000 in your browser. Press CTRL+C to stop.
```

Open **http://127.0.0.1:5000** and search for `TCS`.

Because `FLASK_ENV=development`, the server restarts automatically whenever you
save a Python file. Press `CTRL+C` to stop it.

### Try this first

1. Search `TCS` on the homepage
2. Click through the ten tabs on the stock page
3. Press **"Explain Like I Am a Beginner"** and watch explanations appear
4. Toggle **Dark** in the header
5. Open the **AI Analyst** tab and ask "What are the biggest risks?"
6. Register an account and star a few stocks

---

## 9. Running the tests

```bash
python -m pip install pytest
python -m pytest
```

Expected output:

```
92 passed in 20.19s
```

The suite covers:

| File | What it checks |
|---|---|
| `tests/test_fundamentals.py` | Every ratio and growth formula against hand calculations |
| `tests/test_technicals.py` | SMA, EMA, RSI, MACD, ADX, stochastic, support/resistance, valuation |
| `tests/test_routes.py` | Every page and endpoint, auth, watchlist, AI, and the error cases |

Error cases specifically tested: an invalid symbol, a bad chart period, a
comparison with too few stocks, a request without a CSRF token, a watchlist
request without a login, a wrong password, and a **completely failed data
provider** (which must return a friendly 503, not a stack trace).

Useful flags:

```bash
python -m pytest -v                          # show each test name
python -m pytest tests/test_technicals.py    # one file
python -m pytest -k rsi                      # only tests matching "rsi"
```

---

## 10. Switching to real data

**By default this app shows DEMO DATA.** Every price, statement and headline is
generated by `services/providers/demo_provider.py` from a random-number
generator seeded by the ticker symbol. It is reproducible, internally consistent
and completely made up. An orange **DEMO DATA** badge appears on every screen
that shows it, and the AI is told the data is sample data.

It exists so you can build and test every screen without a market-data licence.

### To use real data

```bash
pip install yfinance
```

Then in `.env`:

```
DATA_PROVIDER=yfinance
```

Restart the app. You now get real prices, real historical candles and real
annual financials.

### What you get, and what you do not

| Method | yfinance |
|---|---|
| `get_company_info` | Yes |
| `get_current_price` | Yes |
| `get_historical_prices` | Yes |
| `get_financials` | Yes |
| `get_quarterly_results` | Yes |
| `get_shareholding` | **No** - see below |
| `get_news` | Yes |
| `get_market_overview` | Indices only - no gainers/losers |

Promoter, FII and DII holdings come from the quarterly shareholding pattern that
companies file with NSE and BSE. Yahoo does not carry it. Rather than guess, the
provider returns `available: False` with an explanation, and the UI says so.
`get_shareholding` in `yfinance_provider.py` has a comment marking exactly where
a real source should be plugged in.

> **Read this before using yfinance for anything serious.** yfinance is a
> community library that reads Yahoo Finance's public endpoints. It is **not**
> an official NSE or BSE feed, it is not licensed for redistribution, and it can
> break without warning. For anything beyond personal research, use a licensed
> data vendor or an official exchange feed, and respect their rate limits and
> terms of service.

### Replacing the stock universe

`services/stock_universe.py` is a convenience list of about 112 companies. Ticker
symbols and BSE scrip codes change (mergers, renames, delistings). For real use,
download the official master lists:

- NSE: <https://www.nseindia.com/market-data/securities-available-for-trading>
- BSE: <https://www.bseindia.com/corporates/List_Scrips.html>

Both publish a CSV. Load it like this:

```python
import csv

def load_universe(csv_path):
    """Replace STOCK_UNIVERSE with rows from an official exchange CSV."""
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append((
                row["SYMBOL"].strip(),
                row["NAME OF COMPANY"].strip(),
                row.get("BSE_CODE", "").strip(),
                row.get("SECTOR", "Unknown").strip(),
                row.get("INDUSTRY", "Unknown").strip(),
            ))
    return rows
```

Adjust the column names to match the file you downloaded, then call
`build_lookup()` again.

---

## 11. Adding another data provider

This is the part the architecture is built around. Adding a broker API, a paid
vendor or your own scraper takes three steps.

### Step 1: copy the demo provider

```bash
cp services/providers/demo_provider.py services/providers/my_provider.py
```

### Step 2: implement the eight methods

Keep the **method names and the returned dictionary keys identical**. That is
the entire contract - it is documented in `services/providers/base.py`.

```python
from services.providers.base import BaseProvider, DataProviderError

class MyProvider(BaseProvider):
    name = "myprovider"

    def get_current_price(self, symbol):
        response = requests.get("https://api.example.com/quote/" + symbol,
                                headers={"Authorization": Config.STOCK_API_KEY},
                                timeout=10)
        if response.status_code != 200:
            # Raise, do not return fake data. The route turns this into a
            # friendly message and an HTTP 503.
            raise DataProviderError("Quote lookup failed for " + symbol)

        payload = response.json()
        return {
            "symbol": symbol.upper(),
            "price": payload["last_price"],
            "change": payload["net_change"],
            "change_pct": payload["percent_change"],
            "previous_close": payload["prev_close"],
            "open": payload["open"],
            "day_high": payload["high"],
            "day_low": payload["low"],
            "volume": payload["volume"],
            "week_52_high": payload.get("year_high"),    # None if absent
            "week_52_low": payload.get("year_low"),
            "currency": "INR",
            "source": "My Data Vendor",
            "as_of": payload["timestamp"],   # THEIR timestamp, never datetime.now()
            "is_demo": False,
        }
```

**Three rules every provider must follow:**

1. **`as_of` must come from the source.** Never invent a timestamp. If the
   source does not give one, set it to `None`.
2. **Missing values are `None`.** Never substitute 0 or a plausible estimate.
3. **`is_demo` is `True` only for made-up data**, so the UI can badge it.

### Step 3: register it

In `services/providers/__init__.py`:

```python
    if choice == "myprovider":
        from services.providers.my_provider import MyProvider
        _provider_instance = MyProvider()
```

Then set `DATA_PROVIDER=myprovider` in `.env`. Nothing else in the codebase
changes - not one route, not one template.

---

## 12. Modifying the UI

### Colours and theming

Every colour is a CSS variable declared once at the top of
`static/css/style.css`:

```css
:root {
  --brand:   #0f5c8c;    /* change this and the whole site rebrands */
  --up:      #14804a;    /* green for gains */
  --down:    #c62828;    /* red for falls */
  --surface: #ffffff;    /* card background */
}

[data-theme="dark"] {
  --brand:   #4da3d9;    /* dark mode redefines the same names */
  --surface: #151d2b;
}
```

Dark mode is about twenty lines because of this. Nothing else in the stylesheet
mentions a colour directly.

### Which file does what

| File | Covers |
|---|---|
| `static/css/style.css` | Header, footer, buttons, cards, tables, forms, dark mode, responsive |
| `static/css/dashboard.css` | Homepage hero, market panels, compare, watchlist |
| `static/css/stock.css` | The stock page: tabs, charts, chat, scenario cards |

### Adding a tab to the stock page

1. Add a button in `templates/stock.html`:
   `<button class="tab" data-tab="mytab">My Tab</button>`
2. Add the panel: `<section class="tab-panel" id="panel-mytab">...</section>`
3. Write a `renderMyTab()` function in `static/js/stock.js`
4. Register it in `TAB_RENDERERS`: `mytab: renderMyTab`

It renders lazily, only when someone clicks it.

### Adding a term to beginner mode

Add one line to the `GLOSSARY` object in `static/js/stock.js`, then call
`explain('your_key')` wherever you want the box to appear. It shows only when
beginner mode is on - the CSS handles that.

---

## 13. The API reference

Everything returns JSON. Try any of these in a browser while the app is running.

### Public

| Method | Endpoint | What it returns |
|---|---|---|
| GET | `/api/status` | Which provider and AI are configured (no secrets) |
| GET | `/api/search?q=TCS` | Search by name, NSE symbol or BSE code |
| GET | `/api/market` | NIFTY 50, SENSEX, gainers, losers, most active |
| GET | `/api/stock/TCS` | Company profile plus the latest price |
| GET | `/api/stock/TCS/price` | The quote |
| GET | `/api/stock/TCS/history?period=1Y` | Candles. Periods: 1D 1W 1M 3M 6M 1Y 3Y 5Y |
| GET | `/api/stock/TCS/financials` | Income statement, balance sheet, cash flow |
| GET | `/api/stock/TCS/fundamentals` | Computed ratios |
| GET | `/api/stock/TCS/earnings` | Quarterly results with YoY and QoQ growth |
| GET | `/api/stock/TCS/shareholding` | Promoter / FII / DII / public by quarter |
| GET | `/api/stock/TCS/technicals` | Indicators, levels and the technical verdict |
| GET | `/api/stock/TCS/valuation` | Multiples, historical band, classification |
| GET | `/api/stock/TCS/news?page=1` | Paginated news with sentiment |
| GET | `/api/stock/TCS/analysis` | **Everything.** All modules in one response |
| GET | `/api/stock/TCS/score` | The scorecard and its methodology |
| GET | `/api/stock/TCS/ai/<section>` | AI text. Sections: fundamental, technical, valuation, bull, bear, quarterly, beginner, summary |
| GET | `/api/compare?stocks=TCS,INFY` | 2 to 5 stocks side by side |
| POST | `/api/ai/chat` | Ask a question. Body: symbol, question, history |

### Requires a login

| Method | Endpoint | What it does |
|---|---|---|
| GET | `/api/watchlist` | Your saved stocks (add `?full=1` for scores) |
| POST | `/api/watchlist` | Add one. Body: symbol |
| DELETE | `/api/watchlist/TCS` | Remove one |
| GET | `/api/watchlist/check/TCS` | Is it saved? |

### Authentication

| Method | Endpoint |
|---|---|
| GET | `/api/auth/csrf-token` |
| POST | `/api/auth/register` |
| POST | `/api/auth/login` |
| POST | `/api/auth/logout` |
| GET | `/api/auth/me` |
| GET | `/api/auth/profile` |
| POST | `/api/auth/change-password` |

### CSRF

Every POST, PUT, PATCH and DELETE needs an `X-CSRF-Token` header. Get one from
`/api/auth/csrf-token`.

Logging in and out clears the session (which prevents session fixation) and
therefore **rotates the token**. Those endpoints return the new `csrf_token` in
their response body, and the `api()` helper in `main.js` stores it
automatically. If you call the API from a script, use the token that came back.

---

## 14. Deploying it

### Before you go anywhere near a public server

1. Set `FLASK_ENV=production` in `.env`. This turns off the debug console -
   leaving it on lets anyone run Python on your server.
2. Generate a **fresh** `SECRET_KEY`. Never reuse the development one.
3. Confirm `.env` is not in your Git history: `git log --all -- .env`
4. Use HTTPS. `SESSION_COOKIE_SECURE` switches on automatically in production,
   and login will stop working over plain HTTP once it does.

### Run it with a real server

Flask's built-in server is for development only. Use Gunicorn (Linux/macOS) or
Waitress (Windows):

```bash
pip install gunicorn
gunicorn --workers 4 --bind 0.0.0.0:8000 app:app
```

```bash
pip install waitress
waitress-serve --port=8000 app:app
```

`app:app` means "the object called `app` inside `app.py`".

### Moving to PostgreSQL

Change one line in `.env`:

```
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/stockiq
```

Then `pip install psycopg[binary]` and restart. **No application code changes**,
because everything goes through SQLAlchemy. The tables are created on start-up
exactly as they are with SQLite.

### Worth adding for a real deployment

- Nginx or Caddy in front, for TLS and static files
- Redis for the cache and the rate limiter (the current ones live in each
  process, so with several workers each gets its own copy)
- Log rotation and an error tracker
- Database backups

---

## 15. Data quality rules

These are enforced in code, not just documented.

**Never fabricated:** prices, financial statements, earnings, ratios, news,
analyst estimates, technical indicators, announcements, price targets.

**When data cannot be verified,** the app shows "Data unavailable" or explains
why the figure is missing. `utils/validators.py` checks values, timestamps and
plausible ranges before anything is displayed, and the frontend prints
"Data unavailable" for any `null` rather than a zero.

**Four kinds of information are kept visibly separate:**

| Kind | How it appears |
|---|---|
| **Historical** | Actual reported figures, with the period labelled (FY2026) |
| **Current** | Latest available, with a timestamp from the source |
| **Forecast** | Not provided. Forward P/E is left blank, with a note saying why |
| **Assumption** | Scenario analysis, with every input printed beside the output |

**Source transparency.** Every card carries a footer naming its source and the
timestamp the provider supplied. Timestamps are never invented - if a source
gives none, the UI says "timestamp not provided by the data source".

**Cache durations** (configurable in `.env`):

| Data | Default | Why |
|---|---|---|
| Price | 60 seconds | Prices move constantly |
| History | 15 minutes | Candles barely change intraday |
| Financials | 24 hours | Annual reports change a few times a year |
| News | 15 minutes | |
| Company profile | 7 days | Sector and industry almost never change |
| AI narratives | 1 hour | They cost money, so reuse them |

---

## 16. Legal and disclaimer

> **This platform is for educational and research purposes only.** AI-generated
> analysis may contain errors and should not be considered personalised
> investment advice. Verify information independently and consider your own
> financial situation, investment horizon and risk tolerance before making
> investment decisions.

**StockIQ India is not a SEBI-registered investment adviser** and does not
provide personalised investment advice.

### On data sources

This project ships with **no scrapers** and violates no site's terms of service.
The default provider is offline sample data. The optional yfinance provider is a
community library reading Yahoo's public endpoints - it is not an official
exchange feed and is not licensed for redistribution.

If you extend this app, prefer:

- Official exchange APIs and licensed market data
- Public company filings, annual reports and investor presentations
- NSE and BSE disclosures, and SEBI publications

and respect API terms, rate limits, data licensing, copyright and terms of
service. Do not redistribute proprietary market data unless you are permitted to.

### On the analysis itself

Scores, verdicts and classifications come from the transparent rules in
`analysis/`. Every one ships with its own methodology text, visible in the UI. A
high score means more of this app's checks were met using the data it could
obtain. **It is not a prediction of future returns.**

---

## Quick reference

```bash
python -m venv venv                  # create the virtual environment
venv\Scripts\activate                # activate it (Windows)
source venv/bin/activate             # activate it (macOS / Linux)
pip install -r requirements.txt      # install the packages
copy .env.example .env               # create your settings file
python app.py                        # run it -> http://127.0.0.1:5000
python -m pytest                     # run the 92 tests
```

To wipe the database and start fresh, delete the `instance/` folder.
