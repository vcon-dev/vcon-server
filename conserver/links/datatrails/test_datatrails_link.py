from datetime import datetime, timedelta
from typing import Any, Generator
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from . import (
    DataTrailsAuth,
    create_asset,
    create_asset_event,
    create_event,
    get_asset_by_attributes,
    run,
)

MODULE = run.__module__


@pytest.fixture
def mock_auth() -> Generator[DataTrailsAuth, Any, None]:
    with patch(f"{MODULE}.requests.post") as mock_post:
        mock_post.return_value.json.return_value = {
            "access_token": "test_token",
            "expires_in": 3600,
        }
        yield DataTrailsAuth("http://test.com", "test_id", "test_secret")


def test_datatrails_auth_get_token(mock_auth):
    token = mock_auth.get_token()
    assert token == "test_token"
    assert mock_auth.token_expiry > datetime.now()


def test_datatrails_auth_refresh_token(mock_auth):
    mock_auth.token_expiry = datetime.now() - timedelta(minutes=5)
    token = mock_auth.get_token()
    assert token == "test_token"
    assert mock_auth.token_expiry > datetime.now()


def test_create_asset(mock_auth):
    mock_auth.get_token = Mock(return_value="test_token")

    with patch(f"{MODULE}.requests.post") as mock_post:
        mock_post.return_value.json.return_value = {
            "id": "new_asset",
            "access_token": "test_token",
            "expires_in": 3600,
        }

        result = create_asset(
            opts={"api_url": "http://test.com", "partner_id": "foo"},
            auth=mock_auth,
            attributes={"name": "Test"},
        )

    assert result == {
        "id": "new_asset",
        "access_token": "test_token",
        "expires_in": 3600,
    }
    assert mock_post.call_args.args[0] == "http://test.com/v2/assets"


def test_get_asset_by_attributes_prefixes_query_params(mock_auth):
    mock_auth.get_token = Mock(return_value="test_token")

    with patch(f"{MODULE}.requests.get") as mock_get:
        mock_get.return_value.json.return_value = {"assets": []}

        result = get_asset_by_attributes(
            opts={"api_url": "http://test.com", "partner_id": "foo"},
            auth=mock_auth,
            attributes={"arc_display_type": "vcon_droid", "droid_id": "2026-05-11"},
        )

    assert result == {"assets": []}
    assert mock_get.call_args.kwargs["params"] == {
        "attributes.arc_display_type": "vcon_droid",
        "attributes.droid_id": "2026-05-11",
    }


def test_create_asset_event_posts_expected_payload(mock_auth):
    mock_auth.get_token = Mock(return_value="test_token")

    with patch(f"{MODULE}.requests.post") as mock_post:
        mock_post.return_value.json.return_value = {"identity": "event-123"}

        result = create_asset_event(
            opts={"api_url": "http://test.com", "partner_id": "foo"},
            asset_id="assets/123",
            auth=mock_auth,
            event_attributes={"subject": "vcon://abc123"},
        )

    assert result == {"identity": "event-123"}
    assert mock_post.call_args.args[0] == "http://test.com/v2/assets/123/events"
    assert mock_post.call_args.kwargs["json"] == {
        "operation": "Record",
        "behaviour": "RecordEvidence",
        "event_attributes": {"subject": "vcon://abc123"},
    }


def test_create_event_posts_expected_payload(mock_auth):
    mock_auth.get_token = Mock(return_value="test_token")

    with patch(f"{MODULE}.requests.post") as mock_post:
        mock_post.return_value.json.return_value = {"identity": "asset-free-123"}

        result = create_event(
            opts={"api_url": "http://test.com", "partner_id": "foo"},
            auth=mock_auth,
            attributes={"subject": "vcon://abc123"},
            trails=["vcon://abc123"],
        )

    assert result == {"identity": "asset-free-123"}
    assert mock_post.call_args.args[0] == "http://test.com/v1/events"
    assert mock_post.call_args.kwargs["json"] == {
        "attributes": {"subject": "vcon://abc123"},
        "trails": ["vcon://abc123"],
    }


def test_run_raises_when_auth_is_missing():
    with pytest.raises(HTTPException) as excinfo:
        run("test-uuid", "datatrails", opts={"partner_id": "foo"})

    assert excinfo.value.status_code == 501
    assert 'Unable to find opt["auth"]' in excinfo.value.detail


def test_run_raises_for_unsupported_auth_type():
    with pytest.raises(HTTPException) as excinfo:
        run(
            "test-uuid",
            "datatrails",
            opts={
                "partner_id": "foo",
                "auth": {"type": "api-key"},
            },
        )

    assert excinfo.value.status_code == 501
    assert "Auth type not currently supported" in excinfo.value.detail


@patch(f"{MODULE}.VconRedis")
def test_run_raises_not_found_when_vcon_missing(mock_vcon_redis):
    mock_vcon_redis.return_value.get_vcon.return_value = None

    with pytest.raises(HTTPException) as excinfo:
        run(
            "test-uuid",
            "datatrails",
            opts={
                "partner_id": "foo",
                "vcon_operation": "transcribe",
                "auth": {
                    "type": "oidc-client-credentials",
                    "token_endpoint": "http://auth.test/token",
                    "client_id": "id",
                    "client_secret": "secret",
                },
            },
        )

    assert excinfo.value.status_code == 404
    assert "vCon not found" in excinfo.value.detail


@patch(f"{MODULE}.increment_counter")
@patch(f"{MODULE}.create_event")
@patch(f"{MODULE}.create_asset_event")
@patch(f"{MODULE}.get_asset_by_attributes")
@patch(f"{MODULE}.VconRedis")
@patch(f"{MODULE}.DataTrailsAuth")
def test_run_uses_existing_asset_and_swallows_asset_free_event_failure(
    _mock_auth_cls,
    mock_vcon_redis,
    mock_get_asset_by_attributes,
    mock_create_asset_event,
    mock_create_event,
    mock_increment_counter,
):
    mock_vcon = Mock(hash="hash-123", updated_at="2024-01-02T00:00:00Z", created_at="2024-01-01T00:00:00Z")
    mock_vcon_redis.return_value.get_vcon.return_value = mock_vcon
    mock_get_asset_by_attributes.return_value = {"assets": [{"identity": "assets/existing"}]}
    mock_create_asset_event.return_value = {"identity": "events/123"}
    mock_create_event.side_effect = Exception("asset free failure")

    result = run(
        "test-uuid",
        "datatrails",
        opts={
            "partner_id": "foo",
            "vcon_operation": "vcon-created",
            "auth": {
                "type": "oidc-client-credentials",
                "token_endpoint": "http://auth.test/token",
                "client_id": "id",
                "client_secret": "secret",
            },
        },
    )

    assert result == "test-uuid"
    mock_create_asset_event.assert_called_once()
    mock_increment_counter.assert_called_once_with(
        "conserver.link.datatrails.event_creation_failures",
        attributes={"link.name": "datatrails", "vcon.uuid": "test-uuid", "event_type": "asset_free"},
    )


@patch(f"{MODULE}.create_event")
@patch(f"{MODULE}.create_asset_event")
@patch(f"{MODULE}.create_asset")
@patch(f"{MODULE}.get_asset_by_attributes")
@patch(f"{MODULE}.VconRedis")
@patch(f"{MODULE}.DataTrailsAuth")
def test_run_creates_asset_when_missing(
    _mock_auth_cls,
    mock_vcon_redis,
    mock_get_asset_by_attributes,
    mock_create_asset,
    mock_create_asset_event,
    mock_create_event,
):
    mock_vcon = Mock(hash="hash-123", updated_at=None, created_at="2024-01-01T00:00:00Z")
    mock_vcon_redis.return_value.get_vcon.return_value = mock_vcon
    mock_get_asset_by_attributes.return_value = {"assets": []}
    mock_create_asset.return_value = {"identity": "assets/new"}
    mock_create_asset_event.return_value = {"identity": "events/123"}
    mock_create_event.return_value = {"identity": "events/456"}

    result = run(
        "test-uuid",
        "datatrails",
        opts={
            "partner_id": "foo",
            "vcon_operation": "transcribe",
            "auth": {
                "type": "oidc-client-credentials",
                "token_endpoint": "http://auth.test/token",
                "client_id": "id",
                "client_secret": "secret",
            },
        },
    )

    assert result == "test-uuid"
    mock_create_asset.assert_called_once()
    mock_create_asset_event.assert_called_once()
    mock_create_event.assert_called_once()


@patch(f"{MODULE}.increment_counter")
@patch(f"{MODULE}.create_asset_event")
@patch(f"{MODULE}.get_asset_by_attributes")
@patch(f"{MODULE}.VconRedis")
@patch(f"{MODULE}.DataTrailsAuth")
def test_run_counts_and_raises_when_asset_event_creation_fails(
    _mock_auth_cls,
    mock_vcon_redis,
    mock_get_asset_by_attributes,
    mock_create_asset_event,
    mock_increment_counter,
):
    mock_vcon = Mock(hash="hash-123", updated_at=None, created_at="2024-01-01T00:00:00Z")
    mock_vcon_redis.return_value.get_vcon.return_value = mock_vcon
    mock_get_asset_by_attributes.return_value = {"assets": [{"identity": "assets/existing"}]}
    mock_create_asset_event.side_effect = Exception("event failed")

    with pytest.raises(Exception, match="event failed"):
        run(
            "test-uuid",
            "datatrails",
            opts={
                "partner_id": "foo",
                "vcon_operation": "transcribe",
                "auth": {
                    "type": "oidc-client-credentials",
                    "token_endpoint": "http://auth.test/token",
                    "client_id": "id",
                    "client_secret": "secret",
                },
            },
        )

    mock_increment_counter.assert_called_once_with(
        "conserver.link.datatrails.event_creation_failures",
        attributes={"link.name": "datatrails", "vcon.uuid": "test-uuid"},
    )
