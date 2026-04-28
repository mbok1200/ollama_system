#!/usr/bin/env bash
set -euo pipefail

usage(){
  cat <<EOF
Usage: $0 --host PI_HOST [--ssh-user SSH_USER] [--ssh-key SSH_KEY] [--domain DOMAIN --email EMAIL]

This script copies the project to the Raspberry Pi, creates user 'bradi', sets up venv, installs deps,
configures systemd and nginx. If you provide --domain and --email the script will also request a TLS
certificate via certbot. If you don't have a domain, omit --domain and the site will be served over HTTP.

Required:
  --host PI_HOST       Remote Raspberry Pi IP or hostname

Optional (for TLS):
  --domain DOMAIN      Domain name pointing to Pi (for certbot)
  --email EMAIL        Email for certbot registration (required if --domain provided)

Optional:
  --ssh-user SSH_USER  Initial SSH user (default: pi)
  --ssh-key SSH_KEY    Path to SSH private key (default: use ssh agent)

EOF
}

PI_HOST=""
SSH_USER="pi"
SSH_KEY=""
DOMAIN=""
EMAIL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) PI_HOST="$2"; shift 2;;
    --ssh-user) SSH_USER="$2"; shift 2;;
    --ssh-key) SSH_KEY="$2"; shift 2;;
    --domain) DOMAIN="$2"; shift 2;;
    --email) EMAIL="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 1;;
  esac
done

if [[ -z "$PI_HOST" ]]; then echo "--host is required"; usage; exit 1; fi
if [[ -n "$DOMAIN" && -z "$EMAIL" ]]; then echo "--email is required when --domain is provided"; usage; exit 1; fi

SSH_OPTS=( -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/dev/null )
if [[ -n "$SSH_KEY" ]]; then
  SSH_OPTS+=( -i "$SSH_KEY" )
fi

REMOTE="${SSH_USER}@${PI_HOST}"

echo "==> Ensuring user 'bradi' exists on ${PI_HOST} (via ${SSH_USER})"
ssh "${SSH_OPTS[@]}" "$REMOTE" bash -s <<'REMOTE'
set -e
if ! id -u bradi >/dev/null 2>&1; then
  sudo adduser --disabled-password --gecos "" bradi
  sudo usermod -aG sudo bradi
  echo "Created user bradi"
else
  echo "User bradi already exists"
fi
REMOTE

echo "==> Syncing project to /home/bradi/ollama_system"
RSYNC_EXCLUDES=(--exclude '.venv' --exclude '.git' --exclude '__pycache__')
if [[ -n "$SSH_KEY" ]]; then
  rsync -az -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=accept-new" "${RSYNC_EXCLUDES[@]}" ./ "bradi@${PI_HOST}:/home/bradi/ollama_system"
else
  rsync -az -e "ssh ${SSH_OPTS[*]}" "${RSYNC_EXCLUDES[@]}" ./ "bradi@${PI_HOST}:/home/bradi/ollama_system"
fi

echo "==> Fixing permissions"
ssh "${SSH_OPTS[@]}" "bradi@${PI_HOST}" sudo chown -R bradi:bradi /home/bradi/ollama_system

echo "==> Installing system packages on Pi"
ssh "${SSH_OPTS[@]}" "bradi@${PI_HOST}" sudo bash -s <<'REMOTE'
set -e
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx
REMOTE

echo "==> Creating venv and installing Python dependencies"
ssh "${SSH_OPTS[@]}" "bradi@${PI_HOST}" bash -s <<'REMOTE'
set -e
cd /home/bradi/ollama_system
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
REMOTE

echo "==> Installing systemd unit and nginx config"
if [[ -n "$DOMAIN" ]]; then
  # replace placeholder with real domain and install ssl nginx config
  ssh "${SSH_OPTS[@]}" "bradi@${PI_HOST}" sudo bash -s <<REMOTE
set -e
sed 's/__DOMAIN__/${DOMAIN//\/\\/}/g' /home/bradi/ollama_system/deploy/nginx/ollama_system.conf > /tmp/ollama_system.conf
cp /home/bradi/ollama_system/deploy/systemd/ollama_system.service /etc/systemd/system/ollama_system.service
cp /tmp/ollama_system.conf /etc/nginx/sites-available/ollama_system.conf
ln -sf /etc/nginx/sites-available/ollama_system.conf /etc/nginx/sites-enabled/ollama_system.conf
systemctl daemon-reload
systemctl enable --now ollama_system
nginx -t
systemctl restart nginx
REMOTE
  else
  # no domain: install non-ssl nginx config and substitute host/IP
  ssh "${SSH_OPTS[@]}" "bradi@${PI_HOST}" sudo bash -s <<REMOTE
set -e
# replace placeholder with PI_HOST
sed 's/__HOST__/${PI_HOST//\/\\/}/g' /home/bradi/ollama_system/deploy/nginx/ollama_system_nossl.conf > /tmp/ollama_system.conf
cp /home/bradi/ollama_system/deploy/systemd/ollama_system.service /etc/systemd/system/ollama_system.service
cp /tmp/ollama_system.conf /etc/nginx/sites-available/ollama_system.conf
ln -sf /etc/nginx/sites-available/ollama_system.conf /etc/nginx/sites-enabled/ollama_system.conf
systemctl daemon-reload
systemctl enable --now ollama_system
nginx -t
systemctl restart nginx
REMOTE
fi
fi

if [[ -n "$DOMAIN" ]]; then
  echo "==> Obtaining TLS certificate with certbot for ${DOMAIN}"
  ssh "${SSH_OPTS[@]}" "bradi@${PI_HOST}" sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" || echo "Certbot failed or already present"
else
  echo "==> No domain provided; skipping TLS obtainment (site served over HTTP)"
fi

echo "==> Deployment finished. You can check logs with: ssh bradi@${PI_HOST} 'sudo journalctl -u ollama_system -f'"
