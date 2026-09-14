#!/usr/bin/env python3
# Recette post-deploiement : verifie sur CE noeud que
#  (1) une requete AVEC IMAGE est servie par le pool normal (plus de pool vision),
#  (2) route_reason porte la trace '+img',
#  (3) la facturation reste coherente,
#  (4) /api/prices non signe est refuse.
# La cle de test est creee puis SUPPRIMEE ici : rien ne fuit, rien ne reste.
import base64, hashlib, json, os, sqlite3, ssl, struct, sys, time, urllib.error, urllib.request, zlib

DB = '/opt/quota-hub/hub.db'
GW = 'https://127.0.0.1:8890'
UID = 18
NAME = 'zz-audit-temp'

def chunk(t, d):
    return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)

def make_png(w, h, quads):
    raw = b''
    for y in range(h):
        row = b'\x00'
        for x in range(w):
            tl, tr, bl, br = quads
            c = tl if (x < w // 2 and y < h // 2) else tr if (x >= w // 2 and y < h // 2) else bl if (x < w // 2) else br
            row += bytes(c)
        raw += row
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))

URI = 'data:image/png;base64,' + base64.b64encode(
    make_png(96, 96, ((0, 170, 0), (220, 30, 30), (240, 220, 40), (30, 60, 220)))).decode()

tok = 'sk-sm-audit' + os.urandom(16).hex()
kh = hashlib.sha256(tok.encode()).hexdigest()
c = sqlite3.connect(DB)
c.execute("INSERT INTO api_keys(user_id,key_hash,prefix,name,plan,created_at) VALUES(?,?,?,?,?,?)",
          (UID, kh, 'sk-sm-audit', NAME, 'auto', int(time.time())))
c.commit()
kid = c.execute("SELECT id FROM api_keys WHERE key_hash=?", (kh,)).fetchone()[0]
prev = c.execute("SELECT tokens_used FROM subscriptions WHERE user_id=? AND plan='auto'", (UID,)).fetchone()
prev_used = prev[0] if prev else 0
print('cle temporaire id=%d (valeur jamais imprimee), tokens_used avant=%d' % (kid, prev_used))

ctx = ssl._create_unverified_context()
def call(body, stream):
    req = urllib.request.Request(GW + '/v1/chat/completions', data=json.dumps(body).encode(),
                                 headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'},
                                 method='POST')
    t0 = time.time()
    st, raw = None, b''
    try:
        with urllib.request.urlopen(req, timeout=150, context=ctx) as r:
            st, raw = r.status, r.read()
    except urllib.error.HTTPError as e:
        st, raw = e.code, e.read()
    except Exception as e:
        return 'ERR', str(e)[:200], round(time.time() - t0, 1)
    return st, raw.decode('utf-8', 'replace'), round(time.time() - t0, 1)

Q = 'Look at the image. Answer with exactly four English color words: top-left, top-right, bottom-left, bottom-right.'
msg = [{'role': 'user', 'content': [{'type': 'text', 'text': Q}, {'type': 'image_url', 'image_url': {'url': URI}}]}]

print('\n--- 1) NON-STREAM avec image ---')
st, body, dt = call({'model': 'auto', 'messages': msg, 'max_tokens': 60}, False)
print('http=%s  %.1fs' % (st, dt if isinstance(dt, float) else 0))
print('corps: %.400s' % body)

print('\n--- 2) STREAM avec image ---')
st2, body2, dt2 = call({'model': 'auto', 'messages': msg, 'max_tokens': 60, 'stream': True}, True)
print('http=%s  %.1fs' % (st2, dt2 if isinstance(dt2, float) else 0))
print('extrait: %.300s' % body2.replace('\n', ' '))

print('\n--- 3) Usage / routage enregistres (ce noeud) ---')
rows = c.execute("SELECT id,model_served,supplier,route_reason,tokens,cached_tokens,prompt_tokens,completion_tokens,latency_ms "
                 "FROM usage_logs WHERE key_id=? ORDER BY id", (kid,)).fetchall()
for r in rows:
    print('  id=%s modele=%s canal=%s raison=%s tokens=%s cache=%s (pt=%s ct=%s) latence=%sms' % r)

print('\n--- 4) /api/prices SANS signature depuis ce noeud (attendu 403) ---')
st3, body3, _ = None, '', 0
try:
    with urllib.request.urlopen('https://127.0.0.1:8890/api/prices', timeout=10, context=ctx) as r:
        st3, body3 = r.status, r.read().decode()[:120]
except urllib.error.HTTPError as e:
    st3, body3 = e.code, e.read().decode()[:120]
except Exception as e:
    st3, body3 = 'ERR', str(e)[:120]
print('http=%s %s' % (st3, body3))

print('\n--- 5) /api/prices en LOOPBACK loopback (attendu 200, vue complete) ---')
try:
    with urllib.request.urlopen('http://127.0.0.1:8890/api/prices', timeout=10) as r:
        d = json.loads(r.read().decode())
    print('http=%s modeles=%d supplier_present=%s' % (r.status, len(d.get('models') or {}),
          'supplier' in json.dumps(d)[:200000]))
except Exception as e:
    print('ERR', str(e)[:120])

# ---- nettoyage ----
c.execute("DELETE FROM usage_logs WHERE key_id=?", (kid,))
c.execute("DELETE FROM api_keys WHERE id=?", (kid,))
if prev:
    c.execute("UPDATE subscriptions SET tokens_used=? WHERE user_id=? AND plan='auto'", (prev_used, UID))
c.commit()
rest = c.execute("SELECT COUNT(*) FROM api_keys WHERE name=?", (NAME,)).fetchone()[0]
left = c.execute("SELECT COUNT(*) FROM usage_logs WHERE key_id=?", (kid,)).fetchone()[0]
print('\n--- 6) Nettoyage : cles restantes=%d, lignes usage restantes=%d, tokens_used restaure=%d ---'
      % (rest, left, prev_used))
c.close()
