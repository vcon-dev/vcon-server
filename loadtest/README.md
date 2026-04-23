# Load-test harness

Small locust-based harness for measuring vcon-server ingress and worker-chain
throughput. **Not** run in CI on every PR — run on-demand before/after
refactors and as part of release qualification.

## Install

```
uv sync --group loadtest
```

## Prerequisites

A running stack: api + conserver + redis-stack. Use docker-compose in another
shell:

```
docker-compose up --build
```

Confirm:

```
curl -sS http://localhost:8000/openapi.json | head -c 200
```

## Scenarios

`locustfile.py` defines one user class (`IngressUser`) with two weighted tasks:

| Task                            | Weight | What it measures                                                           |
|---------------------------------|--------|----------------------------------------------------------------------------|
| `POST /vcon (no ingress)`       | 3      | api storage + Redis index only (no chain work)                             |
| `POST /vcon (with ingress)`     | 1      | api path + enqueue for worker chain (chain throughput depends on chain)    |

For chain-throughput isolation (bypassing the api), seed Redis directly:

```
# Produce 10k synthetic vCon IDs in the ingress list and time worker drain.
for i in $(seq 1 10000); do
  uuid=$(uuidgen)
  redis-cli -u $REDIS_URL RPUSH loadtest_ingress "$uuid" >/dev/null
done
```

## Run a headless baseline (30s, 20 users)

```
CONSERVER_API_TOKEN=your-token \
  uv run locust -f loadtest/locustfile.py \
    --host=http://localhost:8000 --headless \
    -u 20 -r 5 -t 30s \
    --csv=loadtest/baselines/$(date +%Y%m%d)-main
```

Outputs:
- `loadtest/baselines/<date>-main_stats.csv` — aggregate RPS, latency percentiles
- `loadtest/baselines/<date>-main_stats_history.csv` — per-second time series
- `loadtest/baselines/<date>-main_failures.csv` — error breakdown

Commit the three CSVs and a short `baseline_<date>.md` alongside refactor PRs
that change hot paths (config caching, Redis unification, main.py carve-up,
lazy plugin loading). Compare `POST /vcon` p95 latency and aggregate RPS against
the pre-refactor baseline.

## Web UI (exploratory)

```
uv run locust -f loadtest/locustfile.py --host=http://localhost:8000
# → open http://localhost:8089
```

## Environment variables

| Var                         | Default                       | Purpose                              |
|-----------------------------|-------------------------------|--------------------------------------|
| `CONSERVER_API_TOKEN`       | (empty)                       | Value for the API-token header       |
| `CONSERVER_HEADER_NAME`     | `x-conserver-api-token`       | Header name                          |
| `LOADTEST_INGRESS_LIST`     | `loadtest_ingress`            | Ingress list name the chain consumes |
