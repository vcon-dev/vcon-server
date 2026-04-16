"""Comprehensive tests for S3 storage module.

Tests cover:
- S3 client creation with various configurations
- Region configuration handling
- Custom endpoint URL support
- Save and get operations
- Error handling
"""

import json
import pytest
import sys
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime
from io import BytesIO

# Mock the logger module before importing the S3 module
mock_logger = MagicMock()
sys.modules["lib.logging_utils"] = MagicMock(init_logger=MagicMock(return_value=mock_logger))
sys.modules["lib.vcon_redis"] = MagicMock()

from storage.s3 import _create_s3_client, _build_s3_key, _build_lookup_key, _date_prefix, save, get, delete, default_options


class TestCreateS3Client:
    """Tests for the _create_s3_client helper function."""

    def test_create_client_with_required_options_only(self):
        """Test client creation with only required options."""
        opts = {
            "aws_access_key_id": "test-access-key",
            "aws_secret_access_key": "test-secret-key",
        }

        with patch("storage.s3.boto3.client") as mock_client:
            _create_s3_client(opts)

            mock_client.assert_called_once_with(
                "s3",
                aws_access_key_id="test-access-key",
                aws_secret_access_key="test-secret-key",
            )

    def test_create_client_with_region(self):
        """Test client creation with aws_region specified."""
        opts = {
            "aws_access_key_id": "test-access-key",
            "aws_secret_access_key": "test-secret-key",
            "aws_region": "us-west-2",
        }

        with patch("storage.s3.boto3.client") as mock_client:
            _create_s3_client(opts)

            mock_client.assert_called_once_with(
                "s3",
                aws_access_key_id="test-access-key",
                aws_secret_access_key="test-secret-key",
                region_name="us-west-2",
            )

    def test_create_client_with_us_east_2_region(self):
        """Test client creation with us-east-2 region (the error case from issue)."""
        opts = {
            "aws_access_key_id": "test-access-key",
            "aws_secret_access_key": "test-secret-key",
            "aws_region": "us-east-2",
        }

        with patch("storage.s3.boto3.client") as mock_client:
            _create_s3_client(opts)

            mock_client.assert_called_once_with(
                "s3",
                aws_access_key_id="test-access-key",
                aws_secret_access_key="test-secret-key",
                region_name="us-east-2",
            )

    def test_create_client_with_endpoint_url(self):
        """Test client creation with custom endpoint URL (e.g., MinIO)."""
        opts = {
            "aws_access_key_id": "test-access-key",
            "aws_secret_access_key": "test-secret-key",
            "endpoint_url": "http://localhost:9000",
        }

        with patch("storage.s3.boto3.client") as mock_client:
            _create_s3_client(opts)

            mock_client.assert_called_once_with(
                "s3",
                aws_access_key_id="test-access-key",
                aws_secret_access_key="test-secret-key",
                endpoint_url="http://localhost:9000",
            )

    def test_create_client_with_all_options(self):
        """Test client creation with all options specified."""
        opts = {
            "aws_access_key_id": "test-access-key",
            "aws_secret_access_key": "test-secret-key",
            "aws_region": "eu-west-1",
            "endpoint_url": "https://s3.eu-west-1.amazonaws.com",
        }

        with patch("storage.s3.boto3.client") as mock_client:
            _create_s3_client(opts)

            mock_client.assert_called_once_with(
                "s3",
                aws_access_key_id="test-access-key",
                aws_secret_access_key="test-secret-key",
                region_name="eu-west-1",
                endpoint_url="https://s3.eu-west-1.amazonaws.com",
            )

    def test_create_client_ignores_empty_region(self):
        """Test that empty string region is ignored."""
        opts = {
            "aws_access_key_id": "test-access-key",
            "aws_secret_access_key": "test-secret-key",
            "aws_region": "",
        }

        with patch("storage.s3.boto3.client") as mock_client:
            _create_s3_client(opts)

            mock_client.assert_called_once_with(
                "s3",
                aws_access_key_id="test-access-key",
                aws_secret_access_key="test-secret-key",
            )

    def test_create_client_ignores_none_region(self):
        """Test that None region is ignored."""
        opts = {
            "aws_access_key_id": "test-access-key",
            "aws_secret_access_key": "test-secret-key",
            "aws_region": None,
        }

        with patch("storage.s3.boto3.client") as mock_client:
            _create_s3_client(opts)

            mock_client.assert_called_once_with(
                "s3",
                aws_access_key_id="test-access-key",
                aws_secret_access_key="test-secret-key",
            )

    def test_create_client_with_various_aws_regions(self):
        """Test client creation with various AWS regions."""
        regions = [
            "us-east-1",
            "us-east-2",
            "us-west-1",
            "us-west-2",
            "eu-west-1",
            "eu-west-2",
            "eu-central-1",
            "ap-southeast-1",
            "ap-northeast-1",
            "sa-east-1",
        ]

        for region in regions:
            opts = {
                "aws_access_key_id": "test-access-key",
                "aws_secret_access_key": "test-secret-key",
                "aws_region": region,
            }

            with patch("storage.s3.boto3.client") as mock_client:
                _create_s3_client(opts)

                mock_client.assert_called_once_with(
                    "s3",
                    aws_access_key_id="test-access-key",
                    aws_secret_access_key="test-secret-key",
                    region_name=region,
                )


