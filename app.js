/* Smart API Cheap — interface client, sans état fictif */
const API = '/gw';
const APP_STATE = { session: sessionStorage.getItem('qh_session') || '', me: null, keys: [], currentTab: 'home' };
const $ = id => document.getElementById(id);
const fmtBalanceUSD = tokens => '$' + Math.max(0, (tokens || 0) / 1e9 * 10).toFixed(2);
function escapeHtml(value) { return String(value || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c])); }
async function apiCall(path, opts = {}) {
  const loader = $('top-loader'); if (loader) { loader.style.opacity = '1'; loader.style.width = '42%'; }
  const headers = {'Content-Type':'application/json'}; if (APP_STATE.session) headers['X-QH-Session'] = APP_STATE.session;
  try {
    const res = await fetch(API + path, {method: opts.method || 'POST', headers, body: opts.body ? JSON.stringify(opts.body) : undefined});
    const data = await res.json().catch(() => ({error:{message:'Réponse serveur invalide'}}));
    if (loader) { loader.style.width = '100%'; setTimeout(() => { loader.style.opacity='0'; loader.style.width='0'; }, 220); }
    return {status:res.status, data};
  } catch (_) { if (loader) loader.style.opacity='0'; return {status:500,data:{error:{message:'Impossible de joindre Smart API Cheap'}}}; }
}
window.switchTab = function(tab) {
  document.querySelectorAll('.nav-link').forEach(x => x.classList.toggle('active', x.dataset.tab === tab));
  document.querySelectorAll('.tab-pane').forEach(x => x.classList.toggle('active', x.id === 'tab-' + tab));
  APP_STATE.currentTab = tab; window.scrollTo({top:0,behavior:'smooth'});
  if (tab === 'usage') loadUsage();
};
let currentAuthMode = 'login';
window.openAuth = mode => { currentAuthMode=mode; setAuthMode(mode); $('auth-modal').style.display='flex'; document.body.style.overflow='hidden'; };
window.closeAuth = () => { $('auth-modal').style.display='none'; document.body.style.overflow=''; };
window.copyBlock = btn => { const code = btn.closest('.code-panel')?.querySelector('code'); if(!code) return; navigator.clipboard.writeText(code.textContent).then(()=>{ btn.textContent='Copié ✓'; setTimeout(()=>btn.textContent='Copier',1400); }).catch(()=>{}); };
window.setAuthMode = mode => { currentAuthMode=mode; $('tab-auth-signin').classList.toggle('active',mode==='login'); $('tab-auth-signup').classList.toggle('active',mode==='signup'); $('auth-title').textContent=mode==='login'?'Bienvenue.':'Créer votre espace.'; $('auth-subtitle').textContent=mode==='login'?'Connectez-vous pour retrouver votre console.':'Créez un compte, puis activez un forfait payant.'; $('btn-auth-submit').textContent=mode==='login'?'Se connecter':'Créer mon compte'; $('auth-error').hidden=true; };
function initAuth() {
  $('form-auth').onsubmit = async e => { e.preventDefault(); const btn=$('btn-auth-submit'); btn.disabled=true; btn.textContent='Connexion…'; const endpoint=currentAuthMode==='login'?'/api/auth/login':'/api/auth/register'; const r=await apiCall(endpoint,{body:{email:$('auth-email').value.trim(),password:$('auth-password').value}}); if(r.status===200&&r.data.session){ APP_STATE.session=r.data.session; sessionStorage.setItem('qh_session',r.data.session); closeAuth(); await refreshMe(); switchTab('console'); } else { $('auth-error').textContent=r.data.error?.message||'Échec de la connexion'; $('auth-error').hidden=false; } btn.disabled=false; btn.textContent=currentAuthMode==='login'?'Se connecter':'Créer mon compte'; };
  const oauth = async provider => { const note=$('oauth-note'); const r=await apiCall('/api/auth/oauth/start?provider='+provider,{method:'GET'}); if(r.status===200&&r.data.url){ if(note)note.hidden=true; location.href=r.data.url; return; } if(note){ note.textContent = 'La connexion ' + (provider==='google'?'Google':'GitHub') + ' n’est pas encore disponible. Utilisez votre email ci-dessous : votre compte et votre clé fonctionnent dès maintenant.'; note.hidden=false; } };
  $('btn-oauth-google').onclick=()=>oauth('google'); $('btn-oauth-github').onclick=()=>oauth('github');
  const session=new URLSearchParams(location.search).get('oauth_session'); if(session){ history.replaceState({},'',location.pathname); APP_STATE.session=session; sessionStorage.setItem('qh_session',session); refreshMe(); }
}
window.logout=()=>{APP_STATE.session='';APP_STATE.me=null;sessionStorage.removeItem('qh_session');setAuthUI();switchTab('home');};
function setAuthUI(){ const logged=!!APP_STATE.me?.user; $('auth-guest-view').style.display=logged?'none':'flex'; $('auth-user-view').style.display=logged?'flex':'none'; if(logged){const email=APP_STATE.me.user.email||''; $('user-avatar-initial')?.remove(); const avatar=document.querySelector('.user-avatar'); if(avatar)avatar.textContent=(email.split('@')[0]||'Q').charAt(0).toUpperCase();} renderKeys(); }
function renderMe(){ const auto=APP_STATE.me?.subscription?.auto||{}; const balance=fmtBalanceUSD((auto.tokens_total||0)-(auto.tokens_used||0)); const pill=document.querySelector('.header-balance'); if(pill)pill.textContent=balance; APP_STATE.keys=APP_STATE.me.keys||[]; renderKeys(); }
async function refreshMe(){ if(!APP_STATE.session)return; const r=await apiCall('/api/me',{method:'GET'}); if(r.status===200){APP_STATE.me=r.data;renderMe();setAuthUI();}else logout(); }
function renderKeys(){ const box=$('keys-login-box'), table=$('keys-table-container'); if(!box||!table)return; const logged=!!APP_STATE.me; box.style.display=logged?'none':'block'; table.style.display=logged?'block':'none'; if(!logged)return; const keys=APP_STATE.keys||[]; $('keys-table-body').innerHTML=keys.length?keys.map(k=>`<tr><td><strong>${escapeHtml(k.name)}</strong></td><td><code>${escapeHtml(k.prefix)}…</code></td><td>${new Date((k.created_at||0)*1000).toISOString().slice(0,10)}</td><td><span class="key-state ${k.revoked?'revoked':''}">${k.revoked?'Révoquée':'Active'}</span></td><td>${k.revoked?'':`<button class="table-action" onclick="revokeKey(${k.id})">Révoquer</button>`}</td></tr>`).join(''):`<tr><td colspan="5" class="empty-table">Aucune clé. Créez votre première clé.</td></tr>`; }
window.openKeyModal=()=>{if(!APP_STATE.me){openAuth('login');return;}$('key-name-input').value='';$('modal-key').showModal();};
function initKeyCreation(){ $('form-create-key').onsubmit=async e=>{e.preventDefault();const r=await apiCall('/api/keys',{body:{name:$('key-name-input').value.trim()||'Mon agent',plan:'auto'}});if(r.status===200&&r.data.key){$('modal-key').close();$('new-key-val').value=r.data.key;$('modal-key-success').showModal();refreshMe();}else alert(r.data.error?.message||'Impossible de créer la clé');};$('btn-copy-key').onclick=()=>{navigator.clipboard.writeText($('new-key-val').value);$('btn-copy-key').textContent='Copié ✓';};}
window.revokeKey=async id=>{if(!confirm('Révoquer cette clé ?'))return;const r=await apiCall('/api/keys/'+id,{method:'DELETE'});if(r.status===200)refreshMe();};
window.MODEL_STATE={cat:'all',provider:'all',q:''};
window.applyModelFilters=()=>{const s=window.MODEL_STATE;document.querySelectorAll('.model-row').forEach(x=>{const okC=s.cat==='all'||x.dataset.cat===s.cat;const okP=s.provider==='all'||x.dataset.provider===s.provider;const okQ=!s.q||x.dataset.name.includes(s.q);x.style.display=okC&&okP&&okQ?'':'none';});};
window.filterModels=(cat,btn)=>{window.MODEL_STATE.cat=cat;btn.parentElement.querySelectorAll('.filter-btn').forEach(x=>x.classList.remove('active'));btn.classList.add('active');applyModelFilters();};
window.filterProvider=(prov,btn)=>{window.MODEL_STATE.provider=prov;btn.parentElement.querySelectorAll('.filter-btn').forEach(x=>x.classList.remove('active'));btn.classList.add('active');applyModelFilters();};
window.searchModels=q=>{window.MODEL_STATE.q=q.toLowerCase().trim();applyModelFilters();};
window.copyCli=btn=>{navigator.clipboard.writeText('curl -fsSL https://smartapi.cheap/connect.sh | sh').then(()=>{if(btn){btn.textContent='Copié ✓';setTimeout(()=>btn.textContent='Copier',1400);}}).catch(()=>{});};window.copyText=(text,btn)=>{navigator.clipboard.writeText(text).then(()=>{if(btn){btn.textContent='Copié ✓';setTimeout(()=>btn.textContent='Copier',1400);}}).catch(()=>{});};
async function sendChatMessage(text){const box=$('chat-messages');box.querySelector('.chat-empty')?.remove();const u=document.createElement('div');u.className='chat-bubble chat-user';u.textContent=text;box.appendChild(u);const a=document.createElement('div');a.className='chat-bubble chat-assistant';a.textContent=APP_STATE.me?'Créez une clé dans Console pour lancer une requête réelle.':'Connectez-vous puis créez une clé API pour lancer une requête réelle.';box.appendChild(a);}
function initChat(){ $('chat-form').onsubmit=e=>{e.preventDefault();const input=$('chat-input'),text=input.value.trim();if(text)sendChatMessage(text);input.value='';}; }
function initPlayground(){ $('btn-run-playground').onclick=async()=>{const prompt=$('play-user-prompt').value.trim();if(!prompt)return;let key=sessionStorage.getItem('qh_play_key');if(!key){key=promptForKey();if(!key)return;sessionStorage.setItem('qh_play_key',key);}const meta=$('response-meta'),out=$('playground-output');meta.textContent='Routage en cours…';out.textContent='';const t=performance.now();try{const r=await fetch('/v1/chat/completions',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+key},body:JSON.stringify({model:'auto',messages:[{role:'user',content:prompt}],max_tokens:400})});const j=await r.json();meta.textContent=`${r.status} · ${((performance.now()-t)/1000).toFixed(1)} s`;out.textContent=r.ok?(j.choices?.[0]?.message?.content||'Réponse vide'):(j.error?.message||'Erreur');if(APP_STATE.me)refreshMe();}catch(e){meta.textContent='Erreur réseau';out.textContent=e.message;}};}
function promptForKey(){return window.prompt('Votre clé Smart API Cheap (sk-sm-…)');}
function initRedeem(){ $('btn-redeem').onclick=async()=>{const msg=$('redeem-msg'),r=await apiCall('/api/redeem',{body:{code:$('redeem-input').value.trim().toUpperCase()}});msg.hidden=false;msg.textContent=r.status===200?'Crédit activé ✓':(r.data.error?.message||'Code invalide');msg.className=r.status===200?'success-message':'form-error';if(r.status===200){$('redeem-input').value='';refreshMe();}};}
function initRouterStatus(){
  const dot=$('router-live-state'), src=$('router-metric-source'), mdl=$('router-metric-models'), age=$('router-metric-age');
  const badge=document.querySelector('.live-badge');
  fetch(API+'/health').then(r=>r.ok?r.json():null).then(d=>{
    const m=d&&d.market30; if(!m) throw new Error('etat indisponible');
    const minutes=Math.max(0,Math.round((m.age_s||0)/60));
    if(src)src.textContent=m.src==='moy30'?'30 j':'24 h';
    if(mdl)mdl.textContent=String(m.models||0);
    if(age)age.textContent=minutes<=1?'à l’instant':minutes+' min';
    if(dot){dot.classList.add('ok');dot.innerHTML='<i></i> routeur actif';}
    if(badge)badge.innerHTML='<b></b> routeur actif';
  }).catch(()=>{ if(dot){dot.classList.add('ko');dot.textContent='état indisponible';} if(badge)badge.innerHTML='<b></b> routeur'; });
}

