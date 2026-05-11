"""vCon lifecycle hook — no-op default implementation.

Called when vCons are created or deleted via the REST API.
Replace this file at Docker build time with any custom implementation
(e.g. audit logging, metrics, notifications).
"""

from typing import Dict, List, Optional


def on_vcon_created(
    vcon_id: str,
    vcon_dict: Dict,
    ingress_lists: Optional[List[str]],
) -> None:
    pass


def on_vcon_deleted(vcon_id: str) -> None:
    pass