class TestDatePrefix:
    """Tests for the _date_prefix helper function."""

    def test_date_prefix_basic(self):
        assert _date_prefix("2025-12-10T15:30:00Z") == "2025/12/10"

    def test_date_prefix_zero_padded(self):
        assert _date_prefix("2024-01-05T00:00:00Z") == "2024/01/05"

    def test_date_prefix_without_time(self):
        assert _date_prefix("2026-03-26") == "2026/03/26"


class TestBuildLookupKey:
    """Tests for the _build_lookup_key helper function."""

    def test_build_lookup_key_without_prefix(self):
        key = _build_lookup_key("test-uuid")
        assert key == "lookup/test-uuid.txt"

    def test_build_lookup_key_with_prefix(self):
        key = _build_lookup_key("test-uuid", s3_path="vcons")
        assert key == "vcons/lookup/test-uuid.txt"

    def test_build_lookup_key_with_trailing_slash_prefix(self):
        key = _build_lookup_key("test-uuid", s3_path="vcons/")
        assert key == "vcons/lookup/test-uuid.txt"

    def test_build_lookup_key_with_nested_prefix(self):
        key = _build_lookup_key("test-uuid", s3_path="data/vcons")
        assert key == "data/vcons/lookup/test-uuid.txt"

    def test_build_lookup_key_with_none_prefix(self):
        key = _build_lookup_key("test-uuid", s3_path=None)
        assert key == "lookup/test-uuid.txt"


class TestBuildS3Key:
    """Tests for the _build_s3_key helper function."""

    def test_build_key_without_prefix_or_date(self):
        """Test key building without s3_path prefix or created_at."""
        key = _build_s3_key("test-uuid")
        assert key == "test-uuid.vcon"

    def test_build_key_with_prefix_only(self):
        """Test key building with s3_path prefix but no created_at."""
        key = _build_s3_key("test-uuid", s3_path="vcons")
        assert key == "vcons/test-uuid.vcon"

    def test_build_key_with_trailing_slash_prefix(self):
        """Test key building with trailing slash in prefix."""
        key = _build_s3_key("test-uuid", s3_path="vcons/")
        assert key == "vcons/test-uuid.vcon"

    def test_build_key_with_none_prefix(self):
        """Test key building with None prefix."""
        key = _build_s3_key("test-uuid", s3_path=None)
        assert key == "test-uuid.vcon"

    def test_build_key_with_empty_prefix(self):
        """Test key building with empty string prefix."""
        key = _build_s3_key("test-uuid", s3_path="")
        assert key == "test-uuid.vcon"

    def test_build_key_with_nested_prefix(self):
        """Test key building with nested prefix."""
        key = _build_s3_key("test-uuid", s3_path="data/vcons/archive")
        assert key == "data/vcons/archive/test-uuid.vcon"

    def test_build_key_with_date_path(self):
        """Test key building with date_path generates date folder."""
        key = _build_s3_key("test-uuid", date_path="2025/12/10")
        assert key == "2025/12/10/test-uuid.vcon"

    def test_build_key_with_date_path_and_prefix(self):
        """Test key building with both date_path and s3_path."""
        key = _build_s3_key("test-uuid", date_path="2025/12/10", s3_path="vcons")
        assert key == "vcons/2025/12/10/test-uuid.vcon"

    def test_build_key_with_date_path_and_nested_prefix(self):
        """Test key building with date_path and nested prefix."""
        key = _build_s3_key("test-uuid", date_path="2024/01/15", s3_path="data/archive")
        assert key == "data/archive/2024/01/15/test-uuid.vcon"


