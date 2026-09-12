#!/usr/bin/env python3
"""
Quota.Hub Gateway v1 — Passerelle d'abonnement IA.
Produit : abonnement $10 = 1 milliard de tokens (30 jours).
Le client NE CHOISIT PAS le modèle : le routeur interne sert TOUJOURS
le canal le moins cher vivant (floor fiabilité 80 %, hystérésis 15 %
pour préserver le cache de prompts, cooldowns automatiques).

Sécurité :
  - Le front public ne parle JAMAIS directement à cette passerelle : il passe
    par la fonction Vercel /gw/* qui injecte l'en-tête X-QH-Internal (secret
    côté serveur, jamais dans le JS public). Sans ce header -> 403.
  - Mots de passe : scrypt (sel aléatoire). Clés API : sha256 (jamais en clair).
  - Sessions : token HMAC signé (30 j). Rate-limit login (5 échecs -> 15 min).
  - Rate-limit API : 60 req/min par clé (burst 10).
  - L'endpoint /v1/chat/completions ignore totalement le champ "model".
  - Aucune réponse simulée : si l'amont échoue -> 502 typé, 0 token facturé.

Endpoints (derrière le front signé) :
  POST /api/auth/register      {email, password}
  POST /api/auth/login         {email, password} -> session
  GET  /api/me                 -> abonnement + clés + conso
  POST /api/keys               {name} -> clé (affichée UNE fois)
  DELETE /api/keys/<id>        -> révocation
  POST /api/redeem             {code} -> active/étend l'abonnement
  POST /v1/chat/completions    Bearer sk-qh-*, model ignoré
  GET  /health                 statut public minimal (aucune donnée sensible)
Loopback uniquement (ops SSH) :
  POST /admin/codes  X-Admin-Token  {tokens} -> codes d'activation
  GET  /admin/stats       X-Admin-Token     -> stats globales
"""
import json, os, re, ssl, sys, time, hmac, hashlib, secrets, sqlite3, threading, traceback, urllib.request, urllib.error, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import queue

DIR = os.path.dirname(os.path.abspath(__file__))

# ── Configuration (env ou fichier .env local, jamais dans le repo) ──────────
def _load_env_file():
    p = os.path.join(DIR, '.env')
    if not os.path.exists(p):
        return
    for line in open(p, encoding='utf-8'):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())
_load_env_file()

PORT        = int(os.environ.get('QH_PORT', '8890'))
DB_PATH     = os.environ.get('QH_DB', os.path.join(DIR, 'hub.db'))
SECRET      = os.environ.get('QH_INTERNAL_SECRET', '')      # HMAC front<->gateway
SESSION_SEC = os.environ.get('QH_SESSION_SECRET', '')       # signature sessions
ADMIN_TOKEN = os.environ.get('QH_ADMIN_TOKEN', '')          # ops loopback
KEY_FILE    = os.environ.get('A6API_KEY_PATH', os.path.join(DIR, 'key.json'))

def _load_key():
    try:
        k = json.load(open(KEY_FILE, encoding='utf-8')).get('api_key', '')
        if k.startswith('sk-'):
            return k
    except Exception:
        pass
    k = os.environ.get('A6API_KEY', '')
    if k.startswith('sk-'):
        return k
    raise SystemExit('Clé A6API amont introuvable (A6API_KEY_PATH / A6API_KEY)')
UPSTREAM_KEY = _load_key()
UPSTREAM_URL = 'https://api.a6api.com/v1/chat/completions'
MKT_URL      = 'https://a6api.com/api/marketplace/public/channels/search'

# ── Politique produit ───────────────────────────────────────────────────────
# Canaux flash éligibles au plan abonnement (les moins chers du marché, floor 80 %).
# AUCUN modèle premium : c'est ce qui borne le coût amont et rend le plan rentable.
# Pool AUTO : famille flash polyvalente. Les variantes deepseek v4 (latest/vision)
# sans canal vivant aujourd'hui sont conservées : dès qu'un fournisseur en liste un,
# le market scan les inclut automatiquement (aucun redeploy).
MODELS = ['qwen3.8-flash', 'grok-4.6', 'glm-5.3-flash',
          'deepseek-v4-pro', 'deepseek-v4-flash',
          'deepseek-v4.1-flash', 'deepseek-v4-flash-vision', 'deepseek-v4-vision']
# Fournisseurs de confiance (données 24h réelles 2026-09-09) : cache hit élevé + succès stable.
# tokentrans = ancre (le moins cher sur qwen, présent sur les 3 modèles, cache ~76-82 %).
# Changement de modèle = perte du cache amont → on reste sur le MÊME fournisseur tant qu'il vit.
TRUSTED_SUPPLIERS = ['tokentrans', '国产', 'bbgt-vip', 'deepseek线路']
GEMINI_MODEL = 'gemini-3.8-flash'
PLANS = ('auto', 'gemini')
PLAN_DEFAULT = {'auto': 1_000_000_000, 'gemini': 100_000_000}   # tokens par code
SUCCESS_SCALE = 10000
MIN_SUCCESS_RAW = int(80 * SUCCESS_SCALE / 100)   # floor fiabilité 80 %
HYSTERESIS = 0.30                                  # pin canal chaud (cache prompts)
PIN_MIN_HOLD_S = 21600                             # 6 h de retenue mini du modèle élu
PIN_SWITCH_PCT = 50                                # pendant la retenue : basculer seulement
                                                    # si l'alternative est ≥ 50 % moins chère
MARKET_TTL = 1200                                  # s (marché instantané, 24 h) : suit le
                                                    # cycle du sondeur partagé (20 min)
MKT30_URL = 'http://127.0.0.1:8891/api/prices'     # marché 30 j — worker local (même VPS)
MKT30_TTL = 1200                                   # s — cache mémoire de la vue 30 j
                                                    # (aligne sur le cycle du sondeur, 20 min)
MKT30_MAX_AGE_S = 2700                             # fraîcheur exigée du worker (age_s)
MKT30_FLOOR_WORST = 80.0                           # floor fiabilité « pire heure » (moy30)
MKT30_MIN_SAMPLES = 200                            # volume minimal pour juger un canal
COOLDOWN_WAIT_MAX_S = 15                           # anti-503 : attente bornée avant refus
                                                   # (budget front Vercel : maxDuration 120 s)
# ── Budget de temps (front Vercel : maxDuration 120 s) ──────────────────────
REQUEST_BUDGET_S = 105                             # mur interne : on rend la main AVANT Vercel (120 s)
FIRST_BYTE_MAX_S = 45                              # attente max du 1er chunk streaming avant bascule
HEARTBEAT_S = 8                                    # keep-alive SSE pendant l'attente amont
STREAM_TIMEOUT_S = 100                             # lecture amont bornée sous le plafond Vercel
MAX_TOKENS_CAP = 8000                              # plafond par requête (résumés de compression)
RATE_RPM = 60                                      # requêtes/min par clé
RATE_BURST = 10
SESSION_TTL = 30 * 86400

LOCK = threading.Lock()
MKT = {}                 # model -> {'r': ..., 'ts': ...}
MKT_BUSY = set()
MKT30 = {'d': None, 'ts': 0.0, 'busy': False}   # vue marché 30 j (worker local)
COOLDOWN = {}
COOLDOWN_PATH = os.path.join(DIR, 'cooldowns.json')

# ── Pins par conversation (V3 multi-utilisateurs) ───────────────────────────
# Le pin historique était GLOBAL (un seul modèle élu pour tout le service) :
# dès qu'il y a plusieurs clients, chaque conversation cassait le cache des
# autres. V3 : l'état de routage vit PAR CLÉ API ET PAR CONVERSATION — chaque
# client garde SA conversation sur SON modèle tant que le cache chaud le
# justifie ; une conversation neuve part directement sur le moins cher.
CONV_TTL = 7200            # s — durée de vie d'un pin de conversation (2 h d'activité)
CONV_SWITCH_MARGIN = 0.15  # casser une conv chaude exige ≥15 % de gain réel
CONV_MAX = 20000           # borne mémoire : prune TTL + LRU au-delà
CONV = {}                  # (key_id, sig) -> {'model','supplier','ts','tin','tout','cached'}
CONV_LOCK = threading.Lock()

# ── Cache prompt : critère INDISPENSABLE du choix (11-09) ───────────────────
# Certains canaux amont ne proposent PAS de cache prompt. Sans cache, chaque tour
# d'une conversation repaie l'input au prix plein (au lieu de ~0,1x) : le coût
# réel explose. Dès qu'une requête porte un vrai contexte, les canaux sans cache
# sont écartés du choix tant qu'un canal cache-capable existe dans le pool.
CACHE_MIN_TOKENS = 1500    # taille de prompt au-delà de laquelle le cache pèse vraiment

def has_cache(b):
    """Le canal propose-t-il un VRAI cache prompt ? (remise cache_read effective
    ou hit constaté ≥ 30 %)."""
    cr = b.get('cache_read') or 0
    i = b.get('in') or 0
    hit = b.get('cache24') or 0
    if cr > 0 and i > 0 and cr <= 0.5 * i:
        return True
    try:
        return float(hit) >= 30
    except Exception:
        return False

def conv_signature(payload):
    """Empreinte stable d'une conversation : le system (tronqué) + le PREMIER
    message non-system. Ces éléments existent dès le premier tour et ne changent
    jamais quand la conversation s'allonge -> toute la vie de la conversation
    partage la même empreinte (donc le même pin de modèle)."""
    msgs = payload.get('messages') or []
    parts = []
    anchored = False
    for m in msgs:
        if not isinstance(m, dict):
            continue
        role = str(m.get('role') or '')
        cont = m.get('content')
        if isinstance(cont, list):
            cont = ''.join(str(x.get('text') or '') for x in cont if isinstance(x, dict))
        cont = str(cont or '')
        if role == 'system':
            if cont:
                parts.append('system:' + cont[:256])
            continue
        if cont:                     # premier message non-system : l'ancre
            parts.append(role + ':' + cont[:1536])
            anchored = True
            break
    if not anchored or not parts:
        return ''
    return hashlib.sha1('\n'.join(parts).encode('utf-8', 'ignore')).hexdigest()[:16]

