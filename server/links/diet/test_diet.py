import json
import pytest
import logging
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

from server.links.diet import run, default_options, remove_system_prompts_recursive, _upload_to_s3_and_get_presigned_url

@pytest.fixture
def sample_vcon():
    return {
        "dialog": [
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
    # Set up mock for redis.json().get
    mock_json = MagicMock()
    mock_redis.json.return_value = mock_json
    mock_json.get.return_value = None
    
    result = run("nonexistent-uuid", "diet")
    
    # Assert that redis.json().get was called
    mock_json.get.assert_called_once_with("vcon:nonexistent-uuid")
    assert result == "nonexistent-uuid"

@patch('server.links.diet.redis')
def test_remove_dialog_body(mock_redis, sample_vcon):
    # Test removing dialog bodies
    # Set up mock for redis.json()
    mock_json = MagicMock()
    mock_redis.json.return_value = mock_json
    mock_json.get.return_value = sample_vcon
    
    run("test-vcon-123", "diet", {"remove_dialog_body": True})
    
    # Verify JSON.SET was called with the correct parameters
    mock_json.set.assert_called_once()
    # Get the saved vCon from the call arguments
    args, kwargs = mock_json.set.call_args
    saved_vcon = args[2]  # The vcon is the third argument to json().set()
    
    # Check if dialog bodies were removed
    assert saved_vcon["dialog"][0]["body"] == ""
    assert saved_vcon["dialog"][1]["body"] == ""

@patch('server.links.diet.redis')
@patch('server.links.diet.requests.post')
def test_post_media_to_url(mock_post, mock_redis, sample_vcon):
    # Test posting media to URL
    # Set up mock for redis.json()
    mock_json = MagicMock()
    mock_redis.json.return_value = mock_json
    mock_json.get.return_value = sample_vcon
    
    # Mock the post response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"url": "https://media.example.com/dialog1"}
    mock_post.return_value = mock_response
    
    run("test-vcon-123", "diet", {
        "remove_dialog_body": True,
        "post_media_to_url": "https://upload.example.com"
    })
    
    # Verify JSON.SET was called with the correct parameters
    mock_json.set.assert_called_once()
    # Get the saved vCon from the call arguments
    args, kwargs = mock_json.set.call_args
    saved_vcon = args[2]  # The vcon is the third argument to json().set()
    
    # Check if dialog bodies were replaced with URLs
    assert saved_vcon["dialog"][0]["body"] == "https://media.example.com/dialog1"
    assert saved_vcon["dialog"][0]["body_type"] == "url"
    
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
    # Set up mock for redis.json()
    mock_json = MagicMock()
    mock_redis.json.return_value = mock_json
    mock_json.get.return_value = sample_vcon
    
    # Mock the post response as a failure
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_post.return_value = mock_response
    
    run("test-vcon-123", "diet", {
        "remove_dialog_body": True,
        "post_media_to_url": "https://upload.example.com"
    })
    
    # Verify JSON.SET was called with the correct parameters
    mock_json.set.assert_called_once()
    # Get the saved vCon from the call arguments
    args, kwargs = mock_json.set.call_args
    saved_vcon = args[2]  # The vcon is the third argument to json().set()
    
    # Check if dialog bodies were emptied due to failure
    assert saved_vcon["dialog"][0]["body"] == ""

@patch('server.links.diet.redis')
def test_remove_analysis(mock_redis, sample_vcon):
    # Test removing analysis
    # Set up mock for redis.json()
    mock_json = MagicMock()
    mock_redis.json.return_value = mock_json
    mock_json.get.return_value = sample_vcon
    
    run("test-vcon-123", "diet", {"remove_analysis": True})
    
    # Verify JSON.SET was called with the correct parameters
    mock_json.set.assert_called_once()
    # Get the saved vCon from the call arguments
    args, kwargs = mock_json.set.call_args
    saved_vcon = args[2]  # The vcon is the third argument to json().set()
    
    # Check if analysis was removed
    assert "analysis" not in saved_vcon

@patch('server.links.diet.redis')
def test_remove_attachment_types(mock_redis, sample_vcon):
    # Test removing attachments by type
    # Set up mock for redis.json()
    mock_json = MagicMock()
    mock_redis.json.return_value = mock_json
    mock_json.get.return_value = sample_vcon
    
    run("test-vcon-123", "diet", {"remove_attachment_types": ["image/jpeg", "audio/mp3"]})
    
    # Verify JSON.SET was called with the correct parameters
    mock_json.set.assert_called_once()
    # Get the saved vCon from the call arguments
    args, kwargs = mock_json.set.call_args
    saved_vcon = args[2]  # The vcon is the third argument to json().set()
    
    # Check if attachments were filtered correctly
    assert len(saved_vcon["attachments"]) == 1
    assert saved_vcon["attachments"][0]["id"] == "att2"
    assert saved_vcon["attachments"][0]["mime_type"] == "application/pdf"

@patch('server.links.diet.redis')
def test_remove_system_prompts(mock_redis, sample_vcon):
    # Test removing system_prompt keys
    # Set up mock for redis.json()
    mock_json = MagicMock()
    mock_redis.json.return_value = mock_json
    mock_json.get.return_value = sample_vcon
    
    run("test-vcon-123", "diet", {"remove_system_prompts": True})
    
    # Verify JSON.SET was called with the correct parameters
    mock_json.set.assert_called_once()
    # Get the saved vCon from the call arguments
    args, kwargs = mock_json.set.call_args
    saved_vcon = args[2]  # The vcon is the third argument to json().set()
    
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
    # Set up mock for redis.json()
    mock_json = MagicMock()
    mock_redis.json.return_value = mock_json
    mock_json.get.return_value = sample_vcon
    
    run("test-vcon-123", "diet", {
        "remove_dialog_body": True,
        "remove_analysis": True,
        "remove_attachment_types": ["image/jpeg"],
        "remove_system_prompts": True
    })
    
    # Verify JSON.SET was called with the correct parameters
    mock_json.set.assert_called_once()
    # Get the saved vCon from the call arguments
    args, kwargs = mock_json.set.call_args
    saved_vcon = args[2]  # The vcon is the third argument to json().set()
    
    # Check that all transformations were applied
    assert saved_vcon["dialog"][0]["body"] == ""
    assert saved_vcon["dialog"][1]["body"] == ""
    assert "analysis" not in saved_vcon
    assert len(saved_vcon["attachments"]) == 2
    assert saved_vcon["attachments"][0]["id"] == "att2"
    assert "system_prompt" not in saved_vcon["attachments"][1]["metadata"]


@pytest.fixture
def s3_options():
    return {
        "remove_dialog_body": True,
        "s3_bucket": "test-bucket",
        "s3_path": "dialogs",
        "aws_access_key_id": "test-key-id",
        "aws_secret_access_key": "test-secret-key",
        "aws_region": "us-west-2",
        "presigned_url_expiration": 7200,
    }


@patch('server.links.diet.boto3')
def test_upload_to_s3_and_get_presigned_url(mock_boto3):
    # Test the S3 upload helper function
    mock_s3 = MagicMock()
    mock_boto3.client.return_value = mock_s3
    mock_s3.generate_presigned_url.return_value = "https://test-bucket.s3.amazonaws.com/presigned-url"

    options = {
        "s3_bucket": "test-bucket",
        "s3_path": "dialogs",
        "aws_access_key_id": "test-key-id",
        "aws_secret_access_key": "test-secret-key",
        "aws_region": "us-west-2",
        "presigned_url_expiration": 7200,
    }

    result = _upload_to_s3_and_get_presigned_url(
        "test content",
        "vcon-uuid-123",
        "dialog1",
        options
    )

    # Verify S3 client was created with correct credentials
    mock_boto3.client.assert_called_once_with(
        "s3",
        aws_access_key_id="test-key-id",
        aws_secret_access_key="test-secret-key",
        region_name="us-west-2",
    )

    # Verify put_object was called
    mock_s3.put_object.assert_called_once()
    call_kwargs = mock_s3.put_object.call_args[1]
    assert call_kwargs["Bucket"] == "test-bucket"
    assert "dialogs/vcon-uuid-123/dialog1_" in call_kwargs["Key"]
    assert call_kwargs["ContentType"] == "text/plain"

    # Verify presigned URL was generated with correct expiration
    mock_s3.generate_presigned_url.assert_called_once()
    presign_call = mock_s3.generate_presigned_url.call_args
    assert presign_call[0][0] == "get_object"
    assert presign_call[1]["ExpiresIn"] == 7200

    assert result == "https://test-bucket.s3.amazonaws.com/presigned-url"


@patch('server.links.diet.boto3')
def test_upload_to_s3_default_expiration(mock_boto3):
    # Test that default expiration (3600) is used when not specified
    mock_s3 = MagicMock()
    mock_boto3.client.return_value = mock_s3
    mock_s3.generate_presigned_url.return_value = "https://presigned-url"

    options = {
        "s3_bucket": "test-bucket",
        "aws_access_key_id": "test-key-id",
        "aws_secret_access_key": "test-secret-key",
        "presigned_url_expiration": None,  # Not specified
    }

    _upload_to_s3_and_get_presigned_url("content", "vcon-123", "dialog1", options)

    # Verify default expiration of 3600 seconds was used
    presign_call = mock_s3.generate_presigned_url.call_args
    assert presign_call[1]["ExpiresIn"] == 3600


@patch('server.links.diet.boto3')
def test_upload_to_s3_no_path_prefix(mock_boto3):
    # Test S3 upload without path prefix
    mock_s3 = MagicMock()
    mock_boto3.client.return_value = mock_s3
    mock_s3.generate_presigned_url.return_value = "https://presigned-url"

    options = {
        "s3_bucket": "test-bucket",
        "s3_path": "",  # No path prefix
        "aws_access_key_id": "test-key-id",
        "aws_secret_access_key": "test-secret-key",
    }

    _upload_to_s3_and_get_presigned_url("content", "vcon-123", "dialog1", options)

    # Verify key doesn't have prefix
    call_kwargs = mock_s3.put_object.call_args[1]
    assert call_kwargs["Key"].startswith("vcon-123/dialog1_")
    assert not call_kwargs["Key"].startswith("/")


@patch('server.links.diet.boto3')
def test_upload_to_s3_failure(mock_boto3):
    # Test handling of S3 upload failure
    mock_s3 = MagicMock()
    mock_boto3.client.return_value = mock_s3
    mock_s3.put_object.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
        "PutObject"
    )

    options = {
        "s3_bucket": "test-bucket",
        "aws_access_key_id": "test-key-id",
        "aws_secret_access_key": "test-secret-key",
    }

    result = _upload_to_s3_and_get_presigned_url("content", "vcon-123", "dialog1", options)

    assert result is None


@patch('server.links.diet.redis')
@patch('server.links.diet.boto3')
def test_run_with_s3_storage(mock_boto3, mock_redis, sample_vcon, s3_options):
    # Test the full run function with S3 storage
    mock_json = MagicMock()
    mock_redis.json.return_value = mock_json
    mock_json.get.return_value = sample_vcon

    mock_s3 = MagicMock()
    mock_boto3.client.return_value = mock_s3
    mock_s3.generate_presigned_url.return_value = "https://test-bucket.s3.amazonaws.com/presigned-url"

    run("test-vcon-123", "diet", s3_options)

    # Verify JSON.SET was called
    mock_json.set.assert_called_once()
    args, kwargs = mock_json.set.call_args
    saved_vcon = args[2]

    # Check that dialog bodies were replaced with presigned URLs
    assert saved_vcon["dialog"][0]["body"] == "https://test-bucket.s3.amazonaws.com/presigned-url"
    assert saved_vcon["dialog"][0]["body_type"] == "url"
    assert saved_vcon["dialog"][1]["body"] == "https://test-bucket.s3.amazonaws.com/presigned-url"
    assert saved_vcon["dialog"][1]["body_type"] == "url"

    # Verify S3 was called for each dialog
    assert mock_s3.put_object.call_count == 2


@patch('server.links.diet.redis')
@patch('server.links.diet.boto3')
def test_run_with_s3_storage_failure_removes_body(mock_boto3, mock_redis, sample_vcon, s3_options):
    # Test that body is removed when S3 upload fails
    mock_json = MagicMock()
    mock_redis.json.return_value = mock_json
    mock_json.get.return_value = sample_vcon

    mock_s3 = MagicMock()
    mock_boto3.client.return_value = mock_s3
    mock_s3.put_object.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
        "PutObject"
    )

    run("test-vcon-123", "diet", s3_options)

    # Verify JSON.SET was called
    mock_json.set.assert_called_once()
    args, kwargs = mock_json.set.call_args
    saved_vcon = args[2]

    # Check that dialog bodies were removed due to failure
    assert saved_vcon["dialog"][0]["body"] == ""
    assert saved_vcon["dialog"][1]["body"] == ""


