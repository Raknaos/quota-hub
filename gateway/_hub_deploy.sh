#!/bin/bash
# Déploiement Quota.Hub Gateway sur un VPS. Usage: bash _hub_deploy.sh <ip>
# Le token A6API local du VPS (/opt/a6-router/key.json) est réutilisé (aucun secret transféré).
set -e
H="$1"
D="C:/Users/bapti/Documents/Projets_Hermes/HubAPI_Quota/gateway"
KEY="C:/Users/bapti/.ssh/pullbg_vps"
echo "=== $H : dirs + user ==="
ssh -i "$KEY" -o ConnectTimeout=15 root@"$H" '
  mkdir -p /opt/quota-hub
  id qh >/dev/null 2>&1 || useradd -r -s /usr/sbin/nologin qh
  chown -R qh:qh /opt/quota-hub
  # COPIE réelle (jamais de symlink : le user qh ne peut pas lire le fichier 600 du user a6router)
  cp -f /opt/a6-router/key.json /opt/quota-hub/key.json && chown qh:qh /opt/quota-hub/key.json && chmod 600 /opt/quota-hub/key.json
  echo "key.json copié (taille: $(stat -c%s /opt/quota-hub/key.json))"'
echo "=== $H : fichiers ==="
scp -i "$KEY" "$D/gateway.py" root@"$H":/opt/quota-hub/gateway.py
scp -i "$KEY" "$D/.env" root@"$H":/opt/quota-hub/.env
scp -i "$KEY" "$D/hub.service" root@"$H":/etc/systemd/system/quota-hub.service
ssh -i "$KEY" root@"$H" '
  chown qh:qh /opt/quota-hub/.env && chmod 600 /opt/quota-hub/.env
  systemctl daemon-reload
  systemctl enable --now quota-hub 2>/dev/null || systemctl restart quota-hub
  sleep 2
  systemctl is-active quota-hub
  curl -s -m 5 http://127.0.0.1:8890/health && echo'