function modelCuts(){
  const m={};
  document.querySelectorAll('.model-row').forEach(r=>{
    const s=r.querySelector('.model-identity strong'),d=r.querySelector('.discount'),p=r.querySelectorAll('.price-cell.ours b');
    if(!s||!d)return;
    m[s.textContent.trim().toLowerCase().replace(/[\s_]+/g,'-')]={cut:d.textContent.trim(),price:(p.length>=2?p[0].textContent.trim()+' · '+p[1].textContent.trim()+' /M':'')};
  });
  return m;
}

function initAutoMix(){
  const svg=$('automix-donut'), legend=$('automix-legend'), total=$('automix-total'), count=$('automix-count');
  if(!svg) return;
  fetch(API+'/api/auto-mix',{method:'GET'}).then(r=>r.ok?r.json():null).then(d=>{
    if(!d || !d.total || !(d.mix||[]).length){
      if(total) total.textContent='collecte en cours';
      if(legend) legend.innerHTML='<span class="auto-mix-hint">Le routeur n\u2019a pas encore publié de trafic sur les dernières 24 h.</span>';
      if(count) count.textContent='0';
      return;
    }
    const COLORS=['#5de5e1','#9876ff','#ffd479','#6ef0b0','#61a8ff','#ff8d9d','#8ef0e8','#b78cff','#7fb2ff','#9ff7c8'];
    const items=d.mix.slice(0,10), totalN=d.total, R=52, C=2*Math.PI*R;
    let acc=0, segs='';
    items.forEach((it,i)=>{ const frac=it.n/totalN, len=frac*C, col=COLORS[i%COLORS.length];
      segs+=`<circle r="${R}" cx="60" cy="60" fill="none" stroke="${col}" stroke-width="14" stroke-dasharray="${len} ${C-len}" stroke-dashoffset="${-acc}" transform="rotate(-90 60 60)"/>`;
      acc+=len; });
    svg.innerHTML=segs;
    if(count) count.textContent=String(totalN);
    if(total) total.textContent=totalN.toLocaleString('fr-FR')+' requêtes';
    const CUTS=modelCuts();
    const pcts=items.map(it=>Math.round(100*it.n/totalN));const ps=pcts.reduce((a,b)=>a+b,0);
    if(pcts.length&&ps!==100)pcts[pcts.length-1]=Math.max(0,pcts[pcts.length-1]+100-ps);
    if(legend) legend.innerHTML=items.map((it,i)=>{const meta=CUTS[String(it.model||'').trim().toLowerCase().replace(/[\s_]+/g,'-')]||{};return `<div class="auto-mix-item"><i style="background:${COLORS[i%COLORS.length]}"></i><span>${escapeHtml(it.model)}</span>${meta.price?`<em class="auto-mix-price">${escapeHtml(meta.price)}</em>`:''}${meta.cut?`<em class="auto-mix-cut">${escapeHtml(meta.cut)}</em>`:''}<b>${pcts[i]}%</b></div>`;}).join('');
  }).catch(()=>{ if(total) total.textContent='indisponible'; });
}

