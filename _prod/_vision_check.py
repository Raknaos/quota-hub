#!/usr/bin/env python3
# Analyse d'une capture d'ecran via la passerelle SmartAPI (qwen3.8-flash lit les
# images : verifie 4/4 au test image du 14-09). La cle est lue dans le .env Hermes
# et n'est JAMAIS imprimee ni ecrite dans un fichier.
import base64, json, os, re, sys, urllib.request, urllib.error

IMG = r"C:\Users\bapti\AppData\Roaming\Hermes\composer-images\image_3d7f21.png"
ENV = r"C:\Users\bapti\AppData\Local\hermes\.env"

def load_env(path):
    d = {}
    try:
        for line in open(path, encoding='utf-8', errors='replace'):
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            d[k.strip()] = v.strip().strip('"').strip("'")
    except Exception as e:
        print('env illisible:', e)
    return d

env = dict(os.environ)
env.update(load_env(ENV))

b64 = base64.b64encode(open(IMG, 'rb').read()).decode()
print('image: %d Ko, base64: %d car.' % (os.path.getsize(IMG) // 1024, len(b64)))

PROMPT = ("Decris precisement cette capture d'ecran d'un site web. "
          "Recopie TOUT le texte visible et lisible : titres, noms de modeles, prix, "
          "chiffres, boutons, et surtout TOUT message d'erreur. Precise ou se trouve "
          "l'erreur a l'ecran. Reponds en francais, de facon structuree.")

TRIES = [
    ('smartapi/qwen3.8-flash', 'https://smartapi.cheap/v1/chat/completions',
     'HERMES_CUSTOM_SMARTAPI_API_KEY', 'qwen3.8-flash'),
    ('gateway-8895/gemini-3.8-flash', 'http://23.94.144.66:8895/v1/chat/completions',
     'GATEWAY_API_KEY', 'gemini-3.8-flash'),
    ('smartapi/glm-5.3-flash', 'https://smartapi.cheap/v1/chat/completions',
     'HERMES_CUSTOM_SMARTAPI_API_KEY', 'glm-5.3-flash'),
]

for label, url, keyname, model in TRIES:
    key = env.get(keyname) or env.get('HERMES_CUSTOM_SMARTAPI_API_KEY')
    if not key:
        print('[%s] pas de cle %s' % (label, keyname)); continue
    body = json.dumps({
        'model': model,
        'messages': [{'role': 'user', 'content': [
            {'type': 'text', 'text': PROMPT},
            {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + b64}}]}],
        'max_tokens': 1200, 'temperature': 0,
    }).encode()
    req = urllib.request.Request(url, data=body, headers={
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + key,
        'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'),
    })
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            d = json.loads(r.read().decode('utf-8', 'replace'))
        txt = (d.get('choices') or [{}])[0].get('message', {}).get('content') or ''
        print('\n=== [%s / %s] http=200 ===' % (label, model))
        print(txt.strip())
        if txt.strip():
            sys.exit(0)
        print('(reponse vide, essai suivant)')
    except urllib.error.HTTPError as e:
        print('[%s] HTTP %s : %s' % (label, e.code, e.read().decode('utf-8', 'replace')[:220]))
    except Exception as e:
        print('[%s] %s: %s' % (label, type(e).__name__, str(e)[:180]))
