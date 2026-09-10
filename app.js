/**
 * QUOTA.HUB — Front-end Logic (Token Harbor Theme & Integration)
 * Gère l'authentification (Google/GitHub OAuth + Email), la gestion des clés,
 * l'affichage dynamique des modèles, l'activation des pass et le playground.
 */

const API = '/gw';
const APP_STATE = {
  session: sessionStorage.getItem('qh_session') || '',
  me: null,
  keys: [],
  currentTab: 'pricing',
  playKey: ''
};

const $ = id => document.getElementById(id);

// Formatage en Dollars d'usage ou en tokens
const fmtTokens = n => {
  if (n >= 1e9) return (n / 1e9).toFixed(2) + ' Md';
  if (n >= 1e6) return (n / 1e6).toFixed(1) + ' M';
  if (n >= 1e3) return (n / 1e3).toFixed(1) + ' k';
  return String(n);
};

// 1 Md tokens sur plan $10 = équivalent $10.00 de crédit de base (et jusqu'à $60 d'usage officiel)
const fmtBalanceUSD = tokens => {
  if (!tokens || tokens <= 0) return '$0.00';
  // Valeur faciale $10 pour 1 milliard de tokens
  const val = (tokens / 1e9) * 10;
  return '$' + val.toFixed(2);
};

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

async function apiCall(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (APP_STATE.session) headers['X-QH-Session'] = APP_STATE.session;
  const res = await fetch(API + path, {
    method: opts.method || 'POST',
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined
  });
  let data = null;
  try { data = await res.json(); } catch (e) { data = { error: { message: 'Réponse serveur invalide' } }; }
  return { status: res.status, data };
}

/* ============================ NAVIGATION & TABS ============================ */
window.switchTab = function(tabId) {
  document.querySelectorAll('.nav-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.tab === tabId);
  });
  document.querySelectorAll('.tab-pane').forEach(p => {
    p.classList.toggle('active', p.id === 'tab-' + tabId);
  });
  APP_STATE.currentTab = tabId;
  window.scrollTo({ top: 0, behavior: 'smooth' });
};

function initTabs() {
  document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => switchTab(tab.dataset.tab));
  });
  const balanceBadge = $('balance-badge');
  if (balanceBadge) {
    balanceBadge.onclick = () => switchTab('console');
  }
}

/* ============================ AUTHENTIFICATION ============================ */
let authMode = 'login';

window.triggerAuth = function(mode = 'login') {
  authMode = mode;
  const modal = $('modal-auth');
  const title = $('auth-modal-title');
  const subtitle = $('auth-modal-subtitle');
  const submitBtn = $('btn-submit-auth');
  const switchText = $('auth-switch-text');
  const switchLink = $('auth-switch-link');

  if (mode === 'login') {
    title.textContent = 'Welcome back';
    subtitle.textContent = 'Sign in to pick up where you left off.';
    submitBtn.textContent = 'Sign in';
    switchText.textContent = 'New here? ';
    switchLink.textContent = 'Create an account';
  } else {
    title.textContent = 'Create an account';
    subtitle.textContent = 'Start using all models in one unified API.';
    submitBtn.textContent = 'Create account';
    switchText.textContent = 'Already have an account? ';
    switchLink.textContent = 'Sign in';
  }
  $('auth-error-msg').hidden = true;
  modal.showModal();
};

function initAuth() {
  const modal = $('modal-auth');
  $('btn-login-trigger').onclick = () => triggerAuth('login');
  $('btn-register-trigger').onclick = () => triggerAuth('register');
  $('btn-close-auth-modal').onclick = () => modal.close();

  $('auth-switch-link').onclick = e => {
    e.preventDefault();
    triggerAuth(authMode === 'login' ? 'register' : 'login');
  };

  $('btn-logout').onclick = () => {
    APP_STATE.session = '';
    APP_STATE.me = null;
    sessionStorage.removeItem('qh_session');
    setAuthUI();
  };

  $('form-auth').onsubmit = async e => {
    e.preventDefault();
    const email = $('auth-username').value.trim();
    const password = $('auth-password').value;
    const btn = $('btn-submit-auth');
    btn.disabled = true;
    btn.textContent = '…';

    try {
      const endpoint = authMode === 'login' ? '/api/auth/login' : '/api/auth/register';
      const { status, data } = await apiCall(endpoint, { body: { email, password } });
      if (status === 200 && data.session) {
        APP_STATE.session = data.session;
        sessionStorage.setItem('qh_session', data.session);
        modal.close();
        await refreshMe();
      } else {
        $('auth-error-msg').textContent = (data.error && data.error.message) || 'Authentication failed';
        $('auth-error-msg').hidden = false;
      }
    } catch (err) {
      $('auth-error-msg').textContent = 'Passerelle injoignable.';
      $('auth-error-msg').hidden = false;
    } finally {
      btn.disabled = false;
      btn.textContent = authMode === 'login' ? 'Sign in' : 'Create account';
    }
  };
}

/* ============================ OAUTH GOOGLE / GITHUB ============================ */
function initOAuth() {
  const go = async provider => {
    const { status, data } = await apiCall('/api/auth/oauth/start?provider=' + provider, { method: 'GET' });
    if (status === 200 && data.url) {
      window.location.href = data.url;
    } else {
      alert((data.error && data.error.message) || 'Connexion sociale indisponible');
    }
  };

  $('btn-oauth-google').onclick = () => go('google');
  $('btn-oauth-github').onclick = () => go('github');

  const q = new URLSearchParams(window.location.search);
  const s = q.get('oauth_session');
  if (s) {
    history.replaceState({}, '', window.location.pathname);
    APP_STATE.session = s;
    sessionStorage.setItem('qh_session', s);
    refreshMe();
  }
}

/* ============================ UI & ÉTAT UTILISATEUR ============================ */
function setAuthUI() {
  const logged = !!(APP_STATE.me && APP_STATE.me.user);
  $('auth-guest-view').style.display = logged ? 'none' : 'flex';
  $('auth-user-view').style.display = logged ? 'flex' : 'none';

  if (logged) {
    const email = APP_STATE.me.user.email || '';
    const username = email.split('@')[0] || 'User';
    $('auth-user-name').textContent = username;
    $('user-avatar-initial').textContent = username.charAt(0).toUpperCase();
    renderMe();
  } else {
    $('user-tokens').textContent = '$0.00';
    APP_STATE.keys = [];
    renderKeys();
  }
}

function renderMe() {
  const me = APP_STATE.me;
  if (!me) return;
  const subs = me.subscription || {};
  const auto = subs.auto || {};
  const autoLeft = Math.max(0, (auto.tokens_total || 0) - (auto.tokens_used || 0));

  $('user-tokens').textContent = fmtBalanceUSD(autoLeft);
  APP_STATE.keys = me.keys || [];
  renderKeys();
}

async function refreshMe() {
  if (!APP_STATE.session) return;
  const { status, data } = await apiCall('/api/me', { method: 'GET' });
  if (status === 200) {
    APP_STATE.me = data;
    setAuthUI();
  } else {
    APP_STATE.session = '';
    APP_STATE.me = null;
    sessionStorage.removeItem('qh_session');
    setAuthUI();
  }
}

/* ============================ GESTION DES CLÉS API ============================ */
function renderKeys() {
  const tbody = $('keys-table-body');
  const logged = !!APP_STATE.me;
  $('keys-login-hint').style.display = logged ? 'none' : 'block';
  const keys = APP_STATE.keys;

  if (!keys.length) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--muted);">${logged ? 'No API keys yet. Create one to connect your agents.' : 'Sign in to view your API keys.'}</td></tr>`;
    return;
  }

  tbody.innerHTML = keys.map(k => `
    <tr>
      <td><strong>${escapeHtml(k.name)}</strong></td>
      <td><code style="font-family:var(--font-mono);color:var(--emerald);font-size:12px;">${escapeHtml(k.prefix)}…</code></td>
      <td>${new Date((k.created_at || 0) * 1000).toISOString().slice(0, 10)}</td>
      <td>${k.last_used ? new Date(k.last_used * 1000).toISOString().slice(0, 16).replace('T', ' ') : 'never'}</td>
      <td><span style="color:${k.revoked ? 'var(--danger)' : 'var(--emerald)'};font-weight:600;">● ${k.revoked ? 'Revoked' : 'Active'}</span></td>
      <td style="text-align:right;">
        ${k.revoked ? '' : `<button class="btn-ghost" style="color:var(--danger);" onclick="revokeKey(${k.id})">Revoke</button>`}
      </td>
    </tr>`).join('');
}

window.revokeKey = async function(id) {
  if (!confirm('Permanently revoke this key? Any agent using it will stop working.')) return;
  const { status } = await apiCall(`/api/keys/${id}`, { method: 'DELETE' });
  if (status === 200) await refreshMe();
  else alert('Failed to revoke key.');
};

