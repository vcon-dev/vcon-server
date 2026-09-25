import json
import random
from typing import Literal, Optional, TypedDict
from lib.logging_utils import init_logger
from vcon import Vcon

logger = init_logger(__name__)


class OnlyIfFilter(TypedDict, total=False):
    """``only_if`` clause inside :class:`FilterOptions`.

    Exactly one of ``type`` or ``purpose`` should be supplied — they are
    aliases. ``purpose`` is the draft-ietf-vcon-vcon-core-02 spelling for
    attachments; ``type`` is the pre-0.4.0 name (still canonical for
    analysis entries). Either works against either section so existing
    configs keep matching, and spec-current configs can use ``purpose``.

    Keys:
        section: vCon array to scan — ``"attachments"`` or ``"analysis"``.
        type / purpose: identifier to match on each element.
        includes: substring/membership token to look for inside the body.
    """

    section: Literal["attachments", "analysis"]
    type: str
    purpose: str
    includes: str


class FilterOptions(TypedDict, total=False):
    """Options envelope accepted by :func:`is_included`.

    Absent / empty ``only_if`` means "include everything", which is why
    both ``options`` and ``options.only_if`` are optional.
    """

    only_if: OnlyIfFilter


def is_included(options: Optional[FilterOptions], _vcon) -> bool:
    if not options:
        return True
    if not options.get("only_if"):
        return True
    filter = options["only_if"]
    section = filter["section"]
    # Accept either the spec-current ``purpose`` or legacy ``type`` key
    # as the target identifier. They're treated as aliases regardless of
    # section so configs migrate at their own pace.
    target = filter.get("purpose") or filter.get("type")
    includes = filter["includes"]

    try:
        for element in getattr(_vcon, section):
            # draft-ietf-vcon-vcon-core-02 renamed attachment ``type`` →
            # ``purpose``. Accept either on attachments so configs written
            # against the legacy shape keep working alongside spec-current
            # writers. Analysis kept the ``type`` field.
            if section == "attachments":
                if element.get("purpose") != target and element.get("type") != target:
                    continue
            elif element.get("type") != target:
                continue
            if target == "tags":
                # Tags body is a JSON-encoded list of "name:value" strings —
                # the one case where we have to decode before checking.
                tags = Vcon.decoded_body(element)
                if isinstance(tags, list) and includes in tags:
                    return True
                continue
            # Per draft-ietf-vcon-vcon-core-04 §2.3.2, an ``encoding: "json"``
            # body is the JSON value itself (dict/list), not a string — so a
            # plain substring match only works directly for str bodies (the
            # legacy -02 stringified shape, or encoding "none"/"base64url").
            # For a dict/list body, match against its JSON-serialized form so
            # ``includes`` still finds tokens inside it.
            body = element.get("body")
            if isinstance(body, str):
                if includes in body:
                    return True
            elif isinstance(body, (dict, list)):
                if includes in json.dumps(body):
                    return True
    except Exception as e:
        logger.error(f"Error checking inclusion: {e}")
    return False


def randomly_execute_with_sampling(options):
    if options.get("sampling_rate"):
        if random.random() < options["sampling_rate"]:
            return True
        else:
            return False
    return True