def conv_prune():
    """Borne mémoire des pins de conversation : purge TTL puis LRU (jamais
    appelée avec CONV_LOCK déjà pris)."""
    now = time.time()
    with CONV_LOCK:
        dead = [k for k, v in CONV.items() if now - (v.get('ts') or 0) > CONV_TTL * 3]
        for k in dead:
            CONV.pop(k, None)
        if len(CONV) > CONV_MAX:
            for k, _v in sorted(CONV.items(), key=lambda kv: kv[1].get('ts') or 0)[:len(CONV) - CONV_MAX]:
                CONV.pop(k, None)

def cooldowns_save():
    try:
        with LOCK:
            snap = {m: [u, r] for m, (u, r) in COOLDOWN.items()}
        with open(COOLDOWN_PATH, 'w') as f:
            json.dump(snap, f)
    except Exception:
        pass

def cooldowns_load():
    try:
        with open(COOLDOWN_PATH) as f:
            snap = json.load(f)
        now = time.time()
        for m, v in snap.items():
            if v[0] > now:
                COOLDOWN[m] = (v[0], v[1])
    except Exception:
        pass            # model -> (until_ts, reason)
PIN = {'model': None, 'since': 0.0}
NET_FAIL_TS = []         # détection de crise plateforme
LOGIN_FAILS = {}         # (ip, email) -> [ts_list]
RATE = {}                # key_id -> [ts_rolling]

