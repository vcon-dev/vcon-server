"""Sampler link — probabilistically filters vCons before they continue a chain.

Migrated to the BaseLink convention (Refactor #2). Unlike most links this one
does not read or mutate the vCon (sampling is a pure function of the UUID and
options), so it does not touch Redis.
"""
from __future__ import annotations

import hashlib
import random
import time
from typing import Optional

from lib.metrics import increment_counter
from links.base import BaseLink, run_link


class SamplerLink(BaseLink):
    default_options = {"method": "percentage", "value": 50, "seed": None}

    def execute(self, vcon_uuid: str) -> Optional[str]:
        if self.opts["seed"] is not None:
            random.seed(self.opts["seed"])

        method = self.opts["method"]
        value = self.opts["value"]
        attrs = {
            "link.name": self.link_name,
            "vcon.uuid": vcon_uuid,
            "method": method,
        }

        if method == "percentage":
            result = _percentage_sampling(vcon_uuid, value)
        elif method == "rate":
            result = _rate_sampling(vcon_uuid, value)
        elif method == "modulo":
            result = _modulo_sampling(vcon_uuid, value)
        elif method == "time_based":
            result = _time_based_sampling(vcon_uuid, value)
        else:
            raise ValueError(f"Unknown sampling method: {method}")

        if result:
            increment_counter("conserver.link.sampler.sampled_in", attributes=attrs)
        else:
            increment_counter("conserver.link.sampler.sampled_out", attributes=attrs)
        return result


# Backward-compat module-level alias.
default_options = SamplerLink.default_options


def run(vcon_uuid, link_name, opts=None):
    return run_link(SamplerLink, vcon_uuid, link_name, opts)


def _percentage_sampling(vcon_uuid: str, percentage: float) -> Optional[str]:
    """Keep `percentage`% of vCons at random."""
    if random.uniform(0, 100) <= percentage:
        return vcon_uuid
    return None


def _rate_sampling(vcon_uuid: str, rate: float) -> Optional[str]:
    """Sample using an exponential distribution with mean `rate` seconds."""
    if random.expovariate(1.0 / rate) <= 1:
        return vcon_uuid
    return None


def _modulo_sampling(vcon_uuid: str, modulo: int) -> Optional[str]:
    """Keep every nth vCon deterministically based on UUID hash."""
    hash_value = hashlib.sha256(vcon_uuid.encode()).hexdigest()
    hash_int = int(hash_value[:8], 16)
    if hash_int % modulo == 0:
        return vcon_uuid
    return None


def _time_based_sampling(vcon_uuid: str, interval: int) -> Optional[str]:
    """Keep vCons only when current second % interval == 0."""
    current_time = int(time.time())
    if current_time % interval == 0:
        return vcon_uuid
    return None
