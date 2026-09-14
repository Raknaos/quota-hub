#!/usr/bin/env bash
# Deploie le worker marche 30j sur la passerelle Quota.Hub (.66) et cree son service.
set -eu

DIR=/opt/quota-hub
SVC=quota-market.service

echo "=== 1. droits sur le fichier deploye ==="
chown qh:qh "$DIR/market30.py"
chmod 755 "$DIR/market30.py"
ls -la "$DIR/market30.py"

echo
echo "=== 2. mise a jour du service ==="
cat > "/etc/systemd/system/$SVC" <<'UNIT'
[Unit]
Description=Quota.Hub — Worker marche 30j (moyenne ponderee + fiabilite + top 5)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=qh
Group=qh
WorkingDirectory=/opt/quota-hub
Environment=QH_MARKET_PORT=8891
Environment=QH_MARKET_INTERVAL=120
Environment=QH_DB=/opt/quota-hub/hub.db
ExecStart=/usr/bin/python3 /opt/quota-hub/market30.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/quota-market.log
StandardError=append:/var/log/quota-market.log
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true

[Install]
WantedBy=multi-user.target
UNIT

touch /var/log/quota-market.log
chown qh:qh /var/log/quota-market.log

systemctl daemon-reload
systemctl enable "$SVC" >/dev/null 2>&1 || true
systemctl restart "$SVC"
sleep 8
echo "statut : $(systemctl is-active $SVC)"
systemctl status "$SVC" --no-pager | head -12

echo
echo "=== 3. attente de la premiere passe (max 150 s) ==="
for i in $(seq 1 30); do
  if curl -sf -m 5 http://127.0.0.1:8891/health >/tmp/mh.json 2>/dev/null; then
    cat /tmp/mh.json; echo
    break
  fi
  sleep 5
done

echo
echo "=== 4. GET /api/prices (extrait) ==="
curl -s -m 20 http://127.0.0.1:8891/api/prices > /tmp/mp.json || echo "(echec)"
python3 - <<'PY'
import json, os
p = "/tmp/mp.json"
if not os.path.exists(p) or os.path.getsize(p) < 20:
    print("pas de reponse"); raise SystemExit
d = json.load(open(p, encoding="utf-8"))
print("genere il y a:", d.get("age_s"), "s | passes:", d.get("passes"), "| stale:", d.get("stale"))
print(f"{'MODELE':30s} {'n':>4s} {'fiables':>7s}  meilleur (cout30 $/M | pire h | SR24 | cache | j)")
for m, v in d.get("models", {}).items():
    b = v.get("best")
    if not b:
        print(f"{m:30s} {v.get('n_listings',0):4d} {v.get('n_robust',0):7d}  -- aucun canal fiable")
        continue
    print(f"{m:30s} {v['n_listings']:4d} {v['n_robust']:7d}  {b['cost30']:.6f} | {b['worst']:>5.1f}% | "
          f"{b['sr24']:>5.1f}% | {b['cache']:>4.1f}% | {b['days_since_change']:>4.1f}j")
PY

echo
echo "=== 5. table sqlite market30 ==="
python3 -c "
import sqlite3
c=sqlite3.connect('/opt/quota-hub/hub.db')
try:
    n=c.execute('select count(*) from market30').fetchone()[0]
    m=c.execute('select count(distinct model) from market30').fetchone()[0]
    print('lignes:',n,'| modeles:',m)
except Exception as e:
    print('table absente:',e)
"

echo
echo "=== 6. port en ecoute (doit etre 127.0.0.1 uniquement) ==="
ss -ltnp 2>/dev/null | grep -E "8891|8890|8765" || echo "(rien)"
