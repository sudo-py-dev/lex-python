#!/bin/bash
set -e

echo "🐳 Checking Docker Buildx installation..."

if docker buildx version > /dev/null 2>&1; then
    echo "✅ Docker Buildx is already installed."
    exit 0
fi

echo "🚀 Installing Docker Buildx..."

# 1. Prepare Keyrings
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings

# 2. Add Docker's official GPG key
if [ ! -f /etc/apt/keyrings/docker.asc ]; then
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc
fi

# 3. Add the repository to Apt sources
if [ ! -f /etc/apt/sources.list.d/docker.list ]; then
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
fi

# 4. Install plugins and tools
sudo apt-get update
sudo apt-get install -y docker-buildx-plugin postgresql-client

if docker buildx version > /dev/null 2>&1; then
    echo "🎉 Docker Buildx and Postgres tools ready!"
else
    echo "❌ Installation failed. Please check your internet connection."
    exit 1
fi
