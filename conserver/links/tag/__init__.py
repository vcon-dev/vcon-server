"""Tag link — adds tags to a vCon as an attachment.

Migrated to the BaseLink convention (Refactor #2). The functional ``run()``
entrypoint is preserved so the chain processor keeps calling ``module.run(...)``
as before.
"""
from typing import Optional

from lib.vcon_redis import VconRedis  # noqa: F401 — exposed so tests may patch it
from links.base import BaseLink, run_link


class TagLink(BaseLink):
    default_options = {"tags": ["iron", "maiden"]}

    def execute(self, vcon_uuid: str) -> Optional[str]:
        self.logger.debug("Starting tag::execute for %s", vcon_uuid)
        vcon = self.vcon_redis.get_vcon(vcon_uuid)
        for tag in self.opts.get("tags", []):
            vcon.add_tag(tag_name=tag, tag_value=tag)
        self.vcon_redis.store_vcon(vcon)
        return vcon_uuid


# Backward-compat module-level alias (existing configs may reference it).
default_options = TagLink.default_options


def run(vcon_uuid, link_name, opts=None):
    return run_link(TagLink, vcon_uuid, link_name, opts)
