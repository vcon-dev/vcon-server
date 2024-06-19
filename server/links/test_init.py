import pytest
from unittest.mock import patch
import os
import json
# import sys
# from links import run
import redis_mgr 
import importlib

def module_has_function(module_name, function_name):
    # Import the module
    module = importlib.import_module(module_name)
    # Check if the function exists in the module
    if hasattr(module, function_name):
        return True
    else:
        return False

# #load vcons from redis
# def load_vcons():
#     vcons = []
#     for key in redis_mgr.keys("vcon:*"):
#         vcon = redis_mgr.get_key(key)
#         vcons.append(vcon)
#     return vcons


def import_links():
    links = []
    links_path = os.path.dirname(__file__)
    for root, dirs, files in os.walk(links_path):
        for dir in dirs:
            module_name = dir
            try:
                if module_has_function(module_name, "run"):
                    link_module = importlib.import_module(module_name)
                    links.append(link_module)
                    print("Finished importing: ", module_name)
                else:
                    print("Module does not have run function")
            except Exception as e:
                print(e)
                continue
    return links


def test_links():
    links_path = os.path.dirname(__file__)
    for root, dirs, files in os.walk(links_path):
        for file in files:
            if file.startswith('test_') and file.endswith('.py') and {os.path.join(root, __file__)} != {os.path.join(root, file)}:
                # os.system(f'pytest {os.path.join(root, file)}')
                continue

@pytest.fixture(scope="function")
def vcon_input(fixture_name):
    file_path = os.path.join(os.path.dirname(__file__), f'test_dataset/{fixture_name}.json')
    with open(file_path, 'r') as f:
        return json.load(f)


@pytest.mark.parametrize("fixture_name", ["vcon_fixture"])
def test_run(vcon_input):
    mock_vcon_data = vcon_input
    links = import_links()
    for link in links:
        if link.__name__ == 'script':
            try:
                redis_mgr.set_key(f"vcon:{mock_vcon_data["uuid"]}", mock_vcon_data)
                result = link.run(mock_vcon_data["uuid"], link.__name__)
                # assert result == mock_vcon_data["uuid"]
            except Exception as e:
                print(e)
                assert False
                continue
    
#     # self.assertEqual(result, mock_vcon_data["uuid"])
#     # result.add_tag.assert_any_call('strolid', 'iron')
#     # result.add_tag.assert_any_call('strolid', 'maiden')
#     # mock_vcon_redis.return_value.store_vcon.assert_called_once_with(mock_vcon)


# def test_run_vcon_not_found():
#     # There is no vcon at this key
#     result = run('bad_key', 'tag')
#     assert result == 'bad_key'


# @pytest.mark.parametrize("fixture_name", ["bad_vcon"])
# def test_run_bad_vcon(vcon_input):
#     mock_vcon_data = vcon_input
#     links = import_links()
#     for link in links:
#         with pytest.raises(Exception):
#             redis_mgr.set_key(f"vcon:{mock_vcon_data["uuid"]}", mock_vcon_data)
#             link.run(mock_vcon_data["uuid"], link.__name__)
