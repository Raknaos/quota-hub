#!/usr/bin/env python3
# Marge REELLE par modele, calculee sur NOS TARIFS FIXES (table du site,
# $ / 1M tokens entree et sortie) et sur le cout amont reellement paye.
# Lecture seule. Aucune conversion "milliard facture".
import sqlite3, time

PRIX = {   # $ par 1M tokens (nos tarifs fixes, alignes UnoRouter)
    'qwen3.8-flash':       (0.0024, 0.0070),
    'glm-5.3-flash':       (0.02,   0.08),
    'deepseek-v4.1-flash': (0.18,   0.54),
    'grok-4.6':            (0.05,   0.15),
    'deepseek-v4-pro':     (0.04,   0.11),
    'deepseek-v4-flash':   (0.01,   0.03),
    'deepseek-v4-flash-vision-exp': (0.01, 0.03),
    'gemini-3.8-flash':    (0.01,   0.03),
}

c = sqlite3.connect('file:/opt/quota-hub/hub.db?mode=ro', uri=True)
cols = [r[1] for r in c.execute('PRAGMA table_info(usage_logs)').fetchall()]
print('Colonnes usage_logs :', ', '.join(cols))
has_cache = 'cached_tokens' in cols or 'cache_tokens' in cols
ccol = 'cached_tokens' if 'cached_tokens' in cols else ('cache_tokens' if has_cache else None)
now = int(time.time())

for label, since in (('24 h', now - 86400), ('7 jours', now - 7 * 86400)):
    q = ('SELECT model_served, COUNT(*), COALESCE(SUM(prompt_tokens),0),'
         ' COALESCE(SUM(completion_tokens),0),%s COALESCE(SUM(cost_amont_usd),0)'
         ' FROM usage_logs WHERE created_at >= ? AND model_served != ""'
         ' GROUP BY model_served ORDER BY 3 DESC'
         % ((' COALESCE(SUM(%s),0),' % ccol) if ccol else ' 0,'))
    rows = c.execute(q, (since,)).fetchall()
    print('\n=== %s ===' % label)
    print('  %-26s %6s %13s %13s %11s %11s %9s' % ('modele', 'req', 'tok entree', 'tok sortie', 'cout amont', 'revenu', 'marge'))
    trev = tcost = 0.0
    for m, n, pin, pout, pcache, cost in rows:
        p = PRIX.get(m)
        if not p:
            continue
        rev = pin / 1e6 * p[0] + pout / 1e6 * p[1]
        trev += rev
        tcost += cost
        pct = (rev - cost) / rev * 100 if rev else 0
        flag = '  <-- PERTE' if pct < 0 else ('  <-- faible' if pct < 20 else '')
        print('  %-26s %6d %13d %13d %11.5f %11.5f %8.1f%%%s' % (m, n, pin, pout, cost, rev, pct, flag))
    if trev:
        print('  TOTAL revenu=%.5f$ cout=%.5f$ marge=%.1f%%' % (trev, tcost, (trev - tcost) / trev * 100))
c.close()