def log(msg):
    line = time.strftime('%Y-%m-%d %H:%M:%S') + ' ' + str(msg)
    try:
        print(line, flush=True)
    except Exception:
        pass
    try:
        with open(os.path.join(DIR, 'gateway.log'), 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass

# ── Base de données ─────────────────────────────────────────────────────────
def db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=5000')
    conn.row_factory = sqlite3.Row
    return conn

def _ensure_cols(c, table, coldef):
    cols = [r[1] for r in c.execute(f'PRAGMA table_info({table})').fetchall()]
    name = coldef.split()[0]
    if name not in cols:
        try:
            c.execute(f'ALTER TABLE {table} ADD COLUMN {coldef}')
        except Exception:
            pass

def init_db():
    c = db()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        pw_hash TEXT NOT NULL,
        created_at INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS subscriptions(
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        plan TEXT NOT NULL DEFAULT 'auto',
        tokens_total INTEGER NOT NULL DEFAULT 0,
        tokens_used INTEGER NOT NULL DEFAULT 0,
        activated_at INTEGER,
        status TEXT NOT NULL DEFAULT 'inactive',
        PRIMARY KEY(user_id, plan));
    CREATE TABLE IF NOT EXISTS api_keys(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        key_hash TEXT UNIQUE NOT NULL,
        prefix TEXT NOT NULL,
        name TEXT NOT NULL DEFAULT 'Clé',
        plan TEXT NOT NULL DEFAULT 'auto',
        created_at INTEGER NOT NULL,
        revoked INTEGER NOT NULL DEFAULT 0,
        last_used INTEGER);
    CREATE TABLE IF NOT EXISTS usage_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL, key_id INTEGER,
        model_served TEXT, supplier TEXT,
        prompt_tokens INTEGER, completion_tokens INTEGER,
        tokens INTEGER, cost_amont_usd REAL,
        created_at INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS codes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code_hash TEXT UNIQUE NOT NULL,
        tokens INTEGER NOT NULL,
        plan TEXT NOT NULL DEFAULT 'auto',
        created_at INTEGER NOT NULL,
        used_by INTEGER, used_at INTEGER);
    CREATE TABLE IF NOT EXISTS auth_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event TEXT, email TEXT, ip TEXT, ok INTEGER, ts INTEGER NOT NULL);
    ''')
    # migration ancien schéma (users=0 en prod → recréation sûre)
    try:
        cols = [r[1] for r in c.execute('PRAGMA table_info(subscriptions)').fetchall()]
        if 'plan' not in cols:
            c.execute('DROP TABLE subscriptions')
            c.execute('''CREATE TABLE subscriptions(
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                plan TEXT NOT NULL DEFAULT 'auto',
                tokens_total INTEGER NOT NULL DEFAULT 0,
                tokens_used INTEGER NOT NULL DEFAULT 0,
                activated_at INTEGER,
                status TEXT NOT NULL DEFAULT 'inactive',
                PRIMARY KEY(user_id, plan))''')
            c.execute("INSERT INTO subscriptions(user_id,plan,status) SELECT id,'auto','inactive' FROM users")
    except Exception:
        pass
    try:
        kcols = [r[1] for r in c.execute('PRAGMA table_info(api_keys)').fetchall()]
        if 'plan' not in kcols:
            c.execute("ALTER TABLE api_keys ADD COLUMN plan TEXT NOT NULL DEFAULT 'auto'")
    except Exception:
        pass
    c.execute('CREATE INDEX IF NOT EXISTS idx_usage_user ON usage_logs(user_id, id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_keys_user ON api_keys(user_id)')
    _ensure_cols(c, 'codes', "plan TEXT NOT NULL DEFAULT 'auto'")
    _ensure_cols(c, 'usage_logs', "plan TEXT NOT NULL DEFAULT 'auto'")
    _ensure_cols(c, 'usage_logs', 'model_requested TEXT')
    c.commit(); c.close()

def audit(event, email, ip, ok):
    try:
        c = db()
        c.execute('INSERT INTO auth_log(event,email,ip,ok,ts) VALUES(?,?,?,?,?)',
                  (event, (email or '')[:80], (ip or '')[:64], int(bool(ok)), int(time.time())))
        c.execute('DELETE FROM auth_log WHERE ts < ?', (int(time.time()) - 90 * 86400,))
        c.commit(); c.close()
    except Exception:
        pass

# ── Moteur de routage (toujours le moins cher) ──────────────────────────────
def marketplace_best(model_id):
    url = f'{MKT_URL}?page=1&page_size=50&model={urllib.parse.quote(model_id)}&sort=price'
    r = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + UPSTREAM_KEY,
                                             'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(r, timeout=15) as resp:
        d = json.loads(resp.read().decode())
    items = d.get('data', {}).get('items', [])
    alive = [i for i in items if not i.get('supplier_channel_disabled')
             and i.get('listing_availability') == 1
             and (i.get('recent_success_rate') or 0) >= MIN_SUCCESS_RAW
             and (i.get('sample_count') or 0) >= 20]
    trusted = [i for i in alive if str(i.get('supplier_nickname')) in TRUSTED_SUPPLIERS]
    def expected(i):
        s = max((i.get('recent_success_rate') or 0) / SUCCESS_SCALE, 0.01)
        return i.get('input_price_micros', 10**18) / s
    pool = trusted or alive   # si aucun canal de confiance, on retombe sur tous
    pool.sort(key=expected)
    if not pool:
        return {'best': None, 'n_alive': 0, 'trusted_alive': 0}
    b = pool[0]
    return {'best': {'supplier': b.get('supplier_nickname'),
                     'in': b.get('input_price_micros', 0) / 1e6,
                     'out': b.get('output_price_micros', 0) / 1e6,
                     'cache_read': b.get('cache_read_price_micros', 0) / 1e6,
                     'cache24': ((i_cache24 := b.get('cache_hit_rate_24h')) or 0) / 100.0 if b.get('cache_hit_rate_24h') else None,
                     'success': (b.get('recent_success_rate') or 0) / SUCCESS_SCALE * 100},
            'n_alive': len(alive),
            'n_trusted': len(trusted)}

def market_get(model_id, max_age=MARKET_TTL):
    now = time.time()
    with LOCK:
        ent = MKT.get(model_id)
        if ent and now - ent['ts'] < max_age:
            return ent['r']
        if model_id in MKT_BUSY:
            return (ent or {}).get('r')
        MKT_BUSY.add(model_id)
    def _bg():
        try:
            r = marketplace_best(model_id)
            with LOCK: MKT[model_id] = {'r': r, 'ts': time.time()}
        except Exception:
            pass
        finally:
            with LOCK: MKT_BUSY.discard(model_id)
    threading.Thread(target=_bg, daemon=True).start()
    return (ent or {}).get('r')

# ── Marché 30 jours (worker local) : source de DÉCISION ─────────────────────
# Le worker quota-market publie en loopback la moyenne 30 j PONDÉRÉE PAR LE TEMPS
# (in/out/cache) et la fiabilité « pire heure » de chaque canal. On décide dessus :
# un canal stable sur 30 j vaut mieux qu'un pic de prix instantané. Les prix
# instantanés du worker servent, eux, à facturer le coût RÉEL de la requête.
def _mkt30_fetch():
    req = urllib.request.Request(MKT30_URL, headers={'User-Agent': 'quota-hub-gateway'})
    with urllib.request.urlopen(req, timeout=8) as resp:
        d = json.loads(resp.read().decode())
    if not d.get('ok') or d.get('stale'):
        return None
    if float(d.get('age_s') or 0) > MKT30_MAX_AGE_S:
        return None
    return d

def market30_all(max_age=MKT30_TTL):
    """Dernière vue 30 j connue ; rafraîchie en tâche de fond, jamais bloquante."""
    now = time.time()
    with LOCK:
        ent = MKT30['d']
        if (ent and now - MKT30['ts'] < max_age) or MKT30['busy']:
            return ent
        MKT30['busy'] = True
    def _bg():
        try:
            d = _mkt30_fetch()
            if d:
                with LOCK:
                    MKT30['d'] = d
                    MKT30['ts'] = time.time()
        except Exception as e:
            log(f'MOY30 indisponible: {str(e)[:70]}')
        finally:
            MKT30['busy'] = False
    threading.Thread(target=_bg, daemon=True).start()
    return ent

def market30_best(model_id):
    """Meilleur canal 30 j d'un modèle (même forme que marketplace_best), ou None
    si la vue 30 j est absente/périmée -> repli marché instantané."""
    d = market30_all() or {}
    ent = (d.get('models') or {}).get(model_id) or {}
    top = ent.get('top') or []
    if not top:
        return None
    t = top[0]
    if not t.get('available') or t.get('disabled'):
        return None
    if (t.get('worst') or 0) < MKT30_FLOOR_WORST or (t.get('n24') or 0) < MKT30_MIN_SAMPLES:
        return None
    return {'best': {'supplier': t.get('supplier'),
                     'in': t.get('in_now', 0), 'out': t.get('out_now', 0),
                     'cache_read': t.get('cache_now', 0),
                     'cache24': t.get('cache'),
                     'success': t.get('sr24', 0),
                     'cost30': t.get('cost30'), 'worst': t.get('worst'),
                     'n24': t.get('n24'), 'src': 'moy30'},
            'n_alive': ent.get('n_robust', 0), 'n_total': ent.get('n_listings', 0),
            'src': 'moy30'}

def warm_market():
    def _all():
        market30_all(max_age=0)      # vue 30 j (worker local) — décision
        for m in MODELS:
            for attempt in range(5):
                try:
                    r = marketplace_best(m)
                    with LOCK: MKT[m] = {'r': r, 'ts': time.time()}
                    break
                except Exception as e:
                    log(f'MARCHE {m} essai {attempt+1}: {str(e)[:60]}')
                    time.sleep(2 * (attempt + 1))
    threading.Thread(target=_all, daemon=True).start()

def in_cooldown(model_id):
    until, reason = COOLDOWN.get(model_id, (0, ''))
    return time.time() < until, reason

def on_failure(model_id, msg):
    # une erreur param client (400/401/402/413) n'est pas une panne du canal
    if isinstance(msg, str) and re.match(r'^HTTP (400|401|402|413)\b', msg):
        return
    with LOCK:
        now = time.time()
        NET_FAIL_TS.append(now)
        while NET_FAIL_TS and now - NET_FAIL_TS[0] > 120:
            NET_FAIL_TS.pop(0)
        crisis = len(NET_FAIL_TS) >= 2
        dur = 60 if crisis else 90          # crise plateforme -> récupération rapide
        COOLDOWN[model_id] = (now + dur, (msg or '')[:60])
    cooldowns_save()

def pick_model(models, ctx=None):
    """Choix cache-first MULTI-UTILISATEURS (V3) : le pin vit PAR CLÉ API ET
    PAR CONVERSATION (ctx = {'key_id', 'sig'}). Tant que la conversation est
    chaude, on garde son modèle sauf si le gain réel dépasse la perte de cache
    estimée (marge CONV_SWITCH_MARGIN) ; une conversation neuve part au moins
    cher. Sans contexte (appels internes), repli sur le pin global historique.

    Coût espéré : moyenne 30 j pondérée temps du worker local quand elle est
    disponible (stable, insensible aux pics), sinon marché instantané 24 h."""
    cand = []
    for m in models:
        cd, _ = in_cooldown(m)
        if cd:
            continue
        # 1) DÉCISION sur la moyenne 30 j (cache-aware, fiabilité pire heure)
        b = (market30_best(m) or {}).get('best')
        if b and b.get('cost30'):
            success = max(b['success'] / 100.0, 0.01)
            cand.append((b['cost30'] / success, m, b))
            continue
        # 2) repli : marché instantané (24 h)
        r = market_get(m)
        b = (r or {}).get('best')
        if not b:
            continue
        success = max(b['success'] / 100.0, 0.01)
        # coût espéré CACHE-AWARE : le hit réel du canal (cache24) réduit le prix input
        # au prix cache_read. Un canal qui annonce un cache et ne l'honore pas
        # (deepseek chez certains) sort naturellement du classement après mesure.
        chit = max(0.0, min(0.95, (b.get('cache24') or 0) / 100.0))
        eff_in = b['in'] * (1 - chit) + b.get('cache_read', b['in']) * chit
        cand.append(((eff_in + b['out']) / 2 / success, m, b))
    if not cand:
        return None, None
    # CACHE INDISPENSABLE (11-09) : pour une requête qui porte un vrai contexte,
    # on écarte les canaux SANS cache prompt tant qu'un canal cache-capable
    # existe. Sans cache, chaque tour repaie l'input plein : le prix affiché
    # ment. Les petites requêtes (one-shot) gardent le classement par prix pur.
    tin_need = int((ctx or {}).get('tin_est') or 0)
    if tin_need >= CACHE_MIN_TOKENS:
        with_cache = [x for x in cand if has_cache(x[2])]
        if with_cache:
            cand = with_cache
    cand.sort(key=lambda x: x[0])
    best_cost = cand[0][0]
    # 1) PIN PAR CONVERSATION (V3) : chaque clé API garde SA conversation sur SON
    #    modèle tant que le cache chaud vaut plus que le gain d'une bascule. Le
    #    calcul oppose « rester » (la part cachée du contexte est au prix
    #    cache_read) à « switcher » (tout au prix plein, cache froid).
    if ctx and ctx.get('sig') and ctx.get('key_id') is not None:
        st = None
        with CONV_LOCK:
            st = CONV.get((ctx['key_id'], ctx['sig']))
        if st and time.time() - (st.get('ts') or 0) > CONV_TTL:
            st = None
        if st and st.get('model'):
            hit = next((x for x in cand if x[1] == st['model']), None)
            if hit is not None:
                curb = hit[2]
                tin = max(int(st.get('tin') or 0), 0)
                tcas = min(int(st.get('cached') or 0), tin)
                tout = max(int(st.get('tout') or 0), 0)
                rester = ((tin - tcas) * curb.get('in', 0) + tcas * curb.get('cache_read', curb.get('in', 0))
                          + tout * curb.get('out', 0))
                newb = cand[0][2]
                switcher = tin * newb.get('in', 0) + tout * newb.get('out', 0)
                if tin <= 0 or switcher > rester * (1.0 - CONV_SWITCH_MARGIN):
                    cand.sort(key=lambda x: 0 if x[1] == st['model'] else 1)
                    return cand[0][1], cand
                # bascule justifiée : préférer un modèle du MÊME fournisseur
                # (cache amont rattaché au supplier) si le surcoût ≤ +25 %.
                ps = next((x for x in cand if x[1] != st['model']
                           and x[2].get('supplier') == st.get('supplier')), None)
                if ps is not None and ps[0] <= best_cost * 1.25:
                    cand.sort(key=lambda x: 0 if x[1] == ps[1] else 1)
                    return cand[0][1], cand
    if not (ctx and ctx.get('sig')) and PIN.get('model'):
        pc = next((c for c, m, _ in cand if m == PIN['model']), None)
        if pc is not None:
            marge = HYSTERESIS
            since = PIN.get('since') or 0.0
            if PIN_MIN_HOLD_S and (time.time() - since) < PIN_MIN_HOLD_S:
                marge = max(marge, PIN_SWITCH_PCT / 100.0)
            if pc <= best_cost * (1 + marge):
                cand.sort(key=lambda x: 0 if x[1] == PIN['model'] else 1)
                with LOCK:
                    if PIN.get('model') != cand[0][1]:
                        PIN['since'] = time.time()
                    PIN['model'] = cand[0][1]
                return cand[0][1], cand
    # 2) pin fournisseur global (appels sans contexte de conversation)
    if not (ctx and ctx.get('sig')) and PIN.get('supplier'):
        ps = next((t for t, m, b in cand if b.get('supplier') == PIN['supplier']), None)
        if ps is not None and ps <= best_cost * 1.25:
            with LOCK:
                newm = next(m for c, m, b in cand if b.get('supplier') == PIN['supplier'])
                if PIN.get('model') != newm:
                    PIN['since'] = time.time()
                PIN['model'] = newm
            return PIN['model'], cand
    with LOCK:
        if PIN.get('model') != cand[0][1]:
            PIN['since'] = time.time()
        PIN['model'] = cand[0][1]
        PIN['supplier'] = cand[0][2].get('supplier')
    return cand[0][1], cand

def wait_or_last_resort(models, ctx=None):
    """ANTI-503 (repris du routeur v2.2.3) : « tous les canaux en cooldown » n'est
    PAS une panne. Un 503 instantané tue le tour entier d'un agent (rapport, tâche
    longue). On attend donc la fin du cooldown le plus proche (borné par
    COOLDOWN_WAIT_MAX_S) en retentant le routage normal, puis, en véritable dernier
    recours, on essaie le canal le moins cher malgré son cooldown — un essai réel
    vaut mieux qu'un refus sec (le cooldown est un compteur interne, pas une preuve
    que l'amont est mort)."""
    t_dead = time.time() + COOLDOWN_WAIT_MAX_S
    while True:
        with LOCK:
            ups = [u - time.time() for (u, _r) in list(COOLDOWN.values()) if u > time.time()]
        if not ups:
            break
        soon = min(ups)
        if soon > COOLDOWN_WAIT_MAX_S or time.time() >= t_dead:
            break
        log(f'ATTENTE cooldown {round(soon, 1)}s avant nouvel essai (anti-503)')
        time.sleep(min(max(soon, 0.5), 3.0))
        m, c = pick_model(models, ctx)
        if m:
            return m, c
    lr = []
    for m in models:
        b = (market30_best(m) or {}).get('best') or (market_get(m) or {}).get('best')
        if not b:
            continue
        s_ok = max(float(b.get('success', 100) or 100) / 100.0, 0.01)
        base = b['cost30'] if b.get('cost30') else (b.get('in', 0) + b.get('out', 0)) / 2
        lr.append((base / s_ok, m))
    lr.sort(key=lambda x: x[0])
    if not lr:
        with LOCK:
            pin = PIN.get('model')
        lr = [(0.0, pin or models[0])]
    log(f'DERNIER RECOURS {lr[0][1]} (cooldown ignoré) — essai unique')
    return lr[0][1], []

def upstream_timeout(tin_est):
    """Budget d'attente amont adapté à la taille du prompt, borné sous le plafond Vercel (120 s)."""
    if tin_est >= 8000:
        return 75
    return 45

def parse_upstream_response(raw_bytes, requested_model, payload=None):
    """Décode la réponse amont : accepte indifféremment un JSON pur ou un flux
    SSE (text/event-stream) renvoyé par certains fournisseurs (ex: canal glm-5.3-flash).
    Reconstitue un objet chat.completion OpenAI standard complet."""
    text = raw_bytes.decode('utf-8', errors='replace').strip()
    if not text:
        raise ValueError("reponse amont vide")
    if text.startswith('{'):
        try:
            data = json.loads(text)
            if isinstance(data, dict) and 'choices' in data and data['choices']:
                c0 = data['choices'][0]
                if isinstance(c0, dict):
                    fr = c0.get('finish_reason')
                    msg = c0.get('message') or {}
                    txt = msg.get('content') or ''
                    # Si finish_reason == 'length' mais qu'un texte substantiel est présent,
                    # normaliser en 'stop' pour éviter que Hermes rejette la compression.
                    if fr == 'length' and len(txt) >= 200:
                        c0['finish_reason'] = 'stop'
            return data
        except Exception:
            pass

    full_content = []
    reasoning_content = []
    finish_reason = None
    usage = None
    created = int(time.time())
    res_id = f"chatcmpl-{secrets.token_hex(12)}"
    model_ret = requested_model

    for line in text.splitlines():
        line = line.strip()
        if not line or not line.startswith('data:'):
            continue
        data_str = line[5:].strip()
        if data_str == '[DONE]':
            continue
        try:
            obj = json.loads(data_str)
        except Exception:
            continue

        if 'id' in obj and obj['id']:
            res_id = obj['id']
        if 'created' in obj and obj['created']:
            created = obj['created']
        if 'model' in obj and obj['model']:
            model_ret = obj['model']
        if 'usage' in obj and obj['usage']:
            usage = obj['usage']

        choices = obj.get('choices') or []
        if choices:
            c = choices[0]
            if c.get('finish_reason'):
                finish_reason = c['finish_reason']
            delta = c.get('delta') or {}
            c_part = delta.get('content')
            if c_part:
                full_content.append(c_part)
            r_part = delta.get('reasoning_content')
            if r_part:
                reasoning_content.append(r_part)

    final_text = ''.join(full_content)
    if not final_text and reasoning_content:
        final_text = ''.join(reasoning_content)

    if not usage:
        ptok = len(json.dumps(payload.get('messages', []))) // 4 if payload else 0
        ctok = len(final_text) // 4
        usage = {
            'prompt_tokens': ptok,
            'completion_tokens': ctok,
            'total_tokens': ptok + ctok
        }

    eff_finish = finish_reason or 'stop'
    if eff_finish == 'length' and len(final_text) >= 200:
        eff_finish = 'stop'

    return {
        'id': res_id,
        'object': 'chat.completion',
        'created': created,
        'model': model_ret,
        'choices': [{
            'index': 0,
            'message': {
                'role': 'assistant',
                'content': final_text
            },
            'finish_reason': eff_finish
        }],
        'usage': usage
    }

def forward_upstream(model_id, payload, timeout=None):
    body = dict(payload)
    body['model'] = model_id
    body.pop('stream_options', None)
    req = urllib.request.Request(UPSTREAM_URL, data=json.dumps(body).encode(),
        method='POST', headers={'Authorization': 'Bearer ' + UPSTREAM_KEY,
                                'Content-Type': 'application/json'})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout or 65) as resp:
            data = parse_upstream_response(resp.read(), model_id, body)
            return data, None, time.time() - t0
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode() or '{}')
            msg = (err.get('error', {}) or {}).get('message', f'HTTP {e.code}')
        except Exception:
            msg = f'HTTP {e.code}'
        return None, (e.code, str(msg)[:150]), time.time() - t0
    except Exception as e:
        return None, (-1, str(e)[:150]), time.time() - t0

def requested_model(payload):
    """Modèle explicitement demandé par le client (API OpenAI-compatible).
    'auto' (ou vide, ou un alias d'auto-routage) = le routeur décide ; tout autre
    nom EST une demande ferme, servie si un canal du modèle vit."""
    m = (payload.get('model') or '').strip()
    if not m or m.lower() in ('auto', 'default', 'smart', 'router', 'qh-auto', 'smartapi'):
        return None
    # Normalisation : retire les préfixes de namespace (ex: 'z-ai/glm-5.3-flash' -> 'glm-5.3-flash')
    clean = m.split('/')[-1].strip().lower()
    for cand in MODELS + [GEMINI_MODEL]:
        if clean == cand.lower():
            return cand
    return m

def has_images(payload):
    for m in payload.get('messages') or []:
        if isinstance(m.get('content'), list):
            for part in m['content']:
                if isinstance(part, dict) and part.get('type') in ('image_url', 'input_image', 'image'):
                    return True
    return False

def chat_auto(payload, is_stream, plan='auto', key_id=None):
    """Routage du plan : essaie jusqu'à 3 canaux, facture l'usage réel, cooldowns.

    Plan 'auto'   : famille flash polyvalente (qwen/glm/deepseek v4, vision auto
                    dès qu'un canal existe — les images routent vers deepseek-v4-vision).
    Plan 'gemini' : gemini-3.8-flash uniquement (quota dédié 100 M).

    NOTE stream : l'amont est TOUJOURS interrogé en stream:false — la réponse
    JSON complète garantit une facturation exacte (usage réel) et un échec
    propre. Si le client demande stream:true, le handler re-sérialise en SSE."""
    try:
        _est_tok = len(json.dumps(payload.get('messages') or [])) // 4
    except Exception:
        _est_tok = 0
    ctx = {'key_id': key_id, 'sig': conv_signature(payload), 'tin_est': _est_tok}
    requested = payload.get('model')
    body = dict(payload)
    body['stream'] = False
    body.pop('stream_options', None)
    if 'max_completion_tokens' in body and 'max_tokens' not in body:
        body['max_tokens'] = body.pop('max_completion_tokens')
    mt = body.get('max_tokens')
    if mt is None:
        # Si le client (ex: Hermes en compression de contexte) omet max_tokens,
        # allouer le plafond complet pour ne jamais tronquer un résumé.
        body['max_tokens'] = MAX_TOKENS_CAP
    elif isinstance(mt, int):
        # les modèles raisonneurs (deepseek-v4-pro, grok) consomment le budget en
        # reasoning_tokens invisible : un max_tokens court donne un content VIDE
        # (fini en length) que le client paie pour rien -> budget amont minimal.
        if mt < 2048:
            body['max_tokens'] = 2048 if _est_tok < 4000 else MAX_TOKENS_CAP
        elif mt > MAX_TOKENS_CAP:
            body['max_tokens'] = MAX_TOKENS_CAP
    # détection d'images → cible vision si un canal existe (polyvalence auto)
    pool = list(MODELS)
    if plan == 'auto' and has_images(payload):
        vision = [m for m in MODELS if 'vision' in m]
        vr = [m for m in vision if not in_cooldown(m)[0] and (market_get(m) or {}).get('best')]
        if vr:
            pool = vision
        else:
            # aucun canal vision vivant : pas d'appel amont (0 coût, 0 cooldown)
            return None, (400, {'error': {'message': 'images reçues mais aucun canal vision actif pour le moment — réessayez plus tard ou retirer les images',
                                          'type': 'invalid_request_error', 'code': 'vision_unavailable'}}), 0, 0, None
    models = [GEMINI_MODEL] if plan == 'gemini' else pool
    # MODÈLE DEMANDÉ (11-09) : l'API est OpenAI-compatible — quand le client nomme
    # un modèle PUBLIÉ du catalogue et qu'un canal de ce modèle vit, on le sert
    # LUI. Avant, tout choix client était ignoré en silence : aucun épinglage
    # côté client ne pouvait tenir. Sans canal vivant : repli auto assumé, annoncé
    # dans a6_router.ignored.
    req = requested_model(payload)
    honor = False
    if req and plan != 'gemini' and (req in MODELS or req == GEMINI_MODEL):
        rb = (market30_best(req) or {}).get('best') or (market_get(req) or {}).get('best')
        if rb and not in_cooldown(req)[0]:
            pool = [req]
            models = [req]
            honor = True
    elif not honor and _est_tok >= 8000 and plan == 'auto':
        # Prompt volumineux (résumé/compression) : privilégier les modèles véloces
        # pour garantir une réponse < 40s et éviter le mur des 120s Vercel.
        fast_preferred = [m for m in ['glm-5.3-flash', 'deepseek-v4-flash', 'deepseek-v4.1-flash'] if m in models]
        live_fast = [m for m in fast_preferred if not in_cooldown(m)[0] and ((market30_best(m) or {}).get('best') or (market_get(m) or {}).get('best'))]
        if live_fast:
            models = live_fast
    last_err = None
    deadline = time.time() + REQUEST_BUDGET_S
    for attempt in range(3):
        if attempt and time.time() > deadline - 20:
            log('BUDGET epuise avant essai suivant')
            break
        model_id, cand = pick_model(models, ctx)
        chosen = cand[0][2] if cand else None
        if not model_id and attempt == 0:
            # anti-503 : attente bornée du cooldown le plus proche, puis dernier recours
            model_id, cand = wait_or_last_resort(models, ctx)
            chosen = cand[0][2] if cand else None
        if not model_id:
            return None, (503, {'error': {'message': 'aucun canal disponible (cooldowns ou marché inaccessible)',
                                          'type': 'server_error', 'code': 'no_model_available'}}), 0, 0, None
        data, err, dt = forward_upstream(model_id, body, upstream_timeout(_est_tok))
        if err:
            status, msg = err
            log(f'GW essai {attempt+1} {model_id}: {status} {msg[:80]}')
            on_failure(model_id, msg)
            last_err = (status, msg)
            continue
        c0 = (data.get('choices') or [{}])[0]
        content = ''
        msg0 = c0.get('message') or {}
        if isinstance(msg0.get('content'), str):
            content = msg0['content'].strip()
        finish = c0.get('finish_reason')
        if not content and not (msg0.get('tool_calls')) and finish == 'length':
            # réponse vide tronquée par le raisonnement : inutilisable pour le client
            log(f'GW essai {attempt+1} {model_id}: reponse vide (length), canal ecarte')
            on_failure(model_id, 'reponse vide (length)')
            last_err = (502, 'reponse vide (budget raisonnement)')
            continue
        usage = data.get('usage', {}) or {}
        tin = usage.get('prompt_tokens') or 0
        tout = usage.get('completion_tokens') or 0
        cached = ((usage.get('prompt_tokens_details') or {}).get('cached_tokens')) or 0
        # prix du canal RÉELLEMENT servi (instantanés du worker) ; repli cache instantané
        b = chosen or ((market_get(model_id) or {}).get('best') or {})
        # coût amont RÉEL : les tokens cachés sont au prix cache_read (12x moins cher sur qwen)
        est = round(((tin - cached) * b.get('in', 0) + cached * b.get('cache_read', b.get('in', 0))
                     + tout * b.get('out', 0)) / 1e6, 8)
        # noms de chaînes amont JAMAIS exposés au client (fuite concurrentielle) :
        # l'identité du canal reste dans les journaux serveur, la réponse ne porte
        # que le modèle publié + la règle de décision.
        log(f'ROUTE {model_id} via {b.get("supplier")} src={b.get("src") or "instant"} '
            f'lat={round(dt, 2)}s tok={tin}+{tout}')
        data['model'] = model_id
        data['a6_router'] = {'served_model': model_id,
                             'decision': 'modele_demande' if (honor and model_id == req) else (b.get('src') or 'instant'),
                             'note': ('modèle demandé servi (pin client respecté)' if (honor and model_id == req)
                                      else 'modèle choisi automatiquement (le moins cher vivant)'),
                             'requested_model': requested,
                             'ignored': not (honor and model_id == req),
                             'latency_s': round(dt, 2)}
        with LOCK:
            PIN['model'] = model_id
            PIN['supplier'] = b.get('supplier')
        # V3 : on mémorise le pin de CETTE conversation (par clé API) pour que
        # les requêtes suivantes restent sur le même modèle tant que le cache
        # chaud vaut plus qu'une bascule. Nouvelle conversation = nouvel état.
        if ctx.get('key_id') is not None and ctx.get('sig'):
            with CONV_LOCK:
                CONV[(ctx['key_id'], ctx['sig'])] = {
                    'model': model_id, 'supplier': b.get('supplier'),
                    'ts': time.time(), 'tin': int(tin), 'tout': int(tout),
                    'cached': int(cached)}
            conv_prune()
        return data, None, tin, tout, {'model': model_id, 'supplier': b.get('supplier'),
                                       'best': b, 'est': est, 'plan': plan,
                                       'requested': requested, 'cached': cached}
    # message client SANS le détail amont (qui pourrait nommer la chaîne) : le
    # détail complet part dans les journaux du service, jamais dans la réponse.
    log(f'502 tous canaux epuises: {last_err}')
    return None, (502, {'error': {'message': 'aucun canal amont n\'a pu servir la requête — réessayez dans quelques secondes',
                                  'type': 'server_error', 'code': 'all_channels_failed'}}), 0, 0, None

# ── Sécurité : HMAC front, sessions, clés, rate-limit ───────────────────────
HMAC_WINDOW = 300   # s de fraîcheur de signature

def check_sig(headers, path, body_bytes):
    """Auth front(Vercel)->gateway : HMAC-SHA256(ts|path|sha256(body)|auth).
    Le secret ne circule JAMAIS sur le réseau (même en HTTP clair, un sniffeur
    ne peut ni le lire ni rejouer: fenêtre 300 s + couverture du body/auth)."""
    if not SECRET:
        return False
    ts = headers.get('X-QH-TS', '')
    sig = headers.get('X-QH-SIG', '')
    if not ts or not sig:
        return False
    try:
        if abs(time.time() - int(ts)) > HMAC_WINDOW:
            return False
    except Exception:
        return False
    want = hmac.new(SECRET.encode(),
                    f"{ts}|{path}|{hashlib.sha256(body_bytes or b'').hexdigest()}|{headers.get('Authorization','')}".encode(),
                    hashlib.sha256).hexdigest()
    return hmac.compare_digest(want, sig)

def session_token(user_id):
    exp = int(time.time()) + SESSION_TTL
    payload = json.dumps({'uid': user_id, 'exp': exp}, separators=(',', ':'))
    p64 = payload.encode().hex()
    sig = hmac.new(SESSION_SEC.encode(), p64.encode(), hashlib.sha256).hexdigest()
    return f'{p64}.{sig}'

def session_user(token):
    try:
        p64, sig = token.split('.', 1)
        want = hmac.new(SESSION_SEC.encode(), p64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(want, sig):
            return None
        d = json.loads(bytes.fromhex(p64).decode())
        if d.get('exp', 0) < time.time():
            return None
        return int(d['uid'])
    except Exception:
        return None

def hash_pw(password, salt=None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.scrypt(password.encode(), salt=salt.encode(), n=2**14, r=8, p=1, dklen=32)
    return f'scrypt${salt}${h.hex()}'

def verify_pw(password, stored):
    try:
        _, salt, _ = stored.split('$', 2)
    except Exception:
        return False
    return hmac.compare_digest(hash_pw(password, salt), stored)

def new_api_key():
    raw = 'sk-sm-' + secrets.token_hex(20)
    return raw, hashlib.sha256(raw.encode()).hexdigest(), raw[:10]

REGISTER_HITS = {}   # ip -> [ts]
REDEEM_HITS = {}   # uid -> [ts]
def redeem_throttled(uid):
    now = time.time()
    with LOCK:
        _prune(REDEEM_HITS)
        arr = [t for t in REDEEM_HITS.get(uid, []) if now - t < 60]
        arr.append(now)   # compter la tentative courante (sinon jamais déclenché)
        REDEEM_HITS[uid] = arr
        return len(arr) > 10

def register_throttled(ip):
    now = time.time()
    with LOCK:
        _prune(REGISTER_HITS)
        arr = [t for t in REGISTER_HITS.get(ip, []) if now - t < 3600]
        arr.append(now)   # compter la tentative courante
        REGISTER_HITS[ip] = arr
        return len(arr) > 5

def _prune(d, max_keys=10_000):
    """anti-DoS mémoire : les dicts de throttle ne peuvent pas croître sans limite."""
    if len(d) > max_keys:
        for k in list(d.keys())[:len(d) - max_keys]:
            d.pop(k, None)

def login_throttled(ip, email):
    now = time.time()
    with LOCK:
        _prune(LOGIN_FAILS)
        arr = [t for t in LOGIN_FAILS.get((ip, email.lower()), []) if now - t < 900]
        LOGIN_FAILS[(ip, email.lower())] = arr
        return len(arr) >= 5

def login_fail(ip, email):
    with LOCK:
        LOGIN_FAILS.setdefault((ip, email.lower()), []).append(time.time())

def rate_limited(key_id):
    now = time.time()
    with LOCK:
        _prune(RATE)
        arr = [t for t in RATE.get(key_id, []) if now - t < 60]
        if len(arr) >= RATE_RPM:
            RATE[key_id] = arr
            return True
        # burst : pas plus de RATE_BURST en 3 s
        if sum(1 for t in arr if now - t < 3) >= RATE_BURST:
            RATE[key_id] = arr
            return True
        arr.append(now)
        RATE[key_id] = arr
        return False

def err(status, message, code=None, etype='invalid_request_error'):
    return status, {'error': {'message': message, 'type': etype, **({'code': code} if code else {})}}

# ── Logique métier ──────────────────────────────────────────────────────────
def register(payload, ip):
    email = (payload.get('email') or '').strip().lower()
    password = payload.get('password') or ''
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email) or len(email) > 120:
        return err(400, 'email invalide')
    if len(password) < 10:
        return err(400, 'mot de passe trop court (10 caractères minimum)')
    if register_throttled(ip):
        audit('register', email, ip, False)
        return err(429, 'trop de comptes créés depuis cette adresse — réessayez dans 1 h', 'slow_down')
    if len(password) > 200:
        return err(400, 'mot de passe trop long')
    c = db()
    try:
        c.execute('INSERT INTO users(email,pw_hash,created_at) VALUES(?,?,?)',
                  (email, hash_pw(password), int(time.time())))
        uid = c.execute('SELECT last_insert_rowid()').fetchone()[0]
        c.executemany('INSERT INTO subscriptions(user_id,plan,status) VALUES(?,?,"inactive")',
                      [(uid, p) for p in PLANS])
        c.commit()
        audit('register', email, ip, True)
        return 200, {'status': 'ok', 'session': session_token(uid), 'user': {'id': uid, 'email': email}}
    except sqlite3.IntegrityError:
        audit('register', email, ip, False)
        return err(409, 'email déjà utilisé')
    finally:
        c.close()

def login(payload, ip):
    email = (payload.get('email') or '').strip().lower()
    password = payload.get('password') or ''
    if login_throttled(ip, email):
        audit('login', email, ip, False)
        return err(429, 'trop de tentatives — réessayez dans 15 minutes', 'slow_down')
    c = db()
    row = c.execute('SELECT id, pw_hash FROM users WHERE email=?', (email,)).fetchone()
    c.close()
    if not row or not verify_pw(password, row['pw_hash']):
        login_fail(ip, email)
        audit('login', email, ip, False)
        return err(401, 'identifiants incorrects')
    audit('login', email, ip, True)
    return 200, {'status': 'ok', 'session': session_token(row['id'])}

def subscription_view(c, uid):
    rows = c.execute('SELECT plan, tokens_total, tokens_used, activated_at, status FROM subscriptions WHERE user_id=?', (uid,)).fetchall()
    out = {}
    for r in rows:
        d = dict(r); out[d.pop('plan')] = d
    for p in PLANS:
        out.setdefault(p, {'tokens_total': 0, 'tokens_used': 0, 'status': 'inactive', 'activated_at': None})
    return out

def me(uid):
    c = db()
    u = c.execute('SELECT id, email, created_at FROM users WHERE id=?', (uid,)).fetchone()
    if not u:
        c.close()
        return err(401, 'session invalide')
    keys = c.execute('''SELECT k.id, k.prefix, k.name, k.created_at, k.revoked,
                        COUNT(u.id) n, COALESCE(SUM(u.tokens),0) tok,
                        COALESCE(MAX(u.created_at), k.last_used, 0) seen
                        FROM api_keys k LEFT JOIN usage_logs u ON u.key_id=k.id
                        WHERE k.user_id=? GROUP BY k.id ORDER BY k.id DESC''', (uid,)).fetchall()
    sub = subscription_view(c, uid)
    usage_rows = c.execute('''SELECT plan, COUNT(*) n, COALESCE(SUM(tokens),0) tok,
                         COALESCE(SUM(prompt_tokens),0) pin, COALESCE(SUM(completion_tokens),0) pout
                         FROM usage_logs WHERE user_id=? GROUP BY plan''', (uid,)).fetchall()
    last = c.execute('SELECT plan, model_served FROM usage_logs WHERE user_id=? ORDER BY id DESC LIMIT 1', (uid,)).fetchone()
    c.close()
    usage = {r['plan']: dict(r) for r in usage_rows}
    for p in PLANS:
        usage.setdefault(p, {'n': 0, 'tok': 0, 'pin': 0, 'pout': 0})
    if last and last['model_served'] and last['plan'] in usage:
        usage[last['plan']]['last_model'] = last['model_served']
    return 200, {'user': {'id': u['id'], 'email': u['email'], 'created_at': u['created_at']},
                 'subscription': sub,
                 'keys': [dict(k) for k in keys],
                 'usage': usage}

def create_key(uid, payload):
    name = (payload.get('name') or 'Clé')[:60]
    plan = (payload.get('plan') or 'auto').strip().lower()
    if plan not in PLANS:
        return err(400, "plan invalide (auto ou gemini)")
    c = db()
    n = c.execute('SELECT COUNT(*) FROM api_keys WHERE user_id=? AND revoked=0', (uid,)).fetchone()[0]
    if n >= 10:
        c.close()
        return err(400, 'limite de 10 clés actives atteinte')
    raw, kh, prefix = new_api_key()
    c.execute('INSERT INTO api_keys(user_id,key_hash,prefix,name,plan,created_at) VALUES(?,?,?,?,?,?)',
              (uid, kh, prefix, name, plan, int(time.time())))
    c.commit(); c.close()
    return 200, {'status': 'ok', 'key': raw, 'note': "conservez cette clé — elle n'est plus affichée ensuite"}

def revoke_key(uid, key_id):
    c = db()
    cur = c.execute('UPDATE api_keys SET revoked=1 WHERE id=? AND user_id=?', (key_id, uid))
    c.commit(); c.close()
    if cur.rowcount == 0:
        return err(404, 'clé introuvable')
    return 200, {'status': 'ok'}

def redeem(uid, payload):
    code = (payload.get('code') or '').strip().upper()
    if not re.fullmatch(r'(?:QH|SM)-[0-9A-F]{8}-[0-9A-F]{8}', code):
        return err(400, 'format de code invalide')
    ch = hashlib.sha256(code.encode()).hexdigest()
    c = db()
    row = c.execute('SELECT id, tokens, plan FROM codes WHERE code_hash=? AND used_by IS NULL', (ch,)).fetchone()
    if not row:
        c.close()
        return err(404, 'code inconnu ou déjà utilisé')
    plan = row['plan'] or 'auto'
    c.execute('UPDATE codes SET used_by=?, used_at=? WHERE id=? AND used_by IS NULL', (uid, int(time.time()), row['id']))
    if c.total_changes == 0:
        c.close()
        return err(409, 'code déjà utilisé')
    c.execute('''INSERT INTO subscriptions(user_id,plan,tokens_total,tokens_used,activated_at,status)
                 VALUES(?,?,?,0,?,'active')
                 ON CONFLICT(user_id, plan) DO UPDATE SET tokens_total=tokens_total+?,
                 status='active', activated_at=COALESCE(activated_at,?)''',
              (uid, plan, row['tokens'], int(time.time()), row['tokens'], int(time.time())))
    c.commit()
    sub = subscription_view(c, uid)
    c.close()
    return 200, {'status': 'ok', 'plan': plan, 'subscription': sub}

def api_chat(auth_header, payload, ip):
    """Le cœur : clé sk-sm-*/sk-qh-* -> abonnement -> routage auto -> metering réel."""
    if not (auth_header.startswith('Bearer sk-qh-') or auth_header.startswith('Bearer sk-sm-')):
        return err(401, 'clé API manquante (Authorization: Bearer sk-qh-…)', 'auth_error', 'authentication_error')
    raw = auth_header.replace('Bearer ', '').strip()
    kh = hashlib.sha256(raw.encode()).hexdigest()
    c = db()
    k = c.execute('SELECT id, user_id, revoked, plan FROM api_keys WHERE key_hash=?', (kh,)).fetchone()
    if not k or k['revoked']:
        c.close()
        audit('api_auth', 'key:' + raw[:10], ip, False)
        return err(401, 'clé API non reconnue ou révoquée', 'invalid_key', 'authentication_error')
    key_id, uid, plan = k['id'], k['user_id'], k['plan'] or 'auto'
    if rate_limited(key_id):
        c.close()
        return err(429, 'limite de 60 requêtes/min atteinte', 'rate_limit', 'rate_limit_error')
    s = c.execute('''SELECT tokens_total, tokens_used, status FROM subscriptions
                     WHERE user_id=? AND plan=?''', (uid, plan)).fetchone()
    if not s or s['status'] != 'active' or s['tokens_used'] >= s['tokens_total']:
        c.close()
        return err(402, f"abonnement {plan} inactif ou tokens épuisés — activez un code d'abonnement",
                   'quota_exceeded', 'insufficient_quota')
    if not isinstance(payload.get('messages'), list) or not payload['messages']:
        c.close()
        return err(400, 'messages[] requis')
    if len(json.dumps(payload)) > 3_000_000:
        c.close()
        return err(413, 'payload trop volumineux (max 3 Mo)')
    c.execute('UPDATE api_keys SET last_used=? WHERE id=?', (int(time.time()), key_id))
    c.commit(); c.close()

    data, e, tin, tout, served = chat_auto(payload, bool(payload.get('stream')), plan, key_id)
    if e:
        return e[0], e[1]
    tokens = int(tin + tout)
    cached_tok = int(served.get('cached', 0))
    # FACTURATION CACHE : les tokens servis depuis le cache amont coûtent ~12x moins cher
    # (qwen 0.0001 vs 0.0012/M) → ils sont comptés à 10 % au client. C'est le cœur du prix.
    billed = max(0, tokens - int(cached_tok * 0.9))
    # débit : jamais au-delà du plafond ; l'amont a consommé, on impute le volume réel corrigé
    c = db()
    c.execute('''UPDATE subscriptions SET tokens_used = MIN(tokens_total, tokens_used + ?)
                 WHERE user_id=? AND plan=?''', (billed, uid, plan))
    c.execute('''INSERT INTO usage_logs(user_id,key_id,plan,model_served,model_requested,supplier,prompt_tokens,
                 completion_tokens,tokens,cost_amont_usd,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
              (uid, key_id, plan, served['model'], served.get('requested'), served['supplier'],
               tin, tout, billed, served['est'], int(time.time())))
    c.commit()
    remaining = c.execute('SELECT tokens_total - tokens_used FROM subscriptions WHERE user_id=? AND plan=?',
                          (uid, plan)).fetchone()[0]
    c.close()
    data['quota_hub'] = {'plan': plan, 'tokens_billed': billed, 'tokens_raw': tokens,
                         'cache_tokens': cached_tok, 'cache_savings_tokens': tokens - billed,
                         'tokens_remaining': max(0, remaining), 'served_model': served['model']}
    return 200, data

