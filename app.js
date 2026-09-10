/**
 * QUOTA HUB — Front abonnement. Toute la logique métier est côté passerelle ;
 * ici : session (token HMAC signé serveur), clés (hachées côté serveur),
 * activation de codes, playground réel via /v1/chat/completions.
 * Aucun secret dans ce fichier ; aucune donnée simulée : les états vides sont affichés comme tels.
 */
const API = '/gw';
const APP_STATE = {
  session: sessionStorage.getItem('qh_session') || '',
  me: null,
  keys: [],
  currentTab: 'plan',
  glassAlpha: parseFloat(localStorage.getItem('qh_glass') || '0.85'),
  playKey: ''
};

const $ = id => document.getElementById(id);
const fmtM = n => (n >= 1e9 ? (n / 1e9).toFixed(2) + ' Md' : n >= 1e6 ? (n / 1e6).toFixed(1) + ' M' : n >= 1e3 ? (n / 1e3).toFixed(1) + ' k' : String(n));

async function apiCall(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (APP_STATE.session) headers['X-QH-Session'] = APP_STATE.session;
  const res = await fetch(API + path, { method: opts.method || 'POST', headers, body: opts.body ? JSON.stringify(opts.body) : undefined });
  let data = null;
  try { data = await res.json(); } catch (e) { data = { error: { message: 'réponse illisible' } }; }
  return { status: res.status, data };
}

/* ============================ AUTH ============================ */
function setAuthUI() {
  const logged = !!(APP_STATE.me && APP_STATE.me.user);
  $('auth-guest-view').style.display = logged ? 'none' : 'flex';
  $('auth-user-view').style.display = logged ? 'flex' : 'none';
  if (logged) {
    const email = APP_STATE.me.user.email;
    $('auth-user-name').textContent = email.split('@')[0];
    renderMe();
  } else {
    $('user-tokens').textContent = '—';
    APP_STATE.keys = [];
    renderKeys();
  }
}

function renderMe() {
  const me = APP_STATE.me;
  if (!me) return;
  const subs = me.subscription || {};
  const auto = subs.auto || {}, gem = subs.gemini || {};
  const autoLeft = Math.max(0, (auto.tokens_total || 0) - (auto.tokens_used || 0));
  const gemLeft = Math.max(0, (gem.tokens_total || 0) - (gem.tokens_used || 0));
  $('user-tokens').textContent = fmtM(autoLeft);
  $('metric-tokens-left').textContent = fmtM(autoLeft);
  const usageAuto = (me.usage && me.usage.auto) || {};
  $('metric-requests').textContent = String(usageAuto.n || 0);
  const autoActive = auto.status === 'active';
  $('metric-sub-status').textContent = autoActive ? 'Actif' : 'Inactif';
  $('metric-sub-status').style.color = autoActive ? 'var(--lime)' : 'var(--soft)';
  const pct = auto.tokens_total ? Math.min(100, Math.round(100 * (auto.tokens_used || 0) / auto.tokens_total)) : 0;
  $('label-sub-quota').textContent = `${fmtM(auto.tokens_used || 0)} / ${fmtM(auto.tokens_total)} tokens`;
  $('track-sub-quota').style.width = pct + '%';
  $('label-quota-detail').textContent = `${fmtM(auto.tokens_used || 0)} / ${fmtM(auto.tokens_total)}`;
  $('track-quota-detail').style.width = pct + '%';
  $('metric-prompt-tokens').textContent = fmtM(usageAuto.pin || 0);
  $('metric-completion-tokens').textContent = fmtM(usageAuto.pout || 0);
  $('metric-served-model').textContent = usageAuto.last_model || '—';
  const gemEl = $('metric-gemini-left');
  if (gemEl) gemEl.textContent = `${fmtM(gemLeft)}${gem.status === 'active' ? '' : ' (inactif)'}`;
  APP_STATE.keys = me.keys || [];
  renderKeys();
}

