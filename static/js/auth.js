/* ==========================================================================
   static/js/auth.js
   ==========================================================================
   Login, registration and profile.

   The password is sent once over the POST body and never stored in the
   browser. Flask hashes it and returns only a signed session cookie.
   ========================================================================== */

/** Show a success or error message above a form. */
function authMessage(text, kind = 'error') {
  const box = document.getElementById('authMessage');
  if (!box) return;
  box.innerHTML = '<div class="notice notice-' + kind + '" style="margin-bottom:14px">' +
                  esc(text) + '</div>';
}

/** Where to go after a successful login. `?next=` lets the star button send
    the user back to the stock page they came from. */
function nextUrl() {
  const next = new URLSearchParams(window.location.search).get('next');
  // Only allow same-site paths, so ?next=https://evil.example cannot redirect away.
  return (next && next.startsWith('/') && !next.startsWith('//')) ? next : '/watchlist';
}

function initLoginForm() {
  const form = document.getElementById('loginForm');
  if (!form) return;

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = document.getElementById('loginSubmit');
    button.disabled = true;
    button.textContent = 'Logging in...';

    try {
      await api('/api/auth/login', {
        method: 'POST',
        body: {
          username: document.getElementById('username').value,
          password: document.getElementById('password').value
        }
      });
      window.location.href = nextUrl();
    } catch (error) {
      authMessage(error.message);
      button.disabled = false;
      button.textContent = 'Log in';
    }
  });
}

function initRegisterForm() {
  const form = document.getElementById('registerForm');
  if (!form) return;

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = document.getElementById('registerSubmit');
    button.disabled = true;
    button.textContent = 'Creating account...';

    try {
      await api('/api/auth/register', {
        method: 'POST',
        body: {
          username: document.getElementById('username').value,
          email: document.getElementById('email').value,
          password: document.getElementById('password').value
        }
      });
      window.location.href = nextUrl();
    } catch (error) {
      // The backend returns a list of problems for validation failures.
      const messages = (error.data && error.data.messages)
        ? error.data.messages.join(' ') : error.message;
      authMessage(messages);
      button.disabled = false;
      button.textContent = 'Create account';
    }
  });
}

async function initProfile() {
  const box = document.getElementById('profileBox');
  if (!box) return;

  try {
    const data = await api('/api/auth/profile');
    box.innerHTML =
      '<div class="metrics">' +
        '<div class="metric"><div class="label">Username</div>' +
          '<div class="value" style="font-size:1rem">' + esc(data.user.username) + '</div></div>' +
        '<div class="metric"><div class="label">Email</div>' +
          '<div class="value" style="font-size:.95rem">' + esc(data.user.email) + '</div></div>' +
        '<div class="metric"><div class="label">Member since</div>' +
          '<div class="value" style="font-size:.95rem">' +
            esc(formatTimestamp(data.user.created_at)) + '</div></div>' +
        '<div class="metric"><div class="label">Stocks watched</div>' +
          '<div class="value">' + data.watchlist_count + '</div></div>' +
      '</div>' +
      '<p style="margin-top:14px"><a class="btn btn-outline btn-sm" href="/watchlist">' +
        'Open my watchlist</a></p>';
  } catch (error) {
    showError(box, error.message);
  }
}

function initPasswordForm() {
  const form = document.getElementById('passwordForm');
  if (!form) return;

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const box = document.getElementById('passwordMessage');

    try {
      const result = await api('/api/auth/change-password', {
        method: 'POST',
        body: {
          current_password: document.getElementById('current_password').value,
          new_password: document.getElementById('new_password').value
        }
      });
      box.innerHTML = '<div class="notice" style="margin-bottom:14px">' +
                      esc(result.message) + '</div>';
      form.reset();
    } catch (error) {
      const messages = (error.data && error.data.messages)
        ? error.data.messages.join(' ') : error.message;
      box.innerHTML = '<div class="notice notice-error" style="margin-bottom:14px">' +
                      esc(messages) + '</div>';
    }
  });
}

document.addEventListener('DOMContentLoaded', () => {
  initLoginForm();
  initRegisterForm();
  initProfile();
  initPasswordForm();
});
