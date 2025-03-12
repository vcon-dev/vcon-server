import json
import pytest
from unittest.mock import patch, MagicMock

from server.links.diet import run, default_options, remove_system_prompts_recursive

@pytest.fixture
def sample_vcon():
    return {
        "dialogs": [
            {
                "id": "dialog1",
                "body": "This is dialog content that should be removed",
                "body_type": "text/plain"
            },
            {
                "id": "dialog2",
                "body": "Another dialog with content"
            }
        ],
        "analysis": {
            "sentiment": "positive",
            "entities": ["test", "example"],
            "system_prompt": "You are a helpful assistant"
        },
        "attachments": [
            {
                "id": "att1",
                "mime_type": "image/jpeg",
                "data": "base64data..."
            },
            {
                "id": "att2", 
                "mime_type": "application/pdf",
                "data": "pdf data..."
            },
            {
                "id": "att3",
                "mime_type": "audio/mp3",
                "metadata": {
                    "system_prompt": "Hidden instruction"
                }
            }
        ]
    }

@patch('server.links.diet.redis')
def test_nonexistent_vcon(mock_redis):
    # Test handling of nonexistent vCon
    mock_redis.get.return_value = None
    
    result = run("nonexistent-uuid", "diet")
    
    mock_redis.get.assert_called_once_with("vcon:nonexistent-uuid")
    assert result == "nonexistent-uuid"

@patch('server.links.diet.redis')
def test_remove_dialog_body(mock_redis, sample_vcon):
    # Test removing dialog bodies
    mock_redis.get.return_value = json.dumps(sample_vcon)
    
    run("test-vcon-123", "diet", {"remove_dialog_body": True})
    
    # Get the saved vCon
    args, kwargs = mock_redis.set.call_args
    saved_vcon = json.loads(args[1])
    
    # Check if dialog bodies were removed
    assert saved_vcon["dialogs"][0]["body"] == ""
    assert saved_vcon["dialogs"][1]["body"] == ""

@patch('server.links.diet.redis')
@patch('server.links.diet.requests.post')
def test_post_media_to_url(mock_post, mock_redis, sample_vcon):
    # Test posting media to URL
    mock_redis.get.return_value = json.dumps(sample_vcon)
    
    # Mock the post response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"url": "https://media.example.com/dialog1"}
    mock_post.return_value = mock_response
    
    run("test-vcon-123", "diet", {
        "remove_dialog_body": True,
        "post_media_to_url": "https://upload.example.com"
    })
    
    # Get the saved vCon
    args, kwargs = mock_redis.set.call_args
    saved_vcon = json.loads(args[1])
    
    # Check if dialog bodies were replaced with URLs
    assert saved_vcon["dialogs"][0]["body"] == "https://media.example.com/dialog1"
    assert saved_vcon["dialogs"][0]["body_type"] == "url"
    
    # Verify both dialogs were posted. Use call_args_list to check all calls.
    assert len(mock_post.call_args_list) == 2
    
    # Check first call (dialog1)
    first_call = mock_post.call_args_list[0]
    assert first_call[0][0] == "https://upload.example.com"
    assert first_call[1]["json"]["content"] == "This is dialog content that should be removed"
    assert first_call[1]["json"]["dialog_id"] == "dialog1"
    assert first_call[1]["json"]["vcon_uuid"] == "test-vcon-123"
    
    # Check second call (dialog2)
    second_call = mock_post.call_args_list[1]
    assert second_call[0][0] == "https://upload.example.com"
    assert second_call[1]["json"]["content"] == "Another dialog with content"
    assert second_call[1]["json"]["dialog_id"] == "dialog2"
    assert second_call[1]["json"]["vcon_uuid"] == "test-vcon-123"