# ── Connexion sociale : Google / GitHub (10-09) ─────────────────────────────
# Credentials uniquement dans le .env de la passerelle : QH_GOOGLE_CLIENT_ID /
# QH_GOOGLE_CLIENT_SECRET / QH_GITHUB_CLIENT_ID / QH_GITHUB_CLIENT_SECRET.
# Le callback est public (le navigateur revient de Google/GitHub sans HMAC) ;
# le state (anti-CSRF) est stocké en mémoire, TTL 10 min, usage unique.
OAUTH_CB_BASE = os.environ.get('QH_OAUTH_CB_BASE',
    'https://smartapi.cheap/gw/api/auth/oauth/callback/')
FRONT_URL = os.environ.get('QH_FRONT_URL', 'https://smartapi.cheap').rstrip('/')
GOOGLE_CID = os.environ.get('QH_GOOGLE_CLIENT_ID', '')
GOOGLE_CSEC = os.environ.get('QH_GOOGLE_CLIENT_SECRET', '')
GITHUB_CID = os.environ.get('QH_GITHUB_CLIENT_ID', '')
GITHUB_CSEC = os.environ.get('QH_GITHUB_CLIENT_SECRET', '')
OAUTH_STATES = {}                     # state -> {'ts', 'return_to'} (mémoire)
OAUTH_STATE_TTL = 600

