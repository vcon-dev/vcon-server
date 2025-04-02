import pytest
from unittest.mock import patch, MagicMock
from links.tag_router import run
from vcon import Vcon

@pytest.fixture
def mock_vcon_redis():
    """Mock the VconRedis class"""
    with patch('links.tag_router.VconRedis') as mock:
        yield mock

@pytest.fixture
def mock_redis():
    """Mock the redis module"""
    with patch('links.tag_router.redis') as mock:
        yield mock

@pytest.fixture
def sample_vcon_with_tags():
    """Create a sample vCon with tag attachments"""
    return Vcon({
        "uuid": "test-uuid",
        "vcon": "0.0.1",
        "meta": {
            "arc_display_name": "Test vCon with Tags"
        },
        "parties": [],
        "dialog": [],
        "analysis": [],
        "attachments": [
            {
                "type": "tags",
                "body": [
                    "important:important",
                    "followup:followup"
                ],
                "encoding": "json"
            },
            {
                "type": "note",  # Not a tag
                "body": "This is just a note"
            }
        ],
        "redacted": {}
    })

@pytest.fixture
def sample_vcon_with_tags_plural_format():
    """Create a sample vCon with tags in plural format with body array"""
    return Vcon({
        "uuid": "test-uuid-plural-tags",
        "vcon": "0.0.1",
        "meta": {
            "arc_display_name": "Test vCon with Plural Tags Format"
        },
        "parties": [],
        "dialog": [],
        "analysis": [],
        "attachments": [
            {
                "type": "tags",
                "body": [
                    "cdr_id:17430873690a85865c466bad87e6fd8919f782d8b0",
                    "orig_callid:20250327145603024756-62ea191bd80afaf8563dd5e362a10974",
                    "duration:353",
                    "call_type:0",
                    "mapped_call_type:Outbound"
                ],
                "encoding": "json"
            },
            {
                "type": "note",  # Not a tag
                "body": "This is just a note"
            }
        ],
        "redacted": {}
    })

@pytest.fixture
def sample_vcon_with_tags_dict_body():
    """Create a sample vCon with tags that have a dictionary body"""
    return Vcon({
        "uuid": "test-uuid-dict-tags",
        "vcon": "0.0.1",
        "meta": {
            "arc_display_name": "Test vCon with Dict Tags"
        },
        "parties": [],
        "dialog": [],
        "analysis": [],
        "attachments": [
            {
                "type": "tags",
                "body": {
                    "cdr_id": "17430873690a85865c466bad87e6fd8919f782d8b0",
                    "call_type": "0",
                    "mapped_call_type": "Outbound"
                },
                "encoding": "json"
            }
        ],
        "redacted": {}
    })

@pytest.fixture
def sample_vcon_without_tags():
    """Create a sample vCon without tag attachments"""
    return Vcon({
        "uuid": "test-uuid-no-tags",
        "vcon": "0.0.1",
        "meta": {
            "arc_display_name": "Test vCon without Tags"
        },
        "parties": [],
        "dialog": [],
        "analysis": [],
        "attachments": [
            {
                "type": "note",
                "body": "This is just a note"
            }
        ],
        "redacted": {}
    })

@pytest.fixture
def sample_vcon_with_name_only_tags():
    """Create a sample vCon with tags that have name but no value"""
    return Vcon({
        "uuid": "test-uuid-name-tags",
        "vcon": "0.0.1",
        "meta": {
            "arc_display_name": "Test vCon with Name-only Tags"
        },
        "parties": [],
        "dialog": [],
        "analysis": [],
        "attachments": [
            {
                "type": "tags",
                "body": [
                    "urgent:",
                    "escalate:"
                ],
                "encoding": "json"
            }
        ],
        "redacted": {}
    })

@pytest.fixture
def mock_redis_with_vcon(mock_vcon_redis, mock_redis, sample_vcon_with_tags):
    """Set up mock Redis with sample vCon with tags"""
    mock_instance = MagicMock()
    mock_instance.get_vcon.return_value = sample_vcon_with_tags
    mock_vcon_redis.return_value = mock_instance
    return mock_vcon_redis, mock_redis

@pytest.fixture
def mock_redis_with_plural_tags(mock_vcon_redis, mock_redis, sample_vcon_with_tags_plural_format):
    """Set up mock Redis with sample vCon with plural tags format"""
    mock_instance = MagicMock()
    mock_instance.get_vcon.return_value = sample_vcon_with_tags_plural_format
    mock_vcon_redis.return_value = mock_instance
    return mock_vcon_redis, mock_redis

