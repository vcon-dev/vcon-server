import json
import os

from fastapi.testclient import TestClient
from vcon_fixture import generate_mock_vcon
import pytest
from unittest.mock import AsyncMock, patch
import api
from datetime import datetime
from settings import CONSERVER_API_TOKEN, CONSERVER_HEADER_NAME

# Set default values for testing if not set
CONSERVER_API_TOKEN = CONSERVER_API_TOKEN or "default_token"
CONSERVER_HEADER_NAME = CONSERVER_HEADER_NAME or "X-API-Token"

since_str = datetime.now().isoformat()


@pytest.fixture(autouse=True)
def disable_storage_fallbacks():
    # These tests exercise the API's Redis-backed lifecycle. Disabling external
    # storage backends keeps them fast and avoids unrelated network noise.
    with patch.object(api.Configuration, "get_storages", return_value={}):
        yield


def post_vcon(vcon):
    # Use the TestClient to make requests to the app.
    with TestClient(app=api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        response = client.post("/vcon", json=vcon)
        assert response.status_code == 201
        print("response: {}".format(response))
        return response


@pytest.mark.anyio
def test_api_vcon_lifecycle():
    # Write a dozen vcons
    test_vcon = generate_mock_vcon()
    post_vcon(test_vcon)

    # Read the vcon back using the test client
    with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        response = client.get("/vcon/{}".format(test_vcon["uuid"]))
        assert response.status_code == 200
        print("response: {}".format(response))

    # Delete the vcon using the test client
    with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        response = client.delete("/vcon/{}".format(test_vcon["uuid"]))
        assert response.status_code == 204
        print("response: {}".format(response))

    # Read the vcon back
    with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        response = client.get("/vcon/{}".format(test_vcon["uuid"]))
        assert response.status_code == 404
        print("response: {}".format(response))


@pytest.mark.anyio
def test_get_vcons():
    vcon_uuids = []
    # Write a dozen vcons and read them back
    for i in range(12):
        test_vcon = generate_mock_vcon()
        post_vcon(test_vcon)
        vcon_uuids.append(test_vcon["uuid"])

    # Read the vcons back using the test client, deleting them as we go
    with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        # Get the list of vCons from the server
        response = client.get(f"/vcon?since={since_str}")
        assert response.status_code == 200
        print("response: {}".format(response))

        # Take the list of vCons, check to see if they are in the list
        # of vCons we created, and delete them
        vcon_list = response.json()
        for vcon_id in vcon_list:
            assert vcon_id in vcon_uuids
            response = client.delete("/vcon/{}".format(vcon_id))
            assert response.status_code == 204
            print(f"API response for {vcon_id}: {response}")


@pytest.mark.anyio
def test_create_vcon_with_extra_attribute():
    # Write a dozen vcons and read them back

    test_vcon = generate_mock_vcon()
    test_vcon["meta"] = {"foo": "bar"}
    post_vcon(test_vcon)

    # Read the vcon back using the test client
    with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        response = client.get("/vcon/{}".format(test_vcon["uuid"]))
        assert response.status_code == 200
        assert response.json()["meta"] == {"foo": "bar"}


_INVALID_FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "invalid_fixtures")


