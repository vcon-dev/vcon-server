import pytest
import hashlib
import json
from unittest.mock import patch, MagicMock

from server.vcon import Vcon
from lib.vcon_redis import VconRedis

import server.tracers.jlinc as jlinc_module

@pytest.fixture
def sample_vcon():
    """Create a sample vCon with transcript analysis for testing"""
    vcon = Vcon.build_new()
    # Add a dialog
    vcon.add_dialog({
        "type": "text",
        "body": "Hello world"
    })
    return vcon

@pytest.fixture(autouse=True)
def reset_globals():
    # reset globals between tests
    jlinc_module.domain = ""
    jlinc_module.system_short_name = ""
    jlinc_module.entities = []
    yield
    jlinc_module.domain = ""
    jlinc_module.system_short_name = ""
    jlinc_module.entities = []

@pytest.fixture
def mock_vcon_redis():
    """Mock the VconRedis class"""
    with patch('server.tracers.jlinc.VconRedis', autospec=True) as mock:
        yield mock

@pytest.fixture
def mock_redis_with_vcon(mock_vcon_redis, sample_vcon):
    """Set up mock Redis with sample vCon"""
    mock_instance = MagicMock()
    mock_instance.get_vcon.return_value = sample_vcon
    mock_vcon_redis.return_value = mock_instance
    return mock_instance

def test_sanitize():
    assert jlinc_module._sanitize("Hello World!") == "hello_world_"
    assert jlinc_module._sanitize("safe-Name.123") == "safe-name.123"