/* — Journaux (11-09) : historique requêtes / tokens / dépenses, sans état fictif — */
async function loadUsage(){
  const box=$('usage-login-box'), content=$('usage-content');
  if(!box||!content)return;
  if(!APP_STATE.session){ box.style.display='block'; content.style.display='none'; return; }
  box.style.display='none'; content.style.display='block';
  const r=await apiCall('/api/usage?limit=50',{method:'GET'});
  if(r.status!==200){ $('usage-table-body').innerHTML='<tr><td colspan="6" class="empty-table">'+escapeHtml(r.data.error?.message||'Journaux indisponibles')+'</td></tr>'; return; }
  const d=r.data||{}, nf=n=>Number(n||0).toLocaleString('fr-FR');
  $('usage-stats').innerHTML =
    `<div class="usage-stat"><b>${nf(d.totals?.requests)}</b><span>Requêtes au total</span></div>`+
    `<div class="usage-stat"><b>${nf(d.totals?.tokens)}</b><span>Tokens facturés</span></div>`+
    `<div class="usage-stat"><b>$${Number(d.totals?.cost_usd||0).toFixed(4)}</b><span>Coût réel des requêtes</span></div>`;
  const days=d.per_day||[], mx=Math.max(1,...days.map(x=>x.tokens||0));
  $('usage-chart').innerHTML = days.length ? days.map(x=>`<div class="usage-bar" title="${escapeHtml(x.d)} · ${nf(x.tokens)} tokens"><i style="height:${Math.max(3,Math.round(100*(x.tokens||0)/mx))}%"></i><span>${escapeHtml((x.d||'').slice(5))}</span></div>`).join('') : '<span class="auto-mix-hint">Aucune requête sur les 30 derniers jours.</span>';
  const rows=d.rows||[];
  $('usage-table-body').innerHTML = rows.length ? rows.map(x=>`<tr><td>${new Date((x.ts||0)*1000).toLocaleString('fr-FR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})}</td><td><code>${escapeHtml(x.model)}</code></td><td>${nf(x.in)}</td><td>${nf(x.out)}</td><td><b>${nf(x.tokens)}</b></td><td>$${Number(x.cost_usd||0).toFixed(5)}</td></tr>`).join('') : '<tr><td colspan="6" class="empty-table">Aucune requête pour le moment — lancez-en une depuis le playground ou avec votre clé.</td></tr>';
  const items=d.per_model||[], COLORS=['#5de5e1','#9876ff','#ffd479','#6ef0b0','#61a8ff','#ff8d9d','#8ef0e8','#b78cff','#7fb2ff','#9ff7c8'];
  $('usage-models').innerHTML = items.length ? items.map((it,i)=>`<div class="usage-model-item"><i style="background:${COLORS[i%COLORS.length]}"></i><span>${escapeHtml(it.model)}</span><b>${nf(it.tokens)} tok · ${nf(it.n)} req</b></div>`).join('') : '<span class="auto-mix-hint">Pas encore de données.</span>';
  $('usage-refresh-note').textContent='mis à jour à '+new Date().toLocaleTimeString('fr-FR');
}
document.addEventListener('DOMContentLoaded',()=>{document.querySelectorAll('.nav-link').forEach(x=>x.onclick=()=>switchTab(x.dataset.tab));initAuth();initKeyCreation();initChat();initPlayground();initRedeem();initRouterStatus();initAutoMix();const menu=$('mobile-menu-toggle'),nav=$('main-nav');menu.onclick=()=>{const open=nav.classList.toggle('open');menu.setAttribute('aria-expanded',open);menu.textContent=open?'×':'☰';};nav.querySelectorAll('.nav-link').forEach(x=>x.addEventListener('click',()=>{nav.classList.remove('open');menu.setAttribute('aria-expanded','false');menu.textContent='☰';}));if(APP_STATE.session)refreshMe();});
