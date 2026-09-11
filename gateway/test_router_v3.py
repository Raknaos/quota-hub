# -*- coding: utf-8 -*-
"""Test du routeur V3 (pin par clé API + conversation). Lancé localement :
    python3 gateway/test_router_v3.py
Scénarios du mode auto multi-utilisateurs, marché simulé, aucun réseau.
Rappel formule réelle du classement : coût = ((eff_in + out) / 2) / succès,
avec eff_in pondéré par le cache24 du canal ; ici cache24 absent -> (in+out)/2."""
import importlib.util
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('A6API_KEY', 'sk-TEST-ONLY')       # clé amont factice (aucun appel réseau)
os.environ.setdefault('A6API_KEY_PATH', os.path.join(HERE, '_no_such_key.json'))
spec = importlib.util.spec_from_file_location('gw', os.path.join(HERE, 'gateway.py'))
gw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gw)

M1, M2, M3 = 'qwen3.8-flash', 'glm-5.3-flash', 'qwen3.8-pro'   # M1/M3 même fournisseur A
BASE = {
    M1: {'supplier': 'A', 'in': 0.6, 'out': 2.4, 'cache_read': 0.06, 'success': 100},
    M2: {'supplier': 'B', 'in': 0.3, 'out': 1.2, 'cache_read': 0.03, 'success': 100},
    M3: {'supplier': 'A', 'in': 0.5, 'out': 2.0, 'cache_read': 0.05, 'success': 100},
}
SIM = {k: dict(v) for k, v in BASE.items()}
MODELS = [M1, M2, M3]
gw.market30_best = lambda m: None                       # pas de vue 30 j
gw.market_get = lambda m: {'best': SIM[m]} if m in SIM else None
gw.COOLDOWN = {}

ok = True

def check(label, got, want):
    global ok
    status = 'OK  ' if got == want else 'FAIL'
    if got != want:
        ok = False
    print(f'{status} {label}: {got} (attendu {want})')

now = time.time()

# 1) conversation NEUVE -> le moins cher (glm 0.75 < pro 1.25 < qwen 1.5)
m, _ = gw.pick_model(MODELS, ctx={'key_id': 1, 'sig': 'conv-alice'})
check('conv neuve -> moins cher', m, M2)

# 2) conversation CHAUDE sur m1 (40k tokens en cache) -> on GARDE m1
#    rester = 0.6*10000 + 0.06*40000 + 2.4*500 = 9600 ; seuil -15% = 8160
#    switcher(glm) = 0.3*50000 + 1.2*500 = 15600 -> on garde.
gw.CONV[(1, 'conv-alice')] = {'model': M1, 'supplier': 'A', 'ts': now,
                              'tin': 50000, 'tout': 500, 'cached': 40000}
m, _ = gw.pick_model(MODELS, ctx={'key_id': 1, 'sig': 'conv-alice'})
check('conv chaude + cache -> garder m1', m, M1)

# 3) la même clé mais une AUTRE conversation -> moins cher (isolation par conv)
m, _ = gw.pick_model(MODELS, ctx={'key_id': 1, 'sig': 'conv-bob'})
check('autre conv même clé -> moins cher', m, M2)

# 4) une AUTRE clé avec la même sig -> pas d état -> moins cher (isolation par clé)
m, _ = gw.pick_model(MODELS, ctx={'key_id': 2, 'sig': 'conv-alice'})
check('autre clé même sig -> moins cher', m, M2)

# 5) gain énorme, modèle supplier B (0.36) et pro supplier A (0.15) :
#    switcher = 0.10*50000+0.20*500 = 5100 < 8160 -> bascule, et meme
#    fournisseur A préféré (pro 0.15 <= best*1.25) -> qwen3.8-pro.
SIM[M2]['in'], SIM[M2]['out'] = 0.12, 0.6
SIM[M3]['in'], SIM[M3]['out'] = 0.10, 0.20
m, _ = gw.pick_model(MODELS, ctx={'key_id': 1, 'sig': 'conv-alice'})
check('gain énorme -> bascule même fournisseur (m3)', m, M3)

# 6) même bascule mais AUCUN modèle du fournisseur A -> le moins cher (m2)
gw.market_get = lambda m: {'best': SIM[m]} if m in (M1, M2) else None
m, _ = gw.pick_model(MODELS, ctx={'key_id': 1, 'sig': 'conv-alice'})
check('gain énorme -> bascule vers le moins cher (m2)', m, M2)

# 7) conversation FROIDE (> CONV_TTL) -> moins cher
SIM.update({k: dict(v) for k, v in BASE.items()})
gw.market_get = lambda m: {'best': SIM[m]} if m in SIM else None
gw.CONV[(1, 'conv-alice')]['ts'] = now - gw.CONV_TTL - 100
m, _ = gw.pick_model(MODELS, ctx={'key_id': 1, 'sig': 'conv-alice'})
check('conv froide -> moins cher', m, M2)

# 8) sans contexte (appels internes) -> ancien pin global conservé.
#    m1 ramené à (0.5+1.0)/2 = 0.75 == best -> dans la marge 1.5x -> gardé.
SIM[M1]['in'], SIM[M1]['out'] = 0.5, 1.0
gw.PIN['model'] = M1
gw.PIN['since'] = now
m, _ = gw.pick_model(MODELS)
check('sans ctx -> pin global m1', m, M1)

# 9) prune : la borne mémoire ne casse rien
for i in range(100):
    gw.CONV[(99, f's{i}')] = {'model': M1, 'ts': now - gw.CONV_TTL * 4, 'tin': 1, 'tout': 1, 'cached': 0}
gw.conv_prune()
assert (99, 's0') not in gw.CONV, 'les entrées TTL expirées doivent être purgées'
print('OK   prune TTL exécuté, entrées mortes purgées')

print('RESULTAT:', 'TOUT VERT' if ok else 'ECHEC')
sys.exit(0 if ok else 1)
