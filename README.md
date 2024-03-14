# vcon-server

# Quick Start Instructions Ubuntu 23.10

This guide will walk you through the steps to install the necessary software on a Digital Ocean droplet running Ubuntu 23.10 with the following specifications:
- 4 GB Memory
- 2 Intel vCPUs
- 120 GB Disk
- SYD1 region

## Prerequisites

Before starting the installation process, make sure you have a fresh installation of Ubuntu 23.10 on your Digital Ocean droplet.

## Installation Steps

1. Update the package list:
   ```bash
   sudo apt update
   ```

2. Upgrade installed packages:
   ```bash
   sudo apt upgrade -y
   ```

3. Install required dependencies:
   ```bash
   sudo apt install -y make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev
   ```

4. Install pyenv:
   ```bash
   curl https://pyenv.run | bash
   ```

5. Set up pyenv environment variables:
   ```bash
   export PATH="$HOME/.pyenv/bin:$PATH"
   eval "$(pyenv init --path)"
   eval "$(pyenv virtualenv-init -)"
   source ~/.bashrc # Or source ~/.zshrc if using Zsh
   ```

6. Install Python 3.12.2 using pyenv:
   ```bash
   pyenv install 3.12.2
   pyenv global 3.12.2
   ```

7. Install Poetry:
   ```bash
   curl -sSL https://install.python-poetry.org | python3.12 -
   echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
   source ~/.bashrc
   ```

8. Install project dependencies using Poetry:
   ```bash
   poetry install
   ```

9. Install Docker using snap:
   ```bash
   snap install docker
   ```

10. Create and configure the `.env` file:
    ```bash
    vim .env
    ```
    Here is an example .env file:
    ```
    AWS_BUCKET=vcon-xxxx
    AWS_KEY_ID=AKIxxxxx
    AWS_SECRET_KEY=XluPCOxxxxxxx
    DEEPGRAM_KEY=7b00axxxxxxx
    ENV=dev

    # CORE DEPENDENCIES
    ENV=dev
    HOSTNAME=http://0.0.0.0:8000
    HOST=0.0.0.0
    PORT=8000
    REDIS_URL=redis://redis

    # Overriding these on pairing so they don't conflict with django port etc
    REDIS_EXTERNAL_PORT=8001
    CONSERVER_EXTERNAL_PORT=8000

    CONSERVER_API_TOKEN=234dfssdfsd
    CONSERVER_CONFIG_FILE=./config.yml



    ```


11. Copy the example configuration file:
    ```bash
    cp example_config.yml config.yml
    ```

12. Start the Docker containers:
    ```bash
    docker compose up -d
    ```
