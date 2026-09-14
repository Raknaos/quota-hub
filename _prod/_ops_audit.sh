#!/bin/bash
# Ops du 14-09 apres audit. A executer sur le PRIMAIRE (Sandra) pour la partie
# donnees, et sur CHAQUE noeud pour la partie systeme.
set -u
KEY="${QH_SSH_KEY:-C:/Users/bapti/.ssh/pullbg_vps}"
SSHOPT="-o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=10"
MODE="$1"; NODE="$2"

if [ "$MODE" = "data" ]; then
echo "=== Nettoyage des orphelins (Sandra) ==="
ssh $SSHOPT -i "$KEY" "root@$NODE" python3 - <<'PY'
import sqlite3, time
c = sqlite3.connect('/opt/quota-hub/hub.db')
# 1. RÉVOQUER les seules clés orphelines RÉELLEMENT mortes : celles dont le
#    user_id n'existe pas. Les clés de trafic (fleet-*, Hermes) appartiennent à
#    un user existant et ne sont PAS touchées.
cur = c.execute("""UPDATE api_keys SET revoked=1
    WHERE revoked=0 AND user_id NOT IN (SELECT id FROM users)""")
print('  cles orphelines revoquees :', cur.rowcount)
# 2. Abonnements orphelins -> 'inactive' (on ne SUPPRIME rien : on garde la trace)
cur2 = c.execute("""UPDATE subscriptions SET status='inactive'
    WHERE status!='inactive' AND user_id NOT IN (SELECT id FROM users)""")
print('  abonnements orphelins desactives :', cur2.rowcount)
c.commit()
left_k = c.execute("SELECT COUNT(*) FROM api_keys WHERE revoked=0 AND user_id NOT IN (SELECT id FROM users)").fetchone()[0]
left_s = c.execute("SELECT COUNT(*) FROM subscriptions WHERE status='active' AND user_id NOT IN (SELECT id FROM users)").fetchone()[0]
print('  restants orphelins actifs : cles=%d abonnements=%d' % (left_k, left_s))
c.close()
PY
echo "=== Sauvegarde rotative de hub.db (script + cron) ==="
ssh $SSHOPT -i "$KEY" "root@$NODE" bash -s <<'EOS'
set -e
cat > /opt/quota-hub/_backup-db.py <<'PY'
#!/usr/bin/env python3
"""Sauvegarde quotidienne ROTATIVE de hub.db (14-09).
Motif : l'audit n'a trouve QU'UNE sauvegarde, vieille de 2 jours et incomplete
(511 lignes sur 7184). Une sauvegarde non verifiee n'est pas une sauvegarde."""
import datetime, os, sqlite3, sys
SRC = '/opt/quota-hub/hub.db'
DIR = '/opt/quota-hub/backups'
KEEP = 14
os.makedirs(DIR, exist_ok=True)
stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
out = os.path.join(DIR, 'hub-%s.db' % stamp)
src = sqlite3.connect(SRC)
dst = sqlite3.connect(out)
with dst:
    src.backup(dst)
dst.close(); src.close()
ok = sqlite3.connect(out).execute('PRAGMA integrity_check').fetchone()[0]
n = sqlite3.connect(out).execute('SELECT COUNT(*) FROM usage_logs').fetchone()[0]
print('%s backup=%s integrite=%s lignes_usage=%d' % (
    datetime.datetime.now().isoformat(timespec='seconds'), stamp, ok, n))
if ok != 'ok':
    sys.exit(1)
files = sorted((os.path.join(DIR, f) for f in os.listdir(DIR) if f.startswith('hub-')), reverse=True)
for f in files[KEEP:]:
    os.remove(f)
    print('  rotation: supprime %s' % os.path.basename(f))
PY
chmod +x /opt/quota-hub/_backup-db.py
echo "-- execution immediate (preuve que ca marche) --"
/usr/bin/python3 /opt/quota-hub/_backup-db.py
echo "-- cron quotidien 04:30 --"
( crontab -l 2>/dev/null | grep -v "_backup-db.py" ; echo "30 4 * * * /usr/bin/python3 /opt/quota-hub/_backup-db.py >> /var/log/qh-backup.log 2>&1" ) | crontab -
crontab -l | grep backup
EOS
fi

if [ "$MODE" = "sys" ]; then
echo "=== $NODE : journald borne + MemoryMax ==="
ssh $SSHOPT -i "$KEY" "root@$NODE" bash -s <<'EOS'
set -e
# 1. journald borne (Sandra etait a 229 Mo, au-dela du standard flotte de 200 Mo)
mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\nSystemMaxUse=200M\nSystemMaxFileSize=50M\n' > /etc/systemd/journald.conf.d/10-qh-size.conf
systemctl restart systemd-journald
journalctl --vacuum-size=200M >/dev/null 2>&1 || true
echo -n "journal="; journalctl --disk-usage
# 2. MemoryMax : usage mesure <= 42 Mo, plafond 384 Mo = filet de securite sans effet
mkdir -p /etc/systemd/system/quota-hub.service.d /etc/systemd/system/quota-market.service.d
printf '[Service]\nMemoryMax=384M\n' > /etc/systemd/system/quota-hub.service.d/10-qh-mem.conf
printf '[Service]\nMemoryMax=384M\n' > /etc/systemd/system/quota-market.service.d/10-qh-mem.conf
systemctl daemon-reload
systemctl restart quota-hub quota-market
sleep 3
systemctl show quota-hub -p MemoryMax -p MemoryCurrent --value
systemctl is-active quota-hub quota-market
EOS
fi
