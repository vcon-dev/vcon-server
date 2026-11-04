# Upgrade vCon Server

This page moves a running server to newer code without losing queued work.

## Prepare for the upgrade

### Read the release notes

Check [GitHub Releases](https://github.com/vcon-dev/vcon-server/releases) for your target tag. Image tags follow Git tags, so `v2.0.9` publishes image tag `2.0.9`. List tags with `git tag --list`.

To see what you run now:

```bash
curl http://localhost:8000/api/version
```

A local build reports `dev` unless you pass `VCON_SERVER_VERSION` at image build.

### Check these breaking changes

| Your deployment | Before you upgrade |
|---|---|
| Runs Redis Stack, or stores vCons as RedisJSON | Complete the [Redis migration](redis-migration.md). Old and new workers cannot share keys, and the plain Redis image cannot read a Stack volume |
| Sets `REDIS_EXTERNAL_PORT` or uses Redis Insight | Remove them. Compose publishes no Redis port now |
| Installs Python dependencies with another tool | Move to [uv](manual-installation.md#install-the-dependencies). `uv.lock` is the only lock file |
| Runs code from `server/` | Update paths: `api/api.py`, `conserver/main.py`, `common/` and `conserver/links/`. Custom modules import `lib.*` and `vcon`, as in [Creating links](../extending/creating-links.md) |
| Names a vendor transcription module | It still works through a redirect, with a warning in the log. Move to [`links.transcribe`](../reference/links/transcribe.md) |
| Has consumers that expect `vcon: "0.0.1"` | The server now writes `0.4.0`. Set [`EGRESS_FORMAT_VERSION`](../configuration/egress-compatibility.md) for them |

The server normalizes legacy field names when it reads a vCon, so stored records keep working.

### Back up your data

Follow [Backup and restore](../operations/backup-restore.md) for Redis, your storage backends, `.env` and `config.yml`.

### Test on a second copy

Clone the repo to another folder, give it its own `.env` and `config.yml`, and run the upgrade there first. Use a different `CONSERVER_EXTERNAL_PORT`. Compose services share the `conserver` network by name, so run the test on another host if you can, and never point it at your production `REDIS_URL`.

## Upgrade a Compose deployment

```bash
git fetch origin --tags
git checkout <tag>

docker compose build --no-cache
docker compose up -d --no-deps api
docker compose up -d --no-deps conserver
```

`up -d` recreates each service in turn, so the API drops requests for a moment and queued vCons wait in Redis. A worker that receives `SIGTERM` finishes its current vCon. The Compose file gives it `stop_grace_period: 5s`, so raise that if your chains run longer.

## Upgrade a Kubernetes deployment

```bash
kubectl set image deployment/api \
  api=public.ecr.aws/r4g1k2s3/vcon-dev/vcon-server-api:<version> \
  -n vcon-server

kubectl set image deployment/worker \
  worker=public.ecr.aws/r4g1k2s3/vcon-dev/vcon-server-conserver:<version> \
  -n vcon-server

kubectl rollout status deployment/api -n vcon-server
kubectl rollout status deployment/worker -n vcon-server
```

## Upgrade a manual install

Stop the processes, then:

```bash
git fetch origin --tags
git checkout <tag>
uv sync --group api --group conserver
```

Start them again as in [Start the server](manual-installation.md#start-the-server).

## Check the upgrade

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/version
docker compose logs -f --tail=100
```

Send a test vCon to a chain and confirm that it reaches storage. The [quick start](../getting-started/quick-start.md) has a sample body.

Then compare your configuration with the samples:

```bash
diff .env.example .env
```

The [environment reference](../reference/environment.md) lists every variable the code reads.

## Roll back an upgrade

=== "Compose"

    ```bash
    docker compose down
    git checkout <previous-tag>
    docker compose up -d --build
    ```

=== "Kubernetes"

    ```bash
    kubectl rollout undo deployment/api -n vcon-server
    kubectl rollout undo deployment/worker -n vcon-server
    ```

Restore data only if the upgrade changed it. See [Backup and restore](../operations/backup-restore.md).

After a Redis migration, the rollback rules are stricter. Read the end of [Verify and switch the application](redis-migration.md#verify-and-switch-the-application).

## Change database schemas

The repo ships no migration tool. If the release notes name a schema change, apply it to your database by hand.

## Troubleshoot an upgrade

Print the configuration the server loads:

```bash
docker compose exec conserver python -c "from config import get_config; import json; print(json.dumps(get_config(), indent=2))"
```

Check a queue:

```bash
docker compose exec redis redis-cli LLEN <ingress_list>
```

Read the API's own schema at `http://localhost:8000/api/docs`, or the [API reference](../reference/api.md). See [Troubleshooting](../operations/troubleshooting.md) for other faults.

## Get help

Search [GitHub Issues](https://github.com/vcon-dev/vcon-server/issues). If you open a new issue, give your current and target versions, the error messages and your configuration with secrets removed.
