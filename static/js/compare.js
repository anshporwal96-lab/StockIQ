/* ==========================================================================
   static/js/compare.js
   ==========================================================================
   The /compare page.

   NOTE ON THE STOCK.JS IMPORT
   ---------------------------
   compare.html also loads stock.js, purely to reuse `buildComparisonTable`,
   `PEER_METRICS` and `peerCommentary` - the same table the Peers tab draws.
   Duplicating that logic here would mean fixing every bug twice. stock.js
   safely does nothing on this page because its start-up code returns early
   when there is no #stockRoot element.
   ========================================================================== */

const compareState = {
  symbols: []
};

/** Draw the little removable chips for each selected company. */
function renderChips() {
  const container = document.getElementById('compareChips');
  container.innerHTML = compareState.symbols.map(symbol =>
    '<span class="chip">' + esc(symbol) +
      '<button data-symbol="' + esc(symbol) + '" aria-label="Remove ' + esc(symbol) +
      '">&times;</button></span>'
  ).join('');

  container.querySelectorAll('button').forEach(button => {
    button.addEventListener('click', () => {
      compareState.symbols = compareState.symbols.filter(s => s !== button.dataset.symbol);
      renderChips();
      updateHint();
    });
  });
}

function updateHint() {
  const hint = document.getElementById('compareHint');
  const count = compareState.symbols.length;
  if (count === 0) hint.textContent = 'Add at least two companies to compare.';
  else if (count === 1) hint.textContent = 'Add at least one more company.';
  else if (count >= 5) hint.textContent = 'Five is the maximum. Remove one to add another.';
  else hint.textContent = count + ' selected. Press Compare, or add up to ' +
                          (5 - count) + ' more.';
}

function addSymbol(symbol) {
  symbol = String(symbol || '').toUpperCase().trim();
  if (!symbol) return;
  if (compareState.symbols.includes(symbol)) return;
  if (compareState.symbols.length >= 5) {
    alert('You can compare at most five stocks at a time.');
    return;
  }
  compareState.symbols.push(symbol);
  renderChips();
  updateHint();
}

/** Fetch the comparison and draw the table plus the written commentary. */
async function runComparison() {
  const output = document.getElementById('compareOutput');

  if (compareState.symbols.length < 2) {
    showError(output, 'Please add at least two companies before comparing.', 'warn');
    return;
  }

  showLoading(output, 'Loading and comparing ' + compareState.symbols.length + ' companies...');

  // Keep the selection in the URL so the comparison can be bookmarked or shared.
  const query = compareState.symbols.join(',');
  history.replaceState(null, '', '/compare?stocks=' + encodeURIComponent(query));

  try {
    const data = await api('/api/compare?stocks=' + encodeURIComponent(query));
    const rows = data.rows || [];
    const good = rows.filter(r => !r.error);
    const failed = rows.filter(r => r.error);

    if (good.length < 2) {
      showError(output, 'We could not load enough data to compare these companies.', 'warn');
      return;
    }

    const failures = failed.length
      ? '<div class="notice notice-warn" style="margin-bottom:14px">Could not load: ' +
        failed.map(r => esc(r.symbol) + ' (' + esc(r.error) + ')').join('; ') + '</div>'
      : '';

    output.innerHTML =
      '<div class="card">' + failures +
        '<div class="card-head"><h2>Comparison</h2>' +
        '<span class="small muted">Best value in each row is highlighted where higher or ' +
        'lower is clearly better.</span></div>' +
        buildComparisonTable(good, true) +
      '</div>' +
      peerCommentary(good);

  } catch (error) {
    showError(output, error.message);
  }
}

/* ---------- Page start-up ------------------------------------------------ */

document.addEventListener('DOMContentLoaded', () => {
  // The search dropdown adds a chip instead of navigating away.
  initSearch('compareSearch', 'compareSearchResults');

  const results = document.getElementById('compareSearchResults');
  results.addEventListener('click', (event) => {
    const link = event.target.closest('.search-item');
    if (!link) return;
    event.preventDefault();
    addSymbol(link.getAttribute('href').replace('/stock/', ''));
    document.getElementById('compareSearch').value = '';
    results.hidden = true;
  });

  document.getElementById('compareRun').addEventListener('click', runComparison);
  document.getElementById('compareClear').addEventListener('click', () => {
    compareState.symbols = [];
    renderChips();
    updateHint();
    document.getElementById('compareOutput').innerHTML = '';
  });

  // ?stocks=TCS,INFY in the URL pre-fills and runs the comparison.
  const preset = new URLSearchParams(window.location.search).get('stocks');
  if (preset) {
    preset.split(',').forEach(addSymbol);
    if (compareState.symbols.length >= 2) runComparison();
  }
  renderChips();
  updateHint();
});
