import json, hmac, hashlib, time, urllib.request, ssl
ctx = ssl._create_unverified_context()
env = {}
for line in open('/opt/quota-hub/.env'):
    if '=' in line and not line.strip().startswith('#'):
        k, _, v = line.strip().partition('=')
        env[k] = v
SEC = env.get('QH_INTERNAL_SECRET', '')
ADM = env.get('QH_ADMIN_TOKEN', '')
BASE = 'https://127.0.0.1:8890'

def call(path, obj=None, sess=None, admin=False):
    body = json.dumps(obj).encode() if obj is not None else b''
    ts = str(int(time.time()))
    payload = f"{ts}|{path}|{hashlib.sha256(body).hexdigest()}|"
    sig = hmac.new(SEC.encode(), payload.encode(), hashlib.sha256).hexdigest()
    h = {'X-QH-Ts': ts, 'X-QH-Sig': sig, 'Content-Type': 'application/json'}
    if sess:
        h['X-QH-Session'] = sess
    if admin:
        h['X-Admin-Token'] = ADM
    req = urllib.request.Request(BASE + path, data=body, headers=h, method='POST')
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        return json.loads(r.read().decode())

email = 'nonreg-%d@example.invalid' % int(time.time())
sess = call('/api/auth/register', {'email': email, 'password': 'NonRegression2026!Test'})['session']
key = call('/api/keys', {'name': 'nonreg'}, sess=sess)['key']
code = call('/admin/codes', {'pack': 20}, admin=True)['codes'][0]
call('/api/redeem', {'code': code}, sess=sess)
print('compte de test credite (40$)')

body = json.dumps({'model': 'autosmart-flash-1.0',
                   'messages': [{'role': 'user', 'content': 'Dis simplement bonjour en un mot.'}],
                   'stream': True, 'max_tokens': 400}).encode()
req = urllib.request.Request(BASE + '/v1/chat/completions', data=body, method='POST',
                             headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
txt, n, fin = '', 0, None
with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
    for line in r:
        s = line.strip()
        if not s.startswith(b'data:'):
            continue
        p = s[5:].strip()
        if p == b'[DONE]':
            break
        n += 1
        try:
            d = json.loads(p)
            ch = (d.get('choices') or [{}])[0]
            txt += ((ch.get('delta') or {}).get('content') or '')
            fin = ch.get('finish_reason') or fin
        except Exception:
            pass
print('chunks recus :', n, '| finish:', fin)
print('texte reassemble :', repr(txt[:80]))
assert txt.strip(), 'REGRESSION: aucun contenu recu'
print('NON-REGRESSION STREAM: OK')
