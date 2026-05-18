from unittest.mock import patch

from lib.error_tracking import capture_exception, init_error_tracker


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


@patch("lib.error_tracking.sentry_sdk.capture_exception")
def test_capture_exception_only_reports_when_enabled(mock_capture_exception, monkeypatch):
    err = RuntimeError("boom")

    monkeypatch.delenv("SENTRY_DSN", raising=False)
    capture_exception(err)
    mock_capture_exception.assert_not_called()

    monkeypatch.setenv("SENTRY_DSN", "https://example@sentry.io/1")
    capture_exception(err)
    mock_capture_exception.assert_called_once_with(err)