def oauth_start(provider):
    provider = (provider or '').lower()
    if provider == 'google' and not GOOGLE_CID:
        return err(503, 'connexion Google non configurée (QH_GOOGLE_CLIENT_ID)')
    if provider == 'github' and not GITHUB_CID:
        return err(503, 'connexion GitHub non configurée (QH_GITHUB_CLIENT_ID)')
    if provider not in ('google', 'github'):
        return err(400, 'provider inconnu (google|github)')
    state = secrets.token_urlsafe(24)
    with LOCK:
        OAUTH_STATES[state] = {'ts': time.time(), 'return_to': '/'}
    if provider == 'google':
        url = ('https://accounts.google.com/o/oauth2/v2/auth?client_id='
               + urllib.parse.quote(GOOGLE_CID, safe='')
               + '&redirect_uri=' + urllib.parse.quote(OAUTH_CB_BASE + 'google', safe='')
               + '&response_type=code&scope=openid%20email%20profile&state=' + state
               + '&prompt=select_account')
    else:
        url = ('https://github.com/login/oauth/authorize?client_id='
               + urllib.parse.quote(GITHUB_CID, safe='') + '&scope=user:email&state=' + state)
    return 200, {'url': url}

def _oauth_gate(provider, code):
    """Échange le code d'autorisation contre l'identité (email vérifié + sub)."""
    if provider == 'google':
        data = urllib.parse.urlencode({
            'code': code, 'client_id': GOOGLE_CID, 'client_secret': GOOGLE_CSEC,
            'redirect_uri': OAUTH_CB_BASE + 'google', 'grant_type': 'authorization_code'}).encode()
        req = urllib.request.Request('https://oauth2.googleapis.com/token', data=data, method='POST',
                                     headers={'Content-Type': 'application/x-www-form-urlencoded'})
        with urllib.request.urlopen(req, timeout=15) as r:
            tok = json.loads(r.read().decode())
        access = tok.get('access_token')
        if not access:
            raise RuntimeError('token Google absent')
        req = urllib.request.Request('https://openidconnect.googleapis.com/v1/userinfo',
                                     headers={'Authorization': 'Bearer ' + access})
        with urllib.request.urlopen(req, timeout=15) as r:
            info = json.loads(r.read().decode())
        return {'provider': 'google', 'sub': str(info.get('sub', '')),
                'email': (info.get('email') or '').lower(),
                'verified': bool(info.get('email_verified')),
                'name': info.get('name') or ''}
    data = urllib.parse.urlencode({'client_id': GITHUB_CID, 'client_secret': GITHUB_CSEC,
                                   'code': code}).encode()
    req = urllib.request.Request('https://github.com/login/oauth/access_token', data=data,
                                 method='POST', headers={'Accept': 'application/json',
                                                         'Content-Type': 'application/x-www-form-urlencoded'})
    with urllib.request.urlopen(req, timeout=15) as r:
        tok = json.loads(r.read().decode())
    access = tok.get('access_token')
    if not access:
        raise RuntimeError('token GitHub absent')
    req = urllib.request.Request('https://api.github.com/user',
                                 headers={'Authorization': 'Bearer ' + access, 'User-Agent': 'quota-hub'})
    with urllib.request.urlopen(req, timeout=15) as r:
        info = json.loads(r.read().decode())
    email = (info.get('email') or '').lower()
    if not email:
        try:
            req = urllib.request.Request('https://api.github.com/user/emails',
                                         headers={'Authorization': 'Bearer ' + access, 'User-Agent': 'quota-hub'})
            with urllib.request.urlopen(req, timeout=15) as r:
                for e in json.loads(r.read().decode()):
                    if e.get('primary') and e.get('verified') and e.get('email'):
                        email = e['email'].lower()
                        break
        except Exception:
            pass
    return {'provider': 'github', 'sub': str(info.get('id', '')),
            'email': email, 'verified': bool(email),
            'name': info.get('name') or info.get('login') or ''}

