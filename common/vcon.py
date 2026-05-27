import copy
import json
import logging
import warnings
from typing import Optional, Union
import hashlib
import time
import uuid6
from datetime import datetime, UTC
from pydash import get as _get
import base64
import os

_LAST_V8_TIMESTAMP = None
UUID8_DOMAIN_NAME = os.getenv("UUID8_DOMAIN_NAME", "strolid.com")

_logger = logging.getLogger(__name__)


class Vcon:
    def __init__(self, vcon_dict={}):
        # Defensive: production logs show callers occasionally pass a
        # JSON-encoded string here, which silently round-trips through
        # json.dumps/loads and leaves self.vcon_dict as a str. Every
        # downstream access (e.g. find_attachment_by_purpose at line
        # ``self.vcon_dict["attachments"]``) then crashes with
        # ``TypeError: string indices must be integers, not 'str'``.
        # Coerce the string back to a dict and log the caller stack so
        # we can find and fix the originating call site.
        if isinstance(vcon_dict, str):
            _logger.error(
                "Vcon.__init__ received a str (len=%d, head=%r); coercing via json.loads",
                len(vcon_dict),
                vcon_dict[:200],
                stack_info=True,
            )
            try:
                vcon_dict = json.loads(vcon_dict)
            except json.JSONDecodeError:
                # Not JSON either — bail out with an empty dict rather
                # than poisoning self.vcon_dict for downstream callers.
                vcon_dict = {}
        # deep copy
        self.vcon_dict = json.loads(json.dumps(vcon_dict))

    @classmethod
    def build_from_json(cls, json_string: str):
        return cls(json.loads(json_string))

    @classmethod
    def build_new(cls):
        vcon_dict = {
            "uuid": cls.uuid8_domain_name("strolid.com"),
            "vcon": "0.0.1",
            "created_at": datetime.now(UTC).isoformat()[:-3] + "+00:00",
            "redacted": {},
            "group": [],
            "parties": [],
            "dialog": [],
            "attachments": [],
            "analysis": [],
        }
        return cls(vcon_dict)

    @property
    def tags(self):
        return self.find_attachment_by_purpose("tags")

    @staticmethod
    def decoded_body(entry):
        """Return an attachment/analysis ``body`` as a live Python value.

        Per draft-ietf-vcon-vcon-core-02 §2.3.2 ``body`` is *always* a String;
        the ``encoding`` tells you how to interpret it:

        - ``json`` → body is a JSON-encoded object/array, parse with ``json.loads``.
        - ``base64url`` → body is base64url-encoded bytes, returned verbatim
          (binary decoding is caller-specific).
        - ``none`` → body is a freeform string, returned verbatim.

        For backwards compatibility with legacy writers that placed a raw
        dict/list under ``body`` with ``encoding: none``, the dict/list is
        returned as-is. ``VconRedis._enforce_spec_on_write`` later normalises
        that to spec-correct ``encoding: json`` + stringified body, after
        which this helper still returns the same Python value on reload.

        Returns ``None`` if ``entry`` is falsy.
        """
        if not entry:
            return None
        body = entry.get("body")
        if entry.get("encoding") == "json" and isinstance(body, str):
            return json.loads(body)
        return body

    @staticmethod
    def with_decoded_body(entry):
        """Shallow copy of an attachment/analysis entry with body decoded.

        Returns a new dict identical to ``entry`` except ``body`` is replaced
        with the live Python value parsed via :meth:`decoded_body`. Useful
        when a caller wants to navigate into ``body`` with dict syntax (e.g.
        via a dot-path navigator) without having to know whether body
        arrived as a JSON-encoded string from storage.

        Returns ``None`` if ``entry`` is falsy.
        """
        if not entry:
            return None
        return {**entry, "body": Vcon.decoded_body(entry)}

    def get_tag(self, tag_name):
        tags_attachment = self.find_attachment_by_purpose("tags")
        if not tags_attachment:
            return None
        tags = self.decoded_body(tags_attachment) or []
        tag = next((t for t in tags if t.startswith(f"{tag_name}:")), None)
        if not tag:
            return None
        return tag.split(":", 1)[1]

    def add_tag(self, tag_name, tag_value):
        tags_attachment = self.find_attachment_by_purpose("tags")
        if tags_attachment is None:
            # Spec 0.4.0 renamed attachment ``type`` → ``purpose``. New
            # writes use the spec-current key; lookup tolerates both.
            tags_attachment = {"purpose": "tags"}
            self.vcon_dict["attachments"].append(tags_attachment)
        # Decode existing body so a prior add_tag (or a Redis round-trip
        # via VconRedis._enforce_spec_on_write) round-trips cleanly. Write
        # back as spec-correct ``encoding=json`` + stringified list, per
        # draft-ietf-vcon-vcon-core-02 §2.3.2 (body is always a String).
        tags = self.decoded_body(tags_attachment) or []
        tags.append(f"{tag_name}:{tag_value}")
        tags_attachment["body"] = json.dumps(tags)
        tags_attachment["encoding"] = "json"

    def find_attachment_by_purpose(self, purpose):
        # IETF vCon spec 0.4.0 attachment lookup. Matches `purpose` first
        # (spec-current key) and falls back to legacy `type` so attachments
        # written by older producers still resolve. `.get` tolerates missing
        # keys so a mixed-shape attachment list never raises KeyError.
        return next(
            (
                a
                for a in self.vcon_dict["attachments"]
                if a.get("purpose") == purpose or a.get("type") == purpose
            ),
            None,
        )

    def find_attachment_by_type(self, type):
        """Deprecated: use :meth:`find_attachment_by_purpose` instead.

        Kept for callers written against the pre-spec-0.4.0 shape. Delegates
        to ``find_attachment_by_purpose``, which already matches both `type`
        and `purpose` keys for back-compat.
        """
        warnings.warn(
            "Vcon.find_attachment_by_type is deprecated; use "
            "Vcon.find_attachment_by_purpose (spec 0.4.0 renamed the field).",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.find_attachment_by_purpose(type)

    def add_attachment(self, *, body: Union[dict, list, str], type: str, encoding="none"):
        if encoding not in ['json', 'none', 'base64url']:
            raise Exception("Invalid encoding")

        # Per draft-ietf-vcon-vcon-core-02 §2.3.2 ``body`` is always a String.
        # If a caller hands us a dict/list as a convenience, JSON-encode it
        # immediately so any reader that touches the attachment between now
        # and storage sees the spec-correct shape.
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
            encoding = "json"

        if encoding == "json":
            try:
                json.loads(body)
            except Exception as e:
                raise Exception("Invalid JSON body: ", e)

        if encoding == 'base64url':
            try:
                base64.urlsafe_b64decode(body)
            except Exception as e:
                raise Exception("Invalid base64url body: ", e)

        self.vcon_dict["attachments"].append({
            "type": type,
            "body": body,
            "encoding": encoding,
        })

    def find_analysis_by_type(self, type):  # TODO fix to search for specific dialog id if it's passed
        return next((a for a in self.vcon_dict["analysis"] if a["type"] == type), None)

    def add_analysis(self, *, type: str, dialog: Union[list, int], vendor: str, body: Union[dict, list, str], encoding="none", extra={}):
        if encoding not in ['json', 'none', 'base64url']:
            raise Exception("Invalid encoding")

        # Per draft-ietf-vcon-vcon-core-02 §2.3.2 ``body`` is always a String.
        # If a caller hands us a dict/list as a convenience, JSON-encode it
        # immediately so any reader that touches the analysis between now
        # and storage sees the spec-correct shape.
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
            encoding = "json"

        if encoding == "json":
            try:
                json.loads(body)
            except Exception as e:
                raise Exception("Invalid JSON body: ", e)

        if encoding == 'base64url':
            try:
                base64.urlsafe_b64decode(body)
            except Exception as e:
                raise Exception("Invalid base64url body: ", e)

        self.vcon_dict["analysis"].append({
            "type": type,
            "dialog": dialog,
            "vendor": vendor,
            "body": body,
            "encoding": encoding,
            **extra,
        })

    def add_party(self, party: dict):
        self.vcon_dict["parties"].append(party)

    def find_party_index(self, by: str, val: str) -> Optional[int]:
        return next(
            (
                ind
                for ind, party in enumerate(self.vcon_dict["parties"])
                if _get(party, by) == val
            ),
            None,
        )

    def find_dialog(self, by: str, val: str) -> Optional[dict]:
        return next(
            (dialog for dialog in self.dialog if _get(dialog, by) == val),
            None,
        )

    def add_dialog(self, dialog: dict):
        self.vcon_dict["dialog"].append(dialog)

    def to_json(self) -> str:
        tmp_vcon_dict = copy.copy(self.vcon_dict)
        return json.dumps(tmp_vcon_dict)

    def to_dict(self) -> dict:
        return json.loads(self.to_json())  # convert from internal dict format to vcon format

    def dumps(self) -> str:
        return self.to_json()

    # return the SHA-256 hash of the vCon
    @property
    def hash(self) -> str:
        return hashlib.sha256(self.dumps().encode()).hexdigest()
    
    @property
    def parties(self) -> list:
        return self.vcon_dict.get("parties", [])

    @parties.setter
    def parties(self, value: list):
        self.vcon_dict["parties"] = value

    @property
    def dialog(self) -> list:
        return self.vcon_dict.get("dialog", [])

    @dialog.setter
    def dialog(self, value: list):
        self.vcon_dict["dialog"] = value

    @property
    def attachments(self) -> list:
        return self.vcon_dict.get("attachments", [])

    @attachments.setter
    def attachments(self, value: list):
        self.vcon_dict["attachments"] = value

    @property
    def analysis(self):
        return self.vcon_dict.get("analysis", [])

    @analysis.setter
    def analysis(self, value: list):
        self.vcon_dict["analysis"] = value

    @property
    def uuid(self) -> str:
        """
        The [UUID] for the vCon is used to refer to it when privacy or
        security may not allow for inclusion or URL reference to a vCon.  The
        UUID MUST be globally unique.
        """
        return self.vcon_dict["uuid"]

    @property
    def vcon(self) -> str:
        """
        The the value of vcon parameter contains the syntactic version of the JSON format used in the vCon.
        """
        return self.vcon_dict["vcon"]

    @property
    def subject(self) -> Optional[str]:
        return self.vcon_dict.get("subject")

    @property
    def created_at(self):
        """"
        The created_at parameter provides the creation time of this vcon,
        which MUST be present, and should not changed once the vcon object is
        created.
        """
        return self.vcon_dict.get("created_at")

    @property
    def updated_at(self):
        return self.vcon_dict.get("updated_at")

    @property
    def redacted(self):
        return self.vcon_dict.get("redacted")

    @property
    def appended(self):
        return self.vcon_dict.get("appended")

    @property
    def group(self):
        return self.vcon_dict.get("group", [])

    @staticmethod
    def uuid8_domain_name(domain_name: str) -> str:
        """
        Generate a version 8 (custom) UUID using the upper 62 bits of the SHA-1 hash
        for the given DNS domain name string for custom_c and generating
        custom_a and custom_b the same way as unix_ts_ms and rand_a respectively
        for UUID version 7 (per IETF I-D draft-peabody-dispatch-new-uuid-format-04).

        Parameters:
        domain_name: a DNS domain name string, should generally be a fully qualified host
            name.

        Returns:
        UUID version 8 string
        """

        sha1_hasher = hashlib.sha1()
        sha1_hasher.update(bytes(domain_name, "utf-8"))
        dn_sha1 = sha1_hasher.digest()

        hash_upper_64 = dn_sha1[0:8]
        int64 = int.from_bytes(hash_upper_64, byteorder="big")

        uuid8_domain = Vcon.uuid8_time(int64)

        return uuid8_domain

    @staticmethod
    def uuid8_time(custom_c_62_bits: int) -> str:
        """
        Generate a version 8 (custom) UUID using the given custom_c and generating
        custom_a and custom_b the same way as unix_ts_ms and rand_a respectively
        for UUID version 7 (per IETF I-D draft-peabody-dispatch-new-uuid-format-04).

        Parameters:
        custom_c_62_bits: the 62 bit value as an integer to be used for custom_b
            portion of UUID version 8.

        Returns:
        UUID version 8 string
        """
        # This is partially from uuid6.uuid7 implementation:
        global _LAST_V8_TIMESTAMP

        nanoseconds = time.time_ns()
        if _LAST_V8_TIMESTAMP is not None and nanoseconds <= _LAST_V8_TIMESTAMP:
            nanoseconds = _LAST_V8_TIMESTAMP + 1
        timestamp_ms, timestamp_ns = divmod(nanoseconds, 10**6)
        subsec = uuid6._subsec_encode(timestamp_ns)

        # This is not what is in the vCon I-D.  It says random bits
        # not bits from the time stamp.  May want to change this
        subsec_a = subsec >> 8
        uuid_int = (timestamp_ms & 0xFFFFFFFFFFFF) << 80
        uuid_int |= subsec_a << 64
        uuid_int |= custom_c_62_bits

        # We lie about the version and then correct it afterwards
        uuid_str = str(uuid6.UUID(int=uuid_int, version=7))
        assert uuid_str[14] == "7"
        uuid_str = uuid_str[:14] + "8" + uuid_str[15:]

        return uuid_str