class TestSave:
    """Tests for the save function."""

    @pytest.fixture
    def mock_vcon(self):
        """Create a mock vCon object."""
        mock = MagicMock()
        mock.dumps.return_value = '{"uuid": "test-uuid", "vcon": "1.0.0"}'
        mock.created_at = "2025-12-10T15:30:00Z"
        return mock

    @pytest.fixture
    def base_opts(self):
        """Base options for S3 storage."""
        return {
            "aws_access_key_id": "test-access-key",
            "aws_secret_access_key": "test-secret-key",
            "aws_bucket": "test-bucket",
        }

    def test_save_basic(self, mock_vcon, base_opts):
        """Test basic save operation writes vcon file and lookup pointer."""
        with patch("storage.s3.VconRedis") as mock_redis_class, \
             patch("storage.s3.boto3.client") as mock_boto_client:

            mock_redis = MagicMock()
            mock_redis.get_vcon.return_value = mock_vcon
            mock_redis_class.return_value = mock_redis

            mock_s3 = MagicMock()
            mock_boto_client.return_value = mock_s3

            save("test-uuid", base_opts)

            mock_redis.get_vcon.assert_called_once_with("test-uuid")
            assert mock_s3.put_object.call_count == 2

            calls = {c.kwargs["Key"]: c.kwargs for c in mock_s3.put_object.call_args_list}
            assert "2025/12/10/test-uuid.vcon" in calls
            assert calls["2025/12/10/test-uuid.vcon"]["Bucket"] == "test-bucket"
            assert "lookup/test-uuid.txt" in calls
            assert calls["lookup/test-uuid.txt"]["Body"] == b"2025/12/10"

    def test_save_with_s3_path_prefix(self, mock_vcon, base_opts):
        """Test save operation with s3_path prefix writes correct keys."""
        base_opts["s3_path"] = "vcons"

        with patch("storage.s3.VconRedis") as mock_redis_class, \
             patch("storage.s3.boto3.client") as mock_boto_client:

            mock_redis = MagicMock()
            mock_redis.get_vcon.return_value = mock_vcon
            mock_redis_class.return_value = mock_redis

            mock_s3 = MagicMock()
            mock_boto_client.return_value = mock_s3

            save("test-uuid", base_opts)

            calls = {c.kwargs["Key"]: c.kwargs for c in mock_s3.put_object.call_args_list}
            assert "vcons/2025/12/10/test-uuid.vcon" in calls
            assert "vcons/lookup/test-uuid.txt" in calls
            assert calls["vcons/lookup/test-uuid.txt"]["Body"] == b"2025/12/10"

    def test_save_with_region(self, mock_vcon, base_opts):
        """Test save operation with region specified."""
        base_opts["aws_region"] = "us-east-2"

        with patch("storage.s3.VconRedis") as mock_redis_class, \
             patch("storage.s3.boto3.client") as mock_boto_client:

            mock_redis = MagicMock()
            mock_redis.get_vcon.return_value = mock_vcon
            mock_redis_class.return_value = mock_redis

            mock_s3 = MagicMock()
            mock_boto_client.return_value = mock_s3

            save("test-uuid", base_opts)

            mock_boto_client.assert_called_once_with(
                "s3",
                aws_access_key_id="test-access-key",
                aws_secret_access_key="test-secret-key",
                region_name="us-east-2",
            )

    def test_save_raises_exception_on_error(self, mock_vcon, base_opts):
        """Test that save raises exception on S3 error."""
        with patch("storage.s3.VconRedis") as mock_redis_class, \
             patch("storage.s3.boto3.client") as mock_boto_client:

            mock_redis = MagicMock()
            mock_redis.get_vcon.return_value = mock_vcon
            mock_redis_class.return_value = mock_redis

            mock_s3 = MagicMock()
            mock_s3.put_object.side_effect = Exception("S3 Error")
            mock_boto_client.return_value = mock_s3

            with pytest.raises(Exception, match="S3 Error"):
                save("test-uuid", base_opts)


