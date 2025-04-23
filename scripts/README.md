# Conserver Installation Script

A bash script to easily install and configure Conserver vCon Server with all necessary components.

## Overview

This script automates the installation process for the Conserver vCon Server, setting up:
- Docker containers
- MongoDB
- Redis
- vCon Server API
- Admin interface
- Traefik for routing

## Quick Installation

```bash
curl -o install_conserver.sh https://raw.githubusercontent.com/your-username/your-repo/main/install_conserver.sh
chmod +x install_conserver.sh
sudo ./install_conserver.sh --domain your-domain.com --email your-email@example.com
```

## Requirements

- Ubuntu Linux (recommended)
- Root access
- Public internet access
- DNS record pointing to your server for the domain you specify

## Usage Options

```bash
./install_conserver.sh [options]
```

### Required Parameters:
- `-d, --domain DOMAIN` - Domain name for the installation
- `-e, --email EMAIL` - Email for DNS registration and notifications

### Optional Parameters:
- `-t, --token TOKEN` - API token (default: randomly generated)
- `-h, --help` - Display help information

## Post-Installation

After successful installation, you'll have access to:

- **Admin Portal**: `https://your-domain.com/admin/` (default login: admin/admin)
- **API Documentation**: `https://your-domain.com/api/docs`
- **API Token**: Displayed at the end of installation (save this!)
- **MongoDB Express**: `https://your-domain.com/mongo-express`
- **Redis Stack**: `http://localhost:8001`

## Configuration

The script creates the following configuration:
- Docker network named "conserver"
- MongoDB for vCon storage
- Redis for message queuing
- Pipeline configuration with tags set to "conserver"

## Troubleshooting

If you encounter issues:

1. Check Docker container status: `docker ps`
2. Inspect Docker network: `docker network inspect conserver`
3. View container logs: `docker logs [container-name]`

## Security Notes

- Change the default admin/admin credentials immediately after installation
- The API token is displayed at the end of installation - save it securely
- Consider restricting access to Redis on port 8001 if not needed externally

## License

This script is provided as-is under the same license as the Conserver vCon Server.

## Contributing

Feel free to submit issues or pull requests to improve this installation script.