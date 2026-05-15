from unittest.mock import MagicMock, patch

import pytest

from storage import milvus as milvus_module
from storage.milvus import (
    check_vcon_exists,
    create_collection,
    ensure_milvus_connection,
    extract_party_id,
    get,
    get_embedding,
    save,
)


@pytest.fixture
def milvus_env():
    with patch.object(milvus_module, "connections") as mock_connections, patch.object(
        milvus_module, "utility"
    ) as mock_utility, patch.object(milvus_module, "Collection") as mock_collection_class:
        mock_utility.has_collection.return_value = True
        mock_utility.list_collections.return_value = ["vcons"]
        mock_collection = MagicMock()
        mock_collection_class.return_value = mock_collection
        yield {
            "connections": mock_connections,
            "utility": mock_utility,
            "collection_class": mock_collection_class,
            "collection": mock_collection,
        }


@pytest.mark.parametrize(
    ("opts", "expected_type", "expected_params"),
    [
        ({"index_type": "IVF_PQ", "pq_m": 12, "pq_nbits": 6, "nlist": 64}, "IVF_PQ", {"nlist": 64, "m": 12, "nbits": 6}),
        ({"index_type": "HNSW", "m": 32, "ef_construction": 99}, "HNSW", {"M": 32, "efConstruction": 99}),
        ({"index_type": "ANNOY", "n_trees": 75}, "ANNOY", {"n_trees": 75}),
        ({"index_type": "FLAT"}, "FLAT", {}),
        ({"index_type": "UNKNOWN", "nlist": 16}, "IVF_FLAT", {"nlist": 16}),
    ],
)
def test_create_collection_uses_expected_index_parameters(opts, expected_type, expected_params):
    with patch.object(milvus_module, "FieldSchema", side_effect=lambda **kwargs: kwargs), patch.object(
        milvus_module,
        "CollectionSchema",
        side_effect=lambda fields, description: {"fields": fields, "description": description},
    ), patch.object(milvus_module, "Collection") as mock_collection_class:
        collection = MagicMock()
        mock_collection_class.return_value = collection

        result = create_collection("vcons", 1536, opts)

    assert result is collection
    collection.create_index.assert_called_once_with(
        field_name="embedding",
        index_params={
            "metric_type": opts.get("metric_type", "L2"),
            "index_type": expected_type,
            "params": expected_params,
        },
    )


def test_create_collection_returns_none_on_failure():
    with patch.object(milvus_module, "FieldSchema", side_effect=lambda **kwargs: kwargs), patch.object(
        milvus_module,
        "CollectionSchema",
        side_effect=lambda fields, description: {"fields": fields, "description": description},
    ), patch.object(milvus_module, "Collection", side_effect=RuntimeError("boom")):
        assert create_collection("vcons", 1536, {"index_type": "FLAT"}) is None


def test_ensure_milvus_connection_returns_false_when_reconnect_fails(milvus_env):
    milvus_env["utility"].list_collections.side_effect = Exception("stale")
    milvus_env["connections"].connect.side_effect = RuntimeError("down")

    assert ensure_milvus_connection("localhost", "19530") is False


def test_get_embedding_returns_zero_vector_when_openai_call_fails():
    failing_client = MagicMock()
    failing_client.embeddings.create.side_effect = RuntimeError("no embedding")

    with patch.object(milvus_module, "increment_counter") as mock_counter:
        embedding = get_embedding("hello", failing_client, "text-embedding-3-small")

    assert len(embedding) == 1536
    assert set(embedding) == {0}
    mock_counter.assert_called_once_with("conserver.storage.milvus.embedding_failures")


def test_extract_party_id_covers_remaining_identifier_fallbacks():
    assert extract_party_id({"parties": [{"uuid": "party-uuid"}]}) == "party-uuid"
    assert extract_party_id({"parties": [{"mailto": "person@example.com"}]}) == "mailto:person@example.com"
    assert extract_party_id({"parties": [{"role": "agent"}]}) == "agent"
    assert extract_party_id({"parties": [{"partyId": "legacy-id"}]}) == "legacy-id"
    assert extract_party_id({"parties": [{}], "metadata": {"creator": "creator-id"}}) == "party_index:0"
    assert extract_party_id({"metadata": {"creator": "creator-id"}}) == "creator-id"
    assert extract_party_id({"parties": [{}]}) == "party_index:0"


def test_check_vcon_exists_returns_false_when_query_errors(milvus_env):
    milvus_env["collection"].query.side_effect = RuntimeError("query failed")

    assert check_vcon_exists(milvus_env["collection"], "vc-1") is False


