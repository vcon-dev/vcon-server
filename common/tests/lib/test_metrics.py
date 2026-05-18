from unittest.mock import Mock, patch

from lib import metrics as metrics_module


def test_increment_counter_creates_and_reuses_counter(monkeypatch):
    meter = Mock()
    counter = Mock()
    meter.create_counter.return_value = counter

    monkeypatch.setattr(metrics_module, "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel.test")
    monkeypatch.setattr(metrics_module, "meter", meter)
    monkeypatch.setattr(metrics_module, "counter_metrics", {})

    with patch("lib.metrics._init_otel_metrics") as mock_init:
        metrics_module.increment_counter("test.counter", attributes={"foo": "bar"})
        metrics_module.increment_counter("test.counter", value=2)

    mock_init.assert_called()
    meter.create_counter.assert_called_once()
    assert counter.add.call_args_list[0].args == (1,)
    assert counter.add.call_args_list[0].kwargs == {"attributes": {"foo": "bar"}}
    assert counter.add.call_args_list[1].args == (2,)
    assert counter.add.call_args_list[1].kwargs == {"attributes": {}}


def test_record_histogram_creates_and_reuses_histogram(monkeypatch):
    meter = Mock()
    histogram = Mock()
    meter.create_histogram.return_value = histogram

    monkeypatch.setattr(metrics_module, "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel.test")
    monkeypatch.setattr(metrics_module, "meter", meter)
    monkeypatch.setattr(metrics_module, "histogram_metrics", {})

    with patch("lib.metrics._init_otel_metrics") as mock_init:
        metrics_module.record_histogram("test.histogram", 1.5, attributes={"foo": "bar"})
        metrics_module.record_histogram("test.histogram", 2.5)

    mock_init.assert_called()
    meter.create_histogram.assert_called_once()
    assert histogram.record.call_args_list[0].args == (1.5,)
    assert histogram.record.call_args_list[0].kwargs == {"attributes": {"foo": "bar"}}
    assert histogram.record.call_args_list[1].args == (2.5,)
    assert histogram.record.call_args_list[1].kwargs == {"attributes": {}}


def test_increment_counter_noops_without_endpoint(monkeypatch):
    monkeypatch.setattr(metrics_module, "OTEL_EXPORTER_OTLP_ENDPOINT", None)
    monkeypatch.setattr(metrics_module, "meter", None)
    monkeypatch.setattr(metrics_module, "counter_metrics", {})

    with patch("lib.metrics._init_otel_metrics") as mock_init:
        metrics_module.increment_counter("test.counter")

    mock_init.assert_called_once()


def test_deprecated_metric_helpers_warn(caplog):
    metrics_module.init_metrics()
    metrics_module.stats_gauge("test.metric", 1)
    metrics_module.stats_count("test.metric", 2)

    assert "deprecated" in caplog.text.lower()
