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
MODELS = ['qwen3.8-flash', 'glm-5.3-flash', 'deepseek-v4-flash',
          'deepseek-v4.1-flash', 'deepseek-v4-flash-vision', 'deepseek-v4-vision']
GEMINI_MODEL = 'gemini-3.8-flash'
PLANS = ('auto', 'gemini')
PLAN_DEFAULT = {'auto': 1_000_000_000, 'gemini': 100_000_000}   # tokens par code
SUCCESS_SCALE = 10000
MIN_SUCCESS_RAW = int(80 * SUCCESS_SCALE / 100)   # floor fiabilité 80 %
HYSTERESIS = 0.15                                  # pin canal chaud (cache prompts)
MARKET_TTL = 60                                    # s
MAX_TOKENS_CAP = 4000                              # plafond par requête
RATE_RPM = 60                                      # requêtes/min par clé
RATE_BURST = 10
SESSION_TTL = 30 * 86400

LOCK = threading.Lock()
MKT = {}                 # model -> {'r': ..., 'ts': ...}
MKT_BUSY = set()
COOLDOWN = {}
COOLDOWN_PATH = os.path.join(DIR, 'cooldowns.json')

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
PIN = {'model': None}
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
    def expected(i):
        s = max((i.get('recent_success_rate') or 0) / SUCCESS_SCALE, 0.01)
        return i.get('input_price_micros', 10**18) / s
    alive.sort(key=expected)
    if not alive:
        return {'best': None, 'n_alive': 0}
    b = alive[0]
    return {'best': {'supplier': b.get('supplier_nickname'),
                     'in': b.get('input_price_micros', 0) / 1e6,
                     'out': b.get('output_price_micros', 0) / 1e6,
                     'cache_read': b.get('cache_read_price_micros', 0) / 1e6,
                     'success': (b.get('recent_success_rate') or 0) / SUCCESS_SCALE * 100},
            'n_alive': len(alive)}

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

def warm_market():
    def _all():
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

def pick_model(models):
    """Modèle le moins cher vivant du pool ; hystérésis 15 % (préserve le cache amont)."""
    cand = []
    for m in models:
        cd, _ = in_cooldown(m)
        if cd:
            continue
        r = market_get(m)
        b = (r or {}).get('best')
        if not b:
            continue
        success = max(b['success'] / 100.0, 0.01)
        cand.append(((b['in'] + b['out']) / 2 / success, m, b))
    if not cand:
        return None, None
    cand.sort(key=lambda x: x[0])
    if PIN.get('model'):
        pc = next((c for c, m, _ in cand if m == PIN['model']), None)
        if pc is not None and pc <= cand[0][0] * (1 + HYSTERESIS):
            cand.sort(key=lambda x: 0 if x[1] == PIN['model'] else 1)
    with LOCK:
        PIN['model'] = cand[0][1]
    return cand[0][1], cand

