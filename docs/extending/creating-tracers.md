# Create a tracer

A tracer reports each step of a chain to somewhere else, such as a log or an audit service. This page shows how to write one. The [JLINC tracer](../reference/tracers/jlinc.md) is the one that ships with the server.

## Implement the interface

A tracer is a module with a `run` function. It has no event names: the server calls it at two kinds of point, and `link_index` tells you which.

```python
def run(
    in_vcon_uuid: str,
    out_vcon_uuid: str,
    tracer_name: str,
    links: list[str],
    link_index: int,
    opts: dict = default_options,
) -> None:
    ...
```

| Argument | Value |
|---|---|
| `in_vcon_uuid` | Before the first link, the vCon id. After a link, the id the link returned, or the current id if the link halted |
| `out_vcon_uuid` | The vCon id the chain held when the link ran |
| `tracer_name` | The name of this entry in `config.yml` |
| `links` | The chain's link names |
| `link_index` | `-1` before the first link. After that, the index in `links` of the link that just finished |
| `opts` | The entry's `options`. `None` when the entry has no `options` key |

The two ids differ only when a link swaps the vCon for another.

## Learn the tracer schedule

- Every tracer under the top-level `tracers` key runs for every chain. A `tracers` key inside a chain is not read.
- Each runs once before the first link, then once after each link that returns, including one that halts.
- A tracer does not run after a link that raises.
- A chain with no links runs no tracers. Tracers do not run around storage or egress.
- The return value is ignored.

Tracers run inline, so the chain waits for them. See [the link contract](creating-links.md#follow-the-link-contract) for the full sequence.

## Lay out the module

```
conserver/tracers/my_tracer/
  __init__.py       # run() and default_options
  README.md
  test_my_tracer.py # Tests sit beside the code
```

## Write a basic tracer

```python
# conserver/tracers/my_tracer/__init__.py

import json
from datetime import UTC, datetime

from lib.logging_utils import init_logger

logger = init_logger(__name__)

default_options = {
    "log_file": "/var/log/vcon/trace.log",
}


def run(in_vcon_uuid, out_vcon_uuid, tracer_name, links, link_index, opts=default_options):
    options = {**default_options, **(opts or {})}

    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "tracer": tracer_name,
        "in_vcon_uuid": in_vcon_uuid,
        "out_vcon_uuid": out_vcon_uuid,
        "link": links[link_index] if link_index >= 0 else None,
        "link_index": link_index,
    }

    with open(options["log_file"], "a") as f:
        f.write(json.dumps(record) + "\n")
```

## Register the tracer

```yaml
tracers:
  my_tracer:
    module: tracers.my_tracer
    options:
      log_file: /var/log/vcon/trace.log
```

Always write `options`, even as `options: {}`. The error handler in `conserver/main.py` reads it, so a failing tracer with no options raises a second error that stops the chain.

`pip_name` works here as it does for links. See [Dynamic modules](dynamic-modules.md).

## Handle a tracer failure

The server catches an exception from a tracer and logs it, and the chain continues. If the tracer's options set `dlq_vcon_on_error: true`, the exception stops the chain and the vCon moves to the dead letter queue. A failing tracer with no `options` key also stops the chain and sends the vCon to the DLQ, so always set `options`, even as `options: {}`.

So raise when something goes wrong and let the operator choose with that option. A tracer needs no `try` block of its own for this.

## Apply these patterns

### Send events to an HTTP service

Always set a timeout, because the chain waits for the call.

```python
from datetime import UTC, datetime

import requests

default_options = {
    "api_url": "https://audit.example.com/events",
    "api_key": "",
    "system_id": "vcon-server",
    "timeout": 5,
}


def run(in_vcon_uuid, out_vcon_uuid, tracer_name, links, link_index, opts=default_options):
    options = {**default_options, **(opts or {})}

    response = requests.post(
        options["api_url"],
        headers={"Authorization": f"Bearer {options['api_key']}"},
        json={
            "system_id": options["system_id"],
            "entity_id": out_vcon_uuid,
            "step": links[link_index] if link_index >= 0 else "start",
            "timestamp": datetime.now(UTC).isoformat(),
        },
        timeout=options["timeout"],
    )
    response.raise_for_status()
```

### Record a content hash

A tracer can read the vCon. Use `out_vcon_uuid`, as the JLINC tracer does, and allow for a missing vCon.

```python
import hashlib

from lib.vcon_redis import VconRedis


def run(in_vcon_uuid, out_vcon_uuid, tracer_name, links, link_index, opts=default_options):
    vcon = VconRedis().get_vcon(out_vcon_uuid)
    if vcon is None:
        return

    digest = hashlib.sha256(vcon.dumps().encode()).hexdigest()
    logger.info("vCon %s at step %s has hash %s", out_vcon_uuid, link_index, digest)
```

`Vcon.hash` gives the same value.

### Hand work to a background thread

To keep a slow call out of the chain, submit it to a pool. A failure then never reaches the server, so `dlq_vcon_on_error` has no effect.

```python
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=5)


def run(in_vcon_uuid, out_vcon_uuid, tracer_name, links, link_index, opts=default_options):
    _executor.submit(_send, out_vcon_uuid, link_index, opts)


def _send(vcon_uuid, link_index, opts):
    try:
        ...
    except Exception:
        logger.exception("Trace failed for %s", vcon_uuid)
```

For timing and counts, you may not need a tracer. The server already emits [metrics](../reference/metrics.md) and OpenTelemetry spans for each link and storage write.

## Test the tracer

```python
# conserver/tracers/my_tracer/test_my_tracer.py

import json

from tracers.my_tracer import run


def test_run_records_the_step(tmp_path):
    log_file = tmp_path / "trace.log"

    run("id-1", "id-1", "my_tracer", ["first", "second"], 1, {"log_file": str(log_file)})

    record = json.loads(log_file.read_text())
    assert record["link"] == "second"
    assert record["link_index"] == 1


def test_run_handles_the_start_of_a_chain(tmp_path):
    log_file = tmp_path / "trace.log"

    run("id-1", "id-1", "my_tracer", ["first"], -1, {"log_file": str(log_file)})

    assert json.loads(log_file.read_text())["link"] is None
```

Run them with `uv run pytest conserver/tracers/my_tracer`.

## Follow these practices

- Keep `run` fast, since it runs on every link of every chain.
- Handle `link_index` of `-1` before you index into `links`.
- Keep vCon content and credentials out of trace records unless the destination is meant to hold them.
- Add a README with the options, and a page under `docs/reference/tracers/`.
