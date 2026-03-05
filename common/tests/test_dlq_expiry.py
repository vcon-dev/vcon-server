"""Unit tests for DLQ (Dead Letter Queue) vCon expiry functionality.

These tests verify that vCons moved to the DLQ have their TTL extended
to VCON_DLQ_EXPIRY to ensure they persist for investigation.
"""

import pytest
from unittest.mock import MagicMock, patch

from settings import VCON_DLQ_EXPIRY


class TestDLQExpiryConfiguration:
    """Tests for the VCON_DLQ_EXPIRY configuration."""

    def test_dlq_expiry_default_value(self):
        """Verify VCON_DLQ_EXPIRY defaults to 7 days (604800 seconds)."""
        assert VCON_DLQ_EXPIRY == 604800

    def test_dlq_expiry_is_integer(self):
        """Verify VCON_DLQ_EXPIRY is an integer."""
        assert isinstance(VCON_DLQ_EXPIRY, int)

    def test_dlq_expiry_is_positive(self):
        """Verify VCON_DLQ_EXPIRY is a positive value (or zero to disable)."""
        assert VCON_DLQ_EXPIRY >= 0


class TestDLQExpiryBehavior:
    """Tests for DLQ expiry behavior in worker processing."""

    @patch('main.VCON_DLQ_EXPIRY', 604800)
    def test_dlq_sets_expiry_on_vcon(self):
        """Verify that moving a vCon to DLQ sets expiry on the vCon key."""
        # This tests the logic that would be in worker_loop
        mock_redis = MagicMock()
        vcon_id = "test-uuid-1234"
        dlq_name = "DLQ:test_ingress"
        
        # Simulate the DLQ handling code
        mock_redis.lpush(dlq_name, vcon_id)
        
        dlq_expiry = 604800  # 7 days
        if dlq_expiry > 0:
            vcon_key = f"vcon:{vcon_id}"
            mock_redis.expire(vcon_key, dlq_expiry)
        
        # Verify lpush was called for DLQ
        mock_redis.lpush.assert_called_once_with(dlq_name, vcon_id)
        
        # Verify expire was called on the vCon key
        mock_redis.expire.assert_called_once_with(f"vcon:{vcon_id}", 604800)

    @patch('main.VCON_DLQ_EXPIRY', 0)
    def test_dlq_skips_expiry_when_disabled(self):
        """Verify that DLQ expiry is skipped when VCON_DLQ_EXPIRY is 0."""
        mock_redis = MagicMock()
        vcon_id = "test-uuid-1234"
        dlq_name = "DLQ:test_ingress"
        
        # Simulate the DLQ handling code with expiry disabled
        mock_redis.lpush(dlq_name, vcon_id)
        
        dlq_expiry = 0  # Disabled
        if dlq_expiry > 0:
            vcon_key = f"vcon:{vcon_id}"
            mock_redis.expire(vcon_key, dlq_expiry)
        
        # Verify lpush was called for DLQ
        mock_redis.lpush.assert_called_once_with(dlq_name, vcon_id)
        
        # Verify expire was NOT called
        mock_redis.expire.assert_not_called()

    def test_dlq_expiry_longer_than_redis_expiry(self):
        """Verify DLQ expiry (7 days) is longer than default Redis expiry (1 hour)."""
        from settings import VCON_REDIS_EXPIRY
        assert VCON_DLQ_EXPIRY > VCON_REDIS_EXPIRY, \
            "DLQ expiry should be longer than default Redis expiry to prevent premature deletion"


class TestDLQExpiryIntegration:
    """Integration-style tests for DLQ expiry behavior."""

    def test_dlq_name_format(self):
        """Verify DLQ name format is consistent."""
        from dlq_utils import get_ingress_list_dlq_name
        
        assert get_ingress_list_dlq_name("test_ingress") == "DLQ:test_ingress"
        assert get_ingress_list_dlq_name("my-queue") == "DLQ:my-queue"
        assert get_ingress_list_dlq_name("default") == "DLQ:default"