def oauth_upsert_user(idt):
    """Compte lié (provider, sub) ; sinon compte email existant LIÉ (identité
    confirmée par le fournisseur) ; sinon création."""
    c = db()
    try:
        row = c.execute('SELECT id FROM users WHERE oauth_provider=? AND oauth_sub=?',
                        (idt['provider'], idt['sub'])).fetchone()
        if row:
            return row['id']
        if idt['email']:
            row = c.execute('SELECT id FROM users WHERE email=?', (idt['email'],)).fetchone()
            if row:
                c.execute('UPDATE users SET oauth_provider=?, oauth_sub=? WHERE id=?',
                          (idt['provider'], idt['sub'], row['id']))
                c.commit()
                return row['id']
        cur = c.execute('INSERT INTO users(email, pw_hash, created_at, oauth_provider, oauth_sub) '
                        'VALUES(?,?,?,?,?)',
                        (idt['email'] or (idt['provider'] + '-' + idt['sub'] + '@oauth.local'),
                         '', int(time.time()), idt['provider'], idt['sub']))
        c.commit()
        return cur.lastrowid
    finally:
        c.close()

def oauth_callback(provider, state, code):
    provider = (provider or '').lower()
    now = time.time()
    with LOCK:
        st = OAUTH_STATES.pop(state, None)
    if not st:
        return err(400, 'état OAuth inconnu ou déjà utilisé — rechargez la page et réessayez')
    if now - st['ts'] > OAUTH_STATE_TTL:
        return err(400, 'état OAuth expiré (10 min) — réessayez')
    try:
        idt = _oauth_gate(provider, code)
    except Exception as e:
        log(f'OAuth {provider} échange échoué: {str(e)[:90]}')
        return err(502, 'échange avec le fournisseur échoué')
    if not idt['sub']:
        return err(400, 'identité fournisseur absente')
    if provider == 'google' and not (idt['verified'] and idt['email']):
        return err(400, 'email Google non vérifié — connexion impossible')
    user_id = oauth_upsert_user(idt)
    if not user_id:
        return err(500, 'impossible de créer/lier le compte')
    sess = session_token(user_id)
    log(f'OAuth {provider} connecte user {user_id}')
    return 302, {'location': FRONT_URL + '/?oauth_session=' + sess + '&oauthed=1'}

