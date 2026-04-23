"""JQ filter link — forwards or drops vCons based on a jq expression.

Migrated to the BaseLink convention (Refactor #2).
"""
from typing import Optional

import jq

from lib.metrics import increment_counter
from lib.vcon_redis import VconRedis  # noqa: F401 — exposed so tests may patch it
from links.base import BaseLink, run_link


class JqLink(BaseLink):
    default_options = {
        # jq filter expression to evaluate
        "filter": ".",
        # if True, forward vCons that match the filter
        # if False, forward vCons that don't match the filter
        "forward_matches": True,
    }

    def execute(self, vcon_uuid: str) -> Optional[str]:
        self.logger.debug("Starting jq_link::execute for %s", vcon_uuid)

        vcon = self.vcon_redis.get_vcon(vcon_uuid)
        if not vcon:
            self.logger.error(f"Could not find vCon {vcon_uuid}")
            return None

        vcon_dict = vcon.to_dict()
        attrs = {"link.name": self.link_name, "vcon.uuid": vcon_uuid}
        filter_expr = self.opts["filter"]

        try:
            self.logger.debug(f"Applying jq filter '{filter_expr}' to vCon {vcon_uuid}")
            program = jq.compile(filter_expr)
            results = list(program.input(vcon_dict))
            if not results:
                self.logger.debug(f"JQ filter returned no results for vCon {vcon_uuid}")
                matches = False
            else:
                matches = bool(results[0])
            self.logger.debug(f"JQ filter results: {results}")
        except Exception as e:
            increment_counter("conserver.link.jq.filter_errors", attributes=attrs)
            self.logger.error(
                f"Error applying jq filter '{filter_expr}' to vCon {vcon_uuid}: {e}"
            )
            self.logger.debug(f"vCon content: {vcon_dict}")
            return None

        should_forward = matches == self.opts["forward_matches"]
        if should_forward:
            self.logger.info(
                f"vCon {vcon_uuid} {'' if matches else 'did not '}match filter - forwarding"
            )
            return vcon_uuid
        increment_counter("conserver.link.jq.vcon_filtered_out", attributes=attrs)
        self.logger.info(
            f"vCon {vcon_uuid} {'' if matches else 'did not '}match filter - filtering out"
        )
        return None


# Backward-compat module-level alias.
default_options = JqLink.default_options


def run(vcon_uuid, link_name, opts=None):
    return run_link(JqLink, vcon_uuid, link_name, opts)
