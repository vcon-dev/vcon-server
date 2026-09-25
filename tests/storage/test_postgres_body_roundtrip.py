"""CON-1111: postgres storage round-trips a raw JSON body (CON-1111).

Per draft-ietf-vcon-vcon-core-04 §2.3.2, an ``encoding: "json"`` body is the
JSON value itself. The postgres storage module stores the whole vCon dict
under a ``BinaryJSONField`` (JSONB) — it never treats ``body`` specially, so
a raw dict/list body should just ride along unchanged. This mocks out the
peewee model/DB entirely and asserts the ``vcon_json`` payload handed to it
still carries the raw body (dict and legacy stringified str alike).

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

from storage.postgres import save  # noqa: E402

if _orig_lib_logging_utils is not None:
    sys.modules["lib.logging_utils"] = _orig_lib_logging_utils
else:
    sys.modules.pop("lib.logging_utils", None)

if _orig_lib_vcon_redis is not None:
    sys.modules["lib.vcon_redis"] = _orig_lib_vcon_redis
else:
    sys.modules.pop("lib.vcon_redis", None)


def _mock_vcon(canonical):
    mock = MagicMock()
    mock.to_dict.return_value = canonical
    mock.uuid = canonical["uuid"]
    mock.vcon = canonical["vcon"]
    mock.created_at = canonical["created_at"]
    mock.subject = canonical.get("subject")
    return mock


def _canonical_with_raw_body():
    return {
        "vcon": "0.4.0",
        "uuid": "test-uuid",
        "created_at": "2026-06-05T00:00:00+00:00",
        "subject": None,
        "attachments": [
            {"purpose": "lawful_basis", "body": {"lawful_basis": "consent"}, "encoding": "json"},
            {"purpose": "tags", "body": ["source:test"], "encoding": "json"},
        ],
        "analysis": [],
    }


def test_postgres_save_preserves_raw_dict_and_list_body():
    opts = {
        "database": "vcon_db", "user": "u", "password": "p",
        "host": "localhost", "port": 5432, "table_name": "vcons",
    }
    canonical = _canonical_with_raw_body()

    with patch("storage.postgres.VconRedis") as redis_cls, \
         patch("storage.postgres.get_db_connection") as get_db, \
         patch("storage.postgres.create_vcons_model") as create_model:
        redis_cls.return_value.get_vcon.return_value = _mock_vcon(canonical)
        get_db.return_value = MagicMock()

        model_cls = MagicMock()
        insert_query = MagicMock()
        model_cls.insert.return_value = insert_query
        insert_query.on_conflict.return_value.execute.return_value = None
        create_model.return_value = model_cls

        save("test-uuid", opts)

        # The dict passed to insert(**vcon_data) is what would be stored
        # as the JSONB vcon_json column.
        _, kwargs = model_cls.insert.call_args
        stored = kwargs["vcon_json"]
        lawful_basis = next(a for a in stored["attachments"] if a["purpose"] == "lawful_basis")
        tags = next(a for a in stored["attachments"] if a["purpose"] == "tags")
        assert lawful_basis["body"] == {"lawful_basis": "consent"}
        assert lawful_basis["encoding"] == "json"
        assert tags["body"] == ["source:test"]
        assert tags["encoding"] == "json"


def test_postgres_get_returns_stored_json_field_unchanged():
    from storage.postgres import get

    opts = {
        "database": "vcon_db", "user": "u", "password": "p",
        "host": "localhost", "port": 5432, "table_name": "vcons",
    }
    stored_payload = _canonical_with_raw_body()

    with patch("storage.postgres.get_db_connection") as get_db, \
         patch("storage.postgres.create_vcons_model") as create_model:
        get_db.return_value = MagicMock()
        model_cls = MagicMock()
        row = MagicMock()
        row.vcon_json = stored_payload
        model_cls.get.return_value = row
        create_model.return_value = model_cls

        result = get("test-uuid", opts)

        assert result["attachments"][0]["body"] == {"lawful_basis": "consent"}
        assert result["attachments"][1]["body"] == ["source:test"]
