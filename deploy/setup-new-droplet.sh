#!/bin/bash
# Complete droplet setup — run from LOCAL machine
# Usage: ./deploy/setup-new-droplet.sh <DROPLET_IP>

set -euo pipefail

DROPLET_IP="$1"
SSH_KEY_PATH="$HOME/.ssh/docean-talkvault"
APP_REPO="${GITHUB_APP_REPO:-YOUR_USER/talkvault}"
VAULT_REPO="${GITHUB_VAULT_REPO:-YOUR_USER/YOUR_VAULT}"
APP_DIR="/opt/talkvault"
VAULT_DIR="/opt/talkvault/vault"

run_on_droplet() { ssh -o StrictHostKeyChecking=no -i "$SSH_KEY_PATH" root@"$DROPLET_IP" "$@"; }

if [ -z "$DROPLET_IP" ]; then
    echo "Usage: $0 <DROPLET_IP>"
    exit 1
fi

echo "═══ TalkVault Droplet Setup ═══"
echo "IP: $DROPLET_IP"

# Step 1: SSH key
if [ ! -f "$SSH_KEY_PATH" ]; then
    echo "Creating SSH key..."
    ssh-keygen -t ed25519 -f "$SSH_KEY_PATH" -C "talkvault-deploy" -N ""
    cat "${SSH_KEY_PATH}.pub"
    echo ""
    echo "Add this key to your droplet's authorized_keys, then press ENTER"
    read -r
fi

# Step 2: SSH config
ssh-keygen -R "$DROPLET_IP" 2>/dev/null || true
grep -q "Host talkvault" ~/.ssh/config 2>/dev/null || cat >> ~/.ssh/config << EOF

Host talkvault
  Hostname $DROPLET_IP
  User root
  IdentityFile $SSH_KEY_PATH
  AddKeysToAgent yes
EOF

# Step 3: Test connection
echo "Testing SSH..."
run_on_droplet "echo 'Connected'"

# Step 4: Run droplet setup
echo "Running droplet setup script..."
scp -i "$SSH_KEY_PATH" deploy/digital-ocean-setup.sh root@"$DROPLET_IP":/tmp/
run_on_droplet "bash /tmp/digital-ocean-setup.sh"

# Step 5: Deploy keys (app repo)
echo "Creating deploy key for app repo..."
APP_KEY=$(run_on_droplet "ssh-keygen -t ed25519 -f ~/.ssh/github_app -C 'talkvault-app-deploy' -N '' >/dev/null 2>&1; cat ~/.ssh/github_app.pub")
echo "App deploy key: $APP_KEY"
echo "Add to https://github.com/$APP_REPO/settings/keys (read-only), then press ENTER"
read -r

# Step 6: Deploy key (vault repo)
echo "Creating deploy key for vault repo..."
VAULT_KEY=$(run_on_droplet "ssh-keygen -t ed25519 -f ~/.ssh/github_vault -C 'talkvault-vault-deploy' -N '' >/dev/null 2>&1; cat ~/.ssh/github_vault.pub")
echo "Vault deploy key: $VAULT_KEY"
echo "Add to https://github.com/$VAULT_REPO/settings/keys (write access!), then press ENTER"
read -r

# Step 7: SSH config for GitHub (two deploy keys)
run_on_droplet "cat > ~/.ssh/config << 'SSHEOF'
Host github-app
  Hostname github.com
  IdentityFile ~/.ssh/github_app
  AddKeysToAgent yes

Host github-vault
  Hostname github.com
  IdentityFile ~/.ssh/github_vault
  AddKeysToAgent yes
SSHEOF"

# Step 8: Clone repos
echo "Cloning app repo..."
run_on_droplet "cd $APP_DIR && git init && git remote add origin git@github-app:$APP_REPO.git && GIT_SSH_COMMAND='ssh -o StrictHostKeyChecking=no' git pull origin main"

echo "Cloning vault repo..."
run_on_droplet "git clone git@github-vault:$VAULT_REPO.git $VAULT_DIR || (cd $VAULT_DIR && git pull)"

# Configure git user for vault commits
run_on_droplet "cd $VAULT_DIR && git config user.name 'TalkVault Bot' && git config user.email 'bot@talkvault'"

# Step 9: Copy .env
if [ -f ".env" ]; then
    echo "Copying .env..."
    scp -i "$SSH_KEY_PATH" .env root@"$DROPLET_IP":"$APP_DIR"/.env
fi

# Step 10: Build and start
echo "Building and starting bot..."
run_on_droplet "cd $APP_DIR && docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose.prod.yml --env-file .env up -d --build"
run_on_droplet "docker builder prune -af && docker system prune -f" >/dev/null 2>&1

echo ""
echo "═══ Setup Complete ═══"
echo "SSH: ssh talkvault"
echo "Logs: ssh talkvault 'cd $APP_DIR && docker compose -f infrastructure/docker-compose.yml logs -f'"
