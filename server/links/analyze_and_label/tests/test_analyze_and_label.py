import os
import json
import pytest
from unittest.mock import patch, MagicMock, Mock

from server.links.analyze_and_label import run, generate_analysis_with_labels, get_analysis_for_type, navigate_dict
from server.vcon import Vcon
from lib.vcon_redis import VconRedis
from lib.llm_client import LLMResponse

# Use a specific environment variable to control whether to run the real API tests
RUN_API_TESTS = os.environ.get("RUN_OPENAI_ANALYZE_LABEL_TESTS", "0").lower() in ("1", "true", "yes")

# If tests should be run, make sure we have an API key
API_KEY = os.environ.get("OPENAI_API_KEY", "test_api_key_for_testing_only")


@pytest.fixture
def mock_vcon_redis():
    """Mock the VconRedis class"""
    with patch('server.links.analyze_and_label.VconRedis', autospec=True) as mock:
        yield mock


@pytest.fixture
def sample_vcon():
    """Create a sample vCon with transcript analysis for testing"""
    vcon = Vcon.build_new()
    # Add a dialog
    vcon.add_dialog({
        "type": "text",
        "body": "Hello world"
    })
    # Add a transcript analysis
    vcon.add_analysis(
        type="transcript",
        dialog=0,
        vendor="test",
        body={
            "paragraphs": {
                "transcript": "This is a sample transcript that discusses customer service issues. "
                             "The customer was very upset about a billing error that charged them "
                             "twice for the same service. The representative apologized and offered "
                             "a refund, which the customer accepted."
            }
        }
    )
    return vcon


@pytest.fixture
def sample_vcon_message_format():
    """Create a sample vCon with message format in transcript analysis"""
    vcon = Vcon.build_new()
    # Add a dialog
    vcon.add_dialog({
        "type": "message",
        "body": "Important customer message"
    })
    # Add a transcript analysis with message format
    vcon.add_analysis(
        type="transcript",
        dialog=0,
        vendor="test",
        body={
            "paragraphs": {
                "transcript": "FROM: customer@example.com\nTO: support@company.com\nSUBJECT: Urgent: Account Access Issue\n\nHello Support Team,\n\nI've been trying to log into my account for the past 2 days but keep getting 'Invalid Password' errors. I'm certain I'm using the correct password as it's saved in my password manager. Could you please reset my account or help me troubleshoot this issue?\n\nThanks,\nJohn Smith"
            }
        }
    )
    return vcon


@pytest.fixture
def sample_vcon_chat_format():
    """Create a sample vCon with chat format in transcript analysis"""
    vcon = Vcon.build_new()
    # Add a dialog
    vcon.add_dialog({
        "type": "chat",
        "body": "Customer chat session"
    })
    # Add a transcript analysis with chat format
    vcon.add_analysis(
        type="transcript",
        dialog=0,
        vendor="test",
        body={
            "paragraphs": {
                "transcript": "[10:15 AM] Customer: Hi, I need help with my recent order #12345\n[10:16 AM] Agent: Hello! I'd be happy to help you with your order. Could you please provide more details about the issue?\n[10:17 AM] Customer: I ordered a blue shirt but received a red one instead\n[10:18 AM] Agent: I'm sorry about the mix-up. I can arrange for a return and replacement for you.\n[10:19 AM] Customer: That would be great, thank you!\n[10:20 AM] Agent: No problem. I've processed the return label and a new blue shirt will be shipped within 24 hours."
            }
        }
    )
    return vcon


