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
def sample_vcon_with_tag1_and_tag2():
    """Create a sample vCon with both tag1 and tag2 (for AND-rule tests)."""
    return Vcon({
        "uuid": "test-uuid-both-tags",
        "vcon": "0.0.1",
        "meta": {"arc_display_name": "Test vCon with tag1 and tag2"},
        "parties": [],
        "dialog": [],
        "analysis": [],
        "attachments": [
            {
                "type": "tags",
                "body": ["tag1:value1", "tag2:value2"],
                "encoding": "json"
            }
        ],
        "redacted": {}
    })

@pytest.fixture
def sample_vcon_with_tag1_only():
    """Create a sample vCon with only tag1 (missing tag2 for AND-rule tests)."""
    return Vcon({
        "uuid": "test-uuid-tag1-only",
        "vcon": "0.0.1",
        "meta": {"arc_display_name": "Test vCon with tag1 only"},
        "parties": [],
        "dialog": [],
        "analysis": [],
        "attachments": [
            {
                "type": "tags",
                "body": ["tag1:value1"],
                "encoding": "json"
            }
        ],
        "redacted": {}
    })

@pytest.fixture
def sample_vcon_with_tag1_and_tag2_different_value():
    """vCon with tag1:value1 and tag2:other (tag2 value differs from value2, for exact-match tests)."""
    return Vcon({
        "uuid": "test-uuid-tag2-other",
        "vcon": "0.0.1",
        "meta": {"arc_display_name": "Test vCon tag1 and tag2:other"},
        "parties": [],
        "dialog": [],
        "analysis": [],
        "attachments": [
            {
                "type": "tags",
                "body": ["tag1:value1", "tag2:other"],
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

@pytest.fixture
def mock_redis_with_both_tags_vcon(mock_vcon_redis, mock_redis, sample_vcon_with_tag1_and_tag2):
    """Set up mock Redis with sample vCon that has both tag1 and tag2"""
    mock_instance = MagicMock()
    mock_instance.get_vcon.return_value = sample_vcon_with_tag1_and_tag2
    mock_vcon_redis.return_value = mock_instance
    return mock_vcon_redis, mock_redis

@pytest.fixture
def mock_redis_with_tag1_only_vcon(mock_vcon_redis, mock_redis, sample_vcon_with_tag1_only):
    """Set up mock Redis with sample vCon that has only tag1"""
    mock_instance = MagicMock()
    mock_instance.get_vcon.return_value = sample_vcon_with_tag1_only
    mock_vcon_redis.return_value = mock_instance
    return mock_vcon_redis, mock_redis

@pytest.fixture
def mock_redis_with_tag2_other_vcon(mock_vcon_redis, mock_redis, sample_vcon_with_tag1_and_tag2_different_value):
    """Set up mock Redis with sample vCon that has tag1:value1 and tag2:other"""
    mock_instance = MagicMock()
    mock_instance.get_vcon.return_value = sample_vcon_with_tag1_and_tag2_different_value
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


# --- tag_route_rules (AND logic) tests ---

def test_tag_route_rules_routes_when_all_tags_present(mock_redis_with_both_tags_vcon):
    """Test that tag_route_rules routes when vcon has ALL required tags."""
    _, mock_redis = mock_redis_with_both_tags_vcon

    opts = {
        "tag_route_rules": [
            {"tags": ["tag1", "tag2"], "target_list": "and_rule_list"}
        ],
        "tag_routes": {},
        "forward_original": True,
    }

    result = run("test-uuid-both-tags", "test-link", opts)

    mock_redis.rpush.assert_called_once_with("and_rule_list", "test-uuid-both-tags")
    assert result == "test-uuid-both-tags"


def test_tag_route_rules_does_not_route_when_one_tag_missing(mock_redis_with_tag1_only_vcon):
    """Test that tag_route_rules does not route when vcon is missing a required tag."""
    _, mock_redis = mock_redis_with_tag1_only_vcon

    opts = {
        "tag_route_rules": [
            {"tags": ["tag1", "tag2"], "target_list": "and_rule_list"}
        ],
        "tag_routes": {},
        "forward_original": True,
    }

    result = run("test-uuid-tag1-only", "test-link", opts)

    mock_redis.rpush.assert_not_called()
    assert result == "test-uuid-tag1-only"


def test_tag_route_rules_empty_does_nothing(mock_redis_with_both_tags_vcon):
    """Test that empty tag_route_rules does not route (backward compatibility)."""
    _, mock_redis = mock_redis_with_both_tags_vcon

    opts = {
        "tag_route_rules": [],
        "tag_routes": {},
        "forward_original": True,
    }

    result = run("test-uuid-both-tags", "test-link", opts)

    mock_redis.rpush.assert_not_called()
    assert result == "test-uuid-both-tags"


def test_tag_route_rules_and_tag_routes_both_work(mock_redis_with_both_tags_vcon):
    """Test that tag_route_rules (AND) and tag_routes (OR) can both apply."""
    _, mock_redis = mock_redis_with_both_tags_vcon

    opts = {
        "tag_route_rules": [
            {"tags": ["tag1", "tag2"], "target_list": "and_list"}
        ],
        "tag_routes": {"tag1": "or_list"},
        "forward_original": True,
    }

    result = run("test-uuid-both-tags", "test-link", opts)

    mock_redis.rpush.assert_any_call("and_list", "test-uuid-both-tags")
    mock_redis.rpush.assert_any_call("or_list", "test-uuid-both-tags")
    assert mock_redis.rpush.call_count == 2
    assert result == "test-uuid-both-tags"


# --- exact "name:value" matching tests ---

def test_tag_routes_exact_full_tag_matches(mock_redis_with_both_tags_vcon):
    """tag_routes key "tag1:value1" routes when vcon has that exact tag."""
    _, mock_redis = mock_redis_with_both_tags_vcon

    opts = {
        "tag_routes": {"tag1:value1": "exact_list"},
        "forward_original": True,
    }

    result = run("test-uuid-both-tags", "test-link", opts)

    mock_redis.rpush.assert_called_once_with("exact_list", "test-uuid-both-tags")
    assert result == "test-uuid-both-tags"


def test_tag_routes_exact_full_tag_does_not_match_different_value(mock_redis_with_tag2_other_vcon):
    """tag_routes key "tag2:value2" does NOT route when vcon has tag2:other."""
    _, mock_redis = mock_redis_with_tag2_other_vcon

    opts = {
        "tag_routes": {"tag2:value2": "exact_list"},
        "forward_original": True,
    }

    result = run("test-uuid-tag2-other", "test-link", opts)

    mock_redis.rpush.assert_not_called()
    assert result == "test-uuid-tag2-other"


def test_tag_routes_name_only_still_matches_any_value(mock_redis_with_tag2_other_vcon):
    """tag_routes key "tag2" (name only) still routes when vcon has tag2:other (backward compat)."""
    _, mock_redis = mock_redis_with_tag2_other_vcon

    opts = {
        "tag_routes": {"tag2": "name_only_list"},
        "forward_original": True,
    }

    result = run("test-uuid-tag2-other", "test-link", opts)

    mock_redis.rpush.assert_called_once_with("name_only_list", "test-uuid-tag2-other")
    assert result == "test-uuid-tag2-other"


def test_tag_route_rules_exact_full_tags_match(mock_redis_with_both_tags_vcon):
    """tag_route_rules with full "tag1:value1" and "tag2:value2" route when vcon has both exact tags."""
    _, mock_redis = mock_redis_with_both_tags_vcon

    opts = {
        "tag_route_rules": [
            {"tags": ["tag1:value1", "tag2:value2"], "target_list": "exact_and_list"}
        ],
        "tag_routes": {},
        "forward_original": True,
    }

    result = run("test-uuid-both-tags", "test-link", opts)

    mock_redis.rpush.assert_called_once_with("exact_and_list", "test-uuid-both-tags")
    assert result == "test-uuid-both-tags"


def test_tag_route_rules_exact_full_tags_no_match_wrong_value(mock_redis_with_tag2_other_vcon):
    """tag_route_rules requiring "tag2:value2" do NOT match when vcon has tag2:other."""
    _, mock_redis = mock_redis_with_tag2_other_vcon

    opts = {
        "tag_route_rules": [
            {"tags": ["tag1:value1", "tag2:value2"], "target_list": "exact_and_list"}
        ],
        "tag_routes": {},
        "forward_original": True,
    }

    result = run("test-uuid-tag2-other", "test-link", opts)

    mock_redis.rpush.assert_not_called()
    assert result == "test-uuid-tag2-other"


# --- JSON string body (Redis round-trip deserialization) ---

@pytest.fixture
def sample_vcon_with_json_string_body():
    """vCon whose tags attachment body is a JSON-encoded string (as stored after a Redis round-trip)."""
    return Vcon({
        "uuid": "test-uuid-json-str",
        "vcon": "0.0.1",
        "meta": {"arc_display_name": "Test vCon with JSON string body"},
        "parties": [],
        "dialog": [],
        "analysis": [],
        "attachments": [
            {
                "type": "tags",
                "body": '["important:high", "followup:yes"]',
                "encoding": "json"
            }
        ],
        "redacted": {}
    })

@pytest.fixture
def sample_vcon_with_malformed_json_string_body():
    """vCon whose tags attachment body is a malformed JSON string (should be silently skipped)."""
    return Vcon({
        "uuid": "test-uuid-bad-json",
        "vcon": "0.0.1",
        "meta": {"arc_display_name": "Test vCon with malformed JSON body"},
        "parties": [],
        "dialog": [],
        "analysis": [],
        "attachments": [
            {
                "type": "tags",
                "body": "this is not valid json [[[",
                "encoding": "json"
            }
        ],
        "redacted": {}
    })

@pytest.fixture
def mock_redis_with_json_string_body_vcon(mock_vcon_redis, mock_redis, sample_vcon_with_json_string_body):
    mock_instance = MagicMock()
    mock_instance.get_vcon.return_value = sample_vcon_with_json_string_body
    mock_vcon_redis.return_value = mock_instance
    return mock_vcon_redis, mock_redis

@pytest.fixture
def mock_redis_with_malformed_json_vcon(mock_vcon_redis, mock_redis, sample_vcon_with_malformed_json_string_body):
    mock_instance = MagicMock()
    mock_instance.get_vcon.return_value = sample_vcon_with_malformed_json_string_body
    mock_vcon_redis.return_value = mock_instance
    return mock_vcon_redis, mock_redis


def test_tag_router_json_string_body_is_parsed_and_routed(mock_redis_with_json_string_body_vcon):
    """Tags body stored as a JSON string (Redis round-trip) is parsed and routed correctly."""
    _, mock_redis = mock_redis_with_json_string_body_vcon

    opts = {
        "tag_routes": {"important": "important_list", "followup": "followup_list"},
        "forward_original": True,
    }

    result = run("test-uuid-json-str", "test-link", opts)

    mock_redis.rpush.assert_any_call("important_list", "test-uuid-json-str")
    mock_redis.rpush.assert_any_call("followup_list", "test-uuid-json-str")
    assert mock_redis.rpush.call_count == 2
    assert result == "test-uuid-json-str"


def test_tag_router_malformed_json_string_body_skipped(mock_redis_with_malformed_json_vcon):
    """Malformed JSON string body is silently skipped; vCon is forwarded without routing."""
    _, mock_redis = mock_redis_with_malformed_json_vcon

    opts = {
        "tag_routes": {"important": "important_list"},
        "forward_original": True,
    }

    result = run("test-uuid-bad-json", "test-link", opts)

    mock_redis.rpush.assert_not_called()
    assert result == "test-uuid-bad-json"


# --- forward_original=False with tags present but no match ---

def test_tag_router_no_match_forward_false_returns_none(mock_redis_with_vcon):
    """When tags are present but no route matches and forward_original=False, returns None."""
    _, mock_redis = mock_redis_with_vcon

    opts = {
        "tag_routes": {"nonexistent_tag": "some_list"},
        "forward_original": False,
    }

    result = run("test-uuid", "test-link", opts)

    mock_redis.rpush.assert_not_called()
    assert result is None


# --- multiple tag_route_rules: selective matching ---

def test_tag_route_rules_multiple_rules_only_matching_one_fires(mock_redis_with_both_tags_vcon):
    """With multiple AND rules, only the rule whose tags are all present routes the vCon."""
    _, mock_redis = mock_redis_with_both_tags_vcon

    opts = {
        "tag_route_rules": [
            {"tags": ["tag1", "tag2"], "target_list": "matching_list"},
            {"tags": ["tag1", "tag3"], "target_list": "non_matching_list"},  # tag3 absent
        ],
        "tag_routes": {},
        "forward_original": True,
    }

    result = run("test-uuid-both-tags", "test-link", opts)

    mock_redis.rpush.assert_called_once_with("matching_list", "test-uuid-both-tags")
    assert result == "test-uuid-both-tags"


def test_tag_route_rules_rule_with_empty_tags_is_skipped(mock_redis_with_both_tags_vcon):
    """A rule with an empty tags list is silently skipped (does not route)."""
    _, mock_redis = mock_redis_with_both_tags_vcon

    opts = {
        "tag_route_rules": [
            {"tags": [], "target_list": "should_not_route"},
        ],
        "tag_routes": {},
        "forward_original": True,
    }

    result = run("test-uuid-both-tags", "test-link", opts)

    mock_redis.rpush.assert_not_called()
    assert result == "test-uuid-both-tags"


def test_tag_route_rules_rule_with_missing_target_list_is_skipped(mock_redis_with_both_tags_vcon):
    """A rule without a target_list is silently skipped (does not route)."""
    _, mock_redis = mock_redis_with_both_tags_vcon

    opts = {
        "tag_route_rules": [
            {"tags": ["tag1", "tag2"]},  # target_list absent
        ],
        "tag_routes": {},
        "forward_original": True,
    }

    result = run("test-uuid-both-tags", "test-link", opts)

    mock_redis.rpush.assert_not_called()
    assert result == "test-uuid-both-tags"


# --- dict body: exact name:value keys are not supported ---

def test_tag_routes_exact_key_does_not_match_dict_body(mock_redis_with_dict_tags):
    """Dict-format body only supports name-only keys; a name:value key in tag_routes does not match."""
    _, mock_redis = mock_redis_with_dict_tags

    opts = {
        # dict body has {"call_type": "0"}, but this exact key won't match
        "tag_routes": {"call_type:0": "exact_list"},
        "forward_original": True,
    }

    result = run("test-uuid-dict-tags", "test-link", opts)

    mock_redis.rpush.assert_not_called()
    assert result == "test-uuid-dict-tags"