@pytest.fixture
def mock_redis_with_dict_tags(mock_vcon_redis, mock_redis, sample_vcon_with_tags_dict_body):
    """Set up mock Redis with sample vCon with dict tags"""
    mock_instance = MagicMock()
    mock_instance.get_vcon.return_value = sample_vcon_with_tags_dict_body
    mock_vcon_redis.return_value = mock_instance
    return mock_vcon_redis, mock_redis

@pytest.fixture
def mock_redis_with_no_tag_vcon(mock_vcon_redis, mock_redis, sample_vcon_without_tags):
    """Set up mock Redis with sample vCon without tags"""
    mock_instance = MagicMock()
    mock_instance.get_vcon.return_value = sample_vcon_without_tags
    mock_vcon_redis.return_value = mock_instance
    return mock_vcon_redis, mock_redis

@pytest.fixture
def mock_redis_with_name_tag_vcon(mock_vcon_redis, mock_redis, sample_vcon_with_name_only_tags):
    """Set up mock Redis with sample vCon with name-only tags"""
    mock_instance = MagicMock()
    mock_instance.get_vcon.return_value = sample_vcon_with_name_only_tags
    mock_vcon_redis.return_value = mock_instance
    return mock_vcon_redis, mock_redis

def test_tag_router_with_matching_tags(mock_redis_with_vcon):
    """Test routing vCon with matching tags"""
    _, mock_redis = mock_redis_with_vcon
    
    opts = {
        "tag_routes": {
            "important": "important_list",
            "followup": "followup_list"
        },
        "forward_original": True
    }
    
    result = run("test-uuid", "test-link", opts)
    
    # Check that it was routed to both lists
    mock_redis.rpush.assert_any_call("important_list", "test-uuid")
    mock_redis.rpush.assert_any_call("followup_list", "test-uuid")
    assert mock_redis.rpush.call_count == 2
    
    # Check that it was forwarded
    assert result == "test-uuid"

def test_tag_router_with_plural_tags_format(mock_redis_with_plural_tags):
    """Test routing vCon with tags in the plural format (body array)"""
    _, mock_redis = mock_redis_with_plural_tags
    
    opts = {
        "tag_routes": {
            "cdr_id": "cdr_list",
            "call_type": "call_type_list",
            "mapped_call_type": "mapped_call_list"
        },
        "forward_original": True
    }
    
    result = run("test-uuid-plural-tags", "test-link", opts)
    
    # Check that it was routed to the correct lists
    mock_redis.rpush.assert_any_call("cdr_list", "test-uuid-plural-tags")
    mock_redis.rpush.assert_any_call("call_type_list", "test-uuid-plural-tags")
    mock_redis.rpush.assert_any_call("mapped_call_list", "test-uuid-plural-tags")
    assert mock_redis.rpush.call_count == 3
    
    # Check that it was forwarded
    assert result == "test-uuid-plural-tags"

def test_tag_router_with_dict_body_tags(mock_redis_with_dict_tags):
    """Test routing vCon with tags that have a dictionary body"""
    _, mock_redis = mock_redis_with_dict_tags
    
    opts = {
        "tag_routes": {
            "cdr_id": "cdr_list",
            "call_type": "call_type_list",
            "mapped_call_type": "mapped_call_list"
        },
        "forward_original": True
    }
    
    result = run("test-uuid-dict-tags", "test-link", opts)
    
    # Check that it was routed to the correct lists
    mock_redis.rpush.assert_any_call("cdr_list", "test-uuid-dict-tags")
    mock_redis.rpush.assert_any_call("call_type_list", "test-uuid-dict-tags")
    mock_redis.rpush.assert_any_call("mapped_call_list", "test-uuid-dict-tags")
    assert mock_redis.rpush.call_count == 3
    
    # Check that it was forwarded
    assert result == "test-uuid-dict-tags"

def test_tag_router_with_partial_matching_tags(mock_redis_with_vcon):
    """Test routing vCon with partially matching tags"""
    _, mock_redis = mock_redis_with_vcon
    
    opts = {
        "tag_routes": {
            "important": "important_list",
            "urgent": "urgent_list"  # Not in our vCon
        },
        "forward_original": True
    }
    
    result = run("test-uuid", "test-link", opts)
    
    # Check that it was routed only to the matching list
    mock_redis.rpush.assert_called_once_with("important_list", "test-uuid")
    
    # Check that it was forwarded
    assert result == "test-uuid"

