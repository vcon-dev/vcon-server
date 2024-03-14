#!/bin/bash

# Update package list
sudo apt update

# Upgrade installed packages
sudo apt upgrade -y

# Install required dependencies
sudo apt install -y make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev git

# Check if pyenv is already installed
if [ -d "$HOME/.pyenv" ]; then
    echo "pyenv is already installed. Skipping pyenv installation."
else
    # Install pyenv
    curl https://pyenv.run | bash

    # Set up pyenv environment variables
    echo 'export PATH="$HOME/.pyenv/bin:$PATH"' >> ~/.bashrc
    echo 'eval "$(pyenv init --path)"' >> ~/.bashrc
    echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.bashrc
    source ~/.bashrc
fi

# Install Python 3.12.2 using pyenv
pyenv install 3.12.2
pyenv global 3.12.2

# Install Poetry
curl -sSL https://install.python-poetry.org | python3.12 -
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Clone the repository from GitHub
git clone https://github.com/vcon-dev/vcon-server.git
cd vcon-server

# Install project dependencies using Poetry
poetry install

# Install Docker using snap
sudo snap install docker

# Create and configure the `.env` file
touch .env
# Add your desired environment variables to the `.env` file

# Copy the example configuration file
cp example_config.yml config.yml

# Start the Docker containers
docker compose up -d
