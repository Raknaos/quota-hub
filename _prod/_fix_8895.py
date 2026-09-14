#!/usr/bin/env python3
# Correctif 14-09 : la passerelle Antigravity (port 8895) avait
#     def _auth(self):
#         return True
# -> n'importe qui sur Internet consommait l'abonnement Google One AI Pro
#    sans clé (constate : POST /v1/chat/completions -> 200 + reponse servie).
# On rend la verification REELLE : loopback accepte (agents Hermes locaux),
# distant = clé GATEWAY_API_KEY obligatoire, comparaison a temps constant.
import shutil, sys, time

P = '/opt/gemini-gateway/gemini_gateway.py'
s = open(P, encoding='utf-8').read()
orig = s

OLD_IMPORT = "import json, os, sys, time, secrets, re, urllib.request, urllib.parse, urllib.error, threading"
NEW_IMPORT = "import json, os, sys, time, secrets, re, hmac, urllib.request, urllib.parse, urllib.error, threading"

OLD_AUTH = """    def _auth(self):
        return True
"""
NEW_AUTH = '''    def _auth(self):
        """Cle d'acces OBLIGATOIRE hors loopback (corrige le 14-09).
        AVANT : `return True` -> la passerelle repondait 200 a n'importe qui sur
        Internet, qui consommait donc l'abonnement Google One AI Pro du
        proprietaire sans aucune cle. Les agents Hermes LOCAUX (loopback) restent
        acceptes sans cle pour ne rien casser ; le distant exige la cle.
        """
        try:
            if self.client_address[0] in ('127.0.0.1', '::1'):
                return True
        except Exception:
            pass
        if not SERVER_API_KEY:
            return False        # aucune cle configuree : on FERME au lieu d'ouvrir
        h = (self.headers.get('Authorization') or '').strip()
        tok = h[7:].strip() if h[:7].lower() == 'bearer ' else ''
        return bool(tok) and hmac.compare_digest(tok, SERVER_API_KEY)
'''

if NEW_IMPORT in s and 'CORRIGE le 14-09' in s:
    print('deja corrige'); sys.exit(0)
if OLD_IMPORT not in s:
    print('ANCRE IMPORT INTROUVABLE'); sys.exit(1)
if OLD_AUTH not in s:
    print('ANCRE _auth INTROUVABLE'); sys.exit(1)

s = s.replace(OLD_IMPORT, NEW_IMPORT, 1).replace(OLD_AUTH, NEW_AUTH, 1)
stamp = time.strftime('%Y%m%d-%H%M')
shutil.copy2(P, P + '.bak-' + stamp)
open(P, 'w', encoding='utf-8').write(s)
import py_compile
py_compile.compile(P, doraise=True)
print('corrige, sauvegarde=%s, compilation OK' % (P + '.bak-' + stamp))
