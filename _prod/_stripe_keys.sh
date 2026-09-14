#!/bin/bash
# ============================================================================
# Saisie SECURISEE des cles Stripe pour la passerelle Quota.Hub.
# Rien n'est affiche, rien n'est journalise, rien ne passe par le chat :
# la saisie se fait ICI, sur le serveur, en mode masque (read -s).
#
#   bash /opt/quota-hub/_stripe_keys.sh
#
# Cote Stripe, il faut d'abord creer un endpoint de webhook :
#   URL    : https://smartapi.cheap/api/stripe/webhook
#   Evenement : checkout.session.completed
# et copier le "Signing secret" (whsec_...) qu'il affiche.
# ============================================================================
set -e
ENVF=/opt/quota-hub/.env

echo "== Clés Stripe — saisie masquée (les caractères ne s'affichent pas) =="
read -rsp "1/2 Clé secrète Stripe (sk_live_... ou sk_test_...) : " SK; echo
read -rsp "2/2 Secret du webhook (whsec_...)                 : " WH; echo

case "$SK" in
  sk_*) ;  *) echo "REFUS : une clé secrète Stripe commence par sk_"; exit 1 ;;
esac
case "$WH" in
  whsec_*) ;; *) echo "REFUS : un secret de webhook commence par whsec_"; exit 1 ;;
esac

cp -a "$ENVF" "$ENVF.bak-$(date +%Y%m%d-%H%M)"
grep -vE '^(QH_STRIPE_SECRET_KEY|QH_STRIPE_WEBHOOK_SECRET)=' "$ENVF" > "$ENVF.tmp" || true
printf 'QH_STRIPE_SECRET_KEY=%s\nQH_STRIPE_WEBHOOK_SECRET=%s\n' "$SK" "$WH" >> "$ENVF.tmp"
chmod --reference="$ENVF" "$ENVF.tmp"
chown --reference="$ENVF" "$ENVF.tmp"
mv "$ENVF.tmp" "$ENVF"

systemctl restart quota-hub
sleep 2
echo "--- état ---"
echo -n "service   : "; systemctl is-active quota-hub
echo -n "clé posée : "; grep -q '^QH_STRIPE_SECRET_KEY=sk_' "$ENVF" && echo oui || echo NON
echo -n "mode      : "; grep -q '^QH_STRIPE_SECRET_KEY=sk_test_' "$ENVF" && echo "TEST (aucun vrai paiement)" || echo "LIVE (paiements réels)"
echo -n "webhook   : "; grep -q '^QH_STRIPE_WEBHOOK_SECRET=whsec_' "$ENVF" && echo oui || echo NON
