"""Unit tests for the ``conserver.ingress_list.length`` observable gauge.

The callback construction can be tested without any OpenTelemetry SDK
involvement — the helpers in ``lib.queue_metrics`` return a plain
zero-arg callable whose output is a list of ``Observation``. This file
exercises that callable directly.
"""

from unittest.mock import MagicMock, patch

from lib.queue_metrics import _build_callback, _get_configured_ingress_lists


class TestConfiguredIngressLists:
    def test_empty_config_returns_empty_list(self):
        with patch("config.Configuration.get_config", return_value={}):
            assert _get_configured_ingress_lists() == []

    def test_dedupes_and_sorts_ingress_lists_across_chains(self):
        """Two chains can share an ingress list; the gauge should only see
        each name once, and the order is deterministic so tests don't flap."""
        with patch(
            "config.Configuration.get_config",
            return_value={
                "chains": {
                    "main_chain": {"ingress_lists": ["default", "transcribe"]},
                    "transcription_chain": {"ingress_lists": ["transcribe"]},
                    "scitt_chain": {"ingress_lists": ["scitt_backfill"]},
                },
            },
        ):
            assert _get_configured_ingress_lists() == [
                "default",
                "scitt_backfill",
                "transcribe",
            ]

    def test_returns_empty_list_on_config_failure(self):
        """A broken config read must degrade to 'no series' rather than
        propagate an exception into the export tick."""
        with patch(
            "config.Configuration.get_config",
            side_effect=RuntimeError("config server down"),
        ):
            assert _get_configured_ingress_lists() == []

    def test_skips_empty_ingress_list_names(self):
        """Config edge case: tolerate empty strings or missing list."""
        with patch(
            "config.Configuration.get_config",
            return_value={
                "chains": {
                    "weird_chain": {"ingress_lists": ["", "transcribe", None]},
                },
            },
        ):
            assert _get_configured_ingress_lists() == ["transcribe"]


class TestCallbackEmitsObservations:
    def _make_client(self, llen_values):
        """Build a Redis-shaped MagicMock that returns the given LLEN
        result for each configured key."""
        client = MagicMock()
        client.llen = MagicMock(side_effect=lambda key: llen_values[key])
        return client

    def test_yields_one_observation_per_ingress_and_dlq(self):
        client = self._make_client(
            {
                "transcribe": 1234,
                "DLQ:transcribe": 5,
                "default": 0,
                "DLQ:default": 0,
            }
        )
        cb = _build_callback(client)

        with patch(
            "config.Configuration.get_config",
            return_value={
                "chains": {
                    "main_chain": {"ingress_lists": ["default"]},
                    "transcription_chain": {"ingress_lists": ["transcribe"]},
                },
            },
        ):
            obs = cb()

        emitted = {
            (o.attributes["ingress_list"], o.attributes["kind"]): o.value for o in obs
        }
        assert emitted == {
            ("default", "ingress"): 0,
            ("default", "dlq"): 0,
            ("transcribe", "ingress"): 1234,
            ("transcribe", "dlq"): 5,
        }

    def test_attribute_value_is_bare_ingress_name_not_dlq_prefixed(self):
        """Critical: the ``ingress_list`` attribute must match the
        configured ingress name (``transcribe``) for BOTH the live and
        DLQ observations. The ``kind`` attribute is what discriminates,
        so alert specs read ``{kind="dlq"}`` clean instead of regex-
        matching ``^DLQ:`` in the label value."""
        client = self._make_client({"transcribe": 0, "DLQ:transcribe": 0})
        cb = _build_callback(client)

        with patch(
            "config.Configuration.get_config",
            return_value={
                "chains": {"c": {"ingress_lists": ["transcribe"]}},
            },
        ):
            obs = cb()

        for o in obs:
            assert o.attributes["ingress_list"] == "transcribe"
        assert {o.attributes["kind"] for o in obs} == {"ingress", "dlq"}

    def test_individual_llen_failure_skips_that_series_only(self):
        """If LLEN errors on one key (e.g. transient Redis hiccup), the
        callback must still emit the series that succeeded — never raise
        from inside the export tick."""
        client = MagicMock()
        def _llen(key):
            if key == "DLQ:transcribe":
                raise RuntimeError("transient redis error")
            return 42
        client.llen.side_effect = _llen

        cb = _build_callback(client)
        with patch(
            "config.Configuration.get_config",
            return_value={
                "chains": {"c": {"ingress_lists": ["transcribe"]}},
            },
        ):
            obs = cb()

        emitted = {(o.attributes["ingress_list"], o.attributes["kind"]) for o in obs}
        assert emitted == {("transcribe", "ingress")}

    def test_empty_config_emits_zero_observations(self):
        """No ingress lists configured → callback returns an empty list,
        SDK publishes nothing this tick. Never raises."""
        client = MagicMock()
        cb = _build_callback(client)
        with patch("config.Configuration.get_config", return_value={}):
            obs = cb()
        assert obs == []
        client.llen.assert_not_called()
