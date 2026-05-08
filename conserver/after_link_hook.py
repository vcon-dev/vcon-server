"""after_link hook — no-op default implementation.

Called after every link in the chain completes (success or error).
Replace this file at Docker build time with any custom implementation
(e.g. audit logging, metrics, notifications).
"""

from typing import Any, Dict, List, Optional


def after_link(
    vcon_id: str,
    link_name: str,
    link_module: Any,
    link_opts: Optional[Dict],
    link_hook_config: Optional[Dict],
    status: str,
    error: Optional[Exception],
    parties: Optional[List[str]],
) -> None:
    pass
