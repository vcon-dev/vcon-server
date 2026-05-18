"""Unified transcription link with vendor dispatch.

This is the canonical entry point for ASR transcription in the
conserver. Earlier releases shipped a separate link per vendor
(``openai_transcribe``, ``groq_whisper``, ``hugging_face_whisper``,
``deepgram_link``) plus a built-in Whisper wrapper here. The
vendor-specific modules still exist for back-compat, but new chain
configurations should use this link with an explicit ``vendor:`` option.

Example
-------

.. code-block:: yaml

    links:
      transcribe_openai:
        module: links.transcribe
        options:
          vendor: openai
          vendor_options:
            api_key: ${OPENAI_API_KEY}
            model: whisper-1

Supported vendors
-----------------

* ``openai``         — delegates to ``links.openai_transcribe``
* ``groq``           — delegates to ``links.groq_whisper``
* ``hugging_face``   — delegates to ``links.hugging_face_whisper``
* ``deepgram``       — delegates to ``links.deepgram_link``
* ``whisper_builtin`` — uses vcon-lib's built-in ``Vcon.transcribe()``
  (the historical behavior of this link)

If ``vendor`` is omitted, the link falls back to ``whisper_builtin`` so
existing ``module: links.transcribe`` chain entries continue to work.

WTF transcripts
---------------

WTF-format transcripts live in their own link (``links.wtf_transcribe``)
because they emit a different analysis schema (per
``draft-howe-vcon-wtf-extension``) and have a different consumer
contract. They are intentionally not merged into this dispatcher.
"""

import importlib
from typing import Any, Dict, Optional

from lib.logging_utils import init_logger
from lib.vcon_redis import VconRedis

logger = init_logger(__name__)


# Map vendor name -> (module path, "thin"/"native").
#   thin   = the vendor module exposes the standard ``run(vcon_uuid,
#            link_name, opts)`` signature; we hand off opts directly.
#   native = handle in-process here (only ``whisper_builtin``).
_VENDOR_MODULES = {
    "openai": "links.openai_transcribe",
    "groq": "links.groq_whisper",
    "hugging_face": "links.hugging_face_whisper",
    "deepgram": "links.deepgram_link",
}


default_options: Dict[str, Any] = {
    # Which vendor to use. ``whisper_builtin`` preserves the historical
    # behavior of this link for back-compat with existing configs.
    "vendor": "whisper_builtin",
    # Options forwarded to the chosen vendor module. For ``whisper_builtin``
    # this is forwarded to ``Vcon.transcribe(**vendor_options)``.
    "vendor_options": {"model_size": "base", "output_options": ["vendor"]},
}


def _resolve_vendor(opts: Dict[str, Any]) -> str:
    vendor = opts.get("vendor")
    if not vendor:
        # Legacy callers passed ``transcribe_options`` and no ``vendor``.
        # That shape maps to whisper_builtin.
        if "transcribe_options" in opts:
            return "whisper_builtin"
        return "whisper_builtin"
    return vendor


def _whisper_builtin_run(
    vcon_uuid: str,
    link_name: str,
    vendor_options: Dict[str, Any],
) -> Optional[str]:
    """Run the historical vcon-lib built-in Whisper transcription."""
    vcon_redis = VconRedis()
    vCon = vcon_redis.get_vcon(vcon_uuid)
    if vCon is None:
        logger.error("transcribe(whisper_builtin): vCon %s not found", vcon_uuid)
        return None
    original_analysis_count = len(vCon.analysis)
    annotated_vcon = vCon.transcribe(**vendor_options)
    new_analysis_count = len(annotated_vcon.analysis)
    logger.debug(
        "transcribe(whisper_builtin): vCon %s analysis %d -> %d",
        vcon_uuid,
        original_analysis_count,
        new_analysis_count,
    )
    if new_analysis_count != original_analysis_count:
        vcon_redis.store_vcon(vCon)
    return vcon_uuid


def run(
    vcon_uuid: str,
    link_name: str,
    opts: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Dispatch transcription to the configured vendor."""
    user_opts = opts or {}
    merged = {**default_options, **user_opts}
    vendor = _resolve_vendor(merged)
    # Precedence: if the caller passed explicit vendor_options, use it.
    # Else if they passed legacy ``transcribe_options``, use that. Only
    # fall back to the default's vendor_options when neither is set.
    if "vendor_options" in user_opts:
        vendor_options = user_opts["vendor_options"] or {}
    elif "transcribe_options" in user_opts:
        vendor_options = user_opts["transcribe_options"] or {}
    else:
        vendor_options = merged.get("vendor_options") or {}

    logger.info(
        "transcribe: vendor=%s vcon=%s link=%s", vendor, vcon_uuid, link_name
    )

    if vendor == "whisper_builtin":
        return _whisper_builtin_run(vcon_uuid, link_name, vendor_options)

    module_path = _VENDOR_MODULES.get(vendor)
    if module_path is None:
        raise ValueError(
            f"transcribe: unknown vendor {vendor!r}. "
            f"Supported: {sorted(['whisper_builtin', *_VENDOR_MODULES])}"
        )

    vendor_module = importlib.import_module(module_path)
    # Vendor modules use the standard link contract. Their option
    # schemas differ — callers pass vendor-specific options under
    # ``vendor_options`` and we hand that dict through unmodified.
    return vendor_module.run(vcon_uuid, link_name, vendor_options)