def test_save_raises_when_connection_fails():
    with patch.object(milvus_module, "ensure_milvus_connection", return_value=False):
        with pytest.raises(ConnectionError, match="Failed to connect to Milvus"):
            save("vc-1", {"host": "localhost", "port": "19530"})


def test_save_raises_when_collection_is_missing_and_autocreate_disabled(milvus_env):
    milvus_env["utility"].has_collection.return_value = False

    with patch.object(milvus_module, "ensure_milvus_connection", return_value=True):
        with pytest.raises(ValueError, match="Collection vcons does not exist"):
            save("vc-1", {"collection_name": "vcons", "create_collection_if_missing": False})


def test_save_raises_when_collection_creation_fails(milvus_env):
    milvus_env["utility"].has_collection.return_value = False

    with patch.object(milvus_module, "ensure_milvus_connection", return_value=True), patch.object(
        milvus_module, "create_collection", return_value=None
    ):
        with pytest.raises(ValueError, match="Failed to create collection vcons"):
            save("vc-1", {"collection_name": "vcons", "create_collection_if_missing": True})


def test_save_raises_when_vcon_is_missing_in_redis(milvus_env):
    redis_client = MagicMock()
    redis_client.get_vcon.return_value = None

    with patch.object(milvus_module, "ensure_milvus_connection", return_value=True), patch.object(
        milvus_module, "VconRedis", return_value=redis_client
    ):
        with pytest.raises(ValueError, match="not found in Redis"):
            save("vc-1", {"collection_name": "vcons"})


def test_save_skips_when_vcon_already_exists(milvus_env):
    redis_client = MagicMock()
    redis_client.get_vcon.return_value = {"uuid": "vc-1"}

    with patch.object(milvus_module, "ensure_milvus_connection", return_value=True), patch.object(
        milvus_module, "VconRedis", return_value=redis_client
    ), patch.object(milvus_module, "check_vcon_exists", return_value=True):
        save("vc-1", {"collection_name": "vcons", "skip_if_exists": True})

    milvus_env["collection"].insert.assert_not_called()


def test_save_skips_when_no_text_can_be_extracted(milvus_env):
    redis_client = MagicMock()
    redis_client.get_vcon.return_value = {"uuid": "vc-1"}

    with patch.object(milvus_module, "ensure_milvus_connection", return_value=True), patch.object(
        milvus_module, "VconRedis", return_value=redis_client
    ), patch.object(milvus_module, "check_vcon_exists", return_value=False), patch.object(
        milvus_module, "extract_text_from_vcon", return_value=""
    ), patch.object(milvus_module, "get_openai_client", return_value=MagicMock()):
        save("vc-1", {"collection_name": "vcons", "skip_if_exists": True})

    milvus_env["collection"].insert.assert_not_called()


def test_save_raises_when_embedding_dimension_is_invalid(milvus_env):
    redis_client = MagicMock()
    redis_client.get_vcon.return_value = {"uuid": "vc-1", "metadata": {}, "analysis": [], "parties": []}

    with patch.object(milvus_module, "ensure_milvus_connection", return_value=True), patch.object(
        milvus_module, "VconRedis", return_value=redis_client
    ), patch.object(milvus_module, "check_vcon_exists", return_value=False), patch.object(
        milvus_module, "extract_text_from_vcon", return_value="hello"
    ), patch.object(milvus_module, "extract_party_id", return_value="party-1"), patch.object(
        milvus_module, "get_openai_client", return_value=MagicMock()
    ), patch.object(milvus_module, "get_embedding", return_value=[0.1, 0.2]):
        with pytest.raises(ValueError, match="Invalid embedding dimensions"):
            save(
                "vc-1",
                {"collection_name": "vcons", "embedding_model": "text-embedding-3-small", "embedding_dim": 1536},
            )


def test_get_returns_none_for_connection_collection_and_query_failures(milvus_env):
    with patch.object(milvus_module, "ensure_milvus_connection", return_value=False):
        assert get("vc-1", {"collection_name": "vcons"}) is None

    with patch.object(milvus_module, "ensure_milvus_connection", return_value=True):
        milvus_env["utility"].has_collection.return_value = False
        assert get("vc-1", {"collection_name": "vcons"}) is None

    milvus_env["utility"].has_collection.return_value = True
    milvus_env["collection"].query.side_effect = RuntimeError("query failed")
    with patch.object(milvus_module, "ensure_milvus_connection", return_value=True):
        assert get("vc-1", {"collection_name": "vcons"}) is None
