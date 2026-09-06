/* ==========================================================================
   static/js/main.js
   ==========================================================================
   Shared JavaScript for every page: the API helper, search, theme switching,
   the mobile menu, and number formatting.

   HOW THE FRONTEND TALKS TO FLASK
   -------------------------------
   The browser never contacts a stock API or the AI directly. It calls our own
   Flask backend using fetch():

       fetch('/api/stock/TCS/price')  ->  Flask route  ->  service  ->  provider

   Flask holds the API keys. The browser only ever sees the finished JSON.
   ========================================================================== */

/* ---------- 1. API helper ------------------------------------------------ */

/** Read the CSRF token that base.html rendered into a <meta> tag. */
function csrfToken() {
  const tag = document.querySelector('meta[name="csrf-token"]');
  return tag ? tag.getAttribute('content') : '';
}

/**
 * Call our own backend and return the parsed JSON.
 *
 * Every network call in the app goes through here, so error handling and the
 * CSRF header are written once instead of in twenty places.
 */
async function api(path, options = {}) {
  const config = {
    method: options.method || 'GET',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin'   // send the login cookie
  };

  // State-changing requests must carry the CSRF token.
  if (config.method !== 'GET') {
    config.headers['X-CSRF-Token'] = csrfToken();
  }
  if (options.body) {
    config.body = JSON.stringify(options.body);
  }

  let response;
  try {
    response = await fetch(path, config);
  } catch (networkError) {
    // The server is unreachable (offline, server stopped, DNS failure).
    throw new ApiError('We could not reach the server. Check your connection and try again.', 0);
  }

  let data = null;
  try { data = await response.json(); } catch (e) { data = null; }

  if (!response.ok) {
    const message = (data && (data.message || data.error)) ||
                    'Something went wrong (HTTP ' + response.status + ').';
    throw new ApiError(message, response.status, data);
  }

  // Logging in and out rotates the CSRF token on the server (it clears the
  // session). When the backend sends a new one, store it so the next POST
  // still works without a page reload.
  if (data && data.csrf_token) {
    const tag = document.querySelector('meta[name="csrf-token"]');
    if (tag) tag.setAttribute('content', data.csrf_token);
  }

  return data;
}

/** A custom error type so callers can check `error.status`. */
class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

/* ---------- 2. Formatting helpers ---------------------------------------- */

/** Rupee amounts in the Indian style: 12,34,567 not 1,234,567. */
function formatINR(value, decimals = 2) {
  if (value === null || value === undefined || isNaN(value)) return 'N/A';
  return Number(value).toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });
}

/** Large rupee-crore figures as "1.24 Lakh Cr" / "8,450 Cr". */
function formatCrore(value) {
  if (value === null || value === undefined || isNaN(value)) return 'N/A';
  const n = Number(value);
  if (Math.abs(n) >= 100000) return (n / 100000).toFixed(2) + ' Lakh Cr';
  return formatINR(n, 0) + ' Cr';
}

/** A percentage with an explicit sign, e.g. "+2.41%". */
function formatPct(value, decimals = 2) {
  if (value === null || value === undefined || isNaN(value)) return 'N/A';
  const n = Number(value);
  return (n > 0 ? '+' : '') + n.toFixed(decimals) + '%';
}

/** Plain number, or the honest "N/A" when the backend sent null. */
function formatNum(value, decimals = 2) {
  if (value === null || value === undefined || isNaN(value)) return 'N/A';
  return Number(value).toFixed(decimals);
}

/** 'up' / 'down' / '' - used to colour a number green or red. */
function changeClass(value) {
  if (value === null || value === undefined || isNaN(value)) return '';
  return Number(value) > 0 ? 'up' : (Number(value) < 0 ? 'down' : '');
}

/** Turn an ISO timestamp into readable IST, or say it is unavailable. */
function formatTimestamp(iso) {
  if (!iso) return 'timestamp not provided by the data source';
  const date = new Date(iso);
  if (isNaN(date.getTime())) return String(iso);
  return date.toLocaleString('en-IN', {
    dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kolkata'
  }) + ' IST';
}

/** Escape text before putting it in innerHTML, so data can never inject markup. */
function esc(text) {
  const div = document.createElement('div');
  div.textContent = text === null || text === undefined ? '' : String(text);
  return div.innerHTML;
}

/** Show a message in a container. Used for every error state in the app. */
function showError(container, message, kind = 'error') {
  if (!container) return;
  container.innerHTML = '<div class="notice notice-' + kind + '">' + esc(message) + '</div>';
}

function showLoading(container, text = 'Loading...') {
  if (container) container.innerHTML = '<div class="loading">' + esc(text) + '</div>';
}

/* ---------- 3. Theme (light / dark) -------------------------------------- */

