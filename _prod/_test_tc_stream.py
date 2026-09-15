#!/usr/bin/env python3
"""Test du relais SSE : un tool_call TEXTE doit devenir NATIF dans le flux."""
import json, sys, io

src = open('/opt/quota-hub/gateway.prod.py', encoding='utf-8').read()
start = src.index('_SAFE_DELTA = (')
end = src.index('def sse_chunk')
ns = {'json': json, 'secrets': __import__('secrets'), 'time': __import__('time'),
      'PUBLIC_MODEL_ID': 'autosmart-flash-1.0'}
exec(src[start:end], ns)
tc = ns['text_toolcalls']; hp = ns['_tc_hold_prefix']

# --- simulation du relais : on rejoue la logique de la garde sur des chunks ---
raw_chunks = [
    '<tool_call name="ter', 'minal">{"command": "ssh root@1.2.3.4 \"uptime\"",',
    ' "timeout": 45}</tool', '_call>'
]
tools = [{'type': 'function', 'function': {'name': 'terminal'}}]
sent_content = []
held, hold = [], True
for c in raw_chunks:
    held.append(c)
    acc = ''.join(held)
    if hp(acc):
        pass                      # maintenu
    else:
        hold = False
        sent_content.append(acc)
        held = []
print('chunks texte envoyes au client pendant le flux :', sent_content if sent_content else 'AUCUN (correct)')
calls, rest = tc(''.join(held) if hold else '', tools)
print('converti en natif a la fin  :', bool(calls), '| outil:', calls[0]['function']['name'] if calls else None)
print('argument JSON rejoue        :', json.loads(calls[0]['function']['arguments']) if calls else None)
assert not sent_content and calls, 'ECHEC: le texte serait parti au client'
print('RESULTAT: OK - le client recoit un vrai tool_calls, plus de blocage')
