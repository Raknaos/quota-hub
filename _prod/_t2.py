import json, sys
BS = chr(92)
QT = chr(34)
src = open('/opt/quota-hub/gateway.prod.py', encoding='utf-8').read()
a = src.index('def _tc_hold_prefix'); b = src.index('def sse_chunk')
ns = {'json': json}
exec(src[a:b], ns)
tc = ns['text_toolcalls']
tools = [{'type': 'function', 'function': {'name': 'terminal'}}]

# Variante 1: arguments sans guillemets internes
t1 = '<tool_call name=' + QT + 'terminal' + QT + '>{' + QT + 'command' + QT + ': ' + QT + 'uptime' + QT + ', ' + QT + 'timeout' + QT + ': 45}</' + 'tool_call>'
c1 = tc(t1, tools)[0]
print('1. simple            :', 'OK' if c1 else 'ECHEC')

# Variante 2: comme la capture reelle, commandes ssh avec guillemets echappes
inner = 'ssh -i ' + QT + 'key' + QT + ' root@1.2.3.4 ' + QT + 'systemctl is-active cutbg' + QT
t2 = ('<tool_call name=' + QT + 'terminal' + QT + '>{' + QT + 'command' + QT + ': '
      + QT + inner.replace(QT, BS + QT) + QT + ', ' + QT + 'timeout' + QT + ': 45}</' + 'tool_call>')
c2, _ = tc(t2, tools)
print('2. quotes echappees  :', 'OK' if c2 else 'ECHEC')
if c2:
    back = json.loads(c2[0]['function']['arguments'])
    print('   command reconstruite:', repr(back['command'])[:70])
    assert back['timeout'] == 45
print('FINI')