class TestGet:
    """Tests for the get function."""

    @pytest.fixture
    def base_opts(self):
        """Base options for S3 storage."""
        return {
            "aws_access_key_id": "test-access-key",
            "aws_secret_access_key": "test-secret-key",
            "aws_bucket": "test-bucket",
        }

    def _make_s3_mock(self, vcon_data: dict, date_path: str = "2025/12/10"):
        """Return a mock S3 client that serves a lookup pointer then the vcon."""
        mock_s3 = MagicMock()
        lookup_response = {"Body": BytesIO(date_path.encode())}
        vcon_response = {"Body": BytesIO(json.dumps(vcon_data).encode("utf-8"))}
        mock_s3.get_object.side_effect = [lookup_response, vcon_response]
        return mock_s3

    def test_get_basic(self, base_opts):
        """Test get resolves path via lookup pointer then fetches vcon."""
        vcon_data = {"uuid": "test-uuid", "vcon": "1.0.0"}

        with patch("storage.s3.boto3.client") as mock_boto_client:
            mock_s3 = self._make_s3_mock(vcon_data, "2025/12/10")
            mock_boto_client.return_value = mock_s3

            result = get("test-uuid", base_opts)

            assert result == vcon_data
            assert mock_s3.get_object.call_count == 2
            mock_s3.get_object.assert_any_call(Bucket="test-bucket", Key="lookup/test-uuid.txt")
            mock_s3.get_object.assert_any_call(Bucket="test-bucket", Key="2025/12/10/test-uuid.vcon")

    def test_get_with_s3_path_prefix(self, base_opts):
        """Test get uses prefixed lookup and vcon keys when s3_path is set."""
        base_opts["s3_path"] = "vcons"
        vcon_data = {"uuid": "test-uuid"}

        with patch("storage.s3.boto3.client") as mock_boto_client:
            mock_s3 = self._make_s3_mock(vcon_data, "2025/12/10")
            mock_boto_client.return_value = mock_s3

            result = get("test-uuid", base_opts)

            assert result == vcon_data
            mock_s3.get_object.assert_any_call(Bucket="test-bucket", Key="vcons/lookup/test-uuid.txt")
            mock_s3.get_object.assert_any_call(Bucket="test-bucket", Key="vcons/2025/12/10/test-uuid.vcon")

    def test_get_with_region(self, base_opts):
        """Test get operation with region specified."""
        base_opts["aws_region"] = "eu-west-1"
        vcon_data = {"uuid": "test-uuid"}

        with patch("storage.s3.boto3.client") as mock_boto_client:
            mock_s3 = self._make_s3_mock(vcon_data)
            mock_boto_client.return_value = mock_s3

            result = get("test-uuid", base_opts)

            mock_boto_client.assert_called_once_with(
                "s3",
                aws_access_key_id="test-access-key",
                aws_secret_access_key="test-secret-key",
                region_name="eu-west-1",
            )

    def test_get_returns_none_on_lookup_error(self, base_opts):
        """Test that get returns None when the lookup pointer is missing."""
        from botocore.exceptions import ClientError

        with patch("storage.s3.boto3.client") as mock_boto_client:
            mock_s3 = MagicMock()
            error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}
            mock_s3.get_object.side_effect = ClientError(error_response, "GetObject")
            mock_boto_client.return_value = mock_s3

            result = get("nonexistent-uuid", base_opts)

            assert result is None

    def test_get_returns_none_on_vcon_fetch_error(self, base_opts):
        """Test that get returns None when the vcon object fetch fails."""
        from botocore.exceptions import ClientError

        with patch("storage.s3.boto3.client") as mock_boto_client:
            mock_s3 = MagicMock()
            lookup_response = {"Body": BytesIO(b"2025/12/10")}
            error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}
            mock_s3.get_object.side_effect = [
                lookup_response,
                ClientError(error_response, "GetObject"),
            ]
            mock_boto_client.return_value = mock_s3

            result = get("test-uuid", base_opts)

            assert result is None


