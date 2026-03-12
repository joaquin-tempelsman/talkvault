#!/bin/bash
# Digital Ocean Initial Setup Script
# Run on a fresh Ubuntu 22.04+ droplet as root

set -e
export DEBIAN_FRONTEND=noninteractive

echo "════════════════════════════════════════════"
echo "  TalkVault - Droplet Setup"
echo "════════════════════════════════════════════"

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root"
    exit 1
fi

echo "1. Updating system..."
apt-get update
apt-get upgrade -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"

echo "2. Installing packages..."
apt-get install -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" \
    curl git ufw fail2ban ca-certificates gnupg lsb-release

echo "3. Installing Docker..."
mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl start docker
systemctl enable docker

echo "4. Configuring firewall..."
ufw --force enable
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh

echo "5. Setting up directories..."
mkdir -p /opt/talkvault

echo "6. Configuring fail2ban..."
systemctl start fail2ban
systemctl enable fail2ban

echo ""
echo "════════════════════════════════════════════"
echo "  Setup complete!"
echo "════════════════════════════════════════════"
echo ""
echo "Next: run setup-new-droplet.sh from your local machine"
