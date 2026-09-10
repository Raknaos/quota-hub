/**
 * QUOTA.HUB — Token Harbor Exact Integration Script
 */

const API = '/gw';
const APP_STATE = {
  session: sessionStorage.getItem('qh_session') || '',
  me: null,
  keys: [],
  currentTab: 'pricing',
  billingCycle: 'month'
};

const $ = id => document.getElementById(id);

const fmtBalanceUSD = tokens => {
  if (!tokens || tokens <= 0) return '$0.00';
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
  const loader = $('top-loader');
  if (loader) { loader.style.width = '45%'; loader.style.opacity = '1'; }
  const headers = { 'Content-Type': 'application/json' };
  if (APP_STATE.session) headers['X-QH-Session'] = APP_STATE.session;
  try {
    const res = await fetch(API + path, {
      method: opts.method || 'POST',
      headers,
      body: opts.body ? JSON.stringify(opts.body) : undefined
    });
    if (loader) loader.style.width = '90%';
    let data = null;
    try { data = await res.json(); } catch (e) { data = { error: { message: 'Réponse serveur invalide' } }; }
    if (loader) {
      loader.style.width = '100%';
      setTimeout(() => { loader.style.opacity = '0'; loader.style.width = '0%'; }, 200);
    }
    return { status: res.status, data };
  } catch (err) {
    if (loader) { loader.style.opacity = '0'; loader.style.width = '0%'; }
    return { status: 500, data: { error: { message: 'Erreur de connexion' } } };
  }
}

/* ── Navigation ── */
window.switchTab = function(tabId) {
  document.querySelectorAll('.th-nav-link').forEach(t => {
    t.classList.toggle('active', t.dataset.tab === tabId);
  });
  document.querySelectorAll('.tab-pane').forEach(p => {
    p.classList.toggle('active', p.id === 'tab-' + tabId);
  });
  APP_STATE.currentTab = tabId;
  window.scrollTo({ top: 0, behavior: 'smooth' });
};

window.setCycle = function(cycle) {
  APP_STATE.billingCycle = cycle;
  $('btn-cycle-month').classList.toggle('active', cycle === 'month');
  $('btn-cycle-year').classList.toggle('active', cycle === 'year');
  if (cycle === 'year') {
    $('price-agent').innerHTML = '$0.79 <span>/ month</span>';
    $('price-office').innerHTML = '$7.99 <span>/ month</span>';
    $('price-frontier').innerHTML = '$79 <span>/ month</span>';
  } else {
    $('price-agent').innerHTML = '$0.99 <span>/ month</span>';
    $('price-office').innerHTML = '$9.99 <span>/ month</span>';
    $('price-frontier').innerHTML = '$99 <span>/ month</span>';
  }
};

/* ── Split-Screen Auth ── */
let currentAuthMode = 'login';

window.openAuth = function(mode = 'login') {
  currentAuthMode = mode;
  setAuthMode(mode);
  $('auth-modal').style.display = 'grid';
  document.body.style.overflow = 'hidden';
};

window.closeAuth = function() {
  $('auth-modal').style.display = 'none';
  document.body.style.overflow = '';
};

window.setAuthMode = function(mode) {
  currentAuthMode = mode;
  $('tab-auth-signin').classList.toggle('active', mode === 'login');
  $('tab-auth-signup').classList.toggle('active', mode === 'signup');
  if (mode === 'login') {
    $('auth-title').textContent = 'Welcome back';
    $('auth-subtitle').textContent = 'Sign in to pick up where you left off.';
    $('btn-auth-submit').textContent = 'Sign in';
  } else {
    $('auth-title').textContent = 'Create an account';
    $('auth-subtitle').textContent = 'Start using all models in one unified API.';
    $('btn-auth-submit').textContent = 'Create account';
  }
  $('auth-error').hidden = true;
};

