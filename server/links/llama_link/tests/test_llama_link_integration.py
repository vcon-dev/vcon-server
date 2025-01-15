import pytest
import os
from server.vcon import Vcon
from server.links.llama_link import run

# Additional test transcripts
CUSTOMER_SERVICE_TRANSCRIPT = """
Customer: Hi, I need help with my order #12345.
Agent: I'll be happy to help. Can you tell me what's wrong with the order?
Customer: It's been a week and I haven't received it yet.
Agent: I apologize for the delay. Let me check the status for you.
"""

TECHNICAL_SUPPORT_TRANSCRIPT = """
Customer: My application keeps crashing after the latest update.
Agent: I understand that's frustrating. Let's troubleshoot this together.
Customer: I've already tried restarting my computer.
Agent: Good first step. Let's check your application logs next.
"""


@pytest.mark.integration
@pytest.fixture
def test_vcons():
    """Create multiple test vCons with different types of transcripts"""
    vcons = []
    for transcript in [CUSTOMER_SERVICE_TRANSCRIPT, TECHNICAL_SUPPORT_TRANSCRIPT]:
        vcon = Vcon()
        vcon.uuid = f"integration-test-{len(vcons)}"
        vcon.dialog = [
            {
                "type": "transcript",
                "body": {"text": transcript},
            }
        ]
        vcon.analysis = []
        vcons.append(vcon)
    return vcons


@pytest.mark.integration
def test_multiple_conversation_types(test_vcons, monkeypatch):
    """Test analysis of different conversation types"""
    test_opts = {
        "model_path": os.getenv('ACTUAL_MODEL_PATH'),
        "max_tokens": 500,
        "temperature": 0.7,
        "context_window": 4096,
        "n_gpu_layers": -1,
    }

    class MockVconRedis:
        def __init__(self):
            self.vcons = {vcon.uuid: vcon for vcon in test_vcons}

        def get_vcon(self, uuid):
            return self.vcons.get(uuid)

        def store_vcon(self, vcon):
            self.vcons[vcon.uuid] = vcon

    monkeypatch.setattr("server.links.llama_link.VconRedis", MockVconRedis)

    # Process each vCon
    for vcon in test_vcons:
        result = run(vcon.uuid, "test-link", test_opts)

        # Verify
        assert result == vcon.uuid
        assert len(vcon.analysis) == 1
        analysis = vcon.analysis[0]

        # Basic structure checks
        assert analysis["type"] == "llm_analysis"
        assert analysis["vendor"] == "llama_cpp"
        assert isinstance(analysis["body"], str)
        assert len(analysis["body"]) > 0

        # Print analysis for manual review
        print(f"\nAnalysis for {vcon.uuid}:\n{analysis['body']}")
