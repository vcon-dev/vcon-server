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


# For test cleanup, use the testing endpoint to completely clear Redis lists
def clear_redis_list(list_name):
    """Clear a Redis list using the testing endpoint"""
    with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        response = client.post("/testing/clear_list", params={"list_name": list_name})
        assert response.status_code == 204
        print(f"Cleared Redis list: {list_name}")


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


@pytest.mark.anyio
def test_get_multiple_vcons():
    """Test fetching multiple vCons by UUIDs endpoint"""
    # Create several vCons
    test_vcons = []
    for i in range(5):
        test_vcon = generate_mock_vcon()
        post_vcon(test_vcon)
        test_vcons.append(test_vcon)
    
    # Get the UUIDs to query
    uuids = [vcon["uuid"] for vcon in test_vcons]
    
    # Fetch the vCons by UUIDs
    with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        response = client.get("/vcons", params={"vcon_uuids": uuids})
        assert response.status_code == 200
        vcons = response.json()
        assert len(vcons) == len(uuids)
        
        # Verify each vCon is present
        retrieved_uuids = [vcon["uuid"] for vcon in vcons if vcon]
        for uuid in uuids:
            assert uuid in retrieved_uuids
        
        print(f"Successfully retrieved {len(vcons)} vCons by UUIDs")


@pytest.mark.anyio
def test_search_vcons():
    """Test searching vCons by various parameters"""
    # Create a vCon with specific attributes for searching
    test_vcon = generate_mock_vcon()
    
    # Set a specific phone number, email, and name for easy searching
    test_phone = "+1234567890"
    test_email = "test.search@example.com"
    test_name = "Test Search User"
    
    # Update the first party with these values
    if test_vcon["parties"]:
        test_vcon["parties"][0]["tel"] = test_phone
        test_vcon["parties"][0]["mailto"] = test_email
        test_vcon["parties"][0]["name"] = test_name
    else:
        test_vcon["parties"] = [{
            "tel": test_phone,
            "mailto": test_email,
            "name": test_name,
            "meta": {"role": "customer"}
        }]
    
    # Store the vCon
    post_vcon(test_vcon)
    
    print(f"Test vCon UUID: {test_vcon['uuid']}")
    print(f"Phone number to search: {test_phone}")
    
    # Test searching by phone number
    with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        # Create URL with properly encoded parameter
        import urllib.parse
        encoded_phone = urllib.parse.quote_plus(test_phone)
        search_url = f"/vcons/search?tel={encoded_phone}"
        print(f"Search URL: {search_url}")
        
        response = client.get(search_url)
        assert response.status_code == 200
        results = response.json()
        print(f"Search results: {results}")
        assert test_vcon["uuid"] in results
        print(f"Successfully searched vCon by phone: found {len(results)} results")
    
    # Test searching by email
    with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        response = client.get(f"/vcons/search?mailto={test_email}")
        assert response.status_code == 200
        results = response.json()
        assert test_vcon["uuid"] in results
        print(f"Successfully searched vCon by email: found {len(results)} results")
    
    # Test searching by name
    with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        response = client.get(f"/vcons/search?name={test_name}")
        assert response.status_code == 200
        results = response.json()
        assert test_vcon["uuid"] in results
        print(f"Successfully searched vCon by name: found {len(results)} results")
    
    # Test combined search (should return the same result)
    with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        response = client.get(f"/vcons/search?tel={encoded_phone}&mailto={test_email}")
        assert response.status_code == 200
        results = response.json()
        assert test_vcon["uuid"] in results
        print(f"Successfully performed combined search: found {len(results)} results")


@pytest.mark.anyio
def test_vcon_ingress_and_count():
    """Test adding vCons to an ingress list and checking the count"""
    # Clear the test list before starting
    ingress_list_name = "test_ingress_count_list"
    clear_redis_list(ingress_list_name)
    
    # Create some vCons
    test_vcons = []
    for i in range(3):
        test_vcon = generate_mock_vcon()
        post_vcon(test_vcon)
        test_vcons.append(test_vcon)
    
    # Get the UUIDs
    uuids = [vcon["uuid"] for vcon in test_vcons]
    
    # Add the vCon UUIDs to the ingress list
    with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        response = client.post("/vcon/ingress", 
                               json=uuids, 
                               params={"ingress_list": ingress_list_name})
        assert response.status_code == 204
        print(f"Added {len(uuids)} vCons to ingress list {ingress_list_name}")
    
    # Check the count
    with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        response = client.get(f"/vcons/count?egress_list={ingress_list_name}")
        assert response.status_code == 200
        count = response.json()
        assert count == len(uuids)
        print(f"Count in ingress list {ingress_list_name}: {count}")
    
    # Get the vCons from the egress list
    with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        response = client.get(f"/vcon/egress?egress_list={ingress_list_name}&limit={len(uuids)}")
        assert response.status_code == 200
        egress_uuids = response.json()
        assert len(egress_uuids) == len(uuids)
        
        # Verify each UUID is in the response
        for uuid in uuids:
            assert uuid in egress_uuids
        print(f"Successfully retrieved {len(egress_uuids)} vCons from egress list")


