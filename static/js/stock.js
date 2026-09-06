/* ==========================================================================
   static/js/stock.js
   ==========================================================================
   Everything on the individual stock page.

   HOW THE PAGE LOADS
   ------------------
   1. On page load we fetch the header data (company + price) so the top of the
      page fills in immediately.
   2. The full analysis (/api/stock/<sym>/analysis) is fetched once and cached
      in `state.analysis`, because almost every tab needs part of it.
   3. Each tab renders LAZILY - only when you click it. That keeps the first
      paint fast and avoids doing work nobody looks at.
   ========================================================================== */

const state = {
  symbol: null,
  analysis: null,      // the big object from /analysis, fetched once
  history: null,       // candles for the currently selected period
  period: '1Y',
  loadedTabs: {},      // which tabs have already been rendered
  chatHistory: []
};

/* ---------- Beginner-mode glossary --------------------------------------
   Every entry becomes a small blue box under the relevant number when
   "Explain Like I Am a Beginner" is switched on.
   ---------------------------------------------------------------------- */
const GLOSSARY = {
  market_cap: 'Market cap is the price of one share multiplied by the number of shares. It is what the whole company is worth on the stock market today.',
  revenue: 'Revenue (or sales) is the total money customers paid the company. Nothing has been subtracted yet.',
  ebitda: 'EBITDA is profit before interest, tax, depreciation and amortisation. It shows how much the core operations earn before financing and accounting choices.',
  pat: 'PAT (Profit After Tax), also called net profit, is what is left after every cost, interest payment and tax.',
  eps: 'EPS (Earnings Per Share) is net profit divided by the number of shares. It is your slice of the profit per share you own.',
  pe: 'P/E compares price with earnings. If a company earns Rs 10 per share and the share costs Rs 200, its P/E is 20: you pay Rs 20 for every Rs 1 of yearly earnings.',
  pb: 'P/B compares the share price with the book value (assets minus liabilities) per share. Below 1 means you pay less than the accounting value of the company.',
  roe: 'ROE (Return on Equity) is profit as a percentage of the owners money in the business. 20% means Rs 100 of owners capital produced Rs 20 of profit in a year.',
  roce: 'ROCE (Return on Capital Employed) is like ROE but counts borrowed money too. It is harder to flatter with debt, so it says more about business quality.',
  de: 'Debt to Equity compares borrowed money with the owners money. 0 means no debt. Above 1 means the company has borrowed more than the owners put in.',
  fcf: 'Free Cash Flow is the cash left after paying to run and grow the business. Profit is an accounting number; free cash flow is actual money.',
  dividend_yield: 'Dividend yield is the yearly dividend as a percentage of the share price. A 2% yield means Rs 2 a year for every Rs 100 invested.',
  rsi: 'RSI compares the size of recent gains with recent losses on a 0 to 100 scale. Above 70 is called overbought and below 30 oversold. It describes the past, not the future.',
  ma: 'A moving average is the average closing price over the last N days. It smooths out daily noise so a trend is easier to see.',
  support: 'Support is a price area where buyers have stepped in before. Resistance is where sellers have. Neither is a rule, only a pattern in past trading.',
  ev_ebitda: 'EV/EBITDA compares the whole company (including its debt) with its operating earnings. It is useful when comparing companies with different debt levels.',
  peg: 'PEG divides the P/E by the earnings growth rate. Near 1 is the old rule of thumb for growth roughly justifying the price.'
};

/** Render a glossary box. Shown only when beginner mode is on (CSS handles it). */
function explain(key) {
  const text = GLOSSARY[key];
  return text ? '<div class="explain">' + esc(text) + '</div>' : '';
}

/** A metric tile that prints "Data unavailable" instead of a fake zero. */
function metricTile(label, value, sub, glossaryKey) {
  const missing = value === null || value === undefined || value === 'N/A';
  return '' +
    '<div class="metric' + (missing ? ' unavailable' : '') + '">' +
      '<div class="label">' + esc(label) + '</div>' +
      '<div class="value">' + (missing ? 'Data unavailable' : value) + '</div>' +
      (sub ? '<div class="sub">' + sub + '</div>' : '') +
      (glossaryKey ? explain(glossaryKey) : '') +
    '</div>';
}

/** Colour a score 0-10 as good / mid / bad for the progress bars. */
function scoreClass(score) {
  if (score === null || score === undefined) return '';
  return score >= 7 ? 'good' : (score >= 5 ? 'mid' : 'bad');
}

/** Turn a verdict word into the matching CSS class. */
function verdictClass(view) {
  const v = String(view || '').toUpperCase();
  if (v.includes('BULL')) return 'verdict-bullish';
  if (v.includes('BEAR')) return 'verdict-bearish';
  return 'verdict-neutral';
}

/** Fetch the full analysis once and reuse it everywhere. */
async function getAnalysis() {
  if (state.analysis) return state.analysis;
  state.analysis = await api('/api/stock/' + state.symbol + '/analysis');
  return state.analysis;
}

/** A standard "where did this come from" footer for a card. */
function sourceNote(source, asOf, extra) {
  let text = 'Source: ' + esc(source || 'not stated by the provider');
  if (asOf) text += ' &middot; Data updated: ' + esc(formatTimestamp(asOf));
  if (extra) text += ' &middot; ' + esc(extra);
  return '<p class="source-note">' + text + '</p>';
}

/* ==========================================================================
   HEADER: company name, price, quick stats
   ========================================================================== */

async function loadHeader() {
  try {
    const data = await api('/api/stock/' + state.symbol);
    const company = data.company || {};
    const price = data.price || {};

    document.getElementById('companyName').textContent =
      company.company_name || state.symbol;

    const demoBadge = company.is_demo
      ? '<span class="badge badge-demo">Demo data</span>' : '';
    document.getElementById('exchangeLine').innerHTML =
      '<span>NSE: <strong>' + esc(company.nse_symbol || state.symbol) + '</strong></span>' +
      '<span>BSE: <strong>' + esc(company.bse_code || 'N/A') + '</strong></span>' +
      '<span>' + esc(company.sector || '') + '</span>' +
      '<span class="badge badge-neutral">' + esc(company.industry || '') + '</span>' +
      demoBadge;

    const direction = changeClass(price.change_pct);
    document.getElementById('priceRow').innerHTML =
      '<span class="price-main">Rs ' + formatINR(price.price) + '</span>' +
      '<span class="price-change ' + direction + '">' +
        (price.change > 0 ? '+' : '') + formatINR(price.change) +
        ' (' + formatPct(price.change_pct) + ')</span>' +
      '<span class="price-range">52W High Rs ' + formatINR(price.week_52_high) +
        ' &middot; 52W Low Rs ' + formatINR(price.week_52_low) + '</span>';

    document.getElementById('quickStats').innerHTML =
      metricTile('Market cap', formatCrore(company.market_cap_cr), null, 'market_cap') +
      metricTile('Day range',
        price.day_low && price.day_high
          ? formatINR(price.day_low) + ' - ' + formatINR(price.day_high) : null) +
      metricTile('Volume', price.volume ? Number(price.volume).toLocaleString('en-IN') : null) +
      metricTile('Face value', company.face_value !== null && company.face_value !== undefined
        ? 'Rs ' + company.face_value : null) +
      metricTile('Open', price.open ? 'Rs ' + formatINR(price.open) : null) +
      metricTile('Previous close', price.previous_close
        ? 'Rs ' + formatINR(price.previous_close) : null);

    let note = 'Source: ' + esc(price.source || 'unknown') +
               ' &middot; Data updated: ' + esc(formatTimestamp(price.as_of));
    // Requirement 38: warn when the provider's own data looks stale or incomplete.
    if (price.quality && !price.quality.ok) {
      note += ' <span class="badge badge-warn">' +
              esc(price.quality.issues.join('; ')) + '</span>';
    }
    document.getElementById('priceSource').innerHTML = note;

  } catch (error) {
    document.getElementById('priceRow').innerHTML =
      '<div class="notice notice-error">' + esc(error.message) + '</div>';
  }
}

