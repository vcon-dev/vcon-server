import sys
import types
from unittest.mock import patch

import pytest

from lib.error_tracking import capture_exception, init_error_tracker, init_sentry


@patch("lib.error_tracking.init_sentry")
def test_init_error_tracker_noops_without_dsn(mock_init_sentry, monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)

    init_error_tracker()

    mock_init_sentry.assert_not_called()


@patch("lib.error_tracking.init_sentry")
def test_init_error_tracker_initializes_when_dsn_is_present(mock_init_sentry, monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://example@sentry.io/1")

    init_error_tracker()

    mock_init_sentry.assert_called_once()


@pytest.fixture
def _no_ext_module():
    # Tests that exercise init_error_tracker shouldn't see whatever
    # error_tracking_ext is on the host's path; clear it for the test.
    saved = sys.modules.pop("error_tracking_ext", None)
    try:
        yield
    finally:
        if saved is not None:
            sys.modules["error_tracking_ext"] = saved


@patch("lib.error_tracking.sentry_sdk.init")
def test_init_sentry_passes_release_from_git_commit_env(mock_init, monkeypatch):
    # Sentry's release field is what lets a regression be tied back to a
    # specific deploy. The Docker image already bakes in the commit SHA,
    # so wire it through if present.
    monkeypatch.setenv("SENTRY_DSN", "https://example@sentry.io/1")
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("VCON_SERVER_GIT_COMMIT", "abc1234")

    init_sentry()

    kwargs = mock_init.call_args.kwargs
    assert kwargs["release"] == "abc1234"


@patch("lib.error_tracking.sentry_sdk.init")
def test_init_sentry_release_is_none_when_commit_env_missing(mock_init, monkeypatch):
    # Release is optional; an unset commit shouldn't poison init with "".
    monkeypatch.setenv("SENTRY_DSN", "https://example@sentry.io/1")
    monkeypatch.setenv("ENV", "test")
    monkeypatch.delenv("VCON_SERVER_GIT_COMMIT", raising=False)

    init_sentry()

    assert mock_init.call_args.kwargs["release"] is None


@patch("lib.error_tracking.init_sentry")
def test_init_error_tracker_invokes_extension_enrich_when_present(
    mock_init_sentry, monkeypatch, _no_ext_module
):
    # Deployments can ship an error_tracking_ext module to attach
    # proprietary tags after OSS init. When present, its enrich()
    # must be called once.
    monkeypatch.setenv("SENTRY_DSN", "https://example@sentry.io/1")
    fake_ext = types.ModuleType("error_tracking_ext")
    enrich_calls = []
    fake_ext.enrich = lambda: enrich_calls.append(1)
    sys.modules["error_tracking_ext"] = fake_ext

    init_error_tracker()

    mock_init_sentry.assert_called_once()
    assert enrich_calls == [1]


@patch("lib.error_tracking.init_sentry")
def test_init_error_tracker_tolerates_missing_extension_module(
    mock_init_sentry, monkeypatch, _no_ext_module
):
    # The extension hook is opportunistic — absence is the OSS default,
    # not an error.
    monkeypatch.setenv("SENTRY_DSN", "https://example@sentry.io/1")

    init_error_tracker()  # must not raise

    mock_init_sentry.assert_called_once()


@patch("lib.error_tracking.init_sentry")
def test_init_error_tracker_swallows_extension_errors(
    mock_init_sentry, monkeypatch, _no_ext_module, caplog
):
    # A broken enrichment must never abort startup. Log and continue.
    monkeypatch.setenv("SENTRY_DSN", "https://example@sentry.io/1")
    fake_ext = types.ModuleType("error_tracking_ext")

    def boom():
        raise RuntimeError("broken extension")

    fake_ext.enrich = boom
    sys.modules["error_tracking_ext"] = fake_ext

    with caplog.at_level("ERROR"):
        init_error_tracker()

    mock_init_sentry.assert_called_once()
    assert any("error_tracking_ext.enrich() raised" in r.message for r in caplog.records)


@patch("lib.error_tracking.sentry_sdk.capture_exception")
def test_capture_exception_only_reports_when_enabled(mock_capture_exception, monkeypatch):
    err = RuntimeError("boom")

    monkeypatch.delenv("SENTRY_DSN", raising=False)
    capture_exception(err)
    mock_capture_exception.assert_not_called()

    monkeypatch.setenv("SENTRY_DSN", "https://example@sentry.io/1")
    capture_exception(err)
    mock_capture_exception.assert_called_once_with(err)
