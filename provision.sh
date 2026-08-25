#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing prerequisites"
apt-get update -y
apt-get install -y curl gnupg lsb-release ca-certificates software-properties-common

echo "==> Installing Docker (needed for the docker task driver)"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
  usermod -aG docker vagrant
fi

echo "==> Adding the HashiCorp apt repository"
wget -qO- https://apt.releases.hashicorp.com/gpg | gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" \
  > /etc/apt/sources.list.d/hashicorp.list

echo "==> Installing Nomad"
apt-get update -y
apt-get install -y nomad

echo "==> Configuring Nomad to run in dev mode as a systemd service"
systemctl stop nomad 2>/dev/null || true
mkdir -p /opt/nomad/data

# This overrides the package's default unit (which expects a full
# server/client config in /etc/nomad.d) with a simple dev-mode agent -
# fine for local testing, not for anything resembling production.
cat >/etc/systemd/system/nomad.service <<'EOF'
[Unit]
Description=Nomad Agent (dev mode)
Wants=network-online.target
After=network-online.target docker.service

[Service]
ExecStart=/usr/bin/nomad agent -dev -bind=0.0.0.0 -data-dir=/opt/nomad/data
ExecReload=/bin/kill -HUP $MAINPID
KillMode=process
Restart=on-failure
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable nomad
systemctl restart nomad

echo "==> Waiting for the Nomad API to come up..."
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:4646/v1/status/leader >/dev/null; then
    echo "Nomad is up."
    break
  fi
  sleep 1
done

echo "==> Registering the sample job"
if [ -f /vagrant/example-job.nomad.hcl ]; then
  nomad job run /vagrant/example-job.nomad.hcl
fi

echo "==> Provisioning complete. Nomad UI: http://localhost:4646"