/* ==========================================================================
   PRICE CHART
   ========================================================================== */

function selectedMAs() {
  return Array.from(document.querySelectorAll('#maToggles input:checked'))
              .map(input => Number(input.value));
}

async function loadChart(period) {
  state.period = period || state.period;
  const sourceEl = document.getElementById('chartSource');

  try {
    const data = await api('/api/stock/' + state.symbol +
                           '/history?period=' + encodeURIComponent(state.period));
    state.history = data;

    if (!data.candles || data.candles.length === 0) {
      sourceEl.innerHTML = '<span class="badge badge-warn">No price history returned ' +
                           'for this period.</span>';
      return;
    }

    drawPriceChart('priceChart', data.candles, selectedMAs());
    drawVolumeChart('volumeChart', data.candles);
    sourceEl.innerHTML = 'Source: ' + esc(data.source || 'unknown') +
      ' &middot; ' + data.candles.length + ' trading sessions' +
      ' &middot; Last candle: ' + esc(formatTimestamp(data.as_of || data.candles[data.candles.length - 1].date));

  } catch (error) {
    sourceEl.innerHTML = '<span class="badge badge-warn">' + esc(error.message) + '</span>';
  }
}

/* Charts must be redrawn when the theme changes, because their grid and label
   colours are baked in at draw time. charts.js calls this. */
window.redrawAllCharts = function () {
  if (state.history && state.history.candles) {
    drawPriceChart('priceChart', state.history.candles, selectedMAs());
    drawVolumeChart('volumeChart', state.history.candles);
  }
  if (state.analysis && state.analysis.shareholding) {
    drawShareholdingChart('shareholdingChart', state.analysis.shareholding.quarters);
  }
};

/* ==========================================================================
   OVERVIEW TAB
   ========================================================================== */

function renderScoreBox(analysis) {
  const scores = analysis.scores || {};
  const box = document.getElementById('scoreBox');

  if (!scores.available) {
    box.innerHTML = '<p class="muted small">Not enough data to build a score.</p>';
    return;
  }

  const rows = (scores.categories || []).map(category => {
    const score = category.score;
    const width = score === null ? 0 : score * 10;
    return '' +
      '<div class="score-row" title="' + esc(category.reason) + '">' +
        '<div class="name">' + esc(category.category) + '</div>' +
        '<div class="bar ' + scoreClass(score) + '"><span style="width:' + width + '%"></span></div>' +
        '<div class="val">' + (score === null ? '&mdash;' : score + '/10') + '</div>' +
      '</div>';
  }).join('');

  const overall = scores.overall_score === null || scores.overall_score === undefined
    ? '&mdash;' : scores.overall_score;

  box.innerHTML =
    '<div class="big-score">' + overall + '<small>/10</small></div>' +
    '<p class="tiny muted" style="margin:6px 0 14px">Weighted average of the categories ' +
      'below. Hover a row to see exactly which number produced it.</p>' +
    rows +
    '<div class="notice notice-warn" style="margin-top:14px;font-size:.8rem">' +
      esc(scores.warning) + '</div>' +
    '<p class="tiny muted" style="margin-top:10px">' + esc(scores.methodology) + '</p>';
}

function renderProfile(analysis) {
  const company = analysis.company || {};
  const quarters = (analysis.shareholding || {}).quarters || [];
  const latest = quarters.length ? quarters[quarters.length - 1] : {};
  const ratios = (analysis.valuation || {}).ratios || {};
  const yieldValue = ratios.dividend_yield_pct;

  document.getElementById('profileBox').innerHTML =
    '<div class="metrics">' +
      metricTile('Sector', esc(company.sector || 'N/A')) +
      metricTile('Industry', esc(company.industry || 'N/A')) +
      metricTile('Dividend yield',
        (yieldValue === null || yieldValue === undefined) ? null : yieldValue + '%',
        null, 'dividend_yield') +
      metricTile('Promoter holding',
        latest.promoter === undefined ? null : latest.promoter + '%') +
      metricTile('FII holding', latest.fii === undefined ? null : latest.fii + '%') +
      metricTile('DII holding', latest.dii === undefined ? null : latest.dii + '%') +
    '</div>' +
    sourceNote(company.source, company.as_of);
}

function renderBusiness(analysis) {
  const company = analysis.company || {};
  const model = company.business_model;
  const box = document.getElementById('businessBox');

  let html = '<p>' + esc(company.description ||
    'No business description was returned by the data provider.') + '</p>';

  if (model) {
    const segments = (model.segments || []).map(segment =>
      '<li>' + esc(segment.name) + ' &mdash; about ' + segment.share_pct + '% of the business</li>'
    ).join('');

    const geography = Object.entries(model.geography || {}).map(entry =>
      '<li>' + esc(entry[0]) + ': ' + entry[1] + '%</li>'
    ).join('');

    html +=
      '<div class="grid grid-3" style="margin-top:16px">' +
        '<div><h4>What it sells</h4>' +
          '<p class="small muted">' + esc(model.what_it_sells) + '</p>' +
          '<h4 style="margin-top:14px">Who buys it</h4>' +
          '<p class="small muted">' + esc(model.who_buys) + '</p></div>' +
        '<div><h4>Business segments</h4><ul class="small muted">' + segments + '</ul></div>' +
        '<div><h4>Where revenue comes from</h4><ul class="small muted">' + geography + '</ul>' +
          '<h4 style="margin-top:14px">Competitive advantage</h4>' +
          '<p class="small muted">' + esc(model.moat) + '</p></div>' +
      '</div>';
  } else {
    html += '<p class="small muted">A structured business-model breakdown (segments, ' +
            'geography, customers) needs data from company filings. The current provider ' +
            'does not supply it, so nothing is shown rather than guessed.</p>';
  }

  const peers = analysis.peers || [];
  if (peers.length) {
    html += '<h4 style="margin-top:18px">Major competitors in the same industry</h4><p>' +
      peers.map(p => '<a class="badge badge-brand" style="margin-right:6px" href="/stock/' +
                     esc(p) + '">' + esc(p) + '</a>').join('') + '</p>';
  }

  box.innerHTML = html + sourceNote(company.source, company.as_of);
}

function renderShareholding(analysis) {
  const data = analysis.shareholding || {};
  const box = document.getElementById('shareholdingBox');
  const quarters = data.quarters || [];

  if (!quarters.length) {
    box.innerHTML = '<div class="notice notice-warn">' +
      esc(data.reason || 'Shareholding data is not available from the current provider.') +
      '</div>';
    return;
  }

  drawShareholdingChart('shareholdingChart', quarters);

  const rows = quarters.map(q =>
    '<tr><td>' + esc(q.period) + '</td>' +
    '<td class="num">' + formatNum(q.promoter) + '%</td>' +
    '<td class="num">' + formatNum(q.fii) + '%</td>' +
    '<td class="num">' + formatNum(q.dii) + '%</td>' +
    '<td class="num">' + formatNum(q.public) + '%</td></tr>'
  ).join('');

  const changes = data.changes || {};
  const flags = (changes.flags || []).map(f =>
    '<div class="notice notice-warn small" style="margin-top:8px">' + esc(f) + '</div>'
  ).join('');

  const movement = (changes.changes || []).map(c =>
    '<li>' + esc(c.category) + ': ' + formatNum(c.from_pct) + '% to ' +
    formatNum(c.to_pct) + '% (' + (c.change_pp > 0 ? '+' : '') +
    formatNum(c.change_pp) + ' pp)</li>'
  ).join('');

  box.innerHTML =
    '<div class="table-wrap"><table class="data"><thead><tr><th>Quarter</th>' +
      '<th class="num">Promoter</th><th class="num">FII</th><th class="num">DII</th>' +
      '<th class="num">Public</th></tr></thead>' +
      '<tbody>' + rows + '</tbody></table></div>' +
    (movement ? '<h4 style="margin-top:14px">Change over these quarters</h4>' +
                '<ul class="small muted">' + movement + '</ul>' : '') +
    flags +
    '<p class="tiny muted" style="margin-top:10px">' + esc(changes.note || '') + '</p>' +
    sourceNote(data.source, data.as_of);
}