function initAuth() {
  const modal = $('modal-auth');
  let mode = 'login';
  const setMode = m => {
    mode = m;
    $('tab-auth-login').classList.toggle('active', m === 'login');
    $('tab-auth-register').classList.toggle('active', m === 'register');
    $('auth-modal-title').textContent = m === 'login' ? 'Connexion' : 'Créer un compte';
    $('btn-submit-auth').textContent = m === 'login' ? 'Se connecter' : 'Créer mon compte';
    $('auth-error-msg').hidden = true;
  };
  $('btn-login-trigger').onclick = () => { setMode('login'); modal.showModal(); };
  $('btn-register-trigger').onclick = () => { setMode('register'); modal.showModal(); };
  $('tab-auth-login').onclick = () => setMode('login');
  $('tab-auth-register').onclick = () => setMode('register');
  $('btn-close-auth-modal').onclick = () => modal.close();
  $('btn-cancel-auth').onclick = () => modal.close();
  $('btn-logout').onclick = () => {
    APP_STATE.session = ''; APP_STATE.me = null;
    sessionStorage.removeItem('qh_session');
    setAuthUI();
  };
  $('form-auth').onsubmit = async e => {
    e.preventDefault();
    const email = $('auth-username').value.trim();
    const password = $('auth-password').value;
    const btn = $('btn-submit-auth');
    btn.disabled = true; btn.textContent = '…';
    try {
      const { status, data } = await apiCall(mode === 'login' ? '/api/auth/login' : '/api/auth/register', { body: { email, password } });
      if (status === 200 && data.session) {
        APP_STATE.session = data.session;
        sessionStorage.setItem('qh_session', data.session);
        modal.close();
        await refreshMe();
      } else {
        $('auth-error-msg').textContent = (data.error && data.error.message) || 'Échec';
        $('auth-error-msg').hidden = false;
      }
    } catch (err) {
      $('auth-error-msg').textContent = 'Passerelle injoignable.';
      $('auth-error-msg').hidden = false;
    } finally {
      btn.disabled = false;
      setMode(mode);
    }
  };
}

async function refreshMe() {
  if (!APP_STATE.session) return;
  const { status, data } = await apiCall('/api/me', { method: 'GET' });
  if (status === 200) {
    APP_STATE.me = data;
    setAuthUI();
  } else {
    // session expirée / invalide
    APP_STATE.session = ''; APP_STATE.me = null;
    sessionStorage.removeItem('qh_session');
    setAuthUI();
  }
}

/* ============================ ONGLES ============================ */
function initTabs() {
  document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      APP_STATE.currentTab = tab.dataset.tab;
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      const pane = $('tab-' + tab.dataset.tab);
      if (pane) pane.classList.add('active');
    });
  });
  $('balance-badge').onclick = () => document.querySelector('.nav-tab[data-tab="console"]').click();
}

/* ============================ CLÉS ============================ */
function renderKeys() {
  const tbody = $('keys-table-body');
  const logged = !!APP_STATE.me;
  $('keys-login-hint').hidden = logged;
  const keys = APP_STATE.keys;
  $('keys-count-badge').textContent = `${keys.length} clé${keys.length > 1 ? 's' : ''}`;
  if (!keys.length) {
    tbody.innerHTML = `<tr><td colspan="6" style="padding:14px;color:var(--soft);">${logged ? 'Aucune clé — créez-en une pour appeler l\'API.' : 'Connectez-vous pour voir vos clés.'}</td></tr>`;
    fillPlayKeySelect();
    return;
  }
  tbody.innerHTML = keys.map(k => `
    <tr>
      <td><strong>${escapeHtml(k.name)}</strong><div style="font-size:11px;color:var(--soft)">${k.plan === 'gemini' ? 'Gemini 100 M' : 'Auto 1 Md'}</div></td>
      <td><span class="key-code">${escapeHtml(k.prefix)}…</span></td>
      <td>${new Date((k.created_at || 0) * 1000).toISOString().slice(0, 10)}</td>
      <td>${k.last_used ? new Date(k.last_used * 1000).toISOString().slice(0, 16).replace('T', ' ') : 'jamais'}</td>
      <td><span style="font-weight:600;color:${k.revoked ? 'var(--danger)' : 'var(--lime)'}">● ${k.revoked ? 'Révoquée' : 'Active'}</span></td>
      <td style="text-align: right;">
        ${k.revoked ? '' : `<button class="ghost-btn" style="color:#e11d48;" onclick="revokeKey(${k.id})">Révoquer</button>`}
      </td>
    </tr>`).join('');
  fillPlayKeySelect();
}

function fillPlayKeySelect() {
  const sel = $('play-key-select');
  if (!sel) return;
  const keys = (APP_STATE.keys || []).filter(k => !k.revoked);
  sel.innerHTML = keys.length
    ? keys.map(k => `<option value="${k.id}">${escapeHtml(k.name)}</option>`).join('')
    : '<option value="">— aucune clé —</option>';
}

