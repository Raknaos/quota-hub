#!/bin/bash
# ============================================================================
# Ajoute l'enregistrement A  gw.smartapi.cheap -> 23.94.144.66  via l'API OVH.
# LIT les cles dans ~/.ovh/api-credentials.txt (rempli par Baptiste en local).
# N'IMPRIME JAMAIS une cle, un signature, ni un en-tete. Sortie = etat utile.
# ============================================================================
set -u
CRED="$HOME/.ovh/api-credentials.txt"
DOMAIN="smartapi.cheap"
SUB="gw"
TARGET_IP="23.94.144.66"

if [ ! -f "$CRED" ]; then echo "FICHIER DE CLES ABSENT: $CRED"; exit 1; fi
# shellcheck disable=SC1090
source "$CRED"
if [ -z "${OVH_APPLICATION_KEY:-}" ] || [ -z "${OVH_APPLICATION_SECRET:-}" ] || [ -z "${OVH_CONSUMER_KEY:-}" ]; then
  echo "CLES INCOMPLETE: remplace les 3 lignes vides dans $CRED"; exit 1
fi

API="https://eu.api.ovh.com/1.0"
ovh_call() { # $1=GET|POST  $2=/path  [$3=json body]
  local method="$1" p="$2" body="${3:-}"
  local tstate ts sig
  tstate=$(curl -sL -m 15 "$API/time" | tr -dc '0-9')
  [ -z "$tstate" ] && { echo "OVH: /time illisible"; return 1; }
  ts="$tstate"
  # signature OVH : $1$ + sha1hex( SECRET + KEY + METHOD + URL + BODY + TS )
  sig=$(printf '%s+%s+%s+%s+%s+%s' "$OVH_APPLICATION_SECRET" "$OVH_APPLICATION_KEY" \
        "$method" "$API$p" "$body" "$ts" | sha1sum | cut -d' ' -f1)
  if [ "$method" = "GET" ]; then
    curl -sL -m 25 "$API$p" -H "X-Ovh-Application: $OVH_APPLICATION_KEY" \
      -H "X-Ovh-Consumer: $OVH_CONSUMER_KEY" -H "X-Ovh-Timestamp: $ts" -H "X-Ovh-Signature: \$1\$${sig}"
  else
    curl -sL -m 25 -X POST "$API$p" -H "X-Ovh-Application: $OVH_APPLICATION_KEY" \
      -H "X-Ovh-Consumer: $OVH_CONSUMER_KEY" -H "X-Ovh-Timestamp: $ts" \
      -H "X-Ovh-Signature: \$1\$${sig}" -H "Content-Type: application/json" -d "$body"
  fi
}

echo "=== 1. la zone $DOMAIN est-elle joignable ? ==="
zones=$(ovh_call GET "/domain/nameServer" )
[ -z "$zones" ] && { echo "APPEL OVH ECHOUE (cles invalides ou droit manquant)"; exit 1; }
recs=$(ovh_call GET "/domain/$DOMAIN/zone")
if ! echo "$recs" | grep -q '"'; then
  echo "  zone absente -> creation"; ovh_call POST "/domain/$DOMAIN/zone" '{}' | head -c 160; echo
fi
echo "=== 2. enregistrement gw. existant ? ==="
cur=$(ovh_call GET "/domain/$DOMAIN/zone")
if echo "$cur" | grep -qE "\"subDomain\":\s*\"$SUB\""; then
  echo "  existe deja:"; echo "$cur" | tr ',' '\n' | grep -A3 -B1 "\"$SUB\"" | head -8
else
  echo "  absent -> ajout"
  ovh_call POST "/domain/$DOMAIN/zone" "{\"subDomain\":\"$SUB\",\"field\":\"$SUB\",\"value\":\"$TARGET_IP\",\"ttl\":600,\"recordType\":\"A\"}" | head -c 200; echo
fi
echo "=== 3. refresh de la zone ==="
ovh_call POST "/domain/$DOMAIN/zone/refresh" '{}' | head -c 120; echo
echo "=== 4. verification DNS (resolv.conf, puis 1.1.1.1) ==="
for i in 1 2 3 4 5 6; do
  ip=$(nslookup -type=A "$SUB.$DOMAIN" 9.9.9.9 2>/dev/null | awk '/^Address: /{print $2}' | grep -E '^[0-9.]+$' | head -1)
  [ -n "$ip" ] && break; sleep 20
done
echo "  $SUB.$DOMAIN -> ${ip:-RESOUT ENCORE PAS}"
[ "${ip:-}" = "$TARGET_IP" ] && echo "OK DNS" || echo "A VERIFIER"