function initAuth() {
  $('form-auth').onsubmit = async e => {
    e.preventDefault();
    const email = $('auth-email').value.trim();
    const password = $('auth-password').value;
    const btn = $('btn-auth-submit');
    btn.disabled = true; btn.textContent = '…';

    try {
      const endpoint = currentAuthMode === 'login' ? '/api/auth/login' : '/api/auth/register';
      const { status, data } = await apiCall(endpoint, { body: { email, password } });
      if (status === 200 && data.session) {
        APP_STATE.session = data.session;
        sessionStorage.setItem('qh_session', data.session);
        closeAuth();
        await refreshMe();
      } else {
        $('auth-error').textContent = (data.error && data.error.message) || 'Échec de connexion';
        $('auth-error').hidden = false;
      }
    } finally {
      btn.disabled = false;
      btn.textContent = currentAuthMode === 'login' ? 'Sign in' : 'Create account';
    }
  };

  // OAuth Google & GitHub
  const goOAuth = async provider => {
    const { status, data } = await apiCall('/api/auth/oauth/start?provider=' + provider, { method: 'GET' });
    if (status === 200 && data.url) window.location.href = data.url;
    else alert((data.error && data.error.message) || 'Service OAuth indisponible');
  };
  $('btn-oauth-google').onclick = () => goOAuth('google');
  $('btn-oauth-github').onclick = () => goOAuth('github');

  const q = new URLSearchParams(window.location.search);
  const s = q.get('oauth_session');
  if (s) {
    history.replaceState({}, '', window.location.pathname);
    APP_STATE.session = s;
    sessionStorage.setItem('qh_session', s);
    refreshMe();
  }
}

window.logout = function() {
  APP_STATE.session = '';
  APP_STATE.me = null;
  sessionStorage.removeItem('qh_session');
  setAuthUI();
};

function setAuthUI() {
  const logged = !!(APP_STATE.me && APP_STATE.me.user);
  $('auth-guest-view').style.display = logged ? 'none' : 'flex';
  $('auth-user-view').style.display = logged ? 'flex' : 'none';

  if (logged) {
    const email = APP_STATE.me.user.email || '';
    const username = email.split('@')[0] || 'User';
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
    logout();
  }
}

/* ── Keys Management ── */
function renderKeys() {
  const tbody = $('keys-table-body');
  const logged = !!APP_STATE.me;
  $('keys-login-box').style.display = logged ? 'none' : 'block';
  $('keys-table-container').style.display = logged ? 'block' : 'none';

  const keys = APP_STATE.keys || [];
  if (!keys.length) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--muted);">No API keys yet. Click '+ Create Key' above.</td></tr>`;
    return;
  }

  tbody.innerHTML = keys.map(k => `
    <tr>
      <td><strong>${escapeHtml(k.name)}</strong></td>
      <td><code style="font-family:monospace;color:var(--foreground);font-size:12.5px;">${escapeHtml(k.prefix)}…</code></td>
      <td>${new Date((k.created_at || 0) * 1000).toISOString().slice(0, 10)}</td>
      <td><span style="color:${k.revoked ? '#ef4444' : '#10b981'};font-weight:600;">● ${k.revoked ? 'Revoked' : 'Active'}</span></td>
      <td style="text-align:right;">
        ${k.revoked ? '' : `<button class="btn-signin" style="color:#ef4444;padding:2px 6px;" onclick="revokeKey(${k.id})">Revoke</button>`}
      </td>
    </tr>`).join('');
}

async function sendChatMessage(text) {
  const messages = $('chat-messages');
  if (!messages) return;
  const empty = messages.querySelector('.chat-empty');
  if (empty) empty.remove();
  const user = document.createElement('div');
  user.className = 'chat-bubble chat-user';
  user.textContent = text;
  messages.appendChild(user);
  const assistant = document.createElement('div');
  assistant.className = 'chat-bubble chat-assistant';
  assistant.textContent = APP_STATE.me ? 'Le Chat est prêt. Pour une réponse réelle, utilise le Playground avec ta clé API.' : 'Connecte-toi pour lancer une requête réelle depuis le Chat.';
  messages.appendChild(assistant);
}

function initChat() {
  const form = $('chat-form');
  if (!form) return;
  form.onsubmit = e => {
    e.preventDefault();
    const input = $('chat-input');
    const text = input.value.trim();
    if (!text) return;
    sendChatMessage(text);
    input.value = '';
  };
}

window.openKeyModal = function() {
  if (!APP_STATE.me) { openAuth('login'); return; }
  $('key-name-input').value = '';
  $('modal-key').showModal();
};

