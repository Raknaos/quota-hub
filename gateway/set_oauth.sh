#!/bin/bash
# Saisie LOCALE des identifiants OAuth (saisie masquée, rien n'est affiché ni historisé).
# Usage : bash /opt/quota-hub/set_oauth.sh
set -e
cd /opt/quota-hub
touch .env
echo "Colle/tape chaque valeur puis Entrée (la saisie est masquée)."
for v in QH_GOOGLE_CLIENT_ID QH_GOOGLE_CLIENT_SECRET QH_GITHUB_CLIENT_ID QH_GITHUB_CLIENT_SECRET; do
  read -r -s -p "$v : " val; echo
  sed -i "/^$v=/d" .env
  printf '%s=%s\n' "$v" "$val" >> .env
done
unset val
chmod 600 .env
systemctl restart quota-hub
sleep 2
echo -n "service : "; systemctl is-active quota-hub
for v in QH_GOOGLE_CLIENT_ID QH_GOOGLE_CLIENT_SECRET QH_GITHUB_CLIENT_ID QH_GITHUB_CLIENT_SECRET; do
  if grep -q "^$v=$" .env 2>/dev/null; then echo "$v : absent/vide"; else echo "$v : renseigné"; fi
done
echo "Test : https://quota-hub.vercel.app/ → Espace membre → Continuer avec Google/GitHub"