@pytest.mark.anyio
def test_dlq_operations():
    """Test dead letter queue operations"""
    # Clear test lists before starting
    ingress_list = "test_dlq_ingress"
    dlq_name = f"DLQ:{ingress_list}"
    clear_redis_list(ingress_list)
    clear_redis_list(dlq_name)
    
    # First, set up some vCons in an ingress list that we'll move to DLQ
    test_vcons = []
    for i in range(2):
        test_vcon = generate_mock_vcon()
        post_vcon(test_vcon)
        test_vcons.append(test_vcon)
    
    # Define test lists
    ingress_list = "test_dlq_ingress"
    dlq_name = f"DLQ:{ingress_list}"  # Match the format in dlq_utils.py - get_ingress_list_dlq_name
    
    # Add vCons to the ingress list
    uuids = [vcon["uuid"] for vcon in test_vcons]
    with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        client.post("/vcon/ingress", json=uuids, params={"ingress_list": ingress_list})
    
    # Manually move items to DLQ (since we don't have a direct API for this)
    # In a real system, this would happen when processing fails
    with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        # First get the items from the ingress list
        response = client.get(f"/vcon/egress?egress_list={ingress_list}&limit={len(uuids)}")
        egress_uuids = response.json()
        
        # Now simulate adding them to DLQ by adding directly to the DLQ
        client.post("/vcon/ingress", json=egress_uuids, params={"ingress_list": dlq_name})
    
    # Test getting items from DLQ
    with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        response = client.get(f"/dlq?ingress_list={ingress_list}")
        assert response.status_code == 200
        dlq_items = response.json()
        assert len(dlq_items) == len(uuids)
        print(f"Retrieved {len(dlq_items)} items from DLQ")
    
    # Test reprocessing items from DLQ
    with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        response = client.post(f"/dlq/reprocess?ingress_list={ingress_list}")
        assert response.status_code == 200
        reprocessed_count = response.json()
        assert reprocessed_count == len(uuids)
        print(f"Reprocessed {reprocessed_count} items from DLQ")
    
    # Verify items are now in ingress list and DLQ is empty
    with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        # Check ingress list
        response = client.get(f"/vcons/count?egress_list={ingress_list}")
        count = response.json()
        assert count == len(uuids)
        
        # Check DLQ is empty
        response = client.get(f"/dlq?ingress_list={ingress_list}")
        dlq_items = response.json()
        assert len(dlq_items) == 0
        print("DLQ is now empty after reprocessing")


@pytest.mark.anyio
def test_index_vcons():
    """Test the index_vcons endpoint"""
    # Create a few vCons to index
    test_vcons = []
    for i in range(3):
        test_vcon = generate_mock_vcon()
        post_vcon(test_vcon)
        test_vcons.append(test_vcon)
    
    # Call the index_vcons endpoint
    with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
        response = client.get("/index_vcons")
        assert response.status_code == 200
        indexed_count = response.json()
        # Note: This may include more vCons than just what we created
        assert indexed_count >= len(test_vcons)
        print(f"Successfully indexed {indexed_count} vCons")


@pytest.mark.anyio
def test_config_api():
    """Test getting and updating configuration"""
    import os
    import tempfile
    import yaml
    
    # Create a temporary config file
    test_config = {
        "test_key": "test_value",
        "chains": {
            "test_chain": {
                "modules": [
                    {"name": "test_module", "config": {"param1": "value1"}}
                ]
            }
        }
    }
    
    with tempfile.NamedTemporaryFile(delete=False, mode='w') as temp_config:
        yaml.dump(test_config, temp_config)
        temp_config_path = temp_config.name
    
    # Set environment variable for config file
    original_config_path = os.environ.get("CONSERVER_CONFIG_FILE")
    os.environ["CONSERVER_CONFIG_FILE"] = temp_config_path
    
    try:
        # Test getting the config
        with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
            response = client.get("/config")
            assert response.status_code == 200
            config = response.json()
            assert config["test_key"] == "test_value"
            assert "chains" in config
            assert "test_chain" in config["chains"]
            print("Successfully retrieved configuration")
            
        # Test updating the config
        updated_config = test_config.copy()
        updated_config["test_key"] = "updated_value"
        updated_config["new_key"] = "new_value"
        
        with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
            response = client.post("/config", json=updated_config)
            assert response.status_code == 204
            print("Successfully updated configuration")
            
        # Verify the update by getting the config again
        with TestClient(api.app, headers={CONSERVER_HEADER_NAME: CONSERVER_API_TOKEN}) as client:
            response = client.get("/config")
            config = response.json()
            assert config["test_key"] == "updated_value"
            assert config["new_key"] == "new_value"
            print("Verified updated configuration")
    
    finally:
        # Clean up
        if original_config_path:
            os.environ["CONSERVER_CONFIG_FILE"] = original_config_path
        else:
            os.environ.pop("CONSERVER_CONFIG_FILE", None)
        
        # Delete the temporary file
        if os.path.exists(temp_config_path):
            os.unlink(temp_config_path)
        
        # Delete the backup file if it exists
        backup_path = f"{temp_config_path}.bak"
        if os.path.exists(backup_path):
            os.unlink(backup_path)