async function renderSummary() {
  const box = document.getElementById('summaryBox');
  try {
    const analysis = await getAnalysis();
    const thesis = analysis.thesis || {};

    const badge = document.getElementById('summaryBadge');
    badge.className = 'badge ' + (thesis.overall_view === 'Bullish' ? 'badge-up'
                    : thesis.overall_view === 'Bearish' ? 'badge-down' : 'badge-neutral');
    badge.textContent = thesis.overall_view || '';

    const result = await api('/api/stock/' + state.symbol + '/ai/summary');
    box.innerHTML =
      '<div class="ai-output">' + esc(result.text) + '</div>' +
      '<p class="tiny muted" style="margin-top:10px">' + esc(result.note || '') + '</p>';
  } catch (error) {
    showError(box, error.message);
  }
}

/* ==========================================================================
   FUNDAMENTALS TAB
   ========================================================================== */

async function renderFundamentals() {
  const box = document.getElementById('fundamentalsBox');
  try {
    const analysis = await getAnalysis();
    const f = analysis.fundamentals || {};

    if (!f.available) {
      showError(box, f.reason || 'No fundamental data available.', 'warn');
      return;
    }

    const growth = f.growth || {};
    const profit = f.profitability || {};
    const health = f.financial_health || {};
    const quality = f.earnings_quality || {};

    const pct = (v) => (v === null || v === undefined) ? null : formatNum(v) + '%';

    box.innerHTML =
      '<div class="card"><h2>Revenue and growth</h2><div class="metrics">' +
        metricTile('Revenue (' + esc(growth.latest_period || '') + ')',
          growth.revenue === null ? null : 'Rs ' + formatCrore(growth.revenue), null, 'revenue') +
        metricTile('Revenue growth YoY', pct(growth.revenue_yoy_pct)) +
        metricTile('Revenue CAGR 3Y', pct(growth.revenue_cagr_3y_pct)) +
        metricTile('Revenue CAGR 5Y', pct(growth.revenue_cagr_5y_pct)) +
        metricTile('Profit growth YoY', pct(growth.profit_yoy_pct)) +
        metricTile('EPS', growth.eps, null, 'eps') +
      '</div><div class="chart-box" style="height:240px"><canvas id="revenueChart"></canvas></div></div>' +

      '<div class="card"><h2>Profitability</h2><div class="metrics">' +
        metricTile('EBITDA', profit.ebitda === null ? null : 'Rs ' + formatCrore(profit.ebitda),
          null, 'ebitda') +
        metricTile('EBITDA margin', pct(profit.ebitda_margin_pct)) +
        metricTile('EBIT', profit.ebit === null ? null : 'Rs ' + formatCrore(profit.ebit)) +
        metricTile('PAT', profit.pat === null ? null : 'Rs ' + formatCrore(profit.pat), null, 'pat') +
        metricTile('PAT margin', pct(profit.pat_margin_pct)) +
        metricTile('Margin trend', esc(profit.margin_trend || 'N/A'),
          profit.margin_change_pp === null ? null
            : formatNum(profit.margin_change_pp) + ' pp vs last year') +
      '</div><div class="chart-box" style="height:220px"><canvas id="marginChart"></canvas></div></div>' +

      '<div class="card"><h2>Returns on capital</h2><div class="metrics">' +
        metricTile('ROE', pct(profit.roe_pct), null, 'roe') +
        metricTile('ROCE', pct(profit.roce_pct), null, 'roce') +
        metricTile('ROA', pct(profit.roa_pct)) +
      '</div></div>' +

      '<div class="card"><h2>Financial health</h2><div class="metrics">' +
        metricTile('Total debt', health.total_debt === null ? null
          : 'Rs ' + formatCrore(health.total_debt)) +
        metricTile('Debt / equity', formatNum(health.debt_to_equity), null, 'de') +
        metricTile('Interest cover', health.interest_coverage === null ? null
          : formatNum(health.interest_coverage) + 'x') +
        metricTile('Cash', health.cash === null ? null : 'Rs ' + formatCrore(health.cash)) +
        metricTile('Current ratio', formatNum(health.current_ratio)) +
        metricTile('Free cash flow', health.free_cash_flow === null ? null
          : 'Rs ' + formatCrore(health.free_cash_flow), null, 'fcf') +
        metricTile('Cash conversion', formatNum(health.cash_conversion),
          'operating cash flow / net profit') +
      '</div></div>' +

      '<div class="card"><h2>Earnings quality</h2>' +
        (quality.flags && quality.flags.length
          ? quality.flags.map(x => '<div class="notice notice-warn small" ' +
              'style="margin-bottom:8px">' + esc(x) + '</div>').join('')
          : '<p class="small muted">No earnings-quality flags were triggered by the ' +
            'available data.</p>') +
        (quality.observations || []).map(x =>
          '<div class="notice small" style="margin-bottom:8px">' + esc(x) + '</div>').join('') +
        '<p class="tiny muted">' + esc(quality.note || '') + '</p>' +
      '</div>' +
      sourceNote(f.source, f.as_of, f.units);

    // Charts are drawn after the HTML exists, because Chart.js needs the canvas.
    const history = growth.history || [];
    drawBarChart('revenueChart', history.map(r => r.period), [
      { label: 'Revenue (Rs cr)', data: history.map(r => r.revenue) },
      { label: 'Net profit (Rs cr)', data: history.map(r => r.net_profit) }
    ]);

    const margins = profit.margin_history || [];
    drawLineChart('marginChart', margins.map(r => r.period), [
      { label: 'EBITDA margin %', data: margins.map(r => r.ebitda_margin_pct) },
      { label: 'PAT margin %', data: margins.map(r => r.pat_margin_pct) }
    ]);

  } catch (error) {
    showError(box, error.message);
  }
}

/* ==========================================================================
   FINANCIALS TAB - the three statements
   ========================================================================== */

/** Build one statement table. `rows` is [[label, key], ...] */
function statementTable(title, periods, rows, annual) {
  const header = '<tr><th>' + esc(title) + '</th>' +
    periods.map(p => '<th class="num">' + esc(p) + '</th>').join('') + '</tr>';

  const body = rows.map(row => {
    const label = row[0], key = row[1];
    return '<tr><td>' + esc(label) + '</td>' +
      annual.map(year => {
        const value = year[key];
        return '<td class="num">' +
          (value === null || value === undefined ? '&mdash;' : formatINR(value, 1)) + '</td>';
      }).join('') + '</tr>';
  }).join('');

  return '<div class="table-wrap"><table class="data"><thead>' + header +
         '</thead><tbody>' + body + '</tbody></table></div>';
}

