#!/usr/bin/env python3
"""Parcours CLIENT complet sur la passerelle locale (loopback) :
inscription -> cle -> credit -> appel /v1/chat/completions.
N'affiche JAMAIS un secret : la cle creee est masquee, le HMAC jamais imprime."""
import json, hmac, hashlib, time, urllib.request, ssl, re, sys

ENVF = '/opt/quota-hub/.env'
env = {}
for line in open(ENVF):
    if '=' in line and not line.strip().startswith('#'):
        k, _, v = line.strip().partition('=')
        env[k] = v
SEC = env.get('QH_INTERNAL_SECRET', '')
ADM = env.get('QH_ADMIN_TOKEN', '')
BASE = 'https://127.0.0.1:8890'
ctx = ssl._create_unverified_context()

def call(path, obj=None, sess=None, method='POST'):
    body = json.dumps(obj).encode() if obj is not None else b''
    ts = str(int(time.time()))
    payload = f"{ts}|{path}|{hashlib.sha256(body).hexdigest()}|"
    sig = hmac.new(SEC.encode(), payload.encode(), hashlib.sha256).hexdigest()
    h = {'X-QH-Ts': ts, 'X-QH-Sig': sig, 'Content-Type': 'application/json'}
    if sess:
        h['X-QH-Session'] = sess
    req = urllib.request.Request(BASE + path, data=body if method != 'GET' else None, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=90, context=ctx) as r:
            return r.status, r.read().decode('utf-8', 'ignore')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'ignore')

email = 'test-parcours-%d@example.invalid' % int(time.time())
pwd = 'MotDePasseTest2026!'

st, b = call('/api/auth/register', {'email': email, 'password': pwd})
print('1. inscription          ->', st)
if st != 200:
    print('   ', b[:200]); sys.exit(1)
sess = json.loads(b)['session']

st, b = call('/api/keys', {'name': 'test parcours'}, sess=sess)
print('2. creation de cle      ->', st)
raw = json.loads(b).get('key', '')
print('   cle recue              :', (raw[:10] + '…') if raw else 'AUCUNE')

# code d'activation cree par l'ops (loopback + jeton admin)
body = json.dumps({'pack': 20}).encode()
req = urllib.request.Request(BASE + '/admin/codes', data=body,
                             headers={'X-Admin-Token': ADM, 'Content-Type': 'application/json'}, method='POST')
try:
    with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
        code = json.loads(r.read().decode())['codes'][0]
    print('3. code pack 20$        -> cree (creditera 40$)')
    st, b = call('/api/redeem', {'code': code}, sess=sess)
    print('   activation           ->', st, json.loads(b).get('credit_added_usd'), '$ de credit')
except Exception as e:
    print('3. code                 -> ERREUR', str(e)[:120])

print('4. appel du modele tel que le client l envoie :')
for model in ['AutoSmart Flash 1.0', 'autosmart-flash-1.0', 'auto', 'automax']:
    body = json.dumps({'model': model, 'messages': [{'role': 'user', 'content': 'dis juste: ok'}], 'max_tokens': 10}).encode()
    req = urllib.request.Request(BASE + '/v1/chat/completions', data=body, method='POST',
                                 headers={'Authorization': 'Bearer ' + raw, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
            d = json.loads(r.read().decode())
            txt = (d.get('choices') or [{}])[0].get('message', {}).get('content', '')[:40]
            print(f"   {model:24s} -> HTTP {r.status} | modele servi: {d.get('model')} | reponse: {txt!r}")
    except urllib.error.HTTPError as e:
        print(f"   {model:24s} -> HTTP {e.code} | {e.read().decode('utf-8','ignore')[:150]}")
    except Exception as e:
        print(f"   {model:24s} -> ERREUR {str(e)[:120]}")

st, b = call('/api/me', None, sess=sess, method='GET')
try:
    d = json.loads(b)
    a = d['subscription']['auto']
    print('5. solde affiche au client :', a['credit_usd'], '$')
except Exception:
    print('5. solde                 ->', b[:150])
