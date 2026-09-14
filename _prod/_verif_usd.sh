#!/bin/bash
# Verification post-deploiement du credit en dollars (14-09)
KEY="C:/Users/bapti/.ssh/pullbg_vps"
IP=23.94.144.66
SSHOPT="-o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=10"

echo "=== 1. journal du service : migration + demarrage ==="
ssh $SSHOPT -i "$KEY" root@$IP "journalctl -u quota-hub -n 40 --no-pager | grep -iE 'MIGRATION|usd|credit|erreur|error|Traceback' | tail -12"

echo
echo "=== 2. colonnes reelles en base ==="
ssh $SSHOPT -i "$KEY" root@$IP "sqlite3 /opt/quota-hub/hub.db 'PRAGMA table_info(subscriptions);' | tr '\n' ' '; echo; sqlite3 /opt/quota-hub/hub.db \"SELECT 'migrations: '||COALESCE(GROUP_CONCAT(name),'aucune') FROM migrations;\""

echo
echo "=== 3. soldes des clients reels (en dollars) ==="
ssh $SSHOPT -i "$KEY" root@$IP "sqlite3 -header -column /opt/quota-hub/hub.db \"SELECT plan, status, ROUND(usd_total,4) AS credit_accorde, ROUND(usd_used,4) AS consomme, ROUND(usd_total-usd_used,4) AS solde_usd FROM subscriptions WHERE status='active' OR usd_total>0;\""

echo
echo "=== 4. /admin/stats : le credit est-il remonte ? ==="
ssh $SSHOPT -i "$KEY" root@$IP "TOK=\$(grep -h '^QH_ADMIN_TOKEN=' /opt/quota-hub/.env | cut -d= -f2); curl -sk -H \"X-Admin-Token: \$TOK\" https://127.0.0.1:8890/admin/stats | head -c 700"

echo
echo "=== 5. codes existants : portent-ils un montant en dollars ? ==="
ssh $SSHOPT -i "$KEY" root@$IP "sqlite3 -header -column /opt/quota-hub/hub.db \"SELECT plan, COALESCE(usd,-1) AS usd_du_code, COUNT(*) AS n, SUM(used_by IS NULL) AS dispo FROM codes GROUP BY plan, usd_du_code;\""