async function renderFinancials() {
  const box = document.getElementById('financialsBox');
  try {
    const analysis = await getAnalysis();
    const financials = analysis.financials || {};
    const annual = financials.annual || [];

    if (!annual.length) {
      showError(box, 'No financial statements were returned for this company.', 'warn');
      return;
    }

    const periods = annual.map(y => y.period);

    box.innerHTML =
      '<div class="card"><h2>Income statement</h2>' +
        '<p class="small muted">All figures in ' + esc(financials.units || 'Rs crore') + '.</p>' +
        statementTable('Income statement', periods, [
          ['Revenue', 'revenue'], ['EBITDA', 'ebitda'], ['Depreciation', 'depreciation'],
          ['EBIT', 'ebit'], ['Interest expense', 'interest_expense'],
          ['Profit before tax', 'pbt'], ['Net profit', 'net_profit'], ['EPS (Rs)', 'eps']
        ], annual) + explain('ebitda') +
      '</div>' +

      '<div class="card"><h2>Balance sheet</h2>' +
        statementTable('Balance sheet', periods, [
          ['Total assets', 'total_assets'], ['Total debt', 'total_debt'], ['Cash', 'cash'],
          ['Shareholders equity', 'equity'], ['Receivables', 'receivables'],
          ['Inventory', 'inventory'], ['Current assets', 'current_assets'],
          ['Current liabilities', 'current_liabilities']
        ], annual) +
        '<div class="chart-box" style="height:230px"><canvas id="balanceChart"></canvas></div>' +
      '</div>' +

      '<div class="card"><h2>Cash flow</h2>' +
        statementTable('Cash flow', periods, [
          ['Operating cash flow', 'operating_cash_flow'],
          ['Capital expenditure', 'capex'],
          ['Free cash flow', 'free_cash_flow']
        ], annual) + explain('fcf') +
        '<div class="chart-box" style="height:230px"><canvas id="cashChart"></canvas></div>' +
      '</div>' +
      sourceNote(financials.source, financials.as_of, financials.units);

    drawBarChart('balanceChart', periods, [
      { label: 'Total debt', data: annual.map(y => y.total_debt) },
      { label: 'Cash', data: annual.map(y => y.cash) },
      { label: 'Equity', data: annual.map(y => y.equity) }
    ]);
    drawBarChart('cashChart', periods, [
      { label: 'Operating cash flow', data: annual.map(y => y.operating_cash_flow) },
      { label: 'Free cash flow', data: annual.map(y => y.free_cash_flow) }
    ]);

  } catch (error) {
    showError(box, error.message);
  }
}

/* ==========================================================================
   TECHNICALS TAB
   ========================================================================== */

async function renderTechnicals() {
  const box = document.getElementById('technicalsBox');
  try {
    const analysis = await getAnalysis();
    const t = analysis.technicals || {};

    if (!t.available) {
      showError(box, t.reason || 'Technical analysis is not available.', 'warn');
      return;
    }

    const ma = t.moving_averages || {};
    const vsMa = t.price_vs_ma || {};
    const levels = t.levels || {};
    const trend = t.trend || {};
    const vol = t.volatility || {};

    const maTile = (label, key) => metricTile(
      label,
      ma[key] === null ? null : 'Rs ' + formatINR(ma[key]),
      (vsMa[key] === null || vsMa[key] === undefined) ? null
        : '<span class="' + changeClass(vsMa[key]) + '">Price is ' +
          formatPct(vsMa[key]) + ' vs this average</span>'
    );

    box.innerHTML =
      '<div class="card">' +
        '<div class="card-head"><h2>Technical view</h2>' +
          '<span class="verdict ' + verdictClass(t.view) + '">' + esc(t.view) + '</span></div>' +
        '<ul class="reason-list">' +
          (t.reasons || []).map(r => '<li>' + esc(r) + '</li>').join('') + '</ul>' +
        '<div class="notice notice-warn" style="margin-top:14px;font-size:.82rem">' +
          esc(t.disclaimer) + '</div>' +
      '</div>' +

      '<div class="card"><h2>Trend</h2><div class="metrics">' +
        metricTile('Short term', esc(trend.short_term || 'N/A')) +
        metricTile('Medium term', esc(trend.medium_term || 'N/A')) +
        metricTile('Long term', esc(trend.long_term || 'N/A')) +
        metricTile('Overall', esc(trend.overall || 'N/A')) +
      '</div></div>' +

      '<div class="card"><h2>Moving averages</h2><div class="metrics">' +
        maTile('20 DMA', 'dma_20') + maTile('50 DMA', 'dma_50') +
        maTile('100 DMA', 'dma_100') + maTile('200 DMA', 'dma_200') +
      '</div>' + explain('ma') + '</div>' +

      '<div class="card"><h2>Momentum indicators</h2><div class="metrics">' +
        metricTile('RSI (14)', formatNum(t.rsi_14), null, 'rsi') +
        metricTile('MACD', formatNum((t.macd || {}).macd, 3),
          esc((t.macd || {}).crossover || '')) +
        metricTile('MACD signal', formatNum((t.macd || {}).signal, 3)) +
        metricTile('ADX (14)', formatNum(t.adx_14), 'trend strength') +
        metricTile('Stochastic %K', formatNum(t.stochastic_k)) +
      '</div></div>' +

      '<div class="card"><h2>Price levels</h2><div class="metrics">' +
        metricTile('Support', (levels.support || []).length
          ? levels.support.map(v => 'Rs ' + formatINR(v)).join(', ') : null) +
        metricTile('Resistance', (levels.resistance || []).length
          ? levels.resistance.map(v => 'Rs ' + formatINR(v)).join(', ') : null) +
        metricTile('60-day high', 'Rs ' + formatINR(levels.recent_high_60d)) +
        metricTile('60-day low', 'Rs ' + formatINR(levels.recent_low_60d)) +
        metricTile('Breakout level', levels.breakout_level
          ? 'Rs ' + formatINR(levels.breakout_level) : null) +
        metricTile('Breakdown level', levels.breakdown_level
          ? 'Rs ' + formatINR(levels.breakdown_level) : null) +
        metricTile('Consolidating?', levels.consolidating ? 'Yes' : 'No',
          'band narrower than 12% of the recent high') +
      '</div>' + explain('support') + '</div>' +

      '<div class="card"><h2>Volatility and volume</h2><div class="metrics">' +
        metricTile('ATR (14)', vol.atr_14 === null ? null : 'Rs ' + formatINR(vol.atr_14),
          'typical daily move') +
        metricTile('Annualised volatility', vol.annualised_pct === null ? null
          : formatNum(vol.annualised_pct) + '%') +
        metricTile('Largest fall in this window', vol.max_drawdown_pct === null ? null
          : formatNum(vol.max_drawdown_pct) + '%') +
        metricTile('Volume vs 50-day average',
          formatNum((t.volume || {}).ratio_vs_average) + 'x') +
      '</div></div>' +
      sourceNote(t.source, t.as_of);

  } catch (error) {
    showError(box, error.message);
  }
}

/* ==========================================================================
   VALUATION TAB
   ========================================================================== */