@patch("server.tracers.jlinc.requests.post")
@patch("server.tracers.jlinc.VconRedis")
def test_run_success(mock_redis_with_vcon, mock_post, sample_vcon):
    # Set up the mock Redis instance to return our sample vCon
    mock_instance = mock_redis_with_vcon.return_value
    mock_instance.get_vcon.return_value = sample_vcon

    # Mock API responses
    mock_post.return_value.json.side_effect = [
        ["vcon.local"],  # entity/domains/get
        {"didDoc": {"id": "did:jlinc:fedid-server%3A8881:xK4SAdrWS2A3OamvR9XNRq2OLsS_fD77uS_iQ8YFXp8", "created": "2025-08-08T14:22:19Z", "service": [{"id": "did:jlinc:fedid-server%3A8881:6AJ5eiZ9uhl6n5xr1y1Uun-y2cedtEGpNka2bLEvriA", "type": "login", "serviceEndpoint": "http://fedid-server:8881"}], "updated": "2025-08-08T14:22:19Z", "version": "2.0", "@context": ["https://www.w3.org/ns/did/v1", "https://didspec.jlinc.io/v2/ctx.jsonld"], "shortName": "vcontest-system@vcon.local", "deactivated": False, "recoveryHash": "817f9d649256e1069c4a5067751d2d41cc027657954c6404", "verificationMethod": [{"id": "#b811c10ba860250d32cec584febe676c", "key": "--86dugWAID16tpfWhDgPZRygGDZwktLU-j1Qf70aZQ", "type": "device", "created": "2025-08-08T14:22:19Z", "controller": "did:jlinc:fedid-server%3A8881:xK4SAdrWS2A3OamvR9XNRq2OLsS_fD77uS_iQ8YFXp8", "deactivated": None}], "capabilityDelegation": []}},  # entity/get for system
        {"didDoc": {"id": "did:jlinc:fedid-server%3A8881:gd-EgRVJ43HVZbpYar8zE8NjHPtmoxlpqO3CcFIFj4A", "created": "2025-08-08T14:22:19Z", "service": [{"id": "did:jlinc:fedid-server%3A8881:6AJ5eiZ9uhl6n5xr1y1Uun-y2cedtEGpNka2bLEvriA", "type": "login", "serviceEndpoint": "http://fedid-server:8881"}], "updated": "2025-08-08T14:22:19Z", "version": "2.0", "@context": ["https://www.w3.org/ns/did/v1", "https://didspec.jlinc.io/v2/ctx.jsonld"], "shortName": "vcontest-webhook_store_call_log@vcon.local", "deactivated": False, "recoveryHash": "aaa07949119e5f00fc44a04e7e2a4da4a0e5b8d6e0394f1f", "verificationMethod": [{"id": "#1026a2783630d042ec2da53ab7a1cdde", "key": "-_dyE-nYhFKfEvA-iW5I0rQ0RdpfdT34tbjJ5_e8qdc", "type": "device", "created": "2025-08-08T14:22:19Z", "controller": "did:jlinc:fedid-server%3A8881:gd-EgRVJ43HVZbpYar8zE8NjHPtmoxlpqO3CcFIFj4A", "deactivated": None}], "capabilityDelegation": []}}, # entity/get for webhook
        {"created": {"version": 1, "eventId": "0fb26e5a-e7f7-4c49-b4aa-1c39fbe8ecc2", "type": "data", "senderId": "did:jlinc:fedid-server%3A8881:xK4SAdrWS2A3OamvR9XNRq2OLsS_fD77uS_iQ8YFXp8", "recipientId": "did:jlinc:fedid-server%3A8881:gd-EgRVJ43HVZbpYar8zE8NjHPtmoxlpqO3CcFIFj4A", "agreementId": "00000000-0000-0000-0000-000000000000", "created": 1756145787794, "data": {"hash": "bef91b779cc949404fa041ee5f6b70cd3496b5c5d8c84724673a0e84a288830d"}}, "processed": {"auditData": {"audit": {"version": 1, "hashType": "SHA256", "digest": "2d3573c1583f49508628afc7741866fd2ed7bdc1e8ac84472ea29367f83d1ae0", "created": 1756145787811, "eventId": "0fb26e5a-e7f7-4c49-b4aa-1c39fbe8ecc2"}, "signatures": [{"version": 1, "id": "did:jlinc:fedid-server%3A8881:xK4SAdrWS2A3OamvR9XNRq2OLsS_fD77uS_iQ8YFXp8", "signedOn": 1756145787812, "type": "JWS/JCS", "jws": "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCIsImp3ayI6eyJrdHkiOiJPS1AiLCJjcnYiOiJFZDI1NTE5IiwieCI6Ii0tODZkdWdXQUlEMTZ0cGZXaERnUFpSeWdHRFp3a3RMVS1qMVFmNzBhWlEiLCJraWQiOiJkaWQ6amxpbmM6ZmVkaWQtc2VydmVyJTNBODg4MTp4SzRTQWRyV1MyQTNPYW12UjlYTlJxMk9Mc1NfZkQ3N3VTX2lROFlGWHA4In19.eyJjcmVhdGVkIjoxNzU2MTQ1Nzg3ODExLCJkaWdlc3QiOiIyZDM1NzNjMTU4M2Y0OTUwODYyOGFmYzc3NDE4NjZmZDJlZDdiZGMxZThhYzg0NDcyZWEyOTM2N2Y4M2QxYWUwIiwiZXZlbnRJZCI6IjBmYjI2ZTVhLWU3ZjctNGM0OS1iNGFhLTFjMzlmYmU4ZWNjMiIsImhhc2hUeXBlIjoiU0hBMjU2IiwidmVyc2lvbiI6MX0.k09-uCK2BpP72NbjNcxR_s3rfaFDnmLErR_f6TIg1ZBADwAfueujg2qUSWPT6MRFI1LunM1O4707-2xuP6usAw"}], "meta": {"in_vcon_uuid": "123e4567-e89b-12d3-a456-426614174000", "out_vcon_uuid": "123e4567-e89b-12d3-a456-426614174000"}}}},  # event/produce
    ]

    result = jlinc_module.run(
        in_vcon_uuid="test-uuid",
        out_vcon_uuid="test-uuid",
        tracer_name="jlinc",
        links=["webhook_store_call_log"],
        link_index=0,
    )

    assert result is True
    assert "vcon.local" is jlinc_module.domain
    assert "vcontest-system@vcon.local" in jlinc_module.entities
    assert "vcontest-webhook_store_call_log@vcon.local" in jlinc_module.entities

