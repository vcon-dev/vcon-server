# Install with the automated script

`scripts/install_conserver.sh` sets up an Ubuntu host with vcon-admin and vcon-server. It runs both as Docker Compose projects.

!!! danger "Set the API token yourself"
    The script does not write your domain, email or token into the files it creates. `CONSERVER_API_TOKEN` ends up empty in `/opt/vcon-server/.env`, which turns off the API key check, even though the script prints a token. Port 8000 is published on the host. Follow [Repair the generated files](#repair-the-generated-files) straight after the install.

## See the script steps

In order, the script:

1. Asks you to confirm the domain, email and token.
2. Creates a `vcon` user with a Bash shell, and the folders `/opt/vcon-admin`, `/opt/vcon-server` and `/opt/vcon-data/redis`.
3. Installs Docker, with the Compose plugin, if the `docker` command is missing, and adds `vcon` to the `docker` group. A host that has Docker needs the plugin already.
4. Creates the `conserver` Docker network.
5. Clones `vcon-dev/vcon-admin` to `/opt/vcon-admin`, writes its `.env` and `.streamlit/secrets.toml`, and starts it.
6. Clones `vcon-dev/vcon-server` to `/opt/vcon-server`, writes `.env` and a `config.yml` with one `demo_chain`, and starts it.

Running the script again removes nothing in the two clones but pulls them and overwrites `.env` and `config.yml`, so keep your own copies.

The server project is the repo's `docker-compose.yml`, which is built for development. See [Install with Docker](docker.md) for what that means.

## Prepare the host

- Ubuntu. The script uses `apt-get` and Docker's Ubuntu repository.
- Root access.
- A domain name, and a DNS record pointing at the host.

See the [system requirements](../getting-started/requirements.md) for sizing.

## Run the script

The script is in the repo, so clone it first:

```bash
git clone https://github.com/vcon-dev/vcon-server.git
cd vcon-server
sudo ./scripts/install_conserver.sh \
  --domain your-domain.com \
  --email admin@your-domain.com
```

| Option | Required | Description |
|---|---|---|
| `-d`, `--domain` | Yes | Domain name for the installation |
| `-e`, `--email` | Yes | Email for DNS registration |
| `-t`, `--token` | No | API token. A random 16-character hex value when left out. See the warning above |
| `-h`, `--help` | No | Print the options |

## Repair the generated files

Set a token in the server's `.env` and apply it:

```bash
TOKEN=$(openssl rand -hex 32)
sudo sed -i "s/^CONSERVER_API_TOKEN=.*/CONSERVER_API_TOKEN=$TOKEN/" /opt/vcon-server/.env
cd /opt/vcon-server
sudo -u vcon docker compose up -d
```

Then fill in the values the script left blank:

| File | Values to set |
|---|---|
| `/opt/vcon-server/.env` | `DNS_HOST`, `DNS_REGISTRATION_EMAIL` |
| `/opt/vcon-admin/.env` | `DNS_HOST`, `DNS_REGISTRATION_EMAIL` |
| `/opt/vcon-admin/.streamlit/secrets.toml` | `api_url` under `[conserver]`, which needs your domain, and `auth_token`, which needs the token |

Restart vcon-admin after you edit its files:

```bash
cd /opt/vcon-admin
sudo -u vcon docker compose up -d
```

Check that the key is on:

```bash
curl -i http://localhost:8000/api/vcon
```

A `403` means the check is on.

## Find the installed services

This repo's Compose project starts `api`, `conserver` and `redis`. `.env` sets no `COMPOSE_PROFILES`, so no optional service starts. [Ports and services](../reference/ports.md) lists them.

The generated `config.yml` writes to `mongodb://root:example@mongo:27017/`, a host this repo's Compose file does not define.

<!-- TODO(verify): the mongo service, the HTTPS proxy on /api, the admin login and mongo-express come from the vcon-admin Compose project, which is outside this repo. Confirm against vcon-admin. -->

The script's closing summary names these addresses. All but the last depend on vcon-admin, so check them against that project:

| Service | Address |
|---|---|
| Admin portal | `https://your-domain.com/admin/` |
| API docs | `https://your-domain.com/api/docs` |
| Mongo Express | `https://your-domain.com/mongo-express` |
| Redis Stack | `http://localhost:8001`. Out of date: the server now uses plain Redis with no Redis Insight, so nothing in this repo serves this port |

On the host itself, the API answers on `http://localhost:8000/api/health`.

The script opens no firewall ports and sets up no certificates of its own. Restrict port 8000 with your own firewall rules.

## Change the configuration

```bash
sudo -u vcon nano /opt/vcon-server/.env
sudo -u vcon nano /opt/vcon-server/config.yml
```

Apply a change to `.env` with:

```bash
cd /opt/vcon-server
sudo -u vcon docker compose up -d
```

Most changes to `config.yml` need no restart. See [the reload table](../configuration/yaml-configuration.md#plan-for-reloads).

## Update the install

```bash
cd /opt/vcon-server
sudo -u vcon git pull
sudo -u vcon docker compose up -d --build
```

Do the same in `/opt/vcon-admin`. See [Upgrading](upgrading.md) first. An install that predates plain Redis needs the [Redis migration](redis-migration.md).

## Remove the install

```bash
sudo ./scripts/uninstall_conserver.sh
```

The script asks for confirmation, then removes:

- The vcon-server containers and volumes, and the `conserver` network
- Images named `vcon-server` or `vcon-admin`
- `/opt/vcon-data`, `/opt/vcon-server` and `/opt/vcon-admin`
- The `vcon` user, unless that user is logged in

!!! warning "Data is deleted"
    The script has no option to keep data. Back up first. See [Backup and restore](../operations/backup-restore.md).

The script runs `docker compose down` for vcon-server only. Stop vcon-admin first with `docker compose down` in `/opt/vcon-admin`, or its containers keep running. While they run, the `conserver` network stays too, because its removal fails without stopping the script.

## Troubleshoot the install

The script logs to the terminal and keeps no log file. `set -e` stops it at the first failed command, so read the last lines it printed.

| Symptom | Fix |
|---|---|
| `ERROR: This script must be run as root` | Run it with `sudo` |
| Docker install fails | Install Docker yourself, then run the script again |
| Services do not start | Run `docker compose logs` in `/opt/vcon-server` |
| vCons fail at storage | Check that the `mongo` host resolves on the `conserver` network, or change `storages` in `config.yml` |

To see what is running on the shared network:

```bash
docker ps
docker network inspect conserver
```

## Continue with these guides

- [Configuration guide](../configuration/index.md)
- [API reference](../reference/api.md)
- [Monitoring](../operations/monitoring.md)
