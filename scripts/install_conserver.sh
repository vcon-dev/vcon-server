#!/bin/bash

# Conserver vCon Server Installation Script
# Based on installation notes for conserver integration

set -e

# Function to display help message
display_help() {
    echo "Conserver vCon Server Installation Script"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -d, --domain DOMAIN       Domain name for the installation (required)"
    echo "  -e, --email EMAIL         Email for DNS registration (required)"
    echo "  -t, --token TOKEN         API token (default: generates random token)"
    echo "  -h, --help                Display this help message"
    echo ""
    exit 0
}

# Function to log messages
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Parse command line arguments
RANDOM_TOKEN=$(openssl rand -hex 8)
API_TOKEN=${RANDOM_TOKEN}

while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -d|--domain)
            DOMAIN="$2"
            shift 2
            ;;
        -e|--email)
            EMAIL="$2"
            shift 2
            ;;
        -t|--token)
            API_TOKEN="$2"
            shift 2
            ;;
        -h|--help)
            display_help
            shift
            ;;
        *)
            echo "Unknown option: $1"
            display_help
            exit 1
            ;;
    esac
done

# Check for required parameters
if [ -z "$DOMAIN" ]; then
    echo "ERROR: Domain name is required. Use --domain to specify."
    display_help
    exit 1
fi

if [ -z "$EMAIL" ]; then
    echo "ERROR: Email is required. Use --email to specify."
    display_help
    exit 1
fi

# Display configuration and confirm
echo "========================================"
echo "Conserver vCon Server Installation"
echo "========================================"
echo "Domain: $DOMAIN"
echo "Email: $EMAIL"
echo "API Token: $API_TOKEN"
echo "========================================"
echo ""
read -p "Do you want to proceed with this configuration? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Installation cancelled."
    exit 0
fi

# Welcome message
log "Starting Conserver vCon Server installation"
log "Domain: $DOMAIN"
log "Email: $EMAIL"
log "API Token: $API_TOKEN"

# Check if running as root
if [ "$(id -u)" -ne 0 ]; then
    log "ERROR: This script must be run as root"
    exit 1
fi

# Create vcon user and directories if not exist
if ! id "vcon" &>/dev/null; then
    log "Creating user 'vcon'..."
    useradd -m -s /bin/bash vcon
fi
mkdir -p /opt/vcon-admin /opt/vcon-server /opt/vcon-data/redis
chown -R vcon:vcon /opt/vcon-admin /opt/vcon-server /opt/vcon-data

# Install Docker if not already installed
if ! command_exists docker; then
    log "Installing Docker..."
    apt-get update
    apt-get install -y ca-certificates curl gnupg
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    log "Docker installed successfully"
else
    log "Docker is already installed"
fi

# Add vcon user to docker group (after Docker is installed so the group exists)
log "Adding user 'vcon' to docker group..."
usermod -aG docker vcon

# Install git if not already installed
if ! command_exists git; then
    log "Installing git..."
    apt-get update
    apt-get install -y git
    log "Git installed successfully"
else
    log "Git is already installed"
fi

# Create the docker network
log "Creating docker network 'conserver'..."
docker network create conserver || log "Network already exists"

# Clone or update vcon-admin repository as vcon user
if [ -d "/opt/vcon-admin/.git" ]; then
    log "Updating existing vcon-admin repository..."
    cd /opt/vcon-admin
    sudo -u vcon git pull
else
    log "Cloning vcon-admin repository..."
    rm -rf /opt/vcon-admin
    sudo -u vcon git clone https://github.com/vcon-dev/vcon-admin /opt/vcon-admin
    cd /opt/vcon-admin
fi

# Create .env file
log "Creating .env file for vcon-admin..."
sudo -u vcon bash -c 'cat > /opt/vcon-admin/.env << EOF
DNS_HOST=${DOMAIN}
DNS_REGISTRATION_EMAIL=${EMAIL}
EOF'

# Create Streamlit secrets file
log "Creating Streamlit secrets..."
sudo -u vcon mkdir -p /opt/vcon-admin/.streamlit
sudo -u vcon bash -c 'cat > /opt/vcon-admin/.streamlit/secrets.toml << EOF
# .streamlit/secrets.toml

[aws]
AWS_DEFAULT_REGION = "us-east-1"
AWS_ACCESS_KEY_ID=""
AWS_SECRET_ACCESS_KEY=""

[mongo_db]
url = "mongodb://root:example@mongo:27017/"
db = "conserver"
collection = "vcons"

[openai]
testing_key = ""
api_key = ""
organization = ""
project = ""
vector_store_name = "vcons"
assistant_id = ""

[elasticsearch]
url = "http://elasticsearch:9200"
username = "elastic"
password = ""

[conserver]
api_url = "https://${DOMAIN}/api"
auth_token = "${API_TOKEN}"
EOF'

# Build and start vcon-admin as vcon user
log "Building and starting vcon-admin..."
cd /opt/vcon-admin
sudo -u vcon docker compose up --build -d

# Clone or update vcon-server repository as vcon user  
if [ -d "/opt/vcon-server/.git" ]; then
    log "Updating existing vcon-server repository..."
    cd /opt/vcon-server
    sudo -u vcon git pull
else
    log "Cloning vcon-server repository..."
    rm -rf /opt/vcon-server
    sudo -u vcon git clone https://github.com/vcon-dev/vcon-server /opt/vcon-server
    cd /opt/vcon-server
fi

# Create .env file
log "Creating .env file for vcon-server..."
sudo -u vcon bash -c 'cat > /opt/vcon-server/.env << EOF
REDIS_URL=redis://redis

# API security token
CONSERVER_API_TOKEN=${API_TOKEN}

# Custom configuration file
CONSERVER_CONFIG_FILE=./config.yml

# Groq API key for Whisper transcription
GROQ_API_KEY=your_groq_api_key_here

DNS_HOST=${DOMAIN}
DNS_REGISTRATION_EMAIL=${EMAIL}
EOF'

# Create config.yml
log "Creating config.yml file..."
sudo -u vcon bash -c 'cat > /opt/vcon-server/config.yml << EOF
links:
  tag:
    module: links.tag
    ingress-lists: []
    egress-lists: []
    options:
      tags:
      - conserver
 
storages:
  mongo:
    module: storage.mongo
    options:
      url: mongodb://root:example@mongo:27017/
      database: conserver
      collection: vcons
chains:
  demo_chain:
    ingress_lists:
    - conserver_ingress
    links:
    - tag
    storages:
    - mongo
    enabled: 1
EOF'

# Copy example docker-compose.yml to docker-compose.yml
log "Setting up docker-compose.yml..."
sudo -u vcon cp /opt/vcon-server/example_docker-compose.yml /opt/vcon-server/docker-compose.yml

# Build and start vcon-server as vcon user
log "Building and starting vcon-server..."
cd /opt/vcon-server
sudo -u vcon docker compose up --build -d

# Wait for services to start
log "Waiting for services to start..."
sleep 30

# Display the installation summary
log "Installation completed successfully!"
log "-------------------------------------------------------"
log "Portal Address: https://${DOMAIN}/admin/"
log "Default login: admin/admin"
log "SSH Access: vcon@${DOMAIN}"
log "API Access: https://${DOMAIN}/api/docs"
log "API Token: ${API_TOKEN}"
log "Mongo Express Access: https://${DOMAIN}/mongo-express"
log "Redis Stack Access: http://localhost:8001"
log "-------------------------------------------------------"
log "To check the running Docker containers, run: docker ps"
log "To check the Docker network, run: docker network inspect conserver"