function initKeyCreation() {
  const modal = $('modal-create-key');
  const created = $('modal-key-created');

  $('open-create-key-modal').onclick = () => {
    if (!APP_STATE.me) { triggerAuth('login'); return; }
    $('key-name-input').value = '';
    modal.showModal();
  };

  $('btn-cancel-key').onclick = () => modal.close();
  $('btn-done-created').onclick = () => created.close();

  $('btn-copy-new-key').onclick = () => {
    navigator.clipboard.writeText($('newly-created-key-val').value);
    $('btn-copy-new-key').textContent = '✓ Copied';
    setTimeout(() => $('btn-copy-new-key').textContent = 'Copy', 1800);
  };

  $('form-create-key').onsubmit = async e => {
    e.preventDefault();
    const planSel = $('key-plan-select');
    const { status, data } = await apiCall('/api/keys', {
      body: { name: $('key-name-input').value.trim() || 'Agent Key', plan: planSel ? planSel.value : 'auto' }
    });
    if (status === 200 && data.key) {
      modal.close();
      $('newly-created-key-val').value = data.key;
      created.showModal();
      await refreshMe();
    } else {
      alert((data.error && data.error.message) || 'Error generating key');
    }
  };
}

/* ============================ TOP-UP / REDEEM CODE ============================ */
function initRedeem() {
  $('btn-redeem').onclick = async () => {
    const msg = $('redeem-msg');
    const code = $('redeem-input').value.trim().toUpperCase();
    if (!code) return;
    msg.hidden = true;
    const { status, data } = await apiCall('/api/redeem', { body: { code } });
    msg.hidden = false;
    if (status === 200) {
      msg.style.color = 'var(--emerald)';
      msg.textContent = `✓ Code activated! +$10.00 in usage credits added.`;
      $('redeem-input').value = '';
      await refreshMe();
    } else {
      msg.style.color = 'var(--danger)';
      msg.textContent = '✕ ' + ((data.error && data.error.message) || 'Invalid code');
    }
  };
}

/* ============================ RECHERCHE & FILTRES MODÈLES ============================ */
window.filterModels = function(category, btn) {
  document.querySelectorAll('.models-tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');

  const rows = document.querySelectorAll('.model-row');
  rows.forEach(r => {
    if (category === 'all' || r.dataset.cat === category) {
      r.style.display = '';
    } else {
      r.style.display = 'none';
    }
  });
};

window.searchModels = function(query) {
  const q = query.toLowerCase().trim();
  const rows = document.querySelectorAll('.model-row');
  rows.forEach(r => {
    const text = (r.dataset.name || '').toLowerCase();
    r.style.display = text.includes(q) ? '' : 'none';
  });
};

/* ============================ PLAYGROUND INTERACTIF ============================ */
function initPlayground() {
  $('btn-run-playground').onclick = runPlay;
  $('btn-reset-playground').onclick = () => {
    $('playground-output').textContent = 'Ready.';
    $('response-meta').textContent = 'Ready';
  };
}

async function runPlay() {
  const out = $('playground-output');
  const meta = $('response-meta');
  let key = sessionStorage.getItem('qh_play_key') || '';

  if (!key) {
    key = prompt('Paste your Quota.Hub API key (sk-qh-...):');
    if (!key) return;
    if (!/^sk-qh-/.test(key)) { alert('Invalid key format. Expected sk-qh-...'); return; }
    sessionStorage.setItem('qh_play_key', key);
  }

  const promptText = $('play-user-prompt').value.trim();
  if (!promptText) { alert('Please enter a prompt.'); return; }

  meta.textContent = '⏳ Routing request...';
  out.textContent = '…';
  const t0 = performance.now();

  try {
    const res = await fetch('/v1/chat/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key },
      body: JSON.stringify({ model: 'auto', messages: [{ role: 'user', content: promptText }], max_tokens: 400 })
    });
    const dt = ((performance.now() - t0) / 1000).toFixed(1);
    const j = await res.json();
    if (!res.ok) {
      meta.textContent = `HTTP ${res.status}`;
      out.textContent = (j.error && j.error.message) || 'Inference error';
      return;
    }
    const content = (j.choices && j.choices[0] && j.choices[0].message && j.choices[0].message.content) || '(empty)';
    const ar = j.a6_router || {};
    meta.textContent = `200 OK · ${dt}s · served: ${ar.served_model || 'auto'}`;
    out.textContent = content;
    if (APP_STATE.me) refreshMe();
  } catch (e) {
    meta.textContent = 'Network error';
    out.textContent = String(e);
  }
}

window.copyCli = function() {
  navigator.clipboard.writeText('curl -fsSL https://quota-hub.vercel.app/connect.sh | sh');
  alert('Install command copied to clipboard!');
};

/* ============================ INITIALISATION ============================ */
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initAuth();
  initOAuth();
  initKeyCreation();
  initRedeem();
  initPlayground();
  if (APP_STATE.session) refreshMe();
});
