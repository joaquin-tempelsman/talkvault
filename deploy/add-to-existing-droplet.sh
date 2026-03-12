#!/bin/bash
# Add TalkVault to an existing droplet (already running Zenith)
# Usage: ./deploy/add-to-existing-droplet.sh
# Assumes: ssh docean works, Docker is installed, .env is ready locally

set -euo pipefail

REMOTE="docean"
APP_DIR="/opt/talkvault"
VAULT_DIR="/opt/talkvault/vault"
APP_REPO="git@github.com:joaquin-tempelsman/talkvault.git"
VAULT_REPO="git@github.com:joaquin-tempelsman/memory_vault.git"

run() { ssh "$REMOTE" "$@"; }

echo "═══ Adding TalkVault to existing droplet ═══"

# Step 1: Create directory
echo "1. Creating app directory..."
run "mkdir -p $APP_DIR"

# Step 2: Generate SSH key for vault repo (needs write access)
echo "2. Creating SSH deploy key for vault repo..."
KEY_EXISTS=$(run "test -f ~/.ssh/talkvault_vault && echo yes || echo no")
if [ "$KEY_EXISTS" = "no" ]; then
    run "ssh-keygen -t ed25519 -f ~/.ssh/talkvault_vault -C 'talkvault-vault-deploy' -N ''"
    echo ""
    echo "══════════════════════════════════════════════════════"
    echo "  Add this deploy key to memory_vault repo:"
    echo "  https://github.com/joaquin-tempelsman/memory_vault/settings/keys"
    echo "  IMPORTANT: Enable 'Allow write access'"
    echo "══════════════════════════════════════════════════════"
    run "cat ~/.ssh/talkvault_vault.pub"
    echo ""
    read -rp "Press ENTER after adding the deploy key..."
else
    echo "  Key already exists, skipping."
fi

# Step 3: SSH config for vault repo
echo "3. Configuring SSH for vault repo..."
run "grep -q 'Host github-vault' ~/.ssh/config 2>/dev/null || cat >> ~/.ssh/config << 'EOF'

Host github-vault
  Hostname github.com
  IdentityFile ~/.ssh/talkvault_vault
  StrictHostKeyChecking no
EOF"

# Step 4: Clone app repo
echo "4. Cloning TalkVault app..."
run "test -d $APP_DIR/.git && echo 'App repo exists, pulling...' && cd $APP_DIR && git pull || git clone $APP_REPO $APP_DIR"

# Step 5: Clone vault repo
echo "5. Cloning vault repo..."
VAULT_REPO_SSH="git@github-vault:joaquin-tempelsman/memory_vault.git"
run "test -d $VAULT_DIR/.git && echo 'Vault exists, pulling...' && cd $VAULT_DIR && git pull || git clone $VAULT_REPO_SSH $VAULT_DIR"
run "cd $VAULT_DIR && git config user.name 'TalkVault Bot' && git config user.email 'bot@talkvault'"

# Step 6: Seed vault registry if empty
echo "6. Seeding vault registry..."
run "mkdir -p $VAULT_DIR/_meta/note_groups $VAULT_DIR/_meta/entity_groups"

# Step 7: Copy .env
echo "7. Copying .env..."
if [ -f ".env" ]; then
    scp .env "$REMOTE:$APP_DIR/.env"
else
    echo "  No local .env found. Create one from .env.example and re-run, or copy manually."
    echo "  scp .env $REMOTE:$APP_DIR/.env"
fi

# Step 8: Build and start
echo "8. Building and starting TalkVault..."
run "cd $APP_DIR && docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose.prod.yml --env-file .env up -d --build"

echo ""
echo "═══ TalkVault deployed ═══"
echo "Logs: ssh $REMOTE 'cd $APP_DIR && docker compose -f infrastructure/docker-compose.yml logs -f'"
echo "Status: ssh $REMOTE 'docker ps | grep talkvault'"
