import pytest
from unittest.mock import patch
import os
import json
# import sys
from . import run
import redis_mgr
from tests.vcon_fixture import generate_mock_vcon

test_vcons = [generate_mock_vcon() for i in range(10)]

# @pytest.fixture(scope="function")
# def vcon_input(fixture_name):
#     file_path = os.path.join(os.path.dirname(__file__), f'../test_dataset/{fixture_name}.json')
#     with open(file_path, 'r') as f:
#         return json.load(f)


# @pytest.mark.parametrize("fixture_name", ["vcon_fixture"])
def test_run_summary():
    for vcon in test_vcons:
        opts = {
            "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
            "prompt": "Summarize this transcript in a few sentences, identify the purpose of the call and then indicate if there is a clear frustration expressed by the customer and if this was a conversation between two people or if someone left a message, and if agent was helpful?",
            "system_prompt": "You are helpful assistant and respond in json in the format: {'summary': 'Sample summary', 'purpose':'sample purpose','customer_frustration': true, 'conversation_type': 'Voicemail', 'agent_helpful': true}. Conversation type should only be from this list: 'Voicemail', 'Engaged', 'Dropped', 'IVR'.",
            "analysis_type": "summary",
            "model": 'gpt-4o',
            "sampling_rate": 1,
            "temperature": 0,
            "source": {
                "analysis_type": "transcript",
                "text_location": "body.transcript",
            },
        }
        redis_mgr.set_key(f"vcon:{vcon["uuid"]}", vcon)
        result = run(vcon["uuid"], 'analyze', opts)
        assert result == vcon["uuid"]


def test_run_diarization():
    for vcon in test_vcons:
        opts = {
            "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
            "prompt": "Translate the transcript into English if it is not already. Then diarize the conversation and also identify the Agent and the Customer and show the names along with it like Agent(Agent Name) and output in markdown and label each speaker in bold. If it's only one speaker, return the transcript. If you can't diarize the transcript, return an empty string.",
            "analysis_type": "summary",
            "model": 'gpt-3.5-turbo-16k',
            "sampling_rate": 1,
            "temperature": 0,
            "source": {
                "analysis_type": "transcript",
                "text_location": "body.transcript",
            },
        }
        redis_mgr.set_key(f"vcon:{vcon["uuid"]}", vcon)
        result = run(vcon["uuid"], 'analyze', opts)
        assert result == vcon["uuid"]


def test_run_agent_note():
    for vcon in test_vcons:
        opts = {
            "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
            "prompt": "You are a car dealership call center agent. You will take a transcript from a recorded call and pull out only the most important information that a manager could use to help make a sale. Use shorthand to condense the notes as much as possible. You do not always need to add information for every key in the response. Things that are common to all of the agent's calls can be omitted, such as phone number confirmation, dealership location, or appointments. It's okay to return an empty string for a key's value. You will return the data in this JSON format:{'interests': '''information about the vehicle or vehicles the customer is interested in''','concerns': '''things the customer is concerned about''','requests': '''things the customer has requested''','dealer_promises': '''things the agent has promised to follow up on with the customer''','risks': '''things that could cause the dealer to lose the sale''','highlights': '''any extra information that could help the dealer close the sale'''} Here is an example response:{'interests': 'lowest financing rates for pre-owned vehicles, 2023 Pathfinder','concerns': 'condition of the vehicle, possibility of the car being sold before they can visit','requests': 'securing the vehicle with a deposit or shipping options','dealer_promises': '','risks': '','highlights': 'Customer is willing to fly out to make the purchase'}",
            "analysis_type": "summary",
            "model": 'gpt-3.5-turbo-16k',
            "sampling_rate": 1,
            "temperature": 0,
            "source": {
                "analysis_type": "transcript",
                "text_location": "body.transcript",
            },
        }
        redis_mgr.set_key(f"vcon:{vcon["uuid"]}", vcon)
        result = run(vcon["uuid"], 'analyze', opts)
        assert result == vcon["uuid"]

def test_run_vcon_not_found():
    # There is no vcon at this key
    result = run('bad_key', 'tag')
    assert result == 'bad_key'

