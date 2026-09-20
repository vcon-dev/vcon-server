"""HTTP failure propagation uses an opaque probe, not a customer vCon."""

from unittest.mock import patch

import pytest
import requests
from storage import webhook


@pytest.mark.parametrize("status", [401, 500, 503])
def test_http_failure_reaches_storage_dlq(status):
    from main import VconChainRequest

    response = requests.Response()
    response.status_code = status
    response._content = b"{}"
    response.url = "https://receiver.invalid/probe"
    request = VconChainRequest(
        chain_details={"name": "test", "links": [], "storages": ["test_webhook"]},
        vcon_id="synthetic-id",
    )
    with (
        patch.object(webhook, "VconRedis") as bodies,
        patch.object(webhook.requests, "post", return_value=response),
        patch("main.Storage") as storage,
        patch("main.queue") as queue,
    ):
        bodies.return_value.get_vcon.return_value.to_dict.return_value = {"synthetic_retry_probe": True}
        storage.return_value.save.side_effect = lambda vid: webhook.save(vid, {"webhook-urls": [response.url]})
        request._process_storage("test_webhook")
        queue.enqueue_storage_dlq.assert_called_once_with("test_webhook", "synthetic-id", retention_seconds=604800)


@pytest.mark.parametrize("options,expected", [({}, 30), ({"timeout": 4}, 4)])
def test_success_has_bounded_request_timeout(options, expected):
    response = requests.Response()
    response.status_code = 201
    response._content = b"{}"
    with (
        patch.object(webhook, "VconRedis") as bodies,
        patch.object(webhook.requests, "post", return_value=response) as post,
    ):
        bodies.return_value.get_vcon.return_value.to_dict.return_value = {"synthetic_retry_probe": True}
        webhook.save("synthetic-id", {"webhook-urls": ["https://receiver.invalid/probe"], **options})
        assert post.call_args.kwargs["timeout"] == expected