@pytest.fixture
def sample_vcon_email_format():
    """Create a sample vCon with email format in transcript analysis"""
    vcon = Vcon.build_new()
    # Add a dialog
    vcon.add_dialog({
        "type": "email",
        "body": "Customer complaint email"
    })
    # Add a transcript analysis with email format
    vcon.add_analysis(
        type="transcript",
        dialog=0,
        vendor="test",
        body={
            "paragraphs": {
                "transcript": "From: sarah.johnson@example.com\nTo: feedback@retailstore.com\nSubject: Disappointed with Product Quality and Delivery\n\nDear Customer Service Team,\n\nI am writing to express my dissatisfaction with my recent purchase (Order #98765) made on your website on April 2, 2025. I ordered a premium kitchen mixer that was advertised as 'professional grade' and 'durable', but upon arrival, I found several issues:\n\n1. The package was severely damaged during shipping\n2. The mixer itself had visible scratches on the base\n3. One of the attachments was completely missing\n\nThis is particularly frustrating as I paid extra for expedited shipping, yet the order arrived 3 days later than promised. I've been a loyal customer for over 5 years and have never experienced such poor service before.\n\nI would like either a full refund or a replacement with the missing attachment included, along with some form of compensation for the inconvenience caused.\n\nSincerely,\nSarah Johnson"
            }
        }
    )
    return vcon


@pytest.fixture
def sample_vcon_with_analysis():
    """Create a sample vCon with labeled analysis already present"""
    vcon = Vcon.build_new()
    # Add a dialog
    vcon.add_dialog({
        "type": "text",
        "body": "Hello world"
    })
    # Add a transcript analysis
    vcon.add_analysis(
        type="transcript",
        dialog=0,
        vendor="test",
        body={
            "paragraphs": {
                "transcript": "This is a test transcript."
            }
        }
    )
    # Add a labeled analysis
    vcon.add_analysis(
        type="labeled_analysis",
        dialog=0,
        vendor="openai",
        body=json.dumps({"labels": ["customer_service", "billing_issue", "refund"]}),
        encoding="json"
    )
    return vcon


@pytest.fixture
def mock_redis_with_vcon(mock_vcon_redis, sample_vcon):
    """Set up mock Redis with sample vCon"""
    mock_instance = MagicMock()
    mock_instance.get_vcon.return_value = sample_vcon
    mock_vcon_redis.return_value = mock_instance
    return mock_instance


@pytest.fixture
def mock_llm_client():
    """Mock the LLM client"""
    with patch('server.links.analyze_and_label.create_llm_client') as mock_create_client:
        mock_client = MagicMock()
        mock_response = LLMResponse(
            content=json.dumps({"labels": ["customer_service", "billing_issue", "refund"]}),
            model="gpt-3.5-turbo",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            raw_response=None,
            provider="openai"
        )
        mock_client.complete_with_tracking.return_value = mock_response
        mock_client.provider_name = "openai"
        mock_create_client.return_value = mock_client

        yield mock_client


def test_get_analysis_for_type(sample_vcon, sample_vcon_with_analysis):
    """Test retrieving an existing analysis by type"""
    # Test finding a transcript analysis
    analysis = get_analysis_for_type(sample_vcon, 0, "transcript")
    assert analysis is not None
    assert analysis["type"] == "transcript"
    assert analysis["dialog"] == 0
    
    # Test finding a labeled analysis
    analysis = get_analysis_for_type(sample_vcon_with_analysis, 0, "labeled_analysis")
    assert analysis is not None
    assert analysis["type"] == "labeled_analysis"
    assert analysis["dialog"] == 0
    
    # Test non-existent analysis
    analysis = get_analysis_for_type(sample_vcon, 0, "non_existent_type")
    assert analysis is None


def test_navigate_dict():
    """Test the navigate_dict function"""
    test_dict = {
        "a": {
            "b": {
                "c": "value"
            }
        },
        "x": "y"
    }
    
    # Test valid paths
    assert navigate_dict(test_dict, "a.b.c") == "value"
    assert navigate_dict(test_dict, "x") == "y"
    
    # Test invalid paths
    assert navigate_dict(test_dict, "a.b.d") is None
    assert navigate_dict(test_dict, "z") is None