async function renderValuation() {
  const box = document.getElementById('valuationBox');
  try {
    const analysis = await getAnalysis();
    const v = analysis.valuation || {};

    if (!v.available) {
      showError(box, v.reason || 'Valuation could not be calculated.', 'warn');
      return;
    }

    const r = v.ratios || {};
    const band = v.historical_band || {};
    const verdict = v.verdict || {};
    const scenarios = analysis.scenarios || {};

    let bandHtml = '<p class="small muted">' +
      esc(band.reason || 'A historical P/E band could not be built.') + '</p>';
    if (band.available) {
      const position = Math.max(0, Math.min(100, band.percentile_in_range || 0));
      bandHtml =
        '<div class="metrics">' +
          metricTile('Lowest', formatNum(band.low)) +
          metricTile('Median', formatNum(band.median)) +
          metricTile('Highest', formatNum(band.high)) +
          metricTile('Today', formatNum(band.current),
            band.vs_median_pct === null ? null
              : '<span class="' + changeClass(band.vs_median_pct) + '">' +
                formatPct(band.vs_median_pct) + ' vs median</span>') +
        '</div>' +
        '<div class="bar" style="margin-top:12px"><span style="width:' + position + '%"></span></div>' +
        '<p class="tiny muted" style="margin-top:6px">Today sits about ' +
          formatNum(position, 0) + '% of the way up its own recent P/E range.</p>' +
        '<p class="tiny muted">' + esc(band.method_note) + '</p>';
    }

    let scenarioHtml = '<p class="small muted">' +
      esc(scenarios.reason || 'Scenario analysis is unavailable.') + '</p>';
    if (scenarios.available) {
      scenarioHtml =
        '<div class="scenario-grid">' +
          scenarios.scenarios.map(s =>
            '<div class="scenario ' + esc(s.scenario) + '">' +
              '<h4>' + esc(s.scenario) + ' case</h4>' +
              '<div class="small"><strong>Assumption:</strong> EPS grows ' +
                formatNum(s.assumed_eps_growth_pct) + '% a year for 3 years, exit P/E ' +
                formatNum(s.assumed_exit_pe) + '</div>' +
              '<div style="margin-top:8px" class="num"><strong>Illustrative price in year 3: Rs ' +
                formatINR(s.illustrative_price_year_3) + '</strong></div>' +
              '<div class="small ' + changeClass(s.vs_today_pct) + '">' +
                formatPct(s.vs_today_pct) + ' versus today</div>' +
              '<ul>' + s.assumptions.map(a => '<li>' + esc(a) + '</li>').join('') + '</ul>' +
            '</div>').join('') +
        '</div>' +
        '<div class="notice notice-warn" style="margin-top:14px;font-size:.82rem">' +
          esc(scenarios.disclaimer) + '</div>';
    }

    const verdictCss = verdict.label === 'Undervalued' ? 'verdict-bullish'
                     : verdict.label === 'Very Expensive' ? 'verdict-bearish'
                     : 'verdict-neutral';

    box.innerHTML =
      '<div class="card">' +
        '<div class="card-head"><h2>Valuation</h2>' +
          '<span class="verdict ' + verdictCss + '">' + esc(verdict.label || 'N/A') + '</span></div>' +
        '<div class="metrics">' +
          metricTile('P/E', formatNum(r.pe_ratio), null, 'pe') +
          metricTile('P/B', formatNum(r.pb_ratio), null, 'pb') +
          metricTile('EV / EBITDA', formatNum(r.ev_ebitda), null, 'ev_ebitda') +
          metricTile('PEG', formatNum(r.peg_ratio),
            r.earnings_growth_3y_pct === null ? null
              : 'using 3Y profit CAGR of ' + formatNum(r.earnings_growth_3y_pct) + '%', 'peg') +
          metricTile('Price / Sales', formatNum(r.ps_ratio)) +
          metricTile('Dividend yield', r.dividend_yield_pct === null ? null
            : formatNum(r.dividend_yield_pct) + '%', null, 'dividend_yield') +
          metricTile('Forward P/E', null, esc(r.forward_pe_note)) +
          metricTile('Market cap', 'Rs ' + formatCrore(r.market_cap_cr), null, 'market_cap') +
          metricTile('Enterprise value', 'Rs ' + formatCrore(r.enterprise_value_cr)) +
        '</div>' +
        '<h4 style="margin-top:18px">Why this classification</h4>' +
        '<ul class="reason-list">' +
          (verdict.reasons || []).map(x => '<li>' + esc(x) + '</li>').join('') + '</ul>' +
      '</div>' +
      '<div class="card"><h2>Versus its own history</h2>' + bandHtml + '</div>' +
      '<div class="card"><h2>Scenario analysis</h2>' +
        '<p class="small muted">Three sets of assumptions applied to the same arithmetic. ' +
        'These are illustrations, not forecasts.</p>' + scenarioHtml + '</div>' +
      sourceNote(v.source, null);

  } catch (error) {
    showError(box, error.message);
  }
}

/* ==========================================================================
   EARNINGS TAB
   ========================================================================== */

async function renderEarnings() {
  const box = document.getElementById('earningsBox');
  try {
    const analysis = await getAnalysis();
    const quarterly = analysis.quarterly || {};
    const quarters = quarterly.quarters || [];

    if (!quarters.length) {
      showError(box, 'No quarterly results were returned for this company.', 'warn');
      return;
    }

    // Newest quarter first reads more naturally in a results table.
    const ordered = quarters.slice().reverse();
    const rows = ordered.map(q =>
      '<tr>' +
        '<td>' + esc(q.period) + '</td>' +
        '<td class="num">' + formatINR(q.revenue, 1) + '</td>' +
        '<td class="num ' + changeClass(q.revenue_yoy_pct) + '">' +
          (q.revenue_yoy_pct === null ? '&mdash;' : formatPct(q.revenue_yoy_pct)) + '</td>' +
        '<td class="num ' + changeClass(q.revenue_qoq_pct) + '">' +
          (q.revenue_qoq_pct === null ? '&mdash;' : formatPct(q.revenue_qoq_pct)) + '</td>' +
        '<td class="num">' + formatINR(q.ebitda, 1) + '</td>' +
        '<td class="num">' + formatNum(q.ebitda_margin) + '%</td>' +
        '<td class="num">' + formatINR(q.net_profit, 1) + '</td>' +
        '<td class="num ' + changeClass(q.profit_yoy_pct) + '">' +
          (q.profit_yoy_pct === null ? '&mdash;' : formatPct(q.profit_yoy_pct)) + '</td>' +
        '<td class="num">' + formatNum(q.eps) + '</td>' +
      '</tr>'
    ).join('');

    box.innerHTML =
      '<div class="card"><h2>Quarterly results</h2>' +
        '<p class="small muted">All figures in ' + esc(quarterly.units || 'Rs crore') + '.</p>' +
        '<div class="table-wrap"><table class="data"><thead><tr>' +
          '<th>Quarter</th><th class="num">Revenue</th><th class="num">Rev YoY</th>' +
          '<th class="num">Rev QoQ</th><th class="num">EBITDA</th><th class="num">Margin</th>' +
          '<th class="num">PAT</th><th class="num">PAT YoY</th><th class="num">EPS</th>' +
        '</tr></thead><tbody>' + rows + '</tbody></table></div>' +
        '<div class="chart-box" style="height:250px"><canvas id="quarterChart"></canvas></div>' +
        sourceNote(quarterly.source, quarterly.as_of) +
      '</div>' +
      '<div class="card"><h2>What the latest quarter shows</h2>' +
        '<div class="ai-output" id="earningsNarrative">Loading...</div></div>';

    drawBarChart('quarterChart', quarters.map(q => q.period), [
      { label: 'Revenue', data: quarters.map(q => q.revenue) },
      { label: 'Net profit', data: quarters.map(q => q.net_profit) }
    ]);

    const narrative = await api('/api/stock/' + state.symbol + '/ai/quarterly');
    document.getElementById('earningsNarrative').textContent = narrative.text;

  } catch (error) {
    showError(box, error.message);
  }
}

/* ==========================================================================
   NEWS TAB
   ========================================================================== */

