#!/bin/bash

# vCon Server Uninstallation Script
# This script will remove all vCon Server components from the system.

set -e

# Function to display help message
usage() {
    echo "vCon Server Uninstallation Script"
    echo ""
    echo "This will remove all vCon Server containers, images, volumes, networks, data, and the vcon user."
    echo ""
    echo "Usage: sudo $0"
    exit 1
}

# Require root
if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: This script must be run as root."
    exit 1
fi

# Confirm
read -p "Are you sure you want to completely remove vCon Server and all its data? This action is irreversible. (y/N): " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# Stop and remove Docker containers, images, volumes, and network
if docker network ls | grep -q conserver; then
    echo "Stopping and removing Docker containers and network..."
    docker compose -f /opt/vcon-server/docker-compose.yml down --volumes --remove-orphans || true
    docker network rm conserver || true
fi

# Remove Docker images related to vcon-server and vcon-admin
for img in $(docker images --format '{{.Repository}}:{{.Tag}}' | grep -E 'vcon-server|vcon-admin'); do
    docker rmi "$img" || true
done

# Remove persistent data
if [ -d /opt/vcon-data ]; then
    echo "Removing persistent data in /opt/vcon-data..."
    rm -rf /opt/vcon-data
fi

# Remove cloned repositories
if [ -d /opt/vcon-server ]; then
    echo "Removing /opt/vcon-server..."
    rm -rf /opt/vcon-server
fi
if [ -d /opt/vcon-admin ]; then
    echo "Removing /opt/vcon-admin..."
    rm -rf /opt/vcon-admin
fi

# Remove vcon user (if exists and not logged in)
if id "vcon" &>/dev/null; then
    if ! pgrep -u vcon > /dev/null; then
        echo "Removing user 'vcon'..."
        userdel -r vcon || true
    else
        echo "User 'vcon' is currently logged in. Skipping user removal."
    fi
fi

echo "vCon Server uninstallation complete." 