window.revokeKey = async function (id) {
  if (!confirm('Révoquer définitivement cette clé ? Les agents qui l\'utilisent cesseront de fonctionner.')) return;
  const { status, data } = await apiCall(`/api/keys/${id}`, { method: 'DELETE' });
  if (status === 200) await refreshMe();
  else alert((data.error && data.error.message) || 'Échec de la révocation');
};

function initKeyCreation() {
  const modal = $('modal-create-key');
  const created = $('modal-key-created');
  $('open-create-key-modal').onclick = () => {
    if (!APP_STATE.me) { $('btn-login-trigger').click(); return; }
    $('key-name-input').value = '';
    modal.showModal();
  };
  $('btn-close-modal').onclick = () => modal.close();
  $('btn-cancel-key').onclick = () => modal.close();
  $('btn-close-created-modal').onclick = () => created.close();
  $('btn-done-created').onclick = () => created.close();
  $('btn-copy-new-key').onclick = () => {
    navigator.clipboard.writeText($('newly-created-key-val').value);
    $('btn-copy-new-key').textContent = '✓ Copié';
    setTimeout(() => $('btn-copy-new-key').textContent = 'Copier', 1800);
  };
  $('form-create-key').onsubmit = async e => {
    e.preventDefault();
    const planSel = $('key-plan-select');
    const { status, data } = await apiCall('/api/keys', { body: { name: $('key-name-input').value.trim() || 'Clé', plan: planSel ? planSel.value : 'auto' } });
    if (status === 200 && data.key) {
      modal.close();
      $('newly-created-key-val').value = data.key;
      created.showModal();
      await refreshMe();
    } else {
      alert((data.error && data.error.message) || 'Échec de la création');
    }
  };
}

/* ============================ CODES ============================ */
function initRedeem() {
  $('btn-redeem').onclick = async () => {
    const msg = $('redeem-msg');
    const code = $('redeem-input').value.trim().toUpperCase();
    if (!code) return;
    msg.hidden = true;
    const { status, data } = await apiCall('/api/redeem', { body: { code } });
    msg.hidden = false;
    if (status === 200) {
      msg.style.color = 'var(--lime)';
      const pl = data.plan || 'auto';
      const ps = (data.subscription && data.subscription[pl]) || {};
      msg.textContent = `✓ Code ${pl === 'gemini' ? 'Gemini 3.8 Flash' : 'auto polyvalent'} activé : +${fmtM(ps.tokens_total || 0)} tokens.`;
      $('redeem-input').value = '';
      $('redeem-total').textContent = fmtM(ps.tokens_total || 0);
      $('redeem-status').textContent = ps.status === 'active' ? 'Actif' : ps.status || '—';
      await refreshMe();
    } else {
      msg.style.color = 'var(--danger)';
      msg.textContent = '✕ ' + ((data.error && data.error.message) || 'Code refusé');
    }
  };
}

/* ============================ PLAYGROUND ============================ */
function initPlayground() {
  $('btn-run-playground').onclick = runPlay;
  $('btn-reset-playground').onclick = () => {
    $('playground-output').textContent = 'Prêt.';
    $('response-meta').textContent = 'Prêt';
  };
  document.querySelectorAll('#snippet-lang-tabs .mini-tab').forEach(t => {
    t.onclick = () => {
      document.querySelectorAll('#snippet-lang-tabs .mini-tab').forEach(x => x.classList.remove('active'));
      t.classList.add('active');
      updateSnippet(t.dataset.lang);
    };
  });
  $('btn-copy-snippet').onclick = () => {
    navigator.clipboard.writeText($('snippet-code-content').textContent);
    $('btn-copy-snippet').textContent = '✓ Copié';
    setTimeout(() => $('btn-copy-snippet').textContent = 'Copier', 1800);
  };
  updateSnippet('curl');
}

function myKey() {
  // la clé complète n'est JAMAIS stockée par le front : l'utilisateur la colle au besoin.
  return sessionStorage.getItem('qh_play_key') || '';
}

function keyPlanById(id) {
  const k = (APP_STATE.keys || []).find(x => String(x.id) === String(id));
  return (k && k.plan) || 'auto';
}