@patch('server.links.diet.redis')
@patch('server.links.diet.boto3')
def test_s3_takes_precedence_over_post_url(mock_boto3, mock_redis, sample_vcon):
    # Test that S3 storage takes precedence over post_media_to_url
    mock_json = MagicMock()
    mock_redis.json.return_value = mock_json
    mock_json.get.return_value = sample_vcon

    mock_s3 = MagicMock()
    mock_boto3.client.return_value = mock_s3
    mock_s3.generate_presigned_url.return_value = "https://s3-presigned-url"

    options = {
        "remove_dialog_body": True,
        "s3_bucket": "test-bucket",
        "aws_access_key_id": "test-key-id",
        "aws_secret_access_key": "test-secret-key",
        "post_media_to_url": "https://should-not-be-called.com",  # This should be ignored
    }

    with patch('server.links.diet.requests.post') as mock_post:
        run("test-vcon-123", "diet", options)
        # post_media_to_url should not be called when S3 is configured
        mock_post.assert_not_called()

    # Verify S3 was used instead
    assert mock_s3.put_object.call_count == 2


@patch('server.links.diet.redis')
def test_options_logging_redacts_aws_secret_access_key(mock_redis, sample_vcon, caplog):
    # Ensure secrets are not written to logs
    mock_json = MagicMock()
    mock_redis.json.return_value = mock_json
    mock_json.get.return_value = sample_vcon

    secret = "test-secret-key"
    caplog.set_level(logging.INFO)

    run("test-vcon-123", "diet", {
        "remove_dialog_body": False,
        "aws_secret_access_key": secret,
    })

    assert secret not in caplog.text
    assert "diet::aws_secret_access_key: [REDACTED]" in caplog.text