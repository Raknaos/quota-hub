#!/bin/bash
# Deploiement d'une revision de gateway.py sur un noeud, avec sauvegarde,
# controle de compilation, redemarrage et verification de sante.
# usage: _deploy_gw.sh <IP> <chemin/gateway.py>
set -u
NODE="$1"; SRC="$2"
KEY="${QH_SSH_KEY:-C:/Users/bapti/.ssh/pullbg_vps}"
SSHOPT="-o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=10"
STAMP=$(date +%Y%m%d-%H%M)
echo "=== $NODE ==="
scp $SSHOPT -i "$KEY" "$SRC" "root@$NODE:/tmp/gateway.new.py" || { echo "scp KO"; exit 1; }
ssh $SSHOPT -i "$KEY" "root@$NODE" bash -s <<EOF
set -e
/usr/bin/python3 -m py_compile /tmp/gateway.new.py && echo "compile OK"
cp -a /opt/quota-hub/gateway.py /opt/quota-hub/gateway.py.bak-$STAMP
cp /tmp/gateway.new.py /opt/quota-hub/gateway.py
chown --reference=/opt/quota-hub/gateway.py.bak-$STAMP /opt/quota-hub/gateway.py
chmod --reference=/opt/quota-hub/gateway.py.bak-$STAMP /opt/quota-hub/gateway.py
rm -f /tmp/gateway.new.py
systemctl restart quota-hub
sleep 3
systemctl is-active quota-hub
curl -sk -m 8 https://127.0.0.1:8890/health; echo
md5sum /opt/quota-hub/gateway.py
EOF
