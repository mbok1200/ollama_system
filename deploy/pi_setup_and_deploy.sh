#!/usr/bin/env bash
set -euo pipefail

usage(){
  cat <<EOF
Usage: $0 [--local] [--host PI_HOST] [--ssh-user SSH_USER] [--ssh-key SSH_KEY] [--domain DOMAIN --email EMAIL]

Run locally on the Pi with --local, or run from your workstation and connect over SSH to --host.

If run remotely (default):
  --host PI_HOST       Remote Raspberry Pi IP or hostname (required)

If run locally (--local):
  run the script on the Pi as a regular user (or via sudo)

Optional (for TLS):
  --domain DOMAIN      Domain name pointing to Pi (for certbot)
  --email EMAIL        Email for certbot registration (required if --domain provided)

Optional (remote only):
  --ssh-user SSH_USER  Initial SSH user (default: pi)
  --ssh-key SSH_KEY    Path to SSH private key (default: use ssh agent)

EOF
}

LOCAL=false
PI_HOST=""
SSH_USER="pi"
SSH_KEY=""
DOMAIN=""
EMAIL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --local) LOCAL=true; shift 1;;
    --host) PI_HOST="$2"; shift 2;;
    --ssh-user) SSH_USER="$2"; shift 2;;
    --ssh-key) SSH_KEY="$2"; shift 2;;
    --domain) DOMAIN="$2"; shift 2;;
    --email) EMAIL="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 1;;
  esac
done

if [[ "$LOCAL" == false && -z "$PI_HOST" ]]; then echo "--host is required when not running --local"; usage; exit 1; fi
if [[ -n "$DOMAIN" && -z "$EMAIL" ]]; then echo "--email is required when --domain is provided"; usage; exit 1; fi

SSH_OPTS=( -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/dev/null )
if [[ -n "$SSH_KEY" ]]; then
  SSH_OPTS+=( -i "$SSH_KEY" )
fi

if [[ "$LOCAL" == true ]]; then
  echo "Running in local mode (no SSH)."
else
  REMOTE="${SSH_USER}@${PI_HOST}"
fi

echo "==> Ensuring user 'bradi' exists"
if [[ "$LOCAL" == true ]]; then
  if ! id -u bradi >/dev/null 2>&1; then
    sudo adduser --disabled-password --gecos "" bradi
    sudo usermod -aG sudo bradi
    echo "Created user bradi"
  else
    echo "User bradi already exists"
  fi
else
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
fi

echo "==> Syncing project to /home/bradi/ollama_system"
RSYNC_EXCLUDES=(--exclude '.venv' --exclude '.git' --exclude '__pycache__')
if [[ "$LOCAL" == true ]]; then
  sudo mkdir -p /home/bradi/ollama_system
  sudo rsync -az "${RSYNC_EXCLUDES[@]}" ./ /home/bradi/ollama_system/
else
  if [[ -n "$SSH_KEY" ]]; then
    rsync -az -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=accept-new" "${RSYNC_EXCLUDES[@]}" ./ "bradi@${PI_HOST}:/home/bradi/ollama_system"
  else
    rsync -az -e "ssh ${SSH_OPTS[*]}" "${RSYNC_EXCLUDES[@]}" ./ "bradi@${PI_HOST}:/home/bradi/ollama_system"
  fi
fi

echo "==> Fixing permissions"
if [[ "$LOCAL" == true ]]; then
  sudo chown -R bradi:bradi /home/bradi/ollama_system
else
  ssh "${SSH_OPTS[@]}" "bradi@${PI_HOST}" sudo chown -R bradi:bradi /home/bradi/ollama_system
fi

echo "==> Installing system packages"
if [[ "$LOCAL" == true ]]; then
  sudo apt update
  sudo apt install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx
else
  ssh "${SSH_OPTS[@]}" "bradi@${PI_HOST}" sudo bash -s <<'REMOTE'
set -e
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx
REMOTE
fi

