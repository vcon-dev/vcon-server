from fastapi.testclient import TestClient
from vcon_fixture import generate_mock_vcon
import pytest
import api
from datetime import datetime
from settings import CONSERVER_API_TOKEN, CONSERVER_HEADER_NAME

# Set default values for testing if not set
CONSERVER_API_TOKEN = CONSERVER_API_TOKEN or "default_token"
CONSERVER_HEADER_NAME = CONSERVER_HEADER_NAME or "X-API-Token"

since_str = datetime.now().isoformat()


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
