from fastapi.testclient import TestClient
from vcon_fixture import generate_mock_vcon
import pytest
import api
from datetime import datetime
from settings import CONSERVER_API_TOKEN, CONSERVER_HEADER_NAME
import os
import tempfile

# Set default values for testing if not set
CONSERVER_API_TOKEN = CONSERVER_API_TOKEN or "default_token"
CONSERVER_HEADER_NAME = CONSERVER_HEADER_NAME or "X-API-Token"

since_str = datetime.now().isoformat()


# Setup test environment
@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment variables and directories."""
    # Create a temporary directory for test files if needed
    test_dir = tempfile.mkdtemp()
    
    # Set environment variables for testing
    os.environ.setdefault('VCON_STORAGE_PATH', test_dir)
    os.environ.setdefault('REDIS_URL', 'redis://localhost:6379')
    
    yield
    
    # Cleanup after tests
    import shutil
    try:
        shutil.rmtree(test_dir)
    except:
        pass


def post_vcon(vcon):
    """Helper function to post a vCon."""
    # Use the TestClient to make requests to the app.
    with TestClient(app=api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        response = client.post("/vcon", json=vcon)
        assert response.status_code == 201
        print("response: {}".format(response))
        return response


@pytest.mark.anyio
def test_api_vcon_lifecycle():
    """Test the complete lifecycle of a vCon: create, read, delete."""
    # Write a vcon
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

    # Read the vcon back - should be 404
    with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        response = client.get("/vcon/{}".format(test_vcon["uuid"]))
        assert response.status_code == 404
        print("response: {}".format(response))


@pytest.mark.anyio
def test_get_vcons():
    """Test getting multiple vCons."""
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
            if vcon_id in vcon_uuids:  # Only delete vCons we created
                response = client.delete("/vcon/{}".format(vcon_id))
                assert response.status_code == 204
                print(f"API response for {vcon_id}: {response}")


@pytest.mark.anyio
def test_create_vcon_with_extra_attribute():
    """Test creating a vCon with extra metadata."""
    test_vcon = generate_mock_vcon()
    test_vcon["meta"] = {"foo": "bar"}
    post_vcon(test_vcon)

    # Read the vcon back using the test client
    with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        response = client.get("/vcon/{}".format(test_vcon["uuid"]))
        assert response.status_code == 200
        response_data = response.json()
        assert "meta" in response_data
        assert response_data["meta"] == {"foo": "bar"}


@pytest.mark.anyio
def test_post_vcon_with_ingress_list():
    """Test posting a vCon with an ingress list."""
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