def migrate_oauth():
    """Colonnes de liaison sociale sur users (idempotente)."""
    c = db()
    cols = [r[1] for r in c.execute('PRAGMA table_info(users)').fetchall()]
    if 'oauth_provider' not in cols:
        c.execute('ALTER TABLE users ADD COLUMN oauth_provider TEXT')
        c.execute('ALTER TABLE users ADD COLUMN oauth_sub TEXT')
        c.execute('CREATE INDEX IF NOT EXISTS idx_users_oauth ON users(oauth_provider,oauth_sub)')
        c.commit()
        log('migration OAuth appliquée (oauth_provider/oauth_sub)')
    c.close()

def admin_codes(admin_token, payload):
    if not ADMIN_TOKEN or not hmac.compare_digest(admin_token, ADMIN_TOKEN):
        return err(403, 'admin token invalide')
    plan = (payload.get('plan') or 'auto').strip().lower()
    if plan not in PLANS:
        return err(400, 'plan invalide (auto ou gemini)')
    tokens = int(payload.get('tokens') or PLAN_DEFAULT[plan])
    count = min(int(payload.get('count') or 1), 50)
    out = []
    c = db()
    for _ in range(count):
        code = 'SM-' + secrets.token_hex(4).upper() + '-' + secrets.token_hex(4).upper()
        c.execute('INSERT INTO codes(code_hash,tokens,plan,created_at) VALUES(?,?,?,?)',
                  (hashlib.sha256(code.encode()).hexdigest(), tokens, plan, int(time.time())))
        out.append(code)
    c.commit(); c.close()
    return 200, {'status': 'ok', 'codes': out, 'tokens_each': tokens, 'plan': plan}

def admin_stats(admin_token):
    if not ADMIN_TOKEN or not hmac.compare_digest(admin_token, ADMIN_TOKEN):
        return err(403, 'admin token invalide')
    c = db()
    by_plan = {}
    for r in c.execute('''SELECT plan, COUNT(*) n, COALESCE(SUM(tokens_total),0) sold,
                          COALESCE(SUM(tokens_used),0) used FROM subscriptions
                          WHERE status='active' GROUP BY plan''').fetchall():
        by_plan[r['plan']] = {'subs': r['n'], 'tokens_sold': r['sold'], 'tokens_used': r['used']}
    s = {'users': c.execute('SELECT COUNT(*) FROM users').fetchone()[0],
         'plans': by_plan,
         'tokens_amont_cost_usd': round(c.execute('SELECT COALESCE(SUM(cost_amont_usd),0) FROM usage_logs').fetchone()[0], 4),
         'requests': c.execute('SELECT COUNT(*) FROM usage_logs').fetchone()[0],
         'pin': dict(PIN), 'cooldowns': {m: round(u - time.time()) for m, (u, _) in COOLDOWN.items() if u > time.time()}}
    c.close()
    return 200, s

# ── Serveur HTTP ────────────────────────────────────────────────────────────
SIG_HEADER = {}