function initKeyCreation() {
  $('form-create-key').onsubmit = async e => {
    e.preventDefault();
    const name = $('key-name-input').value.trim() || 'API Key';
    const { status, data } = await apiCall('/api/keys', { body: { name, plan: 'auto' } });
    if (status === 200 && data.key) {
      $('modal-key').close();
      $('new-key-val').value = data.key;
      $('modal-key-success').showModal();
      await refreshMe();
    } else {
      alert((data.error && data.error.message) || 'Erreur génération clé');
    }
  };

  $('btn-copy-key').onclick = () => {
    navigator.clipboard.writeText($('new-key-val').value);
    $('btn-copy-key').textContent = '✓ Copied';
    setTimeout(() => $('btn-copy-key').textContent = 'Copy', 1500);
  };
}

window.revokeKey = async function(id) {
  if (!confirm('Permanently revoke this key?')) return;
  const { status } = await apiCall(`/api/keys/${id}`, { method: 'DELETE' });
  if (status === 200) await refreshMe();
};

/* ── Filter / Search Models ── */
window.filterModels = function(cat, btn) {
  document.querySelectorAll('.th-filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.model-row').forEach(r => {
    r.style.display = (cat === 'all' || r.dataset.cat === cat) ? '' : 'none';
  });
};

window.searchModels = function(q) {
  const val = q.toLowerCase().trim();
  document.querySelectorAll('.model-row').forEach(r => {
    r.style.display = r.dataset.name.includes(val) ? '' : 'none';
  });
};

/* ── CLI & Playground ── */
window.copyCli = function() {
  navigator.clipboard.writeText('curl -fsSL https://quota-hub.vercel.app/connect.sh | sh');
  alert('Command copied to clipboard!');
};

function initPlayground() {
  $('btn-run-playground').onclick = async () => {
    const prompt = $('play-user-prompt').value.trim();
    if (!prompt) return alert('Enter a prompt.');
    let key = sessionStorage.getItem('qh_play_key');
    if (!key) {
      key = window.prompt('Enter your Quota.Hub API key (sk-qh-...):');
      if (!key) return;
      sessionStorage.setItem('qh_play_key', key);
    }
    const out = $('playground-output');
    const meta = $('response-meta');
    meta.textContent = '⏳ Routing...';
    out.textContent = '…';
    const t0 = performance.now();
    try {
      const res = await fetch('/v1/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key },
        body: JSON.stringify({ model: 'auto', messages: [{ role: 'user', content: prompt }], max_tokens: 400 })
      });
      const dt = ((performance.now() - t0) / 1000).toFixed(1);
      const j = await res.json();
      if (!res.ok) { meta.textContent = `HTTP ${res.status}`; out.textContent = (j.error && j.error.message) || 'Error'; return; }
      const content = (j.choices && j.choices[0] && j.choices[0].message && j.choices[0].message.content) || '(empty)';
      const ar = j.a6_router || {};
      meta.textContent = `200 OK · ${dt}s · served: ${ar.served_model || 'auto'}`;
      out.textContent = content;
      if (APP_STATE.me) refreshMe();
    } catch (e) {
      meta.textContent = 'Network error';
      out.textContent = String(e);
    }
  };
}

/* ── Code Redeem ── */
function initRedeem() {
  $('btn-redeem').onclick = async () => {
    const msg = $('redeem-msg');
    const code = $('redeem-input').value.trim().toUpperCase();
    if (!code) return;
    msg.hidden = true;
    const { status, data } = await apiCall('/api/redeem', { body: { code } });
    msg.hidden = false;
    if (status === 200) {
      msg.style.color = '#10b981';
      msg.textContent = `✓ Activated! Credits added to your balance.`;
      $('redeem-input').value = '';
      await refreshMe();
    } else {
      msg.style.color = '#ef4444';
      msg.textContent = '✕ ' + ((data.error && data.error.message) || 'Code rejected');
    }
  };
}

/* ── Init ── */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.th-nav-link').forEach(btn => {
    btn.onclick = () => switchTab(btn.dataset.tab);
  });
  initAuth();
  initKeyCreation();
  initPlayground();
  initChat();
  initRedeem();
  if (APP_STATE.session) refreshMe();
});
