import pytest
from unittest.mock import patch, MagicMock
from links.jq_link import run
from vcon import Vcon

@pytest.fixture
def mock_vcon_redis():
    """Mock the VconRedis class"""
    with patch('links.jq_link.VconRedis') as mock:
        yield mock

@pytest.fixture
def sample_vcon():
    """Create a sample vCon for testing"""
    return Vcon({
        "uuid": "test-uuid",
        "vcon": "0.0.1",
        "meta": {
            "arc_display_type": "Cat",
            "weight": "3.6kg",
            "arc_display_name": "Test Cat"
        },
        "parties": [
            {
                "role": "owner",
                "name": "Alice"
            },
            {
                "role": "vet",
                "name": "Dr. Bob"
            }
        ],
        "dialog": [],
        "analysis": [
            {
                "type": "summary",
                "body": "Test summary",
                "vendor": "test"
            }
        ],
        "attachments": [
            {
                "type": "report",
                "body": "Test report"
            }
        ],
        "redacted": {}
    })

@pytest.fixture
def mock_redis_with_vcon(mock_vcon_redis, sample_vcon):
    """Set up mock Redis with sample vCon"""
    mock_instance = MagicMock()
    mock_instance.get_vcon.return_value = sample_vcon
    mock_vcon_redis.return_value = mock_instance
    return mock_vcon_redis

def test_filter_by_display_type(mock_redis_with_vcon, sample_vcon):
    """Test filtering by display type"""
    # Test matching case
    opts = {
        "filter": '.meta.arc_display_type == "Cat"',
        "forward_matches": True
    }
    result = run("test-uuid", "test-link", opts)
    assert result == "test-uuid"

    # Test non-matching case
    opts = {
        "filter": '.meta.arc_display_type == "Dog"',
        "forward_matches": True
    }
    result = run("test-uuid", "test-link", opts)
    assert result is None

def test_filter_by_parties(mock_redis_with_vcon, sample_vcon):
    """Test filtering by party information"""
    # Test matching number of parties
    opts = {
        "filter": '.parties | length == 2',
        "forward_matches": True
    }
    result = run("test-uuid", "test-link", opts)
    assert result == "test-uuid"

    # Test matching party role
    opts = {
        "filter": '.parties[] | select(.role == "vet") | any',
        "forward_matches": True
    }
    result = run("test-uuid", "test-link", opts)
    assert result == "test-uuid"

def test_filter_by_analysis(mock_redis_with_vcon, sample_vcon):
    """Test filtering by analysis presence and content"""
    # Test presence of analysis
    opts = {
        "filter": '.analysis | length > 0',
        "forward_matches": True
    }
    result = run("test-uuid", "test-link", opts)
    assert result == "test-uuid"

    # Test specific analysis type
    opts = {
        "filter": '.analysis[] | select(.type == "summary") | any',
        "forward_matches": True
    }
    result = run("test-uuid", "test-link", opts)
    assert result == "test-uuid"

def test_filter_by_attachments(mock_redis_with_vcon, sample_vcon):
    """Test filtering by attachments"""
    # Test presence of attachments
    opts = {
        "filter": '.attachments | length > 0',
        "forward_matches": True
    }
    result = run("test-uuid", "test-link", opts)
    assert result == "test-uuid"

    # Test specific attachment type
    opts = {
        "filter": '.attachments[] | select(.type == "report") | any',
        "forward_matches": True
    }
    result = run("test-uuid", "test-link", opts)
    assert result == "test-uuid"

def test_inverse_filtering(mock_redis_with_vcon, sample_vcon):
    """Test inverse filtering with forward_matches=False"""
    opts = {
        "filter": '.attributes.arc_display_type == "Dog"',
        "forward_matches": False
    }
    result = run("test-uuid", "test-link", opts)
    assert result == "test-uuid"

def test_complex_filters(mock_redis_with_vcon, sample_vcon):
    """Test complex filter combinations"""
    # Test AND condition
    opts = {
        "filter": '(.meta.arc_display_type == "Cat") and (.analysis | length > 0)',
        "forward_matches": True
    }
    result = run("test-uuid", "test-link", opts)
    assert result == "test-uuid"

    # Test OR condition
    opts = {
        "filter": '(.meta.arc_display_type == "Dog") or (.analysis | length > 0)',
        "forward_matches": True
    }
    result = run("test-uuid", "test-link", opts)
    assert result == "test-uuid"

def test_invalid_filter(mock_redis_with_vcon, sample_vcon):
    """Test handling of invalid jq filter"""
    opts = {
        "filter": 'invalid % filter @ syntax',
        "forward_matches": True
    }
    result = run("test-uuid", "test-link", opts)
    assert result is None

def test_missing_vcon(mock_vcon_redis):
    """Test handling of missing vCon"""
    # Set up mock to return None for get_vcon
    mock_instance = MagicMock()
    mock_instance.get_vcon.return_value = None
    mock_vcon_redis.return_value = mock_instance

    opts = {
        "filter": '.attributes.arc_display_type == "Cat"',
        "forward_matches": True
    }
    result = run("test-uuid", "test-link", opts)
    assert result is None

def test_default_options(mock_redis_with_vcon, sample_vcon):
    """Test link with default options"""
    result = run("test-uuid", "test-link")
    assert result == "test-uuid"  # Default filter '.' should match everything

def test_filter_redacted(mock_redis_with_vcon, sample_vcon):
    """Test filtering based on redaction status"""
    # Test unredacted vCon
    opts = {
        "filter": '.redacted == {}',
        "forward_matches": True
    }
    result = run("test-uuid", "test-link", opts)
    assert result == "test-uuid"

    # Modify vCon to be redacted
    sample_vcon.vcon_dict["redacted"] = {"some": "redaction"}
    opts = {
        "filter": '.redacted != {}',
        "forward_matches": True
    }
    result = run("test-uuid", "test-link", opts)
    assert result == "test-uuid"

def test_numeric_comparisons(mock_redis_with_vcon, sample_vcon):
    """Test filtering with numeric comparisons"""
    # Add numeric field to test
    sample_vcon.vcon_dict["meta"]["count"] = 42
    
    # Test greater than
    opts = {
        "filter": '.meta.count > 40',
        "forward_matches": True
    }
    result = run("test-uuid", "test-link", opts)
    assert result == "test-uuid"

    # Test less than
    opts = {
        "filter": '.meta.count < 50',
        "forward_matches": True
    }
    result = run("test-uuid", "test-link", opts)
    assert result == "test-uuid"