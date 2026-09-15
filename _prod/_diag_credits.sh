#!/bin/bash
# Diagnostic "insufficient credits" (14-09) — ne JAMAIS afficher la cle amont.
KEY="/C/Users/bapti/.ssh/pullbg_vps"
IP=23.94.144.66
SSHOPT="-o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=10"
run() { ssh $SSHOPT -i "$KEY" root@$IP "$1"; }

echo "=== 1. erreurs amont recentes (journal passerelle) ==="
run "journalctl -u quota-hub -n 400 --no-pager | grep -iE 'insufficient|credit|402|400|quota' | tail -8"

echo
echo "=== 2. notre passerelle : que renvoie-t-elle a un client ? ==="
run "TOK=\$(grep -h '^QH_ADMIN_TOKEN=' /opt/quota-hub/.env | cut -d= -f2); curl -sk -H \"X-Admin-Token: \$TOK\" https://127.0.0.1:8890/admin/stats | python3 -c 'import sys,json; d=json.load(sys.stdin); print(json.dumps({k:d[k] for k in (\"users\",\"requests\",\"cooldowns\",\"pin\")}, ensure_ascii=False))'"

echo
echo "=== 3. test REEL de l'amont A6API (le verdict) ==="
run "K=\$(python3 -c \"import json;d=json.load(open('/opt/quota-hub/key.json'));print(d.get('key') or d.get('api_key') or d.get('token') or '')\"); \
     echo -n '  code HTTP amont : '; \
     curl -s -o /tmp/up.json -w '%{http_code}\n' -X POST https://api.a6api.com/v1/chat/completions \
       -H \"Authorization: Bearer \$K\" -H 'Content-Type: application/json' \
       -d '{\"model\":\"glm-5.3-flash\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":5}'; \
     echo -n '  reponse amont   : '; head -c 260 /tmp/up.json; echo"

echo
echo "=== 4. endpoint de solde cote A6API ? ==="
run "K=\$(python3 -c \"import json;d=json.load(open('/opt/quota-hub/key.json'));print(d.get('key') or d.get('api_key') or d.get('token') or '')\"); \
     for p in /v1/dashboard/billing/subscription /v1/credits /api/user/self /v1/balance; do \
       printf '  %-40s -> ' \"\$p\"; \
       curl -s -o /tmp/bal.json -w '%{http_code}' -H \"Authorization: Bearer \$K\" \"https://api.a6api.com\$p\"; \
       echo -n ' '; head -c 160 /tmp/bal.json; echo; \
     done"

echo
echo "=== 5. quels canaux amont repondent encore ? (marche A6API) ==="
run "curl -s -m 20 'https://a6api.com/api/marketplace/public/channels/search?model=glm-5.3-flash' -H 'Accept: application/json' | head -c 300"