class TestDelete:
    """Tests for the delete function."""

    @pytest.fixture
    def base_opts(self):
        return {
            "aws_access_key_id": "test-access-key",
            "aws_secret_access_key": "test-secret-key",
            "aws_bucket": "test-bucket",
        }

    def test_delete_basic(self, base_opts):
        """Test delete removes the vcon file and lookup pointer."""
        with patch("storage.s3.boto3.client") as mock_boto_client:
            mock_s3 = MagicMock()
            mock_s3.get_object.return_value = {"Body": BytesIO(b"2025/12/10")}
            mock_boto_client.return_value = mock_s3

            result = delete("test-uuid", base_opts)

            assert result is True
            mock_s3.delete_object.assert_any_call(Bucket="test-bucket", Key="2025/12/10/test-uuid.vcon")
            mock_s3.delete_object.assert_any_call(Bucket="test-bucket", Key="lookup/test-uuid.txt")
            assert mock_s3.delete_object.call_count == 2

    def test_delete_with_s3_path_prefix(self, base_opts):
        """Test delete uses prefixed keys when s3_path is set."""
        base_opts["s3_path"] = "vcons"

        with patch("storage.s3.boto3.client") as mock_boto_client:
            mock_s3 = MagicMock()
            mock_s3.get_object.return_value = {"Body": BytesIO(b"2025/12/10")}
            mock_boto_client.return_value = mock_s3

            result = delete("test-uuid", base_opts)

            assert result is True
            mock_s3.delete_object.assert_any_call(Bucket="test-bucket", Key="vcons/2025/12/10/test-uuid.vcon")
            mock_s3.delete_object.assert_any_call(Bucket="test-bucket", Key="vcons/lookup/test-uuid.txt")

    def test_delete_returns_false_when_not_found(self, base_opts):
        """Test delete returns False when the lookup pointer is missing."""
        from botocore.exceptions import ClientError

        with patch("storage.s3.boto3.client") as mock_boto_client:
            mock_s3 = MagicMock()
            error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}
            mock_s3.get_object.side_effect = ClientError(error_response, "GetObject")
            mock_boto_client.return_value = mock_s3

            result = delete("nonexistent-uuid", base_opts)

            assert result is False
            mock_s3.delete_object.assert_not_called()

    def test_delete_returns_false_on_error(self, base_opts):
        """Test delete returns False on unexpected S3 error."""
        with patch("storage.s3.boto3.client") as mock_boto_client:
            mock_s3 = MagicMock()
            mock_s3.get_object.side_effect = Exception("S3 Error")
            mock_boto_client.return_value = mock_s3

            result = delete("test-uuid", base_opts)

            assert result is False


class TestRegionErrorScenario:
    """Test the specific error scenario that was reported."""

    def test_without_region_uses_default(self):
        """Test that without region, boto3 uses its default (us-east-1)."""
        opts = {
            "aws_access_key_id": "test-key",
            "aws_secret_access_key": "test-secret",
        }

        with patch("storage.s3.boto3.client") as mock_client:
            _create_s3_client(opts)

            # Verify region_name is NOT passed when not specified
            call_kwargs = mock_client.call_args.kwargs
            assert "region_name" not in call_kwargs

    def test_with_region_passes_to_client(self):
        """Test that specifying region passes it to boto3 client."""
        opts = {
            "aws_access_key_id": "test-key",
            "aws_secret_access_key": "test-secret",
            "aws_region": "us-east-2",
        }

        with patch("storage.s3.boto3.client") as mock_client:
            _create_s3_client(opts)

            call_kwargs = mock_client.call_args.kwargs
            assert "region_name" in call_kwargs
            assert call_kwargs["region_name"] == "us-east-2"


class TestEndpointUrlScenarios:
    """Test custom endpoint URL scenarios for S3-compatible services."""

    def test_minio_endpoint(self):
        """Test configuration for MinIO."""
        opts = {
            "aws_access_key_id": "minioadmin",
            "aws_secret_access_key": "minioadmin",
            "endpoint_url": "http://localhost:9000",
        }

        with patch("storage.s3.boto3.client") as mock_client:
            _create_s3_client(opts)

            call_kwargs = mock_client.call_args.kwargs
            assert call_kwargs["endpoint_url"] == "http://localhost:9000"

    def test_localstack_endpoint(self):
        """Test configuration for LocalStack."""
        opts = {
            "aws_access_key_id": "test",
            "aws_secret_access_key": "test",
            "endpoint_url": "http://localhost:4566",
            "aws_region": "us-east-1",
        }

        with patch("storage.s3.boto3.client") as mock_client:
            _create_s3_client(opts)

            call_kwargs = mock_client.call_args.kwargs
            assert call_kwargs["endpoint_url"] == "http://localhost:4566"
            assert call_kwargs["region_name"] == "us-east-1"

    def test_digital_ocean_spaces_endpoint(self):
        """Test configuration for DigitalOcean Spaces."""
        opts = {
            "aws_access_key_id": "do-access-key",
            "aws_secret_access_key": "do-secret-key",
            "endpoint_url": "https://nyc3.digitaloceanspaces.com",
            "aws_region": "nyc3",
        }

        with patch("storage.s3.boto3.client") as mock_client:
            _create_s3_client(opts)

            call_kwargs = mock_client.call_args.kwargs
            assert call_kwargs["endpoint_url"] == "https://nyc3.digitaloceanspaces.com"
            assert call_kwargs["region_name"] == "nyc3"