function runPlay() {
  const out = $('playground-output');
  const meta = $('response-meta');
  let key = myKey();
  if (!key) {
    key = prompt('Collez une clé sk-qh-… (elle reste dans cet onglet uniquement, jamais envoyée ailleurs) :');
    if (!key) return;
    if (!/^sk-qh-/.test(key)) { alert('Format attendu : sk-qh-…'); return; }
    sessionStorage.setItem('qh_play_key', key);
  }
  const prompt = $('play-user-prompt').value.trim();
  if (!prompt) { alert('Saisissez une invite.'); return; }
  const sel = $('play-key-select');
  const planLbl = keyPlanById(sel && sel.value) === 'gemini' ? 'gemini 3.8 flash' : 'routage auto';
  meta.textContent = `⏳ ${planLbl} en cours…`;
  out.textContent = '…';
  const t0 = performance.now();
  fetch('/v1/chat/completions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key },
    body: JSON.stringify({ model: 'auto', messages: [{ role: 'user', content: prompt }], max_tokens: 400 })
  }).then(async r => {
    const dt = (performance.now() - t0) / 1000;
    const j = await r.json().catch(() => ({}));
    if (!r.ok) {
      meta.textContent = `HTTP ${r.status}`;
      out.textContent = (j.error && j.error.message) || 'échec';
      return;
    }
    const content = (j.choices && j.choices[0] && j.choices[0].message && j.choices[0].message.content) || '(vide)';
    const qh = j.quota_hub || {};
    const ar = j.a6_router || {};
    const srv = ar.served_model || '?';
    const dec = ar.decision ? ` · ${ar.decision}` : '';
    meta.textContent = `200 OK · ${dt.toFixed(1)}s · servi : ${srv}${dec} · restant : ${fmtM(qh.tokens_remaining || 0)}`;
    out.textContent = content;
    if (APP_STATE.me) refreshMe();
  }).catch(e => {
    meta.textContent = 'erreur réseau';
    out.textContent = String(e);
  });
}

function updateSnippet(lang) {
  const code = $('snippet-code-content');
  const title = $('snippet-header-title');
  const BASE = 'https://quota-hub.vercel.app/v1';
  if (lang === 'curl') {
    title.textContent = 'Appel cURL (model ignoré par le routeur)';
    code.textContent = `curl ${BASE}/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer sk-qh-VOTRE_CLE" \\
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "Bonjour !"}],
    "max_tokens": 500
  }'`;
  } else if (lang === 'python') {
    title.textContent = 'SDK OpenAI Python';
    code.textContent = `from openai import OpenAI

client = OpenAI(
    base_url="${BASE}",
    api_key="sk-qh-VOTRE_CLE",
)

r = client.chat.completions.create(
    model="auto",  # ignoré : le routeur choisit le moins cher
    messages=[{"role": "user", "content": "Bonjour !"}],
)
print(r.choices[0].message.content)
print(r.quota_hub.tokens_remaining)  # méta Quota.Hub (attribut extra)`;
  } else {
    title.textContent = 'SDK OpenAI Node.js';
    code.textContent = `import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "${BASE}",
  apiKey: "sk-qh-VOTRE_CLE",
});

const r = await client.chat.completions.create({
  model: "auto", // ignoré : le routeur choisit le moins cher
  messages: [{ role: "user", content: "Bonjour !" }],
});
console.log(r.choices[0].message.content);`;
  }
}

/* ============================ DIVERS ============================ */
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function initGlassControl() {
  const slider = $('glass-alpha-slider');
  slider.value = APP_STATE.glassAlpha;
  document.documentElement.style.setProperty('--glass-alpha', APP_STATE.glassAlpha);
  $('glass-alpha-label').textContent = Math.round(APP_STATE.glassAlpha * 100) + '%';
  slider.addEventListener('input', e => {
    const v = parseFloat(e.target.value);
    APP_STATE.glassAlpha = v;
    document.documentElement.style.setProperty('--glass-alpha', v);
    $('glass-alpha-label').textContent = Math.round(v * 100) + '%';
    localStorage.setItem('qh_glass', String(v));
  });
}

document.addEventListener('DOMContentLoaded', () => {
  initAuth();
  initTabs();
  initKeyCreation();
  initRedeem();
  initPlayground();
  initGlassControl();
  refreshMe().then(() => setAuthUI()).catch(() => setAuthUI());
});
