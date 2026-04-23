"""Base class for vCon chain links (Refactor #2).

A "link" is a step in a processing chain: it receives a vCon UUID, does
something (mutate the vCon, filter it, call out to an external service), and
returns either the UUID (continue the chain) or None (halt the chain).

Historically every link module re-implemented the same boilerplate:
    - init a module-level logger
    - init a module-level VconRedis()
    - declare a module-level default_options dict
    - accept opts=default_options as a keyword default in run()

This class removes the boilerplate. Subclasses set `default_options` (a class
attribute) and implement `execute()`. The functional `run()` entrypoint that
the chain processor calls is a one-liner that delegates to this class.

Example:

    # conserver/links/mylink/__init__.py
    from links.base import BaseLink

    class MyLink(BaseLink):
        default_options = {"greeting": "hi"}

        def execute(self, vcon_uuid):
            vcon = self.vcon_redis.get_vcon(vcon_uuid)
            vcon.add_tag(self.opts["greeting"], self.opts["greeting"])
            self.vcon_redis.store_vcon(vcon)
            return vcon_uuid

    # Functional entrypoint the chain processor invokes.
    default_options = MyLink.default_options

    def run(vcon_uuid, link_name, opts=None):
        return MyLink(link_name, opts).execute(vcon_uuid)

Semantics: `self.opts` is `{**default_options, **(opts or {})}`. This means
options supplied via chain config merge *on top of* defaults key-by-key,
instead of replacing the whole dict. Several links (jq_link, sampler) already
did this manually; BaseLink unifies the behavior.
"""
from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from functools import cached_property
from typing import ClassVar, Optional

from lib.logging_utils import init_logger
from lib.vcon_redis import VconRedis as _DefaultVconRedis


class BaseLink(ABC):
    """Base class for a chain link.

    Subclasses implement :meth:`execute` and optionally override
    :attr:`default_options`. Instantiate via `MyLink(link_name, opts).execute(uuid)`
    or via the `run()` module-level shim below.
    """

    #: Default options for this link. Subclasses override with their own dict.
    default_options: ClassVar[dict] = {}

    def __init__(self, link_name: str, opts: Optional[dict] = None) -> None:
        self.link_name = link_name
        self.logger = init_logger(self.__class__.__module__)
        # Merge config-supplied opts on top of class defaults. A None value
        # from main.py's `link.get("options")` means "use defaults".
        self.opts: dict = {**self.default_options, **(opts or {})}

    @cached_property
    def vcon_redis(self):
        """Lazy VconRedis client. Links that don't touch Redis won't pay the cost.

        Looks up `VconRedis` from the subclass's own module first so existing
        tests that do ``patch('links.mylink.VconRedis')`` keep working after the
        BaseLink migration. Falls back to the canonical import.
        """
        module = sys.modules.get(type(self).__module__)
        cls = getattr(module, "VconRedis", None) or _DefaultVconRedis
        return cls()

    @abstractmethod
    def execute(self, vcon_uuid: str) -> Optional[str]:
        """Run the link.

        Args:
            vcon_uuid: UUID of the vCon to process.

        Returns:
            The (possibly new) vCon UUID to continue the chain, or None to halt.
        """
        raise NotImplementedError


def run_link(link_cls: type[BaseLink], vcon_uuid: str, link_name: str, opts: Optional[dict] = None) -> Optional[str]:
    """Functional adapter: instantiate and execute a BaseLink subclass.

    Intended to be called from a link module's top-level ``run()`` function so
    that the chain processor (conserver/main.py) — which invokes the functional
    ``module.run(vcon_id, link_name, options)`` entrypoint — keeps working
    unchanged.
    """
    return link_cls(link_name, opts).execute(vcon_uuid)