@patch('server.links.diet.redis')
@patch('server.links.diet.requests.post')
def test_post_media_failure(mock_post, mock_redis, sample_vcon):
    # Test handling failed media post
    mock_redis.get.return_value = json.dumps(sample_vcon)
    
    # Mock the post response as a failure
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_post.return_value = mock_response
    
    run("test-vcon-123", "diet", {
        "remove_dialog_body": True,
        "post_media_to_url": "https://upload.example.com"
    })
    
    # Get the saved vCon
    args, kwargs = mock_redis.set.call_args
    saved_vcon = json.loads(args[1])
    
    # Check if dialog bodies were emptied due to failure
    assert saved_vcon["dialogs"][0]["body"] == ""

@patch('server.links.diet.redis')
def test_remove_analysis(mock_redis, sample_vcon):
    # Test removing analysis
    mock_redis.get.return_value = json.dumps(sample_vcon)
    
    run("test-vcon-123", "diet", {"remove_analysis": True})
    
    # Get the saved vCon
    args, kwargs = mock_redis.set.call_args
    saved_vcon = json.loads(args[1])
    
    # Check if analysis was removed
    assert "analysis" not in saved_vcon

@patch('server.links.diet.redis')
def test_remove_attachment_types(mock_redis, sample_vcon):
    # Test removing attachments by type
    mock_redis.get.return_value = json.dumps(sample_vcon)
    
    run("test-vcon-123", "diet", {"remove_attachment_types": ["image/jpeg", "audio/mp3"]})
    
    # Get the saved vCon
    args, kwargs = mock_redis.set.call_args
    saved_vcon = json.loads(args[1])
    
    # Check if attachments were filtered correctly
    assert len(saved_vcon["attachments"]) == 1
    assert saved_vcon["attachments"][0]["id"] == "att2"
    assert saved_vcon["attachments"][0]["mime_type"] == "application/pdf"

@patch('server.links.diet.redis')
def test_remove_system_prompts(mock_redis, sample_vcon):
    # Test removing system_prompt keys
    mock_redis.get.return_value = json.dumps(sample_vcon)
    
    run("test-vcon-123", "diet", {"remove_system_prompts": True})
    
    # Get the saved vCon
    args, kwargs = mock_redis.set.call_args
    saved_vcon = json.loads(args[1])
    
    # Check if system_prompt was removed from analysis
    assert "system_prompt" not in saved_vcon["analysis"]
    
    # Check if system_prompt was removed from attachment metadata
    assert "system_prompt" not in saved_vcon["attachments"][2]["metadata"]

def test_remove_system_prompts_recursive_function():
    # Test the recursive function directly
    test_obj = {
        "name": "test",
        "system_prompt": "This should be removed",
        "nested": {
            "system_prompt": "This should also be removed",
            "data": "Keep this"
        },
        "list": [
            {"system_prompt": "Remove from list"},
            {"keep": "this"}
        ]
    }
    
    remove_system_prompts_recursive(test_obj)
    
    # Check that all system_prompt keys were removed
    assert "system_prompt" not in test_obj
    assert "system_prompt" not in test_obj["nested"]
    assert "system_prompt" not in test_obj["list"][0]
    
    # Check that other data remains
    assert test_obj["name"] == "test"
    assert test_obj["nested"]["data"] == "Keep this"
    assert test_obj["list"][1]["keep"] == "this"

@patch('server.links.diet.redis')
def test_combined_options(mock_redis, sample_vcon):
    # Test all options together
    mock_redis.get.return_value = json.dumps(sample_vcon)
    
    run("test-vcon-123", "diet", {
        "remove_dialog_body": True,
        "remove_analysis": True,
        "remove_attachment_types": ["image/jpeg"],
        "remove_system_prompts": True
    })
    
    # Get the saved vCon
    args, kwargs = mock_redis.set.call_args
    saved_vcon = json.loads(args[1])
    
    # Check that all transformations were applied
    assert saved_vcon["dialogs"][0]["body"] == ""
    assert saved_vcon["dialogs"][1]["body"] == ""
    assert "analysis" not in saved_vcon
    assert len(saved_vcon["attachments"]) == 2
    assert saved_vcon["attachments"][0]["id"] == "att2"
    assert "system_prompt" not in saved_vcon["attachments"][1]["metadata"] 