def test_tag_router_with_no_matching_tags(mock_redis_with_vcon):
    """Test routing vCon with no matching tags"""
    _, mock_redis = mock_redis_with_vcon
    
    opts = {
        "tag_routes": {
            "urgent": "urgent_list",
            "escalate": "escalate_list"
        },
        "forward_original": True
    }
    
    result = run("test-uuid", "test-link", opts)
    
    # Check that no routing occurred
    mock_redis.rpush.assert_not_called()
    
    # Check that it was still forwarded due to forward_original=True
    assert result == "test-uuid"

def test_tag_router_no_forward(mock_redis_with_vcon):
    """Test routing with forward_original=False"""
    _, mock_redis = mock_redis_with_vcon
    
    opts = {
        "tag_routes": {
            "important": "important_list"
        },
        "forward_original": False
    }
    
    result = run("test-uuid", "test-link", opts)
    
    # Check that it was routed
    mock_redis.rpush.assert_called_once_with("important_list", "test-uuid")
    
    # Check that it was not forwarded
    assert result is None

def test_tag_router_missing_vcon(mock_vcon_redis, mock_redis):
    """Test handling of missing vCon"""
    # Set up mock to return None for get_vcon
    mock_instance = MagicMock()
    mock_instance.get_vcon.return_value = None
    mock_vcon_redis.return_value = mock_instance
    
    opts = {
        "tag_routes": {
            "important": "important_list"
        }
    }
    
    result = run("test-uuid", "test-link", opts)
    
    # Check that no routing occurred
    mock_redis.rpush.assert_not_called()
    
    # Check that None was returned
    assert result is None

def test_tag_router_no_tags_in_vcon(mock_redis_with_no_tag_vcon):
    """Test routing vCon without any tag attachments"""
    _, mock_redis = mock_redis_with_no_tag_vcon
    
    opts = {
        "tag_routes": {
            "important": "important_list",
            "followup": "followup_list"
        },
        "forward_original": True
    }
    
    result = run("test-uuid-no-tags", "test-link", opts)
    
    # Check that no routing occurred
    mock_redis.rpush.assert_not_called()
    
    # Check that it was forwarded
    assert result == "test-uuid-no-tags"

def test_tag_router_no_tags_in_vcon_no_forward(mock_redis_with_no_tag_vcon):
    """Test routing vCon without tags and forward_original=False"""
    _, mock_redis = mock_redis_with_no_tag_vcon
    
    opts = {
        "tag_routes": {
            "important": "important_list"
        },
        "forward_original": False
    }
    
    result = run("test-uuid-no-tags", "test-link", opts)
    
    # Check that no routing occurred
    mock_redis.rpush.assert_not_called()
    
    # Check that it was not forwarded
    assert result is None

def test_tag_router_no_routes_configured(mock_redis_with_vcon):
    """Test behavior when no tag routes are configured"""
    _, mock_redis = mock_redis_with_vcon
    
    opts = {
        "tag_routes": {},
        "forward_original": True
    }
    
    result = run("test-uuid", "test-link", opts)
    
    # Check that no routing occurred
    mock_redis.rpush.assert_not_called()
    
    # Check that it was forwarded
    assert result == "test-uuid"

def test_tag_router_with_name_only_tags(mock_redis_with_name_tag_vcon):
    """Test routing vCon with tags that have only name field"""
    _, mock_redis = mock_redis_with_name_tag_vcon
    
    opts = {
        "tag_routes": {
            "urgent": "urgent_list",
            "escalate": "escalate_list"
        },
        "forward_original": True
    }
    
    result = run("test-uuid-name-tags", "test-link", opts)
    
    # Check that it was routed to both lists
    mock_redis.rpush.assert_any_call("urgent_list", "test-uuid-name-tags")
    mock_redis.rpush.assert_any_call("escalate_list", "test-uuid-name-tags")
    assert mock_redis.rpush.call_count == 2
    
    # Check that it was forwarded
    assert result == "test-uuid-name-tags"

def test_tag_router_with_default_options(mock_redis_with_vcon):
    """Test link with default options"""
    _, mock_redis = mock_redis_with_vcon
    
    result = run("test-uuid", "test-link")
    
    # Check that no routing occurred (default tag_routes is empty)
    mock_redis.rpush.assert_not_called()
    
    # Check that it was forwarded (default forward_original is True)
    assert result == "test-uuid"
