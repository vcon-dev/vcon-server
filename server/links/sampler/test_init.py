import pytest
from unittest.mock import patch
import time
from . import (
    run,
)  # Assuming the previous code is in a file named sampler.py


def test_percentage_sampling():
    with patch("random.uniform") as mock_uniform:
        # Test case where vCon should pass
        mock_uniform.return_value = 25
        assert (
            run("test-uuid", "sampler", {"method": "percentage", "value": 50})
            == "test-uuid"
        )

        # Test case where vCon should be filtered out
        mock_uniform.return_value = 75
        assert (
            run("test-uuid", "sampler", {"method": "percentage", "value": 50}) is None
        )


def test_rate_sampling():
    with patch("random.expovariate") as mock_expovariate:
        # Test case where vCon should pass
        mock_expovariate.return_value = 0.5
        assert (
            run("test-uuid", "sampler", {"method": "rate", "value": 2}) == "test-uuid"
        )

        # Test case where vCon should be filtered out
        mock_expovariate.return_value = 1.5
        assert run("test-uuid", "sampler", {"method": "rate", "value": 2}) is None


def test_modulo_sampling():
    # Test cases where vCon should pass
    assert run("uuid-1", "sampler", {"method": "modulo", "value": 3}) == "uuid-1"
    assert run("uuid-2", "sampler", {"method": "modulo", "value": 3}) is None
    assert run("uuid-3", "sampler", {"method": "modulo", "value": 3}) == "uuid-3"
    assert run("uuid-4", "sampler", {"method": "modulo", "value": 7}) == "uuid-4"


def test_time_based_sampling():
    with patch("time.time") as mock_time:
        # Test case where vCon should pass
        mock_time.return_value = 1000
        assert (
            run("test-uuid", "sampler", {"method": "time_based", "value": 5})
            == "test-uuid"
        )

        # Test case where vCon should be filtered out
        mock_time.return_value = 1002
        assert run("test-uuid", "sampler", {"method": "time_based", "value": 5}) is None


def test_unknown_method():
    with pytest.raises(ValueError):
        run("test-uuid", "sampler", {"method": "unknown", "value": 50})


def test_default_options():
    with patch("random.uniform") as mock_uniform:
        mock_uniform.return_value = 25
        assert run("test-uuid", "sampler") == "test-uuid"

        mock_uniform.return_value = 75
        assert run("test-uuid", "sampler") is None


def test_seed():
    # Test that using the same seed produces consistent results
    result1 = run(
        "test-uuid", "sampler", {"method": "percentage", "value": 50, "seed": 42}
    )
    result2 = run(
        "test-uuid", "sampler", {"method": "percentage", "value": 50, "seed": 42}
    )
    assert result1 == result2

    # # Test that different seeds can produce different results
    # result3 = run(
    #     "test-uuid", "sampler", {"method": "percentage", "value": 50, "seed": 24}
    # )
    # assert result1 == result2  # Same seed should still match
    # assert result1 != result3 or result2 != result3  # Different seed might not match


# Run the tests using: pytest test_sampler.py
