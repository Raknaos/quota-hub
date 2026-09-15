import os, ssl, urllib.request
DIR = '/opt/a6-router'
def _pinned_ssl():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        if os.path.exists(os.path.join(DIR, 'quota-gw.pem')):
            ctx.load_verify_locations(os.path.join(DIR, 'quota-gw.pem'))
            ctx.verify_mode = ssl.CERT_REQUIRED
    except Exception:
        pass
    return ctx
ctx = _pinned_ssl()
print('mode verification :', ctx.verify_mode)
r = urllib.request.Request('https://23.94.144.66:8890/health')
with urllib.request.urlopen(r, timeout=10, context=ctx) as resp:
    print('health via TLS epingle ->', resp.status, resp.read(80).decode())
# preuve que le pin sert a quelque chose : sans le pem, CERT_REQUIRED doit echouer
ctx2 = ssl.create_default_context()
try:
    with urllib.request.urlopen(r, timeout=8, context=ctx2) as resp:
        print('SANS pin: repondu (surprenant)')
except Exception as e:
    print('SANS pin (CA de confiance standard) : refuse ->', type(e).__name__)
