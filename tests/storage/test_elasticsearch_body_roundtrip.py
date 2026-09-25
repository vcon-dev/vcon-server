"""CON-1111: elasticsearch storage indexes a raw JSON body correctly.

Per draft-ietf-vcon-vcon-core-04 §2.3.2, an ``encoding: "json"`` body is the
JSON value itself. ``storage.elasticsearch.save`` already special-cases
``encoding == "json" and isinstance(body, str)`` before parsing — a raw
dict/list body falls through untouched, which is already correct. This
locks that behavior in.

Follows tests/storage/test_egress_compat_integration.py's sys.modules
pattern for importing the module without opening a real Redis connection.
"""

import sys
from unittest.mock import MagicMock, patch

_ORIG = {name: sys.modules.get(name) for name in ("lib.logging_utils", "lib.vcon_redis")}
sys.modules["lib.logging_utils"] = MagicMock(init_logger=MagicMock(return_value=MagicMock()))
sys.modules["lib.vcon_redis"] = MagicMock()

from storage import elasticsearch as es_storage  # noqa: E402

for _name, _mod in _ORIG.items():
    if _mod is not None:
        sys.modules[_name] = _mod
    else:
        sys.modules.pop(_name, None)


def _mock_vcon(canonical):
    mock = MagicMock()
    mock.to_dict.return_value = canonical
    mock.find_attachment_by_purpose.side_effect = lambda p: next(
        (a for a in canonical["attachments"] if a.get("purpose") == p), None
    )
    return mock


def test_elasticsearch_indexes_raw_dict_and_list_bodies_unchanged():
    canonical = {
        "uuid": "test-uuid",
        "vcon": "0.4.0",
        "dialog": [{"start": "2026-06-05T00:00:00+00:00"}],
        "parties": [],
        "attachments": [
            {"purpose": "tenant", "body": {"id": 385}, "encoding": "json"},
            {"purpose": "tags", "body": ["source:test"], "encoding": "json"},
        ],
        "analysis": [
            {"type": "summary", "body": {"text": "hi"}, "encoding": "json"},
        ],
    }
    opts = {"url": "http://es:9200", "username": "u", "password": "p"}

    with patch.object(es_storage, "VconRedis") as redis_cls, \
         patch.object(es_storage, "elasticsearch") as es_lib:
        redis_cls.return_value.get_vcon.return_value = _mock_vcon(canonical)
        es = es_lib.Elasticsearch.return_value

        es_storage.save("test-uuid", opts)

        indexed = {c.kwargs["index"]: c.kwargs["document"] for c in es.index.call_args_list}
        tenant_doc = next(d for idx, d in indexed.items() if idx.startswith("vcon_attachments_tenant"))
        tags_doc = next(d for idx, d in indexed.items() if idx.startswith("vcon_attachments_tags"))
        summary_doc = next(d for idx, d in indexed.items() if idx == "vcon_analysis_summary")

        assert tenant_doc["body"] == {"id": 385}
        assert tags_doc["body"] == ["source:test"]
        assert summary_doc["body"] == {"text": "hi"}
        # common_attributes.tenant_id resolution also exercises the raw-dict path.
        assert indexed[next(idx for idx in indexed if idx.startswith("vcon_attachments_tenant"))]["tenant_id"] == 385