function sentimentBadge(sentiment) {
  const map = { positive: 'badge-up', negative: 'badge-down', neutral: 'badge-neutral' };
  return '<span class="badge ' + (map[sentiment] || 'badge-neutral') + '">' +
         esc(sentiment || 'neutral') + '</span>';
}

async function renderNews(page = 1) {
  const box = document.getElementById('newsBox');
  showLoading(box, 'Loading news...');

  try {
    const data = await api('/api/stock/' + state.symbol + '/news?page=' + page);
    const articles = data.articles || [];

    if (!articles.length) {
      box.innerHTML = '<div class="card"><div class="notice notice-warn">' +
        esc(data.message || 'No news available.') + '</div></div>';
      return;
    }

    const summary = data.sentiment_summary || {};
    const items = articles.map(a =>
      '<div class="news-item">' +
        '<div class="news-head">' +
          '<h3>' + (a.url ? '<a href="' + esc(a.url) + '" target="_blank" rel="noopener">' +
                    esc(a.headline) + '</a>' : esc(a.headline)) + '</h3>' +
          sentimentBadge(a.sentiment) +
        '</div>' +
        '<div class="news-meta">' +
          '<span>' + esc(formatTimestamp(a.date)) + '</span>' +
          '<span>Source: ' + esc(a.source) + '</span>' +
          (a.unverified ? '<span class="badge badge-warn">Unverified</span>' : '') +
          (a.is_demo ? '<span class="badge badge-demo">Demo</span>' : '') +
        '</div>' +
        (a.summary ? '<p class="small">' + esc(a.summary) + '</p>' : '') +
        (a.why_it_matters ? '<div class="news-why"><strong>Why it matters:</strong> ' +
          esc(a.why_it_matters) + '</div>' : '') +
      '</div>'
    ).join('');

    const p = data.pagination || {};
    const pager =
      '<div class="pager">' +
        '<button class="btn btn-outline btn-sm" ' + (p.page <= 1 ? 'disabled' : '') +
          ' data-page="' + (p.page - 1) + '">Previous</button>' +
        '<span class="small muted">Page ' + p.page + ' of ' + p.total_pages + '</span>' +
        '<button class="btn btn-outline btn-sm" ' +
          (p.page >= p.total_pages ? 'disabled' : '') +
          ' data-page="' + (p.page + 1) + '">Next</button>' +
      '</div>';

    box.innerHTML =
      '<div class="card">' +
        '<div class="card-head"><h2>Latest news</h2>' +
          '<span class="small muted">' + (summary.counts ? summary.counts.positive : 0) +
          ' positive &middot; ' + (summary.counts ? summary.counts.negative : 0) +
          ' negative &middot; ' + (summary.counts ? summary.counts.neutral : 0) +
          ' neutral on this page</span></div>' +
        items + pager +
        '<p class="tiny muted" style="margin-top:12px">' + esc(data.note || '') + '</p>' +
        sourceNote(data.source, null) +
      '</div>' +
      '<div class="card"><h2>What the news adds up to</h2>' +
        '<div class="ai-output" id="newsNarrative">Loading...</div></div>';

    box.querySelectorAll('.pager button').forEach(button => {
      button.addEventListener('click', () => renderNews(Number(button.dataset.page)));
    });

    const narrative = await api('/api/stock/' + state.symbol + '/news/summary');
    document.getElementById('newsNarrative').textContent = narrative.text;

  } catch (error) {
    showError(box, error.message);
  }
}

/* ==========================================================================
   BULL / BEAR TAB - includes risks, catalysts, governance and the thesis
   ========================================================================== */

function casePoints(points) {
  return points.map(p =>
    '<div class="case-point">' +
      '<div class="pt">' + esc(p.point) +
        '<span class="badge badge-neutral">' + esc(p.strength) + ' evidence</span></div>' +
      '<div class="ev">' + esc(p.evidence) + '</div>' +
    '</div>'
  ).join('');
}

async function renderBullBear() {
  const box = document.getElementById('bullBearBox');
  try {
    const analysis = await getAnalysis();
    const bull = analysis.bull_case || {};
    const bear = analysis.bear_case || {};
    const risks = analysis.risks || {};
    const catalysts = analysis.catalysts || {};
    const entries = analysis.entry_scenarios || {};
    const thesis = analysis.thesis || {};
    const governance = analysis.governance || {};

    const riskGroups = ['High', 'Medium', 'Lower'].map(level => {
      const list = (risks.risks || []).filter(r => r.level === level);
      if (!list.length) return '';
      return '<h4 style="margin-top:16px">' + level + ' risk</h4>' +
        list.map(r =>
          '<div class="risk-item ' + level + '">' +
            '<div class="risk-rank">' + r.rank + '</div>' +
            '<div><strong>' + esc(r.title) + '</strong>' +
              '<div class="small muted">' + esc(r.explanation) + '</div></div>' +
          '</div>').join('');
    }).join('');

    box.innerHTML =
      '<div class="grid grid-2">' +
        '<div class="card">' +
          '<div class="card-head"><h2>Bull case</h2>' +
            '<span class="badge badge-up">Bull score ' + bull.bull_score + '/10</span></div>' +
          casePoints(bull.points || []) +
          '<p class="tiny muted" style="margin-top:12px">' + esc(bull.methodology) + '</p>' +
        '</div>' +
        '<div class="card">' +
          '<div class="card-head"><h2>Bear case</h2>' +
            '<span class="badge badge-down">Risk score ' + bear.risk_score + '/10</span></div>' +
          casePoints(bear.points || []) +
          '<p class="tiny muted" style="margin-top:12px">' + esc(bear.methodology) + '</p>' +
        '</div>' +
      '</div>' +

      '<div class="card"><h2>Ranked risks</h2>' + riskGroups + '</div>' +

      '<div class="card"><h2>Possible catalysts</h2>' +
        '<div class="table-wrap"><table class="data"><thead><tr>' +
          '<th>Catalyst</th><th>What could happen</th><th>Why it matters</th>' +
          '<th>Impact</th></tr></thead><tbody>' +
          (catalysts.catalysts || []).map(c =>
            '<tr><td style="white-space:normal"><strong>' + esc(c.catalyst) + '</strong></td>' +
            '<td style="white-space:normal">' + esc(c.what_could_happen) + '</td>' +
            '<td style="white-space:normal">' + esc(c.why_it_matters) + '</td>' +
            '<td>' + esc(c.potential_impact) + '</td></tr>').join('') +
        '</tbody></table></div></div>' +

      '<div class="grid grid-3">' +
        '<div class="card"><h3>When could it become attractive?</h3>' +
          '<ul class="reason-list">' +
            (entries.attractive_if || []).map(x => '<li>' + esc(x) + '</li>').join('') +
          '</ul></div>' +
        '<div class="card"><h3>When to wait</h3>' +
          '<ul class="reason-list">' +
            (entries.wait_if || []).map(x => '<li>' + esc(x) + '</li>').join('') +
          '</ul></div>' +
        '<div class="card"><h3>When to be cautious</h3>' +
          '<ul class="reason-list">' +
            (entries.avoid_if || []).map(x => '<li>' + esc(x) + '</li>').join('') +
          '</ul></div>' +
      '</div>' +
      '<div class="notice notice-warn" style="margin-top:14px">' +
        esc(entries.disclaimer || '') + '</div>' +

      '<div class="card"><h2>Investment thesis</h2>' +
        '<div class="card-head"><span class="verdict ' + verdictClass(thesis.overall_view) +
          '">' + esc(thesis.overall_view || '') + '</span>' +
          '<span class="tiny muted">' + esc(thesis.view_method || '') + '</span></div>' +
        '<div class="grid grid-2">' +
          '<div><h4>Why investors may like it</h4><ul class="reason-list">' +
            (thesis.why_investors_may_like || []).map(x => '<li>' + esc(x) + '</li>').join('') +
          '</ul></div>' +
          '<div><h4>Why investors may avoid it</h4><ul class="reason-list">' +
            (thesis.why_investors_may_avoid || []).map(x => '<li>' + esc(x) + '</li>').join('') +
          '</ul></div>' +
          '<div><h4>What must go right</h4><ul class="reason-list">' +
            (thesis.what_must_go_right || []).map(x => '<li>' + esc(x) + '</li>').join('') +
          '</ul></div>' +
          '<div><h4>What would prove it wrong</h4><ul class="reason-list">' +
            (thesis.what_would_prove_it_wrong || []).map(x => '<li>' + esc(x) + '</li>').join('') +
          '</ul></div>' +
        '</div></div>' +

      '<div class="card"><h2>Management and governance</h2>' +
        ((governance.notes || []).length
          ? (governance.notes || []).map(n =>
              '<div style="padding:10px 0;border-bottom:1px solid var(--border)">' +
                '<strong>' + esc(n.topic) + '</strong>' +
                '<div class="small">' + esc(n.observation) + '</div>' +
                '<div class="tiny muted">Verify in: ' + esc(n.how_to_verify) + '</div>' +
              '</div>').join('')
          : '<p class="small muted">No governance observations could be made from the ' +
            'available data.</p>') +
        '<h4 style="margin-top:16px">Not covered by this app</h4>' +
        '<ul class="small muted">' +
          (governance.not_covered || []).map(x => '<li>' + esc(x) + '</li>').join('') + '</ul>' +
        '<p class="tiny muted">' + esc(governance.not_covered_note || '') + '</p>' +
        '<div class="notice" style="margin-top:12px;font-size:.82rem">' +
          esc(governance.disclaimer || '') + '</div>' +
      '</div>';

  } catch (error) {
    showError(box, error.message);
  }
}