function initTheme() {
  const toggle = document.getElementById('themeToggle');
  if (!toggle) return;

  toggle.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    // Remember the choice on this device only. localStorage can throw in
    // private-browsing modes, so it is wrapped.
    try { localStorage.setItem('stockiq-theme', next); } catch (e) {}
    // Charts have their own colours, so tell them to redraw.
    document.dispatchEvent(new CustomEvent('themechange', { detail: { theme: next } }));
  });
}

/* ---------- 4. Mobile menu ----------------------------------------------- */

function initNav() {
  const toggle = document.getElementById('navToggle');
  const nav = document.getElementById('siteNav');
  if (!toggle || !nav) return;

  toggle.addEventListener('click', () => {
    const open = nav.classList.toggle('open');
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  });
}

/* ---------- 5. Search with suggestions ----------------------------------- */

/**
 * Wire up a search box so typing shows live suggestions.
 *
 * `debounce` matters here: without it, typing "RELIANCE" would fire eight
 * separate requests. We wait 220 ms after the last keystroke instead.
 */
function initSearch(inputId, resultsId) {
  const input = document.getElementById(inputId);
  const results = document.getElementById(resultsId);
  if (!input || !results) return;

  let timer = null;
  let activeIndex = -1;

  async function runSearch(query) {
    if (query.trim().length < 1) {
      results.hidden = true;
      return;
    }
    try {
      const data = await api('/api/search?q=' + encodeURIComponent(query));
      renderResults(data);
    } catch (error) {
      results.innerHTML = '<div class="search-empty">' + esc(error.message) + '</div>';
      results.hidden = false;
    }
  }

  function renderResults(data) {
    activeIndex = -1;
    if (!data.results || data.results.length === 0) {
      results.innerHTML = '<div class="search-empty">' +
        esc(data.message || 'No matching company found.') + '</div>';
      results.hidden = false;
      return;
    }
    results.innerHTML = data.results.map(row =>
      '<a class="search-item" href="/stock/' + esc(row.symbol) + '">' +
        '<div class="name">' + esc(row.company_name) + '</div>' +
        '<div class="meta">NSE: ' + esc(row.nse_symbol) +
          ' &nbsp;|&nbsp; BSE: ' + esc(row.bse_code) +
          ' &nbsp;|&nbsp; ' + esc(row.industry) + '</div>' +
      '</a>'
    ).join('');
    results.hidden = false;
  }

  input.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(() => runSearch(input.value), 220);
  });

  // Arrow keys and Enter, so the search is usable without a mouse.
  input.addEventListener('keydown', (event) => {
    const items = results.querySelectorAll('.search-item');
    if (event.key === 'ArrowDown' && items.length) {
      event.preventDefault();
      activeIndex = Math.min(activeIndex + 1, items.length - 1);
    } else if (event.key === 'ArrowUp' && items.length) {
      event.preventDefault();
      activeIndex = Math.max(activeIndex - 1, 0);
    } else if (event.key === 'Enter') {
      event.preventDefault();
      if (activeIndex >= 0 && items[activeIndex]) {
        window.location.href = items[activeIndex].getAttribute('href');
      } else if (input.value.trim()) {
        window.location.href = '/stock/' + encodeURIComponent(input.value.trim().toUpperCase());
      }
      return;
    } else if (event.key === 'Escape') {
      results.hidden = true;
      return;
    } else {
      return;
    }
    items.forEach((item, index) => item.classList.toggle('active', index === activeIndex));
  });

  // Clicking anywhere else closes the dropdown.
  document.addEventListener('click', (event) => {
    if (!input.contains(event.target) && !results.contains(event.target)) {
      results.hidden = true;
    }
  });
}

/* ---------- 6. Logout ---------------------------------------------------- */

function initLogout() {
  const button = document.getElementById('logoutBtn');
  if (!button) return;
  button.addEventListener('click', async () => {
    try {
      await api('/api/auth/logout', { method: 'POST' });
      window.location.href = '/';
    } catch (error) {
      alert(error.message);
    }
  });
}

/* ---------- 7. Beginner mode -------------------------------------------- */

/**
 * Beginner mode adds a plain-English explanation under financial terms.
 * The choice is remembered per device in localStorage.
 */
const BeginnerMode = {
  isOn() {
    try { return localStorage.getItem('stockiq-beginner') === 'on'; } catch (e) { return false; }
  },
  set(on) {
    try { localStorage.setItem('stockiq-beginner', on ? 'on' : 'off'); } catch (e) {}
    document.body.classList.toggle('beginner-on', on);
    document.dispatchEvent(new CustomEvent('beginnermode', { detail: { on } }));
  },
  init() {
    document.body.classList.toggle('beginner-on', this.isOn());
  }
};

/* ---------- 8. Start everything on page load ----------------------------- */

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initNav();
  initSearch('navSearch', 'navSearchResults');
  initLogout();
  BeginnerMode.init();
});
