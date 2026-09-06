"""
services/stock_universe.py
==========================
A plain Python list of well-known NSE/BSE listed companies.

WHAT IS THIS FOR?
-----------------
Search needs something to search through. This list gives the app an offline
index of company name -> NSE symbol -> BSE code -> sector -> industry, so the
search box works instantly without calling any external API.

IMPORTANT
---------
This is a convenience reference list, not an official exchange file. Ticker
symbols and BSE scrip codes do change (mergers, renames, delistings). Before
relying on it, replace it with the official master lists:

    NSE : https://www.nseindia.com/market-data/securities-available-for-trading
    BSE : https://www.bseindia.com/corporates/List_Scrips.html

Both exchanges publish a downloadable CSV. See the README section
"Replacing the stock universe" for a short loader.

Each entry: (nse_symbol, company_name, bse_code, sector, industry)
"""

# fmt: off
STOCK_UNIVERSE = [
    # ---- Information Technology ----
    ("TCS",         "Tata Consultancy Services Ltd",        "532540", "Information Technology", "IT Services"),
    ("INFY",        "Infosys Ltd",                          "500209", "Information Technology", "IT Services"),
    ("HCLTECH",     "HCL Technologies Ltd",                 "532281", "Information Technology", "IT Services"),
    ("WIPRO",       "Wipro Ltd",                            "507685", "Information Technology", "IT Services"),
    ("TECHM",       "Tech Mahindra Ltd",                    "532755", "Information Technology", "IT Services"),
    ("LTIM",        "LTIMindtree Ltd",                      "540005", "Information Technology", "IT Services"),
    ("PERSISTENT",  "Persistent Systems Ltd",               "533179", "Information Technology", "IT Services"),
    ("COFORGE",     "Coforge Ltd",                          "532541", "Information Technology", "IT Services"),
    ("MPHASIS",     "Mphasis Ltd",                          "526299", "Information Technology", "IT Services"),
    ("TATAELXSI",   "Tata Elxsi Ltd",                       "500408", "Information Technology", "IT Services"),

    # ---- Banking ----
    ("HDFCBANK",    "HDFC Bank Ltd",                        "500180", "Financials", "Private Bank"),
    ("ICICIBANK",   "ICICI Bank Ltd",                       "532174", "Financials", "Private Bank"),
    ("KOTAKBANK",   "Kotak Mahindra Bank Ltd",              "500247", "Financials", "Private Bank"),
    ("AXISBANK",    "Axis Bank Ltd",                        "532215", "Financials", "Private Bank"),
    ("INDUSINDBK",  "IndusInd Bank Ltd",                    "532187", "Financials", "Private Bank"),
    ("FEDERALBNK",  "Federal Bank Ltd",                     "500469", "Financials", "Private Bank"),
    ("IDFCFIRSTB",  "IDFC First Bank Ltd",                  "539437", "Financials", "Private Bank"),
    ("SBIN",        "State Bank of India",                  "500112", "Financials", "Public Sector Bank"),
    ("BANKBARODA",  "Bank of Baroda",                       "532134", "Financials", "Public Sector Bank"),
    ("PNB",         "Punjab National Bank",                 "532461", "Financials", "Public Sector Bank"),
    ("CANBK",       "Canara Bank",                          "532483", "Financials", "Public Sector Bank"),

    # ---- Non-bank finance and insurance ----
    ("BAJFINANCE",  "Bajaj Finance Ltd",                    "500034", "Financials", "NBFC"),
    ("BAJAJFINSV",  "Bajaj Finserv Ltd",                    "532978", "Financials", "NBFC"),
    ("CHOLAFIN",    "Cholamandalam Investment and Finance", "511243", "Financials", "NBFC"),
    ("MUTHOOTFIN",  "Muthoot Finance Ltd",                  "533398", "Financials", "NBFC"),
    ("LICHSGFIN",   "LIC Housing Finance Ltd",              "500253", "Financials", "NBFC"),
    ("HDFCLIFE",    "HDFC Life Insurance Company Ltd",      "540777", "Financials", "Insurance"),
    ("SBILIFE",     "SBI Life Insurance Company Ltd",       "540719", "Financials", "Insurance"),

    # ---- Energy and utilities ----
    ("RELIANCE",    "Reliance Industries Ltd",              "500325", "Energy", "Oil to Chemicals and Telecom"),
    ("ONGC",        "Oil and Natural Gas Corporation Ltd",  "500312", "Energy", "Oil Exploration"),
    ("IOC",         "Indian Oil Corporation Ltd",           "530965", "Energy", "Oil Refining"),
    ("BPCL",        "Bharat Petroleum Corporation Ltd",     "500547", "Energy", "Oil Refining"),
    ("GAIL",        "GAIL (India) Ltd",                     "532155", "Energy", "Gas Distribution"),
    ("COALINDIA",   "Coal India Ltd",                       "533278", "Energy", "Coal Mining"),
    ("NTPC",        "NTPC Ltd",                             "532555", "Utilities", "Power Generation"),
    ("POWERGRID",   "Power Grid Corporation of India Ltd",  "532898", "Utilities", "Power Transmission"),
    ("TATAPOWER",   "Tata Power Company Ltd",               "500400", "Utilities", "Power Generation"),

    # ---- Metals and mining ----
    ("TATASTEEL",   "Tata Steel Ltd",                       "500470", "Materials", "Steel"),
    ("JSWSTEEL",    "JSW Steel Ltd",                        "500228", "Materials", "Steel"),
    ("JINDALSTEL",  "Jindal Steel and Power Ltd",           "532286", "Materials", "Steel"),
    ("SAIL",        "Steel Authority of India Ltd",         "500113", "Materials", "Steel"),
    ("HINDALCO",    "Hindalco Industries Ltd",              "500440", "Materials", "Non-Ferrous Metals"),
    ("VEDL",        "Vedanta Ltd",                          "500295", "Materials", "Non-Ferrous Metals"),
    ("HINDZINC",    "Hindustan Zinc Ltd",                   "500188", "Materials", "Non-Ferrous Metals"),
    ("NMDC",        "NMDC Ltd",                             "526371", "Materials", "Mining"),

    # ---- Cement ----
    ("ULTRACEMCO",  "UltraTech Cement Ltd",                 "532538", "Materials", "Cement"),
    ("GRASIM",      "Grasim Industries Ltd",                "500300", "Materials", "Cement"),
    ("SHREECEM",    "Shree Cement Ltd",                     "500387", "Materials", "Cement"),
    ("AMBUJACEM",   "Ambuja Cements Ltd",                   "500425", "Materials", "Cement"),
    ("ACC",         "ACC Ltd",                              "500410", "Materials", "Cement"),

    # ---- Consumer staples ----
    ("HINDUNILVR",  "Hindustan Unilever Ltd",               "500696", "Consumer Staples", "FMCG"),
    ("ITC",         "ITC Ltd",                              "500875", "Consumer Staples", "FMCG"),
    ("NESTLEIND",   "Nestle India Ltd",                     "500790", "Consumer Staples", "FMCG"),
    ("BRITANNIA",   "Britannia Industries Ltd",             "500825", "Consumer Staples", "FMCG"),
    ("DABUR",       "Dabur India Ltd",                      "500096", "Consumer Staples", "FMCG"),
    ("MARICO",      "Marico Ltd",                           "531642", "Consumer Staples", "FMCG"),
    ("GODREJCP",    "Godrej Consumer Products Ltd",         "532424", "Consumer Staples", "FMCG"),
    ("COLPAL",      "Colgate-Palmolive (India) Ltd",        "500830", "Consumer Staples", "FMCG"),
    ("TATACONSUM",  "Tata Consumer Products Ltd",           "500800", "Consumer Staples", "FMCG"),
    ("VBL",         "Varun Beverages Ltd",                  "540180", "Consumer Staples", "Beverages"),

    # ---- Healthcare ----
    ("SUNPHARMA",   "Sun Pharmaceutical Industries Ltd",    "524715", "Healthcare", "Pharmaceuticals"),
    ("CIPLA",       "Cipla Ltd",                            "500087", "Healthcare", "Pharmaceuticals"),
    ("DRREDDY",     "Dr Reddys Laboratories Ltd",           "500124", "Healthcare", "Pharmaceuticals"),
    ("DIVISLAB",    "Divis Laboratories Ltd",               "532488", "Healthcare", "Pharmaceuticals"),
    ("AUROPHARMA",  "Aurobindo Pharma Ltd",                 "524804", "Healthcare", "Pharmaceuticals"),
    ("LUPIN",       "Lupin Ltd",                            "500257", "Healthcare", "Pharmaceuticals"),
    ("TORNTPHARM",  "Torrent Pharmaceuticals Ltd",          "500420", "Healthcare", "Pharmaceuticals"),
    ("ZYDUSLIFE",   "Zydus Lifesciences Ltd",               "532321", "Healthcare", "Pharmaceuticals"),
    ("BIOCON",      "Biocon Ltd",                           "532523", "Healthcare", "Pharmaceuticals"),
    ("APOLLOHOSP",  "Apollo Hospitals Enterprise Ltd",      "508869", "Healthcare", "Hospitals"),

    # ---- Automobiles ----
    ("MARUTI",      "Maruti Suzuki India Ltd",              "532500", "Consumer Discretionary", "Automobiles"),
    ("TATAMOTORS",  "Tata Motors Ltd",                      "500570", "Consumer Discretionary", "Automobiles"),
    ("M&M",         "Mahindra and Mahindra Ltd",            "500520", "Consumer Discretionary", "Automobiles"),
    ("BAJAJ-AUTO",  "Bajaj Auto Ltd",                       "532977", "Consumer Discretionary", "Automobiles"),
    ("HEROMOTOCO",  "Hero MotoCorp Ltd",                    "500182", "Consumer Discretionary", "Automobiles"),
    ("EICHERMOT",   "Eicher Motors Ltd",                    "505200", "Consumer Discretionary", "Automobiles"),
    ("TVSMOTOR",    "TVS Motor Company Ltd",                "532343", "Consumer Discretionary", "Automobiles"),
    ("ASHOKLEY",    "Ashok Leyland Ltd",                    "500477", "Consumer Discretionary", "Automobiles"),
    ("MOTHERSON",   "Samvardhana Motherson International",  "517334", "Consumer Discretionary", "Auto Components"),
    ("BHARATFORG",  "Bharat Forge Ltd",                     "500493", "Consumer Discretionary", "Auto Components"),
    ("MRF",         "MRF Ltd",                              "500290", "Consumer Discretionary", "Auto Components"),
    ("BALKRISIND",  "Balkrishna Industries Ltd",            "502355", "Consumer Discretionary", "Auto Components"),

    # ---- Consumer discretionary and retail ----
    ("TITAN",       "Titan Company Ltd",                    "500114", "Consumer Discretionary", "Retail"),
    ("DMART",       "Avenue Supermarts Ltd",                "540376", "Consumer Discretionary", "Retail"),
    ("TRENT",       "Trent Ltd",                            "500251", "Consumer Discretionary", "Retail"),
    ("PAGEIND",     "Page Industries Ltd",                  "532827", "Consumer Discretionary", "Apparel"),
    ("JUBLFOOD",    "Jubilant FoodWorks Ltd",               "533155", "Consumer Discretionary", "Restaurants"),

    # ---- Paints and chemicals ----
    ("ASIANPAINT",  "Asian Paints Ltd",                     "500820", "Materials", "Paints"),
    ("BERGEPAINT",  "Berger Paints India Ltd",              "509480", "Materials", "Paints"),
    ("PIDILITIND",  "Pidilite Industries Ltd",              "500331", "Materials", "Specialty Chemicals"),
    ("SRF",         "SRF Ltd",                              "503806", "Materials", "Specialty Chemicals"),
    ("DEEPAKNTR",   "Deepak Nitrite Ltd",                   "542665", "Materials", "Specialty Chemicals"),
    ("PIIND",       "PI Industries Ltd",                    "523642", "Materials", "Agrochemicals"),
    ("UPL",         "UPL Ltd",                              "512070", "Materials", "Agrochemicals"),

    # ---- Industrials and capital goods ----
    ("LT",          "Larsen and Toubro Ltd",                "500510", "Industrials", "Engineering and Construction"),
    ("SIEMENS",     "Siemens Ltd",                          "500550", "Industrials", "Capital Goods"),
    ("ABB",         "ABB India Ltd",                        "500002", "Industrials", "Capital Goods"),
    ("CUMMINSIND",  "Cummins India Ltd",                    "500480", "Industrials", "Capital Goods"),
    ("THERMAX",     "Thermax Ltd",                          "500411", "Industrials", "Capital Goods"),
    ("HAVELLS",     "Havells India Ltd",                    "517354", "Industrials", "Electrical Equipment"),
    ("POLYCAB",     "Polycab India Ltd",                    "542652", "Industrials", "Electrical Equipment"),
    ("BEL",         "Bharat Electronics Ltd",               "500049", "Industrials", "Defence"),
    ("HAL",         "Hindustan Aeronautics Ltd",            "541154", "Industrials", "Defence"),
    ("DIXON",       "Dixon Technologies (India) Ltd",       "540699", "Industrials", "Electronics Manufacturing"),
    ("ADANIPORTS",  "Adani Ports and SEZ Ltd",              "532921", "Industrials", "Ports and Logistics"),
    ("ADANIENT",    "Adani Enterprises Ltd",                "512599", "Industrials", "Diversified"),
    ("INDIGO",      "InterGlobe Aviation Ltd",              "539448", "Industrials", "Airlines"),
    ("IRCTC",       "Indian Railway Catering and Tourism",  "542830", "Industrials", "Travel Services"),

    # ---- Telecom, media and internet ----
    ("BHARTIARTL",  "Bharti Airtel Ltd",                    "532454", "Communication Services", "Telecom"),
    ("NAUKRI",      "Info Edge (India) Ltd",                "532777", "Communication Services", "Internet"),
    ("SUNTV",       "Sun TV Network Ltd",                   "532733", "Communication Services", "Media"),
    ("PVRINOX",     "PVR INOX Ltd",                         "532689", "Communication Services", "Media"),
]
# fmt: on


