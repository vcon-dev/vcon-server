#!/bin/bash

git clone https://github.com/vcon-dev/vcon-server.git
cd vcon-server/

# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Start the Docker service just in case it's not started automatically after installation
sudo systemctl start docker

# Wait for the Docker daemon to start
while ! systemctl is-active --quiet docker; do 
  echo "Waiting for Docker to start..."
  sleep 1
done

echo "Docker is running."


cp .env.example .env
cp example_config.yml config.yml

docker compose up
