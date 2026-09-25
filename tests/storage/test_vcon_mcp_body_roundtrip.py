"""CON-1111: vcon-mcp REST storage round-trips a raw JSON body.

``storage.vcon_mcp.save`` POSTs ``vcon.to_dict()`` as the request JSON body
verbatim — it never touches ``body`` fields, so a raw dict/list body must
ride along unchanged both on save (outgoing JSON) and get (the response is
handed back as-is).
"""

from unittest.mock import MagicMock, patch

from storage.vcon_mcp import save, get


def _canonical_with_raw_body():
    return {
        "uuid": "test-uuid",
        "vcon": "0.4.0",
        "attachments": [
            {"purpose": "lawful_basis", "body": {"lawful_basis": "consent"}, "encoding": "json"},
            {"purpose": "tags", "body": ["source:test"], "encoding": "json"},
        ],
    }


def test_vcon_mcp_save_posts_raw_body_unchanged():
    canonical = _canonical_with_raw_body()
    mock_vcon = MagicMock()
    mock_vcon.to_dict.return_value = canonical

    with patch("storage.vcon_mcp.VconRedis") as redis_cls, \
         patch("storage.vcon_mcp._session") as session_factory:
        redis_cls.return_value.get_vcon.return_value = mock_vcon
        session = MagicMock()
        session.__enter__.return_value = session
        session.__exit__.return_value = False
        session.post.return_value = MagicMock(status_code=201, raise_for_status=lambda: None)
        session_factory.return_value = session

        save("test-uuid", {"base_url": "http://mcp.local/api/v1"})

        posted = session.post.call_args.kwargs["json"]
        assert posted["attachments"][0]["body"] == {"lawful_basis": "consent"}
        assert posted["attachments"][1]["body"] == ["source:test"]


def test_vcon_mcp_get_returns_raw_body_unchanged():
    canonical = _canonical_with_raw_body()

    with patch("storage.vcon_mcp._session") as session_factory:
        session = MagicMock()
        session.__enter__.return_value = session
        session.__exit__.return_value = False
        response = MagicMock(status_code=200)
        response.raise_for_status = lambda: None
        response.json.return_value = {"vcon": canonical}
        session.get.return_value = response
        session_factory.return_value = session

        result = get("test-uuid", {"base_url": "http://mcp.local/api/v1"})

        assert result["attachments"][0]["body"] == {"lawful_basis": "consent"}
        assert result["attachments"][1]["body"] == ["source:test"]
