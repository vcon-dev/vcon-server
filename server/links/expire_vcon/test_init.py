import pytest
from unittest.mock import patch
import os
import json
# import sys
from . import run
import redis_mgr


@pytest.fixture(scope="function")
def vcon_input(fixture_name):
    file_path = os.path.join(os.path.dirname(__file__), f'../test_dataset/{fixture_name}.json')
    with open(file_path, 'r') as f:
        return json.load(f)


@pytest.mark.parametrize("fixture_name", ["vcon_fixture"])
def test_run(vcon_input):
    vcon = vcon_input
    result = run(vcon["uuid"], 'expire_vcon')
    assert result == vcon["uuid"]


def test_run_vcon_not_found():
    # There is no vcon at this key
    result = run('bad_key', 'tag')
    assert result == 'bad_key'

