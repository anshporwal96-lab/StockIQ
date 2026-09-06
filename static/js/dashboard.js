/* ==========================================================================
   static/js/dashboard.js
   ==========================================================================
   Powers the homepage and the /markets page: the hero search box and the
   market-overview panels.
   ========================================================================== */

/** Build one NIFTY / SENSEX card. */
function renderIndexCard(index) {
  const direction = changeClass(index.change_pct);
  return '' +
    '<div class="card index-card">' +
      '<div>' +
        '<div class="index-name">' + esc(index.name) + '</div>' +
        '<div class="index-value">' + formatINR(index.value) + '</div>' +
      '</div>' +
      '<div class="right">' +
        '<div class="index-change ' + direction + '">' +
          (index.change > 0 ? '+' : '') + formatINR(index.change) +
        '</div>' +
        '<div class="index-change ' + direction + '">' + formatPct(index.change_pct) + '</div>' +
      '</div>' +
    '</div>';
}

/** Build a gainers / losers / most-active list. */
function renderMovers(list) {
  if (!list || list.length === 0) {
    return '<p class="small muted">Not available from the current data provider. ' +
           'We show nothing rather than inventing a list.</p>';
  }
  return '<ul class="mover-list">' + list.map(row =>
    '<li>' +
      '<div>' +
        '<a class="sym" href="/stock/' + esc(row.symbol) + '">' + esc(row.symbol) + '</a>' +
        '<span class="co">' + esc(row.company_name) + '</span>' +
      '</div>' +
      '<div class="right">' +
        '<div class="num small">' + formatINR(row.price) + '</div>' +
        '<div class="pct ' + changeClass(row.change_pct) + '">' +
          formatPct(row.change_pct) + '</div>' +
      '</div>' +
    '</li>'
  ).join('') + '</ul>';
}

/** Load /api/market and fill in every panel on the page. */
async function loadMarketOverview() {
  const indicesEl = document.getElementById('indices');
  const timestampEl = document.getElementById('marketTimestamp');

  try {
    const data = await api('/api/market');

    if (indicesEl) {
      indicesEl.innerHTML = (data.indices && data.indices.length)
        ? data.indices.map(renderIndexCard).join('')
        : '<div class="card"><p class="muted small">Index levels are not available from ' +
          'the current data provider.</p></div>';
    }

    const panels = [
      ['topGainers', data.top_gainers],
      ['topLosers', data.top_losers],
      ['mostActive', data.most_active]
    ];
    panels.forEach(([id, list]) => {
      const element = document.getElementById(id);
      if (element) element.innerHTML = renderMovers(list);
    });

    // Requirement 38 and 46: always show WHEN the data is from and WHERE it came from.
    if (timestampEl) {
      timestampEl.textContent = 'Data updated: ' + formatTimestamp(data.as_of);
    }
    const sourceEl = document.getElementById('marketSource');
    if (sourceEl) {
      let note = 'Source: ' + esc(data.source || 'unknown');
      if (data.sentiment_note) note += ' &middot; ' + esc(data.sentiment_note);
      sourceEl.innerHTML = note;
    }

    // Market sentiment is only shown when the provider actually supplies it.
    const sentimentEl = document.getElementById('marketSentiment');
    if (sentimentEl) {
      sentimentEl.innerHTML = data.sentiment
        ? '<span class="badge badge-brand">' + esc(data.sentiment) + '</span>'
        : '<span class="muted small">' + esc(data.sentiment_note || 'Not available') + '</span>';
    }

  } catch (error) {
    if (indicesEl) {
      showError(indicesEl,
        'We could not retrieve the latest market data. ' + error.message);
    }
    if (timestampEl) timestampEl.textContent = '';
    ['topGainers', 'topLosers', 'mostActive'].forEach(id => {
      const element = document.getElementById(id);
      if (element) element.innerHTML = '<p class="small muted">Unavailable.</p>';
    });
  }
}

/* ---------- Page start-up ------------------------------------------------ */

document.addEventListener('DOMContentLoaded', () => {
  // The hero search box behaves exactly like the one in the header.
  initSearch('heroSearch', 'heroSearchResults');

  const heroButton = document.getElementById('heroSearchBtn');
  const heroInput = document.getElementById('heroSearch');
  if (heroButton && heroInput) {
    heroButton.addEventListener('click', () => {
      const value = heroInput.value.trim();
      if (value) window.location.href = '/stock/' + encodeURIComponent(value.toUpperCase());
    });
  }

  if (document.getElementById('indices')) loadMarketOverview();
});
