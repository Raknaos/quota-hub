#!/usr/bin/env python3
# Diagnostic AVANT nettoyage : quels orphelins sont reellement morts,
# et qui utilise le port 8895 (gemini-gateway) ?
import sqlite3, time
DB = '/opt/quota-hub/hub.db'
c = sqlite3.connect('file:%s?mode=ro' % DB, uri=True)
now = int(time.time())

print('--- CLES API orphelines (user inexistant) : usage reel ? ---')
rows = c.execute("""
  SELECT k.id, k.name, k.user_id, k.revoked, k.created_at,
         COALESCE((SELECT COUNT(*) FROM usage_logs u WHERE u.key_id=k.id),0) n,
         COALESCE((SELECT MAX(created_at) FROM usage_logs u WHERE u.key_id=k.id),0) last
  FROM api_keys k LEFT JOIN users us ON us.id=k.user_id
  WHERE us.id IS NULL ORDER BY n DESC""").fetchall()
for r in rows:
    age = int((now - r[6]) / 86400) if r[6] else None
    print('  id=%-4s %-14s user=%-4s revoked=%s req=%-6s dernier_usage=%s' %
          (r[0], (r[1] or '?')[:14], r[2], r[3], r[5],
           ('il y a %dj' % age) if age is not None else 'JAMAIS'))
print('  total=%d' % len(rows))

print('\n--- CLES VALIDES (a NE PAS toucher) ---')
for r in c.execute("""SELECT k.id,k.name,k.user_id,COUNT(u.id),MAX(u.created_at)
                      FROM api_keys k JOIN users us ON us.id=k.user_id
                      LEFT JOIN usage_logs u ON u.key_id=k.id AND u.created_at > ?
                      GROUP BY k.id ORDER BY 4 DESC""", (now - 7 * 86400,)).fetchall():
    print('  id=%-4s %-14s user=%-4s req_7j=%-6s' % (r[0], (r[1] or '?')[:14], r[2], r[3]))

print('\n--- ABONNEMENTS orphelins (user inexistant) ---')
for r in c.execute("""SELECT s.user_id,s.plan,s.status,s.tokens_total,s.tokens_used
                      FROM subscriptions s LEFT JOIN users us ON us.id=s.user_id
                      WHERE us.id IS NULL ORDER BY s.tokens_total DESC LIMIT 8""").fetchall():
    print('  user=%-4s plan=%-6s statut=%-9s total=%-13s used=%s' % r)
n = c.execute("""SELECT COUNT(*) FROM subscriptions s LEFT JOIN users us ON us.id=s.user_id
                 WHERE us.id IS NULL""").fetchone()[0]
print('  total=%d' % n)

print('\n--- CODES rattaches a un user inexistant ---')
n2 = c.execute("""SELECT COUNT(*) FROM codes co LEFT JOIN users us ON us.id=co.used_by
                  WHERE co.used_by IS NOT NULL AND us.id IS NULL""").fetchone()[0]
print('  total=%d' % n2)
c.close()