echo "==> Creating venv and installing Python dependencies"
if [[ "$LOCAL" == true ]]; then
  cd /home/bradi/ollama_system
  sudo -u bradi python3 -m venv .venv
  sudo -u bradi bash -c 'source .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt'
else
  ssh "${SSH_OPTS[@]}" "bradi@${PI_HOST}" bash -s <<'REMOTE'
set -e
cd /home/bradi/ollama_system
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
REMOTE
fi

echo "==> Installing systemd unit and nginx config"
if [[ -n "$DOMAIN" ]]; then
  if [[ "$LOCAL" == true ]]; then
    sudo sed 's/__DOMAIN__/'"${DOMAIN//\/\\}"'/g' /home/bradi/ollama_system/deploy/nginx/ollama_system.conf > /tmp/ollama_system.conf
    sudo cp /home/bradi/ollama_system/deploy/systemd/ollama_system.service /etc/systemd/system/ollama_system.service
    sudo cp /tmp/ollama_system.conf /etc/nginx/sites-available/ollama_system.conf
    sudo ln -sf /etc/nginx/sites-available/ollama_system.conf /etc/nginx/sites-enabled/ollama_system.conf
    sudo systemctl daemon-reload
    sudo systemctl enable --now ollama_system
    sudo nginx -t
    sudo systemctl restart nginx
  else
    ssh "${SSH_OPTS[@]}" "bradi@${PI_HOST}" sudo bash -s <<REMOTE
set -e
sed 's/__DOMAIN__/${DOMAIN//\/\\}/g' /home/bradi/ollama_system/deploy/nginx/ollama_system.conf > /tmp/ollama_system.conf
cp /home/bradi/ollama_system/deploy/systemd/ollama_system.service /etc/systemd/system/ollama_system.service
cp /tmp/ollama_system.conf /etc/nginx/sites-available/ollama_system.conf
ln -sf /etc/nginx/sites-available/ollama_system.conf /etc/nginx/sites-enabled/ollama_system.conf
systemctl daemon-reload
systemctl enable --now ollama_system
nginx -t
systemctl restart nginx
REMOTE
  fi
else
  if [[ "$LOCAL" == true ]]; then
    sudo sed 's/__HOST__/'"${HOSTNAME:-localhost}"'/g' /home/bradi/ollama_system/deploy/nginx/ollama_system_nossl.conf > /tmp/ollama_system.conf
    sudo cp /home/bradi/ollama_system/deploy/systemd/ollama_system.service /etc/systemd/system/ollama_system.service
    sudo cp /tmp/ollama_system.conf /etc/nginx/sites-available/ollama_system.conf
    sudo ln -sf /etc/nginx/sites-available/ollama_system.conf /etc/nginx/sites-enabled/ollama_system.conf
    sudo systemctl daemon-reload
    sudo systemctl enable --now ollama_system
    sudo nginx -t
    sudo systemctl restart nginx
  else
    ssh "${SSH_OPTS[@]}" "bradi@${PI_HOST}" sudo bash -s <<REMOTE
set -e
sed 's/__HOST__/${PI_HOST//\/\\}/g' /home/bradi/ollama_system/deploy/nginx/ollama_system_nossl.conf > /tmp/ollama_system.conf
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
  echo "==> Obtaining TLS certificate for ${DOMAIN}"
  if [[ "$LOCAL" == true ]]; then
    sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" || echo "Certbot failed or already present"
  else
    ssh "${SSH_OPTS[@]}" "bradi@${PI_HOST}" sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" || echo "Certbot failed or already present"
  fi
else
  echo "==> No domain provided; serving over HTTP"
fi

if [[ "$LOCAL" == true ]]; then
  echo "==> Deployment finished. Check logs: sudo journalctl -u ollama_system -f"
else
  echo "==> Deployment finished. Check logs: ssh bradi@${PI_HOST} 'sudo journalctl -u ollama_system -f'"
fi
