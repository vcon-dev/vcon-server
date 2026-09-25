"""CON-1111: redis_storage round-trips a raw JSON body.

``storage.redis_storage.save`` writes ``vcon.dumps()`` verbatim as a plain
Redis string; ``get`` ``json.loads`` it back. Neither touches ``body``
fields, so a raw dict/list body (draft-ietf-vcon-vcon-core-04 §2.3.2,
encoding "json") must ride along unchanged.
"""

from unittest.mock import MagicMock, patch

from vcon import Vcon
from storage.redis_storage import save, get


def test_save_then_get_preserves_raw_dict_and_list_body():
    vcon = Vcon.build_new()
    vcon.add_attachment(body={"lawful_basis": "consent"}, type="lawful_basis")
    vcon.add_attachment(body=["source:test"], type="tags")

    opts = {"prefix": "vcon_storage", "expires": 3600}
    store = {}

    with patch("storage.redis_storage.VconRedis") as MockVconRedis, \
         patch("storage.redis_storage.redis") as mock_redis:
        mock_vcon_redis = MagicMock()
        mock_vcon_redis.get_vcon.return_value = vcon
        MockVconRedis.return_value = mock_vcon_redis

        def _set(key, value, ex=None):
            store[key] = value

        mock_redis.set.side_effect = _set
        mock_redis.get.side_effect = lambda key: store.get(key)

        save(vcon.uuid, opts)
        result = get(vcon.uuid, opts)

    lawful_basis = next(a for a in result["attachments"] if a["type"] == "lawful_basis")
    tags = next(a for a in result["attachments"] if a["type"] == "tags")
    assert lawful_basis["body"] == {"lawful_basis": "consent"}
    assert lawful_basis["encoding"] == "json"
    assert tags["body"] == ["source:test"]
    assert tags["encoding"] == "json"