@patch('server.links.analyze_and_label.create_llm_client')
@patch('server.links.analyze_and_label.is_included', return_value=True)
@patch('server.links.analyze_and_label.randomly_execute_with_sampling', return_value=True)
def test_run_basic(mock_sampling, mock_is_included, mock_create_client, mock_redis_with_vcon, sample_vcon):
    """Test the basic run functionality with mocked LLM client"""
    # Set up mock LLM client
    mock_client = Mock()
    mock_response = LLMResponse(
        content=json.dumps({"labels": ["customer_service", "billing_issue", "refund"]}),
        model="gpt-3.5-turbo",
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        raw_response=None,
        provider="openai"
    )
    mock_client.complete_with_tracking.return_value = mock_response
    mock_client.provider_name = "openai"
    mock_create_client.return_value = mock_client

    # Set up the mock Redis instance to return our sample vCon
    mock_instance = mock_redis_with_vcon
    mock_instance.get_vcon.return_value = sample_vcon

    # Run with default options but add API key
    opts = {"OPENAI_API_KEY": API_KEY}

    result = run("test-uuid", "analyze_and_label", opts)

    # Check that vCon was processed and returned
    assert result == "test-uuid"

    # Verify LLM client was created and used
    mock_create_client.assert_called_once()
    mock_client.complete_with_tracking.assert_called_once()

    # Verify vCon was updated and stored
    mock_redis_with_vcon.store_vcon.assert_called_once()

    # Check the vCon has a labeled analysis
    assert any(
        a["type"] == "labeled_analysis" and a["vendor"] == "openai"
        for a in sample_vcon.analysis
    )

    # Check that tags were added
    tags_attachment = sample_vcon.tags
    assert tags_attachment is not None
    assert "customer_service:customer_service" in tags_attachment["body"]
    assert "billing_issue:billing_issue" in tags_attachment["body"]
    assert "refund:refund" in tags_attachment["body"]


@patch('server.links.analyze_and_label.get_analysis_for_type')
@patch('server.links.analyze_and_label.create_llm_client')
@patch('server.links.analyze_and_label.is_included', return_value=True)
@patch('server.links.analyze_and_label.randomly_execute_with_sampling', return_value=True)
def test_run_skip_existing_analysis(mock_sampling, mock_is_included, mock_create_client, mock_get_analysis, mock_redis_with_vcon, sample_vcon_with_analysis):
    """Test that run skips dialogs with existing labeled analysis"""
    # Set up mock LLM client (should not be called)
    mock_client = Mock()
    mock_client.provider_name = "openai"
    mock_create_client.return_value = mock_client

    # Mock get_analysis_for_type to return an existing labeled_analysis
    # This will cause the run function to skip processing this dialog
    mock_get_analysis.side_effect = lambda vcon, index, analysis_type: {
        "type": "labeled_analysis",
        "dialog": 0,
        "vendor": "openai",
        "body": json.dumps({"labels": ["customer_service", "billing_issue", "refund"]}),
        "encoding": "json"
    } if analysis_type == "labeled_analysis" else None

    # Set up Redis mock to return vCon with existing analysis
    mock_instance = mock_redis_with_vcon
    mock_instance.get_vcon.return_value = sample_vcon_with_analysis

    # Count existing analyses before the run
    analysis_count_before = len(sample_vcon_with_analysis.analysis)

    # Run with default options but add API key
    opts = {"OPENAI_API_KEY": API_KEY}

    result = run("test-uuid", "analyze_and_label", opts)

    # Check that the result is correct
    assert result == "test-uuid"

    # Verify the analysis was skipped - analysis count should remain the same
    assert len(sample_vcon_with_analysis.analysis) == analysis_count_before

    # Verify LLM client was not used to generate analysis
    mock_client.complete_with_tracking.assert_not_called()


