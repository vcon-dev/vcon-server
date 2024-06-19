import pytest
from unittest.mock import patch
import os
import json
# import sys
from . import run
import redis_mgr
import requests
import requests_mock


@pytest.fixture(scope="function")
def vcon_input(fixture_name):
    file_path = os.path.join(os.path.dirname(__file__), f'../test_dataset/{fixture_name}.json')
    with open(file_path, 'r') as f:
        return json.load(f)


@pytest.mark.parametrize("fixture_name", ["vcon_with_summary"])
def test_run(requests_mock, vcon_input):
    url = 'https://api.slack.com/methods/chat.postMessage'
    vcon = vcon_input
    requests_mock.post(url, json={"success": True}, status_code=200)
    result = run(vcon["uuid"], 'post_analysis_to_slack')
    assert result == vcon["uuid"]


def test_run_vcon_not_found():
    # There is no vcon at this key
    result = run('bad_key', 'tag')
    assert result == 'bad_key'