/* ==========================================================================
   PEERS TAB
   ========================================================================== */

/** Rows for the peer table: [label, key, decimals, higherIsBetter] */
const PEER_METRICS = [
  ['Price (Rs)', 'price', 2, null],
  ['Market cap (Rs cr)', 'market_cap_cr', 0, null],
  ['Revenue growth YoY %', 'revenue_growth_pct', 2, true],
  ['Profit growth YoY %', 'profit_growth_pct', 2, true],
  ['Revenue CAGR 3Y %', 'revenue_cagr_3y_pct', 2, true],
  ['EBITDA margin %', 'ebitda_margin_pct', 2, true],
  ['PAT margin %', 'pat_margin_pct', 2, true],
  ['ROE %', 'roe_pct', 2, true],
  ['ROCE %', 'roce_pct', 2, true],
  ['Debt / equity', 'debt_to_equity', 2, false],
  ['P/E', 'pe_ratio', 2, false],
  ['P/B', 'pb_ratio', 2, false],
  ['EV / EBITDA', 'ev_ebitda', 2, false],
  ['Dividend yield %', 'dividend_yield_pct', 2, true]
];

/** Build the comparison table. `highlight` marks the best value per row. */
function buildComparisonTable(rows, highlight) {
  const header = '<tr><th>Metric</th>' + rows.map(r =>
    '<th class="num"><a href="/stock/' + esc(r.symbol) + '">' + esc(r.symbol) + '</a></th>'
  ).join('') + '</tr>';

  const body = PEER_METRICS.map(metric => {
    const label = metric[0], key = metric[1], decimals = metric[2], higherBetter = metric[3];

    // Find the best value in this row so it can be highlighted.
    let bestSymbol = null;
    if (highlight && higherBetter !== null) {
      const values = rows
        .filter(r => r[key] !== null && r[key] !== undefined && !r.error)
        .map(r => ({ symbol: r.symbol, value: Number(r[key]) }));
      if (values.length > 1) {
        values.sort((a, b) => higherBetter ? b.value - a.value : a.value - b.value);
        bestSymbol = values[0].symbol;
      }
    }

    return '<tr><td class="metric-name">' + esc(label) + '</td>' +
      rows.map(r => {
        const value = r[key];
        const isBest = bestSymbol && r.symbol === bestSymbol;
        return '<td class="num' + (isBest ? ' best' : '') + '">' +
          (value === null || value === undefined ? '&mdash;' : formatINR(value, decimals)) +
        '</td>';
      }).join('') + '</tr>';
  }).join('');

  const extraRows =
    '<tr><td class="metric-name">Valuation view</td>' +
      rows.map(r => '<td>' + esc(r.valuation_label || 'N/A') + '</td>').join('') + '</tr>' +
    '<tr><td class="metric-name">Technical view</td>' +
      rows.map(r => '<td>' + esc(r.technical_view || 'N/A') + '</td>').join('') + '</tr>';

  return '<div class="table-wrap"><table class="data compare"><thead>' + header +
         '</thead><tbody>' + body + extraRows + '</tbody></table></div>';
}

/** A plain-English read of which peer leads on what. Computed, not AI. */
function peerCommentary(rows) {
  const valid = rows.filter(r => !r.error);
  if (valid.length < 2) return '';

  const best = (key, higherBetter) => {
    const values = valid.filter(r => r[key] !== null && r[key] !== undefined);
    if (!values.length) return null;
    values.sort((a, b) => higherBetter ? b[key] - a[key] : a[key] - b[key]);
    return values[0];
  };

  const lines = [];
  const growth = best('revenue_cagr_3y_pct', true);
  if (growth) lines.push('<li><strong>Fastest growing:</strong> ' + esc(growth.symbol) +
    ', with a 3-year revenue CAGR of ' + formatNum(growth.revenue_cagr_3y_pct) + '%.</li>');

  const profitable = best('roce_pct', true);
  if (profitable) lines.push('<li><strong>Most profitable on capital:</strong> ' +
    esc(profitable.symbol) + ', with ROCE of ' + formatNum(profitable.roce_pct) + '%.</li>');

  const strongest = best('debt_to_equity', false);
  if (strongest) lines.push('<li><strong>Strongest balance sheet:</strong> ' +
    esc(strongest.symbol) + ', with debt/equity of ' + formatNum(strongest.debt_to_equity) + '.</li>');

  const cheapest = best('pe_ratio', false);
  if (cheapest) lines.push('<li><strong>Cheapest on P/E:</strong> ' + esc(cheapest.symbol) +
    ' at ' + formatNum(cheapest.pe_ratio) + '. A low P/E is not automatically a bargain - ' +
    'it often reflects lower expected growth or higher risk.</li>');

  const momentum = valid.filter(r => r.technical_view === 'BULLISH');
  lines.push('<li><strong>Best technical momentum:</strong> ' +
    (momentum.length ? momentum.map(r => esc(r.symbol)).join(', ') +
      ' (price above the key moving averages)' : 'none of these currently reads bullish') +
    '.</li>');

  return '<div class="card"><h2>Peer analysis</h2><ul class="reason-list">' + lines.join('') +
    '</ul><div class="notice notice-warn" style="margin-top:12px;font-size:.82rem">' +
    'These comparisons rank the metrics we could compute. The best risk/reward depends on ' +
    'your own time horizon and what you believe about each business - the table cannot ' +
    'settle that for you.</div></div>';
}