def build_lookup():
    """Build dictionaries that make searching fast.

    Returns three things:
      by_symbol : {"TCS": {...}}     - exact NSE symbol lookup
      by_bse    : {"532540": {...}}  - exact BSE scrip code lookup
      all_rows  : [{...}, {...}]     - every company, as dictionaries
    """
    by_symbol, by_bse, all_rows = {}, {}, []
    for nse_symbol, name, bse_code, sector, industry in STOCK_UNIVERSE:
        row = {
            "symbol": nse_symbol,
            "company_name": name,
            "nse_symbol": nse_symbol,
            "bse_code": bse_code,
            "sector": sector,
            "industry": industry,
            "exchange": "NSE/BSE",
        }
        by_symbol[nse_symbol] = row
        by_bse[bse_code] = row
        all_rows.append(row)
    return by_symbol, by_bse, all_rows


# Built once when the module is first imported, then reused.
BY_SYMBOL, BY_BSE, ALL_ROWS = build_lookup()


def get_peers(symbol, limit=4):
    """Return companies in the same industry. Used by the Peers tab.

    Peers are derived from the industry label instead of a hard-coded list, so
    adding a company to STOCK_UNIVERSE automatically gives it peers.
    """
    row = BY_SYMBOL.get(str(symbol).upper())
    if not row:
        return []
    peers = [
        other["symbol"]
        for other in ALL_ROWS
        if other["industry"] == row["industry"] and other["symbol"] != row["symbol"]
    ]
    return peers[:limit]
