"""CON-1111: mongo storage round-trips a raw JSON body.

Per draft-ietf-vcon-vcon-core-04 §2.3.2, an ``encoding: "json"`` body is the
JSON value itself. The mongo storage module stores the whole vCon dict as a
BSON document (``prepare_vcon_for_mongo``/``collection.update_one``) — it
never treats ``body`` specially, so a raw dict/list body should ride along
unchanged through both ``save`` and ``fetch``/``get``.

Follows tests/storage/test_s3.py's sys.modules pattern: lib.vcon_redis /
lib.logging_utils are mocked before importing the module under test so
importing it doesn't open a real Redis connection, then restored.
"""

import sys
from unittest.mock import MagicMock, patch

_orig_lib_logging_utils = sys.modules.get("lib.logging_utils")
_orig_lib_vcon_redis = sys.modules.get("lib.vcon_redis")

sys.modules["lib.logging_utils"] = MagicMock(init_logger=MagicMock(return_value=MagicMock()))
sys.modules["lib.vcon_redis"] = MagicMock()

from storage.mongo import save, get  # noqa: E402

if _orig_lib_logging_utils is not None:
    sys.modules["lib.logging_utils"] = _orig_lib_logging_utils
else:
    sys.modules.pop("lib.logging_utils", None)

if _orig_lib_vcon_redis is not None:
    sys.modules["lib.vcon_redis"] = _orig_lib_vcon_redis
else:
    sys.modules.pop("lib.vcon_redis", None)


def _canonical_with_raw_body():
    return {
        "vcon": "0.4.0",
        "uuid": "test-uuid",
        "created_at": "2026-06-05T00:00:00.000Z",
        "dialog": [],
        "attachments": [
            {"purpose": "lawful_basis", "body": {"lawful_basis": "consent"}, "encoding": "json"},
            {"purpose": "tags", "body": ["source:test"], "encoding": "json"},
        ],
        "analysis": [],
    }


def _mock_vcon(canonical):
    mock = MagicMock()
    mock.to_dict.return_value = canonical
    mock.uuid = canonical["uuid"]
    return mock


def test_mongo_save_preserves_raw_dict_and_list_body():
    opts = {"url": "mongodb://localhost:27017/", "database": "conserver", "collection": "vcons"}
    canonical = _canonical_with_raw_body()

    with patch("storage.mongo.VconRedis") as redis_cls, \
         patch("storage.mongo.pymongo.MongoClient") as mongo_client_cls:
        redis_cls.return_value.get_vcon.return_value = _mock_vcon(canonical)
        collection = MagicMock()
        mongo_client_cls.return_value.__getitem__.return_value.__getitem__.return_value = collection
        collection.update_one.return_value = MagicMock(modified_count=1, upserted_id=None)

        save("test-uuid", opts)

        args, _ = collection.update_one.call_args
        stored = args[1]["$set"]
        lawful_basis = next(a for a in stored["attachments"] if a["purpose"] == "lawful_basis")
        tags = next(a for a in stored["attachments"] if a["purpose"] == "tags")
        assert lawful_basis["body"] == {"lawful_basis": "consent"}
        assert tags["body"] == ["source:test"]


def test_mongo_get_returns_raw_body_unchanged():
    opts = {"url": "mongodb://localhost:27017/", "database": "conserver", "collection": "vcons"}
    stored_doc = {**_canonical_with_raw_body(), "_id": "test-uuid"}

    with patch("storage.mongo.pymongo.MongoClient") as mongo_client_cls:
        collection = MagicMock()
        mongo_client_cls.return_value.__getitem__.return_value.__getitem__.return_value = collection
        collection.find_one.return_value = stored_doc

        result = get("test-uuid", opts)

        assert result["attachments"][0]["body"] == {"lawful_basis": "consent"}
        assert result["attachments"][1]["body"] == ["source:test"]