async function renderPeers() {
  const box = document.getElementById('peersBox');
  try {
    const analysis = await getAnalysis();
    const peers = analysis.peers || [];

    if (!peers.length) {
      showError(box, 'No peer companies are listed for this industry.', 'warn');
      return;
    }

    const symbols = [state.symbol].concat(peers).slice(0, 5);
    const data = await api('/api/compare?stocks=' + encodeURIComponent(symbols.join(',')));
    const rows = (data.rows || []).filter(r => !r.error);

    if (rows.length < 2) {
      showError(box, 'We could not load enough peer data to compare.', 'warn');
      return;
    }

    box.innerHTML =
      '<div class="card"><div class="card-head"><h2>Peer comparison</h2>' +
        '<a class="btn btn-outline btn-sm" href="/compare?stocks=' +
          encodeURIComponent(symbols.join(',')) + '">Open in Compare</a></div>' +
        '<p class="small muted">Best value in each row is highlighted. Peers are companies ' +
          'in the same industry from our reference list.</p>' +
        buildComparisonTable(rows, true) +
      '</div>' +
      peerCommentary(rows);

  } catch (error) {
    showError(box, error.message);
  }
}

/* ==========================================================================
   AI ANALYST TAB
   ========================================================================== */

function appendChat(role, text, meta) {
  const chatWindow = document.getElementById('chatWindow');
  const div = document.createElement('div');
  div.className = 'chat-message ' + role;
  div.innerHTML =
    (role === 'assistant'
      ? '<div class="who">StockIQ' + (meta ? ' &middot; ' + esc(meta) : '') + '</div>' : '') +
    '<p>' + esc(text) + '</p>';
  chatWindow.appendChild(div);
  chatWindow.scrollTop = chatWindow.scrollHeight;
  return div;
}

async function askAI(question) {
  if (!question.trim()) return;

  appendChat('user', question);
  state.chatHistory.push({ role: 'user', content: question });

  const thinking = appendChat('assistant', 'Thinking...');
  const sendButton = document.getElementById('chatSend');
  sendButton.disabled = true;

  try {
    const result = await api('/api/ai/chat', {
      method: 'POST',
      body: { symbol: state.symbol, question: question, history: state.chatHistory.slice(-6) }
    });
    thinking.innerHTML =
      '<div class="who">StockIQ &middot; ' + esc(result.generated_by) + '</div>' +
      '<p>' + esc(result.answer) + '</p>';
    state.chatHistory.push({ role: 'assistant', content: result.answer });
  } catch (error) {
    thinking.innerHTML = '<div class="who">StockIQ</div><p>' + esc(error.message) + '</p>';
  } finally {
    sendButton.disabled = false;
  }
}

async function loadAiSection(section, button) {
  const output = document.getElementById('aiSectionOutput');
  document.querySelectorAll('#aiSections button').forEach(b => b.classList.remove('active'));
  if (button) button.classList.add('active');
  output.textContent = 'Generating...';

  try {
    const result = await api('/api/stock/' + state.symbol + '/ai/' + section);
    output.textContent = result.text;
  } catch (error) {
    output.textContent = error.message;
  }
}

function initAiTab() {
  const badge = document.getElementById('aiModeBadge');
  api('/api/status').then(status => {
    badge.className = 'badge ' + (status.ai_enabled ? 'badge-brand' : 'badge-warn');
    badge.textContent = status.ai_enabled
      ? 'AI: ' + status.ai_model
      : 'No AI key - using the rule-based writer';
  }).catch(() => { badge.textContent = ''; });

  document.getElementById('chatForm').addEventListener('submit', (event) => {
    event.preventDefault();
    const input = document.getElementById('chatInput');
    askAI(input.value);
    input.value = '';
  });

  document.querySelectorAll('#chatSuggestions button').forEach(button => {
    button.addEventListener('click', () => askAI(button.textContent));
  });

  document.querySelectorAll('#aiSections button').forEach(button => {
    button.addEventListener('click', () => loadAiSection(button.dataset.section, button));
  });
}

/* ==========================================================================
   WATCHLIST BUTTON
   ========================================================================== */

async function initWatchButton() {
  const button = document.getElementById('watchBtn');
  const star = document.getElementById('watchStar');
  const label = document.getElementById('watchLabel');
  let saved = false;

  function paint() {
    star.innerHTML = saved ? '&#9733;' : '&#9734;';   // filled or hollow star
    label.textContent = saved ? 'Saved' : 'Watchlist';
    button.classList.toggle('btn-primary', saved);
  }

  // A 401 here just means "not logged in", which is not an error worth showing.
  try {
    const result = await api('/api/watchlist/check/' + state.symbol);
    saved = result.in_watchlist;
    paint();
  } catch (error) { /* not logged in - leave the star hollow */ }

  button.addEventListener('click', async () => {
    try {
      if (saved) {
        await api('/api/watchlist/' + state.symbol, { method: 'DELETE' });
        saved = false;
      } else {
        await api('/api/watchlist', { method: 'POST', body: { symbol: state.symbol } });
        saved = true;
      }
      paint();
    } catch (error) {
      if (error.status === 401) {
        window.location.href = '/login?next=/stock/' + state.symbol;
      } else {
        alert(error.message);
      }
    }
  });
}

/* ==========================================================================
   TABS AND PAGE START-UP
   ========================================================================== */

/** Each tab knows how to render itself. Each runs only once, on first click. */
const TAB_RENDERERS = {
  fundamentals: renderFundamentals,
  financials: renderFinancials,
  technicals: renderTechnicals,
  valuation: renderValuation,
  earnings: renderEarnings,
  news: renderNews,
  bullbear: renderBullBear,
  peers: renderPeers,
  ai: initAiTab
};

function switchTab(name) {
  document.querySelectorAll('.tab').forEach(tab =>
    tab.classList.toggle('active', tab.dataset.tab === name));
  document.querySelectorAll('.tab-panel').forEach(panel =>
    panel.classList.toggle('active', panel.id === 'panel-' + name));

  // Lazy loading: render a tab the first time it is opened, then never again.
  if (!state.loadedTabs[name] && TAB_RENDERERS[name]) {
    state.loadedTabs[name] = true;
    TAB_RENDERERS[name]();
  }

  // Keep the tab in the URL so the page can be shared or reloaded in place.
  history.replaceState(null, '', '#' + name);
}

document.addEventListener('DOMContentLoaded', async () => {
  const root = document.getElementById('stockRoot');
  if (!root) return;                       // the "not found" version of the page
  state.symbol = root.dataset.symbol;

  document.querySelectorAll('.tab').forEach(tab =>
    tab.addEventListener('click', () => switchTab(tab.dataset.tab)));

  document.querySelectorAll('#periodButtons button').forEach(button => {
    button.addEventListener('click', () => {
      document.querySelectorAll('#periodButtons button')
              .forEach(b => b.classList.remove('active'));
      button.classList.add('active');
      loadChart(button.dataset.period);
    });
  });

  document.querySelectorAll('#maToggles input').forEach(input => {
    input.addEventListener('change', () => {
      if (state.history) drawPriceChart('priceChart', state.history.candles, selectedMAs());
    });
  });

  document.getElementById('beginnerToggle')
    .addEventListener('click', () => BeginnerMode.set(!BeginnerMode.isOn()));

  await initWatchButton();
  loadHeader();
  loadChart('1Y');

  // Every overview panel comes from the single analysis call.
  try {
    const analysis = await getAnalysis();
    renderScoreBox(analysis);
    renderProfile(analysis);
    renderBusiness(analysis);
    renderShareholding(analysis);
    renderSummary();
  } catch (error) {
    showError(document.getElementById('scoreBox'), error.message);
  }

  // Honour a #tab in the URL, so links to a specific tab work.
  const requested = window.location.hash.replace('#', '');
  if (requested && document.getElementById('panel-' + requested)) switchTab(requested);
});