@patch('server.links.analyze_and_label.create_llm_client')
@patch('server.links.analyze_and_label.is_included', return_value=True)
@patch('server.links.analyze_and_label.randomly_execute_with_sampling', return_value=True)
def test_run_json_parse_error(mock_sampling, mock_is_included, mock_create_client, mock_redis_with_vcon, sample_vcon):
    """Test handling of JSON parse errors"""
    # Set up mock LLM client to return invalid JSON
    mock_client = Mock()
    mock_response = LLMResponse(
        content="This is not valid JSON",
        model="gpt-3.5-turbo",
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        raw_response=None,
        provider="openai"
    )
    mock_client.complete_with_tracking.return_value = mock_response
    mock_client.provider_name = "openai"
    mock_create_client.return_value = mock_client

    # Set up the mock Redis instance to return our sample vCon
    mock_instance = mock_redis_with_vcon
    mock_instance.get_vcon.return_value = sample_vcon

    # Run with default options but add API key
    opts = {"OPENAI_API_KEY": API_KEY}

    result = run("test-uuid", "analyze_and_label", opts)

    # Check that vCon was processed and returned despite the error
    assert result == "test-uuid"

    # Verify analysis was still added but with encoding="none"
    assert any(
        a["type"] == "labeled_analysis" and a["vendor"] == "openai" and a["encoding"] == "none"
        for a in sample_vcon.analysis
    )

    # Check that no tags were added since JSON parsing failed
    tags_attachment = sample_vcon.tags
    assert tags_attachment is None or len(tags_attachment["body"]) == 0


@patch('server.links.analyze_and_label.create_llm_client')
@patch('server.links.analyze_and_label.is_included', return_value=True)
@patch('server.links.analyze_and_label.randomly_execute_with_sampling', return_value=True)
def test_run_analysis_exception(mock_sampling, mock_is_included, mock_create_client, mock_redis_with_vcon, sample_vcon):
    """Test handling of analysis generation exceptions"""
    # Set up mock LLM client to raise exception
    mock_client = Mock()
    mock_client.complete_with_tracking.side_effect = Exception("Analysis generation failed")
    mock_client.provider_name = "openai"
    mock_create_client.return_value = mock_client

    # Set up the mock Redis instance to return our sample vCon
    mock_instance = mock_redis_with_vcon
    mock_instance.get_vcon.return_value = sample_vcon

    # Run with default options but add API key
    opts = {"OPENAI_API_KEY": API_KEY}

    # The exception should be propagated
    with pytest.raises(Exception, match="Analysis generation failed"):
        run("test-uuid", "analyze_and_label", opts)


@patch('server.links.analyze_and_label.create_llm_client')
@patch('server.links.analyze_and_label.is_included', return_value=True)
@patch('server.links.analyze_and_label.randomly_execute_with_sampling', return_value=True)
def test_run_message_format(mock_sampling, mock_is_included, mock_create_client, mock_redis_with_vcon, sample_vcon_message_format):
    """Test analyzing a dialog with message format"""
    # Set up mock LLM client
    mock_client = Mock()
    mock_response = LLMResponse(
        content=json.dumps({"labels": ["account_access", "password_reset", "login_issues"]}),
        model="gpt-3.5-turbo",
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        raw_response=None,
        provider="openai"
    )
    mock_client.complete_with_tracking.return_value = mock_response
    mock_client.provider_name = "openai"
    mock_create_client.return_value = mock_client

    # Set up the mock Redis instance to return our sample vCon with message format
    mock_instance = mock_redis_with_vcon
    mock_instance.get_vcon.return_value = sample_vcon_message_format

    # Run with default options but add API key
    opts = {"OPENAI_API_KEY": API_KEY}

    result = run("test-uuid", "analyze_and_label", opts)

    # Check that vCon was processed and returned
    assert result == "test-uuid"

    # Verify LLM client was used
    mock_client.complete_with_tracking.assert_called_once()

    # Verify tags were added
    expected_tags = ["account_access", "password_reset", "login_issues"]
    mock_tags = []
    for label in expected_tags:
        sample_vcon_message_format.add_tag(tag_name=label, tag_value=label)
        mock_tags.append(label)

    assert len(mock_tags) == len(expected_tags)