class Handler(BaseHTTPRequestHandler):
    server_version = 'QuotaHub'
    sys_version = ''

    def log_message(self, fmt, *args):
        pass

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except Exception:
            log('HANDLER EXC ' + traceback.format_exc(limit=3).replace('\n', ' | ')[:300])
            try:
                self._json(500, {'error': {'message': 'erreur interne (logguée)', 'type': 'server_error'}})
            except Exception:
                pass

    def _json(self, status, obj):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _sse(self, obj):
        """Re-sérialise une réponse complète en événements SSE compatibles SDK
        OpenAI (chunks delta concaténables). L'amont a déjà été interrogé en
        stream:false : l'usage réel facturé est exact, on ne rejoue que le flux."""
        base = {'id': obj.get('id', 'chatcmpl-qh'),
                'object': 'chat.completion.chunk',
                'created': obj.get('created', int(time.time())),
                'model': obj.get('model', 'auto')}
        c0 = (obj.get('choices') or [{}])[0]
        msg = c0.get('message') or {}
        full = msg.get('content') or ''
        tool_calls = msg.get('tool_calls') or []
        finish = c0.get('finish_reason') or ('tool_calls' if tool_calls else 'stop')
        def chunk(delta, fr=None, idx=0):
            ev = dict(base)
            ev['choices'] = [{'index': idx, 'delta': delta, 'finish_reason': fr}]
            return ('data: ' + json.dumps(ev, ensure_ascii=False) + '\n\n').encode()
        parts = []
        if msg.get('role'):
            parts.append(chunk({'role': msg['role']}, None))
        # découpe du contenu en morceaux lisibles (phrases <= 512 chars)
        import re as _re
        toks = _re.findall(r'.{1,512}(?:\s|$)', full) or ([full] if full else [])
        for t in toks:
            parts.append(chunk({'content': t}, None))
        # appels d'outils (function calling) : SANS eux le flux paraît vide quand
        # le modèle appelle un outil au lieu de répondre (content souvent '').
        for i, tc in enumerate(tool_calls):
            f = tc.get('function') or {}
            parts.append(chunk({'tool_calls': [{
                'index': i,
                'id': tc.get('id') or f'call_qh{i}',
                'type': tc.get('type') or 'function',
                'function': {'name': f.get('name') or '',
                             'arguments': f.get('arguments') or ''}}]}, None))
        parts.append(chunk({}, finish))  # dernier chunk : delta vide + finish_reason réel
        payload = b''.join(parts) + b'data: [DONE]\n\n'
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self):
        # le front appelle son propre domaine (/gw/* via Vercel) : préflights gérés là-bas.
        # CORS minimal : autoriser GET/POST/DELETE sans exposer les en-têtes internes.
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', 'https://smartapi.cheap')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-QH-Session')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def _redirect(self, location):
        self.send_response(302)
        self.send_header('Location', location)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def _read_body(self):
        n = int(self.headers.get('Content-Length', 0) or 0)
        if n > 3_200_000:
            return None
        return self.rfile.read(n) if n else b''

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            d30 = market30_all() or {}
            body = json.dumps({'ok': True, 'service': 'quota-hub-gateway',
                               'market30': {'src': 'moy30' if d30 else 'instant',
                                            'models': len(d30.get('models') or {}),
                                            'age_s': d30.get('age_s')}}).encode()
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        # OAuth social : public (le navigateur revient de Google/GitHub sans HMAC)
        if path == '/api/auth/oauth/start':
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            status, obj = oauth_start((q.get('provider') or [''])[0])
            return self._json(status, obj)
        m = re.fullmatch(r'/api/auth/oauth/callback/([a-z]+)', path)
        if m:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            status, obj = oauth_callback(m.group(1), (q.get('state') or [''])[0],
                                          (q.get('code') or [''])[0])
            if status == 302:
                return self._redirect(obj['location'])
            return self._json(status, obj)
        if path == '/api/me':
            if not check_sig(self.headers, path, b''):
                return self._json(403, {'error': {'message': 'signature invalide'}})
            uid = session_user(self.headers.get('X-QH-Session', ''))
            if not uid:
                return self._json(401, {'error': {'message': 'session absente ou expirée'}})
            status, obj = me(uid)
            return self._json(status, obj)
        if path == '/api/usage':
            # JOURNAUX du client : ses dernières requêtes + totaux 30 j (par jour,
            # par modèle) + totaux globaux. Jamais de nom de canal amont exposé.
            if not check_sig(self.headers, path, b''):
                return self._json(403, {'error': {'message': 'signature invalide'}})
            uid = session_user(self.headers.get('X-QH-Session', ''))
            if not uid:
                return self._json(401, {'error': {'message': 'session absente ou expirée'}})
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:
                limit = max(1, min(200, int((q.get('limit') or ['50'])[0])))
            except Exception:
                limit = 50
            try:
                c = db()
                rows = c.execute(
                    'SELECT u.id, u.plan, u.model_served, u.model_requested, u.prompt_tokens, '
                    'u.completion_tokens, u.tokens, u.cost_amont_usd, u.created_at, '
                    'k.name AS key_name FROM usage_logs u '
                    'LEFT JOIN api_keys k ON k.id=u.key_id '
                    'WHERE u.user_id=? ORDER BY u.id DESC LIMIT ?', (uid, limit)).fetchall()
                since = int(time.time()) - 30 * 86400
                per_day = c.execute(
                    "SELECT date(created_at,'unixepoch') d, COUNT(*) n, SUM(tokens) tok, "
                    "SUM(cost_amont_usd) cost FROM usage_logs WHERE user_id=? AND created_at>=? "
                    "GROUP BY d ORDER BY d", (uid, since)).fetchall()
                per_model = c.execute(
                    'SELECT model_served, COUNT(*) n, SUM(tokens) tok FROM usage_logs '
                    'WHERE user_id=? AND created_at>=? GROUP BY model_served '
                    'ORDER BY tok DESC LIMIT 12', (uid, since)).fetchall()
                per_key = c.execute(
                    'SELECT k.name AS name, COUNT(*) n, COALESCE(SUM(u.tokens),0) tok, '
                    'COALESCE(SUM(u.cost_amont_usd),0) cost FROM usage_logs u '
                    'LEFT JOIN api_keys k ON k.id=u.key_id '
                    'WHERE u.user_id=? AND u.created_at>=? GROUP BY k.name '
                    'ORDER BY tok DESC LIMIT 12', (uid, since)).fetchall()
                tot = c.execute(
                    'SELECT COUNT(*) n, COALESCE(SUM(tokens),0) tok, '
                    'COALESCE(SUM(cost_amont_usd),0) cost FROM usage_logs WHERE user_id=?',
                    (uid,)).fetchone()
                c.close()
            except Exception as ex:
                return self._json(500, {'error': {'message': f'journaux indisponibles: {str(ex)[:60]}'}})
            return self._json(200, {
                'ok': True,
                'totals': {'requests': tot['n'], 'tokens': int(tot['tok']),
                           'cost_usd': round(tot['cost'] or 0, 6)},
                'rows': [{'id': r['id'], 'plan': r['plan'], 'model': r['model_served'],
                          'requested': r['model_requested'], 'in': int(r['prompt_tokens'] or 0),
                          'out': int(r['completion_tokens'] or 0), 'tokens': int(r['tokens'] or 0),
                          'cost_usd': round(r['cost_amont_usd'] or 0, 6),
                          'key': r['key_name'] or '',
                          'ts': int(r['created_at'] or 0)} for r in rows],
                'per_day': [{'d': r['d'], 'n': r['n'], 'tokens': int(r['tok'] or 0),
                             'cost_usd': round(r['cost'] or 0, 6)} for r in per_day],
                'per_model': [{'model': r['model_served'], 'n': r['n'], 'tokens': int(r['tok'] or 0)}
                              for r in per_model],
                'per_key': [{'key': r['name'] or 'clé supprimée', 'n': r['n'],
                             'tokens': int(r['tok'] or 0), 'cost_usd': round(r['cost'] or 0, 6)}
                            for r in per_key]})
        if path == '/admin/stats':
            if self.client_address[0] != '127.0.0.1':
                return self._json(403, {'error': {'message': 'loopback uniquement'}})
            status, obj = admin_stats(self.headers.get('X-Admin-Token', ''))
            return self._json(status, obj)
        if path == '/api/auto-mix':
            # Répartition publique des modèles servis par le mode auto sur 24 h.
            # Agrégée (% par modèle), sans aucune donnée client ni nom de canal amont.
            try:
                c = db()
                since = int(time.time()) - 86400
                rows = c.execute(
                    "SELECT model_served, COUNT(*) n FROM usage_logs "
                    "WHERE created_at>=? AND model_served IS NOT NULL AND model_served!='' "
                    "GROUP BY model_served ORDER BY n DESC LIMIT 12", (since,)).fetchall()
                total = sum((r[1] or 0) for r in rows)
            except Exception:
                rows, total = [], 0
            return self._json(200, {'ok': True, 'window_s': 86400, 'total': total,
                                    'mix': [{'model': r[0], 'n': r[1]} for r in rows]})
        if path == '/v1/models':
            # compat SDK OpenAI : 'auto' (routeur) en tête, puis le pool exposé
            return self._json(200, {'object': 'list', 'data': [
                {'id': 'auto', 'object': 'model', 'owned_by': 'quota-hub'}]
                + [{'id': m, 'object': 'model', 'owned_by': 'quota-hub'} for m in MODELS]
                + [{'id': GEMINI_MODEL, 'object': 'model', 'owned_by': 'quota-hub-gemini'}]})
        self._json(404, {'error': {'message': 'not found'}})

    def do_DELETE(self):
        path = urllib.parse.urlparse(self.path).path
        if not check_sig(self.headers, path, b''):
            return self._json(403, {'error': {'message': 'signature invalide'}})
        uid = session_user(self.headers.get('X-QH-Session', ''))
        if not uid:
            return self._json(401, {'error': {'message': 'session absente ou expirée'}})
        m = re.fullmatch(r'/api/keys/(\d+)', path)
        if m:
            status, obj = revoke_key(uid, int(m.group(1)))
            return self._json(status, obj)
        self._json(404, {'error': {'message': 'not found'}})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        body = self._read_body()
        if body is None:
            return self._json(413, {'error': {'message': 'payload trop volumineux'}})
        ip = self.headers.get('X-Real-IP', '') or (self.client_address[0] if self.client_address else '')
        loopback = self.client_address[0] in ('127.0.0.1', '::1')
        try:
            payload = json.loads(body.decode('utf-8') or '{}')
        except Exception:
            return self._json(400, {'error': {'message': 'JSON invalide'}})

        # ops loopback : création de codes d'activation (SSH)
        if path == '/admin/codes':
            if not loopback:
                return self._json(403, {'error': {'message': 'loopback uniquement'}})
            status, obj = admin_codes(self.headers.get('X-Admin-Token', ''), payload)
            return self._json(status, obj)

        # tout le reste exige la signature du front Vercel
        # SAUF /v1/chat/completions : endpoint public OpenAI-compatible, protégé
        # par la clé sk-qh-* (auth applicative). Le secret HMAC ne protège que
        # la surface session/admin.
        if path != '/v1/chat/completions' and not check_sig(self.headers, path, body):
            log(f'403 signature invalide {path} ip={ip}')
            return self._json(403, {'error': {'message': 'signature invalide — passer par le site officiel'}})

        if path == '/api/auth/register':
            status, obj = register(payload, ip)
        elif path == '/api/auth/login':
            status, obj = login(payload, ip)
        elif path == '/api/keys':
            uid = session_user(self.headers.get('X-QH-Session', ''))
            if not uid:
                return self._json(401, {'error': {'message': 'session absente ou expirée'}})
            status, obj = create_key(uid, payload)
        elif path == '/api/redeem':
            uid = session_user(self.headers.get('X-QH-Session', ''))
            if not uid:
                return self._json(401, {'error': {'message': 'session absente ou expirée'}})
            if redeem_throttled(uid):
                return self._json(429, {'error': {'message': 'trop de tentatives — réessayez dans une minute', 'code': 'slow_down'}})
            status, obj = redeem(uid, payload)
        elif path == '/v1/chat/completions':
            stream_wanted = bool(payload.get('stream'))
            status, obj = api_chat(self.headers.get('Authorization', ''), payload, ip)
            if status == 200 and stream_wanted and isinstance(obj, dict):
                return self._sse(obj)
        else:
            return self._json(404, {'error': {'message': 'not found'}})
        self._json(status, obj)

def refresh_loop():
    """Le routeur rafraîchit le marché LUI-MÊME (jamais dans le chemin d'une
    requête) et le partage à tous les clients : toutes les MARKET_TTL (20 min),
    re-warm du marché instantané + de la vue 30 j. Les requêtes lisent ensuite
    le snapshot — zéro vérification de prix par requête ou par utilisateur."""
    while True:
        time.sleep(MARKET_TTL)
        try:
            warm_market()
            log('REFRESH marché: re-warm lancé (snapshot partagé, 20 min)')
        except Exception as e:
            log(f'REFRESH marché: {str(e)[:80]}')


def main():
    if not SESSION_SEC:
        raise SystemExit('QH_SESSION_SECRET requis (.env)')
    if not SECRET:
        log('AVERTISSEMENT : QH_INTERNAL_SECRET absent — aucune requête signée ne passera')
    init_db()
    migrate_oauth()
    cooldowns_load()
    warm_market()
    threading.Thread(target=refresh_loop, daemon=True).start()
    srv = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    srv.daemon_threads = True
    cert_p, key_p = os.environ.get('QH_TLS_CERT', ''), os.environ.get('QH_TLS_KEY', '')
    if cert_p and key_p and os.path.exists(cert_p) and os.path.exists(key_p):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert_p, key_p)
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
        proto = 'https'
    else:
        proto = 'http (AVERTISSEMENT : TLS absent)'
    log(f'Quota.Hub Gateway sur {proto}://0.0.0.0:{PORT} | plans: auto={PLAN_DEFAULT["auto"]:,} gemini={PLAN_DEFAULT["gemini"]:,} | db={DB_PATH}')
    srv.serve_forever()

if __name__ == '__main__':
    main()
