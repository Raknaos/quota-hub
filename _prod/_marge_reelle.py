#!/usr/bin/env python3
# Marge REELLE par modele : ce qu'on encaisse ($10 / milliard de tokens
# factures, cf. conversion du site) moins ce qu'on paie a l'amont
# (cost_amont_usd, deja en USD). Lecture seule.
import sqlite3, time
c = sqlite3.connect('file:/opt/quota-hub/hub.db?mode=ro', uri=True)
now = int(time.time())
SELL_PER_1E9 = 10.0     # prix de vente du site : 1e9 tokens factures = 10 $

for label, since in (('24 h', now - 86400), ('7 jours', now - 7 * 86400)):
    print('=== %s ===' % label)
    rows = c.execute("""
        SELECT model_served, supplier, COUNT(*) n,
               SUM(tokens) billed, SUM(cost_amont_usd) cost
        FROM usage_logs
        WHERE created_at >= ? AND model_served IS NOT NULL AND model_served != ''
        GROUP BY model_served ORDER BY billed DESC""", (since,)).fetchall()
    tot_b = sum((r[3] or 0) for r in rows)
    tot_c = sum((r[4] or 0) for r in rows)
    print('  %-24s %7s %14s %12s %10s %9s' % ('modele', 'req', 'tokens fact.', 'cout amont', 'revenu', 'marge'))
    for r in rows:
        billed = r[3] or 0
        cost = r[4] or 0
        rev = billed / 1e9 * SELL_PER_1E9
        pct = ((rev - cost) / rev * 100) if rev else 0
        print('  %-24s %7d %14d %12.6f %10.5f %8.1f%%' % (r[0], r[2], billed, cost, rev, pct))
    rev_t = tot_b / 1e9 * SELL_PER_1E9
    print('  TOTAL : tokens=%d cout=%.6f$ revenu=%.5f$ marge=%.1f%%'
          % (tot_b, tot_c, rev_t, ((rev_t - tot_c) / rev_t * 100) if rev_t else 0))
    print('  cout amont par milliard facture = %.2f$  (prix de vente = %.2f$)' % (
        (tot_c / (tot_b / 1e9)) if tot_b else 0, SELL_PER_1E9))
    print()
c.close()