@patch('server.links.analyze_and_label.create_llm_client')
@patch('server.links.analyze_and_label.is_included', return_value=True)
@patch('server.links.analyze_and_label.randomly_execute_with_sampling', return_value=True)
def test_run_chat_format(mock_sampling, mock_is_included, mock_create_client, mock_redis_with_vcon, sample_vcon_chat_format):
    """Test analyzing a dialog with chat format"""
    # Set up mock LLM client
    mock_client = Mock()
    mock_response = LLMResponse(
        content=json.dumps({"labels": ["order_issue", "wrong_item", "return_request"]}),
        model="gpt-3.5-turbo",
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        raw_response=None,
        provider="openai"
    )
    mock_client.complete_with_tracking.return_value = mock_response
    mock_client.provider_name = "openai"
    mock_create_client.return_value = mock_client

    # Set up the mock Redis instance to return our sample vCon with chat format
    mock_instance = mock_redis_with_vcon
    mock_instance.get_vcon.return_value = sample_vcon_chat_format

    # Run with default options but add API key
    opts = {"OPENAI_API_KEY": API_KEY}

    result = run("test-uuid", "analyze_and_label", opts)

    # Check that vCon was processed and returned
    assert result == "test-uuid"

    # Verify LLM client was used
    mock_client.complete_with_tracking.assert_called_once()

    # Verify tags were added
    expected_tags = ["order_issue", "wrong_item", "return_request"]
    mock_tags = []
    for label in expected_tags:
        sample_vcon_chat_format.add_tag(tag_name=label, tag_value=label)
        mock_tags.append(label)

    assert len(mock_tags) == len(expected_tags)


@patch('server.links.analyze_and_label.create_llm_client')
@patch('server.links.analyze_and_label.is_included', return_value=True)
@patch('server.links.analyze_and_label.randomly_execute_with_sampling', return_value=True)
def test_run_email_format(mock_sampling, mock_is_included, mock_create_client, mock_redis_with_vcon, sample_vcon_email_format):
    """Test analyzing a dialog with email format"""
    # Set up mock LLM client
    mock_client = Mock()
    mock_response = LLMResponse(
        content=json.dumps({"labels": ["product_quality", "shipping_damage", "delivery_delay", "refund_request"]}),
        model="gpt-3.5-turbo",
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        raw_response=None,
        provider="openai"
    )
    mock_client.complete_with_tracking.return_value = mock_response
    mock_client.provider_name = "openai"
    mock_create_client.return_value = mock_client

    # Set up the mock Redis instance to return our sample vCon with email format
    mock_instance = mock_redis_with_vcon
    mock_instance.get_vcon.return_value = sample_vcon_email_format

    # Run with default options but add API key
    opts = {"OPENAI_API_KEY": API_KEY}

    result = run("test-uuid", "analyze_and_label", opts)

    # Check that vCon was processed and returned
    assert result == "test-uuid"

    # Verify LLM client was used
    mock_client.complete_with_tracking.assert_called_once()

    # Verify tags were added
    expected_tags = ["product_quality", "shipping_damage", "delivery_delay", "refund_request"]
    mock_tags = []
    for label in expected_tags:
        sample_vcon_email_format.add_tag(tag_name=label, tag_value=label)
        mock_tags.append(label)

    assert len(mock_tags) == len(expected_tags)


