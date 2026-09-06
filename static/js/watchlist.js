/* ==========================================================================
   static/js/watchlist.js
   ==========================================================================
   The /watchlist page: list, add, remove and sort saved stocks.
   ========================================================================== */

const watchState = {
  items: [],
  sort: 'added',
  full: false     // true once the slower score columns have been loaded
};

/** Sort the saved rows according to the dropdown. */
function sortItems(items) {
  const copy = items.slice();
  if (watchState.sort === 'name') {
    copy.sort((a, b) => String(a.company_name || a.symbol)
                        .localeCompare(String(b.company_name || b.symbol)));
  } else if (watchState.sort === 'change') {
    copy.sort((a, b) => (b.change_pct ?? -999) - (a.change_pct ?? -999));
  } else if (watchState.sort === 'score') {
    copy.sort((a, b) => (b.score ?? -1) - (a.score ?? -1));
  }
  // "added" is the order the API already returns (newest first).
  return copy;
}

function renderWatchlist() {
  const box = document.getElementById('watchlistBox');
  if (!box) return;

  if (!watchState.items.length) {
    box.innerHTML = '<div class="empty"><p>Your watchlist is empty.</p>' +
      '<p class="small">Search for a company above, or open any stock page and press the ' +
      'star button.</p></div>';
    return;
  }

  const header =
    '<div class="watch-row watch-head">' +
      '<div>Company</div><div class="right">Price</div><div class="right">Change</div>' +
      '<div class="right">Score</div><div class="right">Views</div><div></div>' +
    '</div>';

  const rows = sortItems(watchState.items).map(item => {
    const views = watchState.full
      ? esc(item.fundamental_view || '-') + ' / ' + esc(item.technical_view || '-')
      : '<span class="tiny muted">Load scores</span>';

    return '<div class="watch-row">' +
      '<div>' +
        '<a class="co-name" href="/stock/' + esc(item.symbol) + '">' +
          esc(item.company_name || item.symbol) + '</a>' +
        '<div class="co-sym">' + esc(item.symbol) +
          (item.sector ? ' &middot; ' + esc(item.sector) : '') +
          (item.is_demo ? ' <span class="badge badge-demo">Demo</span>' : '') + '</div>' +
        (item.error ? '<div class="tiny down">' + esc(item.error) + '</div>' : '') +
      '</div>' +
      '<div class="right num">' + (item.price ? 'Rs ' + formatINR(item.price) : '&mdash;') + '</div>' +
      '<div class="right num ' + changeClass(item.change_pct) + '">' +
        (item.change_pct === null || item.change_pct === undefined
          ? '&mdash;' : formatPct(item.change_pct)) + '</div>' +
      '<div class="right num">' + (item.score === undefined || item.score === null
        ? '&mdash;' : item.score + '/10') + '</div>' +
      '<div class="right tiny">' + views + '</div>' +
      '<div class="right"><button class="btn btn-ghost btn-sm" data-remove="' +
        esc(item.symbol) + '" title="Remove">&times;</button></div>' +
    '</div>';
  }).join('');

  box.innerHTML = header + rows +
    '<p class="tiny muted" style="margin-top:14px">Prices are cached for a short period, ' +
    'so they may lag the live market by up to a minute.</p>';

  box.querySelectorAll('[data-remove]').forEach(button => {
    button.addEventListener('click', () => removeStock(button.dataset.remove));
  });
}

async function loadWatchlist(full) {
  const box = document.getElementById('watchlistBox');
  if (!box) return;

  showLoading(box, full ? 'Loading scores (this takes a moment)...' : 'Loading your watchlist...');
  try {
    const data = await api('/api/watchlist' + (full ? '?full=1' : ''));
    watchState.items = data.items || [];
    watchState.full = !!full;
    renderWatchlist();
  } catch (error) {
    if (error.status === 401) {
      box.innerHTML = '<div class="notice">Please <a href="/login">log in</a> to see ' +
                      'your watchlist.</div>';
    } else {
      showError(box, error.message);
    }
  }
}

async function addStock(symbol) {
  try {
    await api('/api/watchlist', { method: 'POST', body: { symbol } });
    loadWatchlist(watchState.full);
  } catch (error) {
    alert(error.message);
  }
}

async function removeStock(symbol) {
  try {
    await api('/api/watchlist/' + encodeURIComponent(symbol), { method: 'DELETE' });
    watchState.items = watchState.items.filter(item => item.symbol !== symbol);
    renderWatchlist();
  } catch (error) {
    alert(error.message);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  if (!document.getElementById('watchlistBox')) return;   // not logged in

  initSearch('watchSearch', 'watchSearchResults');

  // Clicking a suggestion adds the stock instead of navigating to it.
  const results = document.getElementById('watchSearchResults');
  results.addEventListener('click', (event) => {
    const link = event.target.closest('.search-item');
    if (!link) return;
    event.preventDefault();
    addStock(link.getAttribute('href').replace('/stock/', ''));
    document.getElementById('watchSearch').value = '';
    results.hidden = true;
  });

  document.getElementById('watchSort').addEventListener('change', (event) => {
    watchState.sort = event.target.value;
    renderWatchlist();
  });

  document.getElementById('watchFull').addEventListener('click', () => loadWatchlist(true));

  loadWatchlist(false);
});
