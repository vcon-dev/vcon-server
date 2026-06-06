"""Integration tests for the egress_format_version option (CON-581).

Exercises the real save()/run() code paths of the egress points that consume a
vCon document — the s3 and elasticsearch storage modules and the webhook link —
with the option active, asserting the emitted payload is the legacy 0.0.1 shape
while the canonical copy handed in is untouched.

Follows test_s3's sys.modules pattern: lib.vcon_redis / lib.logging_utils /
lib.metrics are mocked before importing the modules under test (so importing
them doesn't open a real Redis connection), then restored.
"""

import importlib
import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

CONSERVER_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "conserver")

_ORIG = {name: sys.modules.get(name) for name in ("lib.logging_utils", "lib.vcon_redis", "lib.metrics")}

sys.modules["lib.logging_utils"] = MagicMock(init_logger=MagicMock(return_value=MagicMock()))
sys.modules["lib.vcon_redis"] = MagicMock()
sys.modules["lib.metrics"] = MagicMock(increment_counter=MagicMock())

from storage import s3 as s3_storage  # noqa: E402
from storage import elasticsearch as es_storage  # noqa: E402

if CONSERVER_DIR not in sys.path:
    sys.path.insert(0, CONSERVER_DIR)
webhook_link = importlib.import_module("links.webhook")  # noqa: E402

for _name, _mod in _ORIG.items():
    if _mod is not None:
        sys.modules[_name] = _mod
    else:
        sys.modules.pop(_name, None)


def _canonical_dict():
    """A spec-current (0.4.0) vCon as vcon.to_dict() would return it."""
    return {
        "vcon": "0.4.0",
        "uuid": "test-uuid",
        "created_at": "2026-06-05T00:00:00+00:00",
        "subject": None,
        "parties": [{"tel": "+15551234567", "role": "customer"}],
        "dialog": [{"type": "recording", "start": "2026-06-05T00:00:00+00:00", "mediatype": "audio/wav"}],
        "analysis": [{"type": "summary", "dialog": 0, "vendor": "openai", "body": "s", "encoding": "none", "schema": "v1"}],
        "attachments": [{"purpose": "tags", "body": ["category:1"], "encoding": "none"}],
        "meta": {"tenant_id": 42},
    }


def _mock_vcon():
    canonical = _canonical_dict()
    mock = MagicMock()
    mock.to_dict.return_value = canonical
    mock.dumps.return_value = json.dumps(canonical)
    mock.created_at = canonical["created_at"]
    mock.uuid = canonical["uuid"]
    mock.vcon = canonical["vcon"]
    mock.subject = canonical["subject"]
    return mock


# --- s3 storage ------------------------------------------------------------

def test_s3_save_emits_legacy_when_option_set():
    opts = {
        "aws_access_key_id": "k",
        "aws_secret_access_key": "s",
        "aws_bucket": "b",
        "egress_format_version": "0.0.1",
    }
    with patch("storage.s3.VconRedis") as redis_cls, patch("storage.s3.boto3.client") as boto:
        redis_cls.return_value.get_vcon.return_value = _mock_vcon()
        mock_s3 = MagicMock()
        boto.return_value = mock_s3

        s3_storage.save("test-uuid", opts)

        body_call = next(c for c in mock_s3.put_object.call_args_list if c.kwargs["Key"].endswith(".vcon"))
        stored = json.loads(body_call.kwargs["Body"])
        assert stored["vcon"] == "0.0.1"
        assert stored["attachments"][0]["type"] == "tags"
        assert "purpose" not in stored["attachments"][0]
        assert stored["dialog"][0]["mimetype"] == "audio/wav"


def test_s3_save_unchanged_when_option_absent():
    opts = {"aws_access_key_id": "k", "aws_secret_access_key": "s", "aws_bucket": "b"}
    with patch("storage.s3.VconRedis") as redis_cls, patch("storage.s3.boto3.client") as boto:
        vcon = _mock_vcon()
        redis_cls.return_value.get_vcon.return_value = vcon
        mock_s3 = MagicMock()
        boto.return_value = mock_s3

        s3_storage.save("test-uuid", opts)

        body_call = next(c for c in mock_s3.put_object.call_args_list if c.kwargs["Key"].endswith(".vcon"))
        # Default path uses vcon.dumps() verbatim — the canonical 0.4.0 payload.
        assert json.loads(body_call.kwargs["Body"])["vcon"] == "0.4.0"
        vcon.dumps.assert_called_once()


# --- elasticsearch storage -------------------------------------------------

def test_elasticsearch_indexes_attachments_by_legacy_type_when_option_set():
    opts = {"url": "http://es:9200", "username": "u", "password": "p", "egress_format_version": "0.0.1"}
    # Patch the module's bound `elasticsearch` reference wholesale rather than a
    # dotted attribute path — robust to import-name shadowing under full-suite
    # collection order.
    with patch.object(es_storage, "VconRedis") as redis_cls, \
         patch.object(es_storage, "elasticsearch") as es_lib:
        redis_cls.return_value.get_vcon.return_value = _mock_vcon()
        es = es_lib.Elasticsearch.return_value

        es_storage.save("test-uuid", opts)

        attach_indexes = [c.kwargs["index"] for c in es.index.call_args_list if "attachments" in c.kwargs["index"]]
        assert "vcon_attachments_tags" in attach_indexes


# --- webhook link ----------------------------------------------------------

def test_webhook_posts_legacy_payload_when_option_set():
    opts = {"webhook-urls": ["https://downstream.example/ingest"], "egress_format_version": "0.0.1"}
    with patch.object(webhook_link, "VconRedis") as redis_cls, \
         patch.object(webhook_link, "requests") as req:
        redis_cls.return_value.get_vcon.return_value = _mock_vcon()
        req.post.return_value = MagicMock(status_code=200, text="ok")

        result = webhook_link.run("test-uuid", "wh", opts)

        assert result == "test-uuid"
        posted = req.post.call_args.kwargs["json"]
        assert posted["vcon"] == "0.0.1"
        assert posted["attachments"][0]["type"] == "tags"
        assert "purpose" not in posted["attachments"][0]


def test_webhook_posts_canonical_when_option_absent():
    opts = {"webhook-urls": ["https://downstream.example/ingest"]}
    with patch.object(webhook_link, "VconRedis") as redis_cls, \
         patch.object(webhook_link, "requests") as req:
        redis_cls.return_value.get_vcon.return_value = _mock_vcon()
        req.post.return_value = MagicMock(status_code=200, text="ok")

        webhook_link.run("test-uuid", "wh", opts)

        posted = req.post.call_args.kwargs["json"]
        assert posted["vcon"] == "0.4.0"
        assert posted["attachments"][0]["purpose"] == "tags"