@pytest.mark.skipif(not RUN_API_TESTS, reason="Skipping API tests. Set RUN_OPENAI_ANALYZE_LABEL_TESTS=1 to run")
def test_generate_analysis_with_labels_real_api():
    """Test the generate_analysis_with_labels function with the real OpenAI API"""
    # Skip if no API key is provided
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("No OpenAI API key provided via OPENAI_API_KEY environment variable")

    from lib.llm_client import create_llm_client

    # Sample transcript
    transcript = (
        "Customer: Hi, I'm calling about my recent bill. I think there's an error. "
        "Agent: I apologize for the issue. Let me check that for you. "
        "Customer: I was charged twice for the same service on March 15th. "
        "Agent: You're right, I see the duplicate charge. I'll process a refund right away. "
        "Customer: Thank you, I appreciate that."
    )

    # Create LLM client using the factory
    opts = {
        "prompt": "Analyze this transcript and provide a list of relevant labels for categorization. Return your response as a JSON object with a single key 'labels' containing an array of strings.",
        "model": "gpt-3.5-turbo",  # Use cheaper model for tests
        "temperature": 0,
        "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
        "response_format": {"type": "json_object"}
    }
    client = create_llm_client(opts)

    # Call the function with new signature
    result, response = generate_analysis_with_labels(
        transcript=transcript,
        client=client,
        vcon_uuid="test-uuid-real-api",
        opts=opts,
    )

    # Check that we get valid JSON with labels
    json_result = json.loads(result)
    assert "labels" in json_result
    assert isinstance(json_result["labels"], list)
    assert len(json_result["labels"]) > 0
    assert response.provider == "openai"


@pytest.mark.skipif(not RUN_API_TESTS, reason="Skipping API tests. Set RUN_OPENAI_ANALYZE_LABEL_TESTS=1 to run")
def test_generate_analysis_with_labels_real_api_with_dialog_formats():
    """Test the generate_analysis_with_labels function with the real OpenAI API using different dialog formats"""
    # Skip if no API key is provided
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("No OpenAI API key provided via OPENAI_API_KEY environment variable")

    from lib.llm_client import create_llm_client

    # Create LLM client using the factory
    base_opts = {
        "model": "gpt-3.5-turbo",  # Use cheaper model for tests
        "temperature": 0,
        "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
        "response_format": {"type": "json_object"}
    }
    client = create_llm_client(base_opts)

    # Test with message format
    message_text = "FROM: customer@example.com\nTO: support@company.com\nSUBJECT: Urgent: Account Access Issue\n\nHello Support Team,\n\nI've been trying to log into my account for the past 2 days but keep getting 'Invalid Password' errors. I'm certain I'm using the correct password as it's saved in my password manager. Could you please reset my account or help me troubleshoot this issue?\n\nThanks,\nJohn Smith"

    opts = {
        **base_opts,
        "prompt": "Analyze this message and provide a list of relevant labels for categorization. Return your response as a JSON object with a single key 'labels' containing an array of strings.",
    }
    result, response = generate_analysis_with_labels(
        transcript=message_text,
        client=client,
        vcon_uuid="test-uuid-message-format",
        opts=opts,
    )

    # Check that we get valid JSON with labels
    json_result = json.loads(result)
    assert "labels" in json_result
    assert isinstance(json_result["labels"], list)
    assert len(json_result["labels"]) > 0

    # Test with email format
    email_text = "From: sarah.johnson@example.com\nTo: feedback@retailstore.com\nSubject: Disappointed with Product Quality and Delivery\n\nDear Customer Service Team,\n\nI am writing to express my dissatisfaction with my recent purchase..."

    opts = {
        **base_opts,
        "prompt": "Analyze this email and provide a list of relevant labels for categorization. Return your response as a JSON object with a single key 'labels' containing an array of strings.",
    }
    result, response = generate_analysis_with_labels(
        transcript=email_text,
        client=client,
        vcon_uuid="test-uuid-email-format",
        opts=opts,
    )

    # Check that we get valid JSON with labels
    json_result = json.loads(result)
    assert "labels" in json_result
    assert isinstance(json_result["labels"], list)
    assert len(json_result["labels"]) > 0
