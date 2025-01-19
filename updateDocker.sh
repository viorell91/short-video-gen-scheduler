#!/bin/bash

# Exit on any error
set -e

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the script's directory
cd "$SCRIPT_DIR"

# Pull the latest changes from git
echo "Pulling latest changes from git..."
git pull

# Perform Docker Compose up with a forced rebuild
echo "Rebuilding and restarting Docker Compose services..."
docker compose up --build --force-recreate -d
