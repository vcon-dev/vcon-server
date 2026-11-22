import importlib
import logging
import os

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration


def init_sentry():
    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN"],
        environment=os.environ["ENV"],
        # Tag every event with the build commit so a regression can be
        # bisected to a specific deploy. Unset releases are fine — Sentry
        # treats the field as optional.
        release=os.environ.get("VCON_SERVER_GIT_COMMIT") or None,
        integrations=[
            LoggingIntegration(
                level=logging.INFO,  # Capture info and above as breadcrumbs
                event_level=logging.ERROR,
            )
        ],
        traces_sample_rate=0,  # adjust the sample rate in production as needed
    )


def init_error_tracker():
    if not os.environ.get("SENTRY_DSN"):
        return
    init_sentry()
    # Optional downstream enrichment hook. Deployments that ship an
    # ``error_tracking_ext`` module on the Python path can attach
    # process-wide Sentry tags / context there (e.g. proprietary
    # identifiers not appropriate for OSS). Imported opportunistically
    # so OSS keeps zero compile-time dependency on it; an enrichment
    # failure is caught so it never breaks startup.
    try:
        ext = importlib.import_module("error_tracking_ext")
    except ImportError:
        return
    try:
        ext.enrich()
    except Exception:
        logging.getLogger(__name__).exception(
            "error_tracking_ext.enrich() raised; continuing without enrichment"
        )


def capture_exception(e):
    if os.environ.get("SENTRY_DSN"):
        sentry_sdk.capture_exception(e)
