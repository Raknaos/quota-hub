#!/bin/bash
# Aligne un noeud replica sur l'etat de service reel du primaire (14-09) :
#  - meme market30.py que Sandra (la version recente, sonde cache calibree)
#  - meme cadence partout (1200 s = 20 min, la cadence reellement en service)
# Motif : l'audit a montre que Sandra tournait en 1200 s avec un code different
# de celui des replicas (120 s), et que _deploy_market.sh ecrivait 120 -> un
# redeploiement a froid ne reproduisait PAS l'etat en service.
set -u
NODE="$1"; SRC="$2"
KEY="${QH_SSH_KEY:-C:/Users/bapti/.ssh/pullbg_vps}"
SSHOPT="-o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=10"
STAMP=$(date +%Y%m%d-%H%M)
echo "=== $NODE ==="
scp $SSHOPT -i "$KEY" "$SRC" "root@$NODE:/tmp/market30.new.py" || { echo "scp KO"; exit 1; }
ssh $SSHOPT -i "$KEY" "root@$NODE" bash -s <<EOF
set -e
/usr/bin/python3 -m py_compile /tmp/market30.new.py && echo "compile OK"
cp -a /opt/quota-hub/market30.py /opt/quota-hub/market30.py.bak-$STAMP 2>/dev/null || true
cp /tmp/market30.new.py /opt/quota-hub/market30.py
[ -f /opt/quota-hub/market30.py.bak-$STAMP ] && chown --reference=/opt/quota-hub/market30.py.bak-$STAMP /opt/quota-hub/market30.py
rm -f /tmp/market30.new.py
mkdir -p /etc/systemd/system/quota-market.service.d
printf '[Service]\nEnvironment=QH_MARKET_INTERVAL=1200\nEnvironment=QH_PROBE_INTERVAL=1200\n' > /etc/systemd/system/quota-market.service.d/10-qh-interval.conf
systemctl daemon-reload
systemctl restart quota-market
sleep 3
echo -n "market="; systemctl is-active quota-market
echo -n "env="; systemctl show quota-market -p Environment --value
md5sum /opt/quota-hub/market30.py
EOF