@pytest.mark.parametrize("filename", [
    "bad_party_ref.json",
    "bad_duration.json",
    "bad_url.json",
    "bad_mimetype.json",
])
def test_invalid_vcon_rejected(filename):
    """Malformed vCons must be rejected with 422, not silently accepted."""
    with open(os.path.join(_INVALID_FIXTURES_DIR, filename)) as f:
        broken_vcon = json.load(f)
    with TestClient(app=api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        response = client.post("/vcon", json=broken_vcon)
    assert response.status_code == 422, (
        f"{filename} was unexpectedly accepted: status={response.status_code}, body={response.json()}"
    )


@pytest.mark.anyio
def test_post_vcon_with_ingress_list():
    # Generate a mock vCon
    test_vcon = generate_mock_vcon()

    # Define an ingress list name
    ingress_list_name = "test_ingress_list"

    # Post the vCon with the ingress list
    with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        response = client.post("/vcon", json=test_vcon, params={"ingress_lists": [ingress_list_name]})
        assert response.status_code == 201
        print("response: {}".format(response))

    # Verify the vCon ID is in the ingress list
    with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        response = client.get(f"/vcon/egress?egress_list={ingress_list_name}&limit=1")
        assert response.status_code == 200
        vcon_ids = response.json()
        assert test_vcon["uuid"] in vcon_ids
        print("Ingress list contains vCon ID: {}".format(test_vcon["uuid"]))


@pytest.mark.anyio
def test_post_vcon_with_ingress_list_increments_enqueue_counter():
    """The API must count every vCon it pushes onto an ingress list — the
    chain-stall alert uses this counter as its arrivals signal (CON-618)."""
    test_vcon = generate_mock_vcon()
    ingress_list_name = "test_ingress_list_counter"

    with patch("api.increment_counter") as mock_counter:
        with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
            response = client.post(
                "/vcon", json=test_vcon, params={"ingress_lists": [ingress_list_name]}
            )
            assert response.status_code == 201

    mock_counter.assert_called_once_with(
        "conserver.api.count_vcons_enqueued",
        attributes={"ingress_list": ingress_list_name, "source": "new"},
    )


@pytest.mark.anyio
def test_post_vcon_without_ingress_list_skips_enqueue_counter():
    test_vcon = generate_mock_vcon()

    with patch("api.increment_counter") as mock_counter:
        with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
            response = client.post("/vcon", json=test_vcon)
            assert response.status_code == 201

    mock_counter.assert_not_called()


@pytest.mark.anyio
def test_vcon_ingress_bulk_increments_enqueue_counter():
    """POST /vcon/ingress counts every UUID it pushes (source=reingress)."""
    test_vcon = generate_mock_vcon()
    post_vcon(test_vcon)
    ingress_list_name = "test_ingress_bulk_counter"

    with patch("api.increment_counter") as mock_counter:
        with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
            response = client.post(
                "/vcon/ingress",
                json=[test_vcon["uuid"]],
                params={"ingress_list": ingress_list_name},
            )
            assert response.status_code == 204

    mock_counter.assert_called_once_with(
        "conserver.api.count_vcons_enqueued",
        value=1,
        attributes={"ingress_list": ingress_list_name, "source": "reingress"},
    )


@pytest.mark.anyio
def test_external_ingress_increments_enqueue_counter():
    """POST /vcon/external-ingress counts the submitted vCon (source=external)."""
    test_vcon = generate_mock_vcon()
    ingress_list_name = "partner_list"

    with patch.object(
        api.Configuration, "get_ingress_auth", return_value={ingress_list_name: "partner-key"}
    ), patch("api.increment_counter") as mock_counter:
        with TestClient(api.app, headers={CONSERVER_HEADER_NAME: "partner-key"}) as client:
            response = client.post(
                "/vcon/external-ingress",
                json=test_vcon,
                params={"ingress_list": ingress_list_name},
            )
            assert response.status_code == 204

    mock_counter.assert_called_once_with(
        "conserver.api.count_vcons_enqueued",
        attributes={"ingress_list": ingress_list_name, "source": "external"},
    )


@pytest.mark.anyio
def test_dlq_reprocess_increments_enqueue_counter_with_moved_count():
    """POST /dlq/reprocess counts how many items it moved back (source=dlq_reprocess)."""
    ingress_list_name = "test_dlq_counter"

    with patch.object(
        api.queue, "dequeue_dlq_async", new=AsyncMock(side_effect=["uuid-1", "uuid-2", None])
    ), patch.object(api.queue, "enqueue_async", new=AsyncMock()), patch(
        "api.increment_counter"
    ) as mock_counter:
        with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
            response = client.post("/dlq/reprocess", params={"ingress_list": ingress_list_name})
            assert response.status_code == 200
            assert response.json() == 2

    mock_counter.assert_called_once_with(
        "conserver.api.count_vcons_enqueued",
        value=2,
        attributes={"ingress_list": ingress_list_name, "source": "dlq_reprocess"},
    )


@pytest.mark.anyio
def test_dlq_reprocess_empty_dlq_skips_enqueue_counter():
    """An empty DLQ moves nothing and must not emit a zero-count increment."""
    with patch.object(
        api.queue, "dequeue_dlq_async", new=AsyncMock(return_value=None)
    ), patch("api.increment_counter") as mock_counter:
        with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
            response = client.post("/dlq/reprocess", params={"ingress_list": "empty_dlq"})
            assert response.status_code == 200
            assert response.json() == 0

    mock_counter.assert_not_called()