def forward_upstream(model_id, payload):
    body = dict(payload)
    body['model'] = model_id
    body.pop('stream_options', None)
    req = urllib.request.Request(UPSTREAM_URL, data=json.dumps(body).encode(),
        method='POST', headers={'Authorization': 'Bearer ' + UPSTREAM_KEY,
                                'Content-Type': 'application/json'})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode())
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
    requested = payload.get('model')
    body = dict(payload)
    body['stream'] = False
    body.pop('stream_options', None)
    mt = body.get('max_tokens')
    if mt is None:
        body['max_tokens'] = 1000
    if isinstance(mt, int) and mt > MAX_TOKENS_CAP:
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
    last_err = None
    for attempt in range(3):
        model_id, cand = pick_model(models)
        if not model_id:
            return None, (503, {'error': {'message': 'aucun canal disponible (cooldowns ou marché inaccessible)',
                                          'type': 'server_error', 'code': 'no_model_available'}}), 0, 0, None
        data, err, dt = forward_upstream(model_id, body)
        if err:
            status, msg = err
            log(f'GW essai {attempt+1} {model_id}: {status} {msg[:80]}')
            on_failure(model_id, msg)
            last_err = (status, msg)
            continue
        usage = data.get('usage', {}) or {}
        tin = usage.get('prompt_tokens') or 0
        tout = usage.get('completion_tokens') or 0
        r = market_get(model_id) or {}
        b = r.get('best') or {}
        est = round((tin * b.get('in', 0) + tout * b.get('out', 0)) / 1e6, 8)
        data['a6_router'] = {'served_model': model_id, 'supplier': b.get('supplier'),
                             'note': 'modèle choisi automatiquement (le moins cher vivant)',
                             'requested_model': requested, 'ignored': True,
                             'latency_s': round(dt, 2)}
        return data, None, tin, tout, {'model': model_id, 'supplier': b.get('supplier'),
                                       'est': est, 'plan': plan, 'requested': requested}
    return None, (502, {'error': {'message': f'tous les canaux ont échoué: {last_err}',
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
    raw = 'sk-qh-' + secrets.token_hex(20)
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
    keys = c.execute('SELECT id, prefix, name, created_at, revoked FROM api_keys WHERE user_id=? ORDER BY id DESC', (uid,)).fetchall()
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
    if not re.fullmatch(r'QH-[0-9A-F]{8}-[0-9A-F]{8}', code):
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
    """Le cœur : clé sk-qh-* -> abonnement -> routage auto -> metering réel."""
    if not auth_header.startswith('Bearer sk-qh-'):
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
    # débit réel : ne jamais dépasser le plafond ; l'amont a consommé, on impute
    c = db()
    c.execute('''UPDATE subscriptions SET tokens_used = MIN(tokens_total, tokens_used + ?)
                 WHERE user_id=? AND plan=?''', (tokens, uid, plan))
    c.execute('''INSERT INTO usage_logs(user_id,key_id,plan,model_served,model_requested,supplier,prompt_tokens,
                 completion_tokens,tokens,cost_amont_usd,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
              (uid, key_id, plan, served['model'], served.get('requested'), served['supplier'],
               tin, tout, tokens, served['est'], int(time.time())))
    c.commit()
    remaining = c.execute('SELECT tokens_total - tokens_used FROM subscriptions WHERE user_id=? AND plan=?',
                          (uid, plan)).fetchone()[0]
    c.close()
    data['quota_hub'] = {'plan': plan, 'tokens_billed': tokens, 'tokens_remaining': max(0, remaining),
                         'served_model': served['model']}
    return 200, data

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
        code = 'QH-' + secrets.token_hex(4).upper() + '-' + secrets.token_hex(4).upper()
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
        reason = c0.get('finish_reason') or ('stop' if full else 'stop')
        def chunk(delta, fr=None, idx=0):
            ev = dict(base)
            ev['choices'] = [{'index': idx, 'delta': delta, 'finish_reason': fr}]
            return ('data: ' + json.dumps(ev, ensure_ascii=False) + '\n\n').encode()
        parts = []
        role_sent = False
        if msg.get('role'):
            parts.append(chunk({'role': msg['role']}, None))
            role_sent = True
        # découpe du contenu en morceaux lisibles (phrases <= 512 chars)
        import re as _re
        toks = _re.findall(r'.{1,512}(?:\s|$)', full) or ([full] if full else [])
        for t in toks:
            parts.append(chunk({'content': t}, None))
        parts.append(chunk({}, 'stop'))  # dernier chunk : delta vide + finish_reason
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
        self.send_header('Access-Control-Allow-Origin', 'https://quota-hub.vercel.app')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-QH-Session')
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
            body = b'{"ok":true,"service":"quota-hub-gateway"}'
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == '/api/me':
            if not check_sig(self.headers, path, b''):
                return self._json(403, {'error': {'message': 'signature invalide'}})
            uid = session_user(self.headers.get('X-QH-Session', ''))
            if not uid:
                return self._json(401, {'error': {'message': 'session absente ou expirée'}})
            status, obj = me(uid)
            return self._json(status, obj)
        if path == '/admin/stats':
            if self.client_address[0] != '127.0.0.1':
                return self._json(403, {'error': {'message': 'loopback uniquement'}})
            status, obj = admin_stats(self.headers.get('X-Admin-Token', ''))
            return self._json(status, obj)
        if path == '/v1/models':
            # compat SDK OpenAI : la liste exposée est le pool auto (le client ne choisit pas)
            return self._json(200, {'object': 'list', 'data': [
                {'id': m, 'object': 'model', 'owned_by': 'quota-hub'} for m in MODELS]
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

def main():
    if not SESSION_SEC:
        raise SystemExit('QH_SESSION_SECRET requis (.env)')
    if not SECRET:
        log('AVERTISSEMENT : QH_INTERNAL_SECRET absent — aucune requête signée ne passera')
    init_db()
    cooldowns_load()
    warm_market()
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
