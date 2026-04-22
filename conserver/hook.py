"""Hook module for vCon processing lifecycle.

This module provides before- and after-processing hooks that are invoked
for each vCon. The implementation can be replaced at build time (e.g. during
Docker build) with a custom hook.py.
"""

from typing import Any, Dict, Optional


def before_processing(
    vcon_id: str,
    chain_details: Dict[str, Any],
    context: Optional[Dict[str, Any]],
) -> None:
    """Called before processing of a vCon starts.

    Args:
        vcon_id: The vCon identifier.
        chain_details: The chain configuration for this processing run.
        context: Optional context data (e.g. trace_id, span_id).
    """
    pass


def after_processing(
    vcon_id: str,
    chain_details: Dict[str, Any],
    context: Optional[Dict[str, Any]],
    error: Optional[Exception] = None,
) -> None:
    """Called after processing of a vCon has completed (success or failure).

    Args:
        vcon_id: The vCon identifier (may have been updated by the chain).
        chain_details: The chain configuration for this processing run.
        context: Optional context data (e.g. trace_id, span_id).
        error: If set, processing failed with this exception.
    """
    pass
