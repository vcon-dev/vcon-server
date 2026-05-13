"""Direct-to-Supabase storage module.

Writes vCon directly to the Supabase Postgres schema (vcons + parties +
dialog + analysis + attachments) via a long-lived psycopg2 connection
per worker process. Uses multi-row INSERTs within each vCon for batched
writes and retries forever on connection or query failure (does NOT
DLQ — supabase outages are tolerated by retrying).

Bypasses vcon-mcp HTTP layer entirely.

Options:
    dsn: psycopg2 connection string
        (default postgresql://postgres:postgres@172.21.0.1:54322/postgres)
    connect_timeout: seconds for new connection (default 10)
    statement_timeout_ms: postgres statement_timeout in ms (default 60000)
    retry_initial_backoff_s: starting backoff after a failure (default 0.5)
    retry_max_backoff_s: cap on backoff between retries (default 30.0)
"""
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import psycopg2
import psycopg2.extensions
import psycopg2.extras

# Make every Python dict and list serialize to JSONB automatically. Without
# this, fields like `metadata`, `redacted`, etc. raise
# "can't adapt type 'dict'".
psycopg2.extensions.register_adapter(dict, psycopg2.extras.Json)

from server.lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger
from lib.metrics import record_histogram, increment_counter

logger = init_logger(__name__)

default_options: Dict[str, Any] = {
    "dsn": os.environ.get(
        "SUPABASE_DIRECT_DSN",
        "postgresql://postgres:postgres@172.21.0.1:54322/postgres",
    ),
    "connect_timeout": 10,
    "statement_timeout_ms": 60000,
    "retry_initial_backoff_s": 0.5,
    "retry_max_backoff_s": 30.0,
}

_conn_lock = threading.Lock()
_conn: Optional[psycopg2.extensions.connection] = None


def _open_connection(opts: Dict[str, Any]) -> psycopg2.extensions.connection:
    conn = psycopg2.connect(
        opts["dsn"],
        connect_timeout=opts.get("connect_timeout", 10),
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=3,
        application_name="conserver-supabase-direct",
    )
    conn.autocommit = False
    with conn.cursor() as cur:
        cur.execute(
            f"SET statement_timeout = {int(opts.get('statement_timeout_ms', 60000))}"
        )
    conn.commit()
    return conn


def _get_connection(opts: Dict[str, Any]) -> psycopg2.extensions.connection:
    """Return a live persistent connection. Reconnects forever on failure."""
    global _conn
    backoff = opts.get("retry_initial_backoff_s", 0.5)
    max_backoff = opts.get("retry_max_backoff_s", 30.0)
    while True:
        with _conn_lock:
            if _conn is not None and not _conn.closed:
                return _conn
            try:
                _conn = _open_connection(opts)
                logger.info("supabase_direct: connection (re)established")
                return _conn
            except Exception as e:
                logger.warning(
                    f"supabase_direct: connect failed ({e}); retrying in {backoff:.1f}s"
                )
        time.sleep(backoff)
        backoff = min(backoff * 2, max_backoff)


def _drop_connection() -> None:
    global _conn
    with _conn_lock:
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None


def _jsonb(v: Any) -> Optional[psycopg2.extras.Json]:
    return psycopg2.extras.Json(v) if v is not None else None


def _to_int_list(v: Any) -> Optional[list]:
    if v is None:
        return None
    if isinstance(v, list):
        return v
    return [v]


def _to_text_body(v: Any) -> Any:
    """Serialize list/dict bodies to JSON. Pass strings through.

    Postgres TEXT columns accept anything as bytes, but psycopg2's default
    adapter renders Python lists as Postgres array literals ({a,b}) — which
    is wrong for our schema where body is a JSON string.
    """
    if v is None:
        return None
    if isinstance(v, (list, dict)):
        import json as _json
        return _json.dumps(v)
    return v


def _write_vcon(conn: psycopg2.extensions.connection, d: Dict[str, Any]) -> None:
    """Write one vCon (and its child rows) in a single transaction."""
    parties = d.get("parties") or []
    dialog = d.get("dialog") or []
    analysis = d.get("analysis") or []
    attachments = d.get("attachments") or []

    vcon_uuid = d["uuid"]
    now_iso = datetime.now(timezone.utc).isoformat()
    created_at = d.get("created_at") or now_iso
    vcon_version = d.get("vcon") or "0.3.0"

    with conn.cursor() as cur:
        # Upsert the parent vcons row. id == uuid by convention (matches
        # createVCon in vcon-mcp).
        cur.execute(
            """
            INSERT INTO vcons (id, uuid, vcon_version, subject, created_at,
                               redacted, appended, group_data,
                               extensions, must_support)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (uuid) DO UPDATE SET
                vcon_version = EXCLUDED.vcon_version,
                subject      = EXCLUDED.subject,
                updated_at   = now(),
                redacted     = EXCLUDED.redacted,
                appended     = EXCLUDED.appended,
                group_data   = EXCLUDED.group_data,
                extensions   = EXCLUDED.extensions,
                must_support = EXCLUDED.must_support
            """,
            (
                vcon_uuid,
                vcon_uuid,
                vcon_version,
                d.get("subject"),
                created_at,
                _jsonb(d.get("redacted") or {}),
                _jsonb(d.get("appended") or {}),
                _jsonb(d.get("group") or []),
                d.get("extensions") or [],
                d.get("must_support") or [],
            ),
        )

        # Replace children to keep behavior aligned with the upsert path
        # used by vcon-mcp / ingest-vcon edge function.
        cur.execute("DELETE FROM parties WHERE vcon_id = %s", (vcon_uuid,))
        cur.execute("DELETE FROM dialog WHERE vcon_id = %s", (vcon_uuid,))
        cur.execute("DELETE FROM analysis WHERE vcon_id = %s", (vcon_uuid,))
        cur.execute("DELETE FROM attachments WHERE vcon_id = %s", (vcon_uuid,))

        if parties:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO parties (vcon_id, party_index, tel, sip, stir,
                                     mailto, name, did, validation, jcard,
                                     gmlpos, civicaddress, timezone, uuid,
                                     metadata)
                VALUES %s
                """,
                [
                    (
                        vcon_uuid, i,
                        p.get("tel"), p.get("sip"), p.get("stir"),
                        p.get("mailto"), p.get("name"), p.get("did"),
                        p.get("validation"), _jsonb(p.get("jcard")),
                        p.get("gmlpos"), _jsonb(p.get("civicaddress")),
                        p.get("timezone"), p.get("uuid"),
                        _jsonb(p.get("meta") or {}),
                    )
                    for i, p in enumerate(parties)
                ],
            )

        if dialog:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO dialog (vcon_id, dialog_index, type, start_time,
                                    duration_seconds, parties, originator,
                                    mediatype, filename, body, encoding, url,
                                    disposition, transferee, transferor,
                                    transfer_target, original, consultation,
                                    target_dialog, metadata)
                VALUES %s
                """,
                [
                    (
                        vcon_uuid, i,
                        dx.get("type") or "recording",
                        dx.get("start"),
                        dx.get("duration"),
                        _to_int_list(dx.get("parties")),
                        dx.get("originator"),
                        dx.get("mimetype"),
                        dx.get("filename"),
                        _to_text_body(dx.get("body")),
                        dx.get("encoding"),
                        dx.get("url"),
                        dx.get("disposition"),
                        dx.get("transferee"),
                        dx.get("transferor"),
                        _to_int_list(dx.get("transfer_target")),
                        _to_int_list(dx.get("original")),
                        _to_int_list(dx.get("consultation")),
                        _to_int_list(dx.get("target_dialog")),
                        _jsonb(dx.get("meta") or {}),
                    )
                    for i, dx in enumerate(dialog)
                ],
            )

        if analysis:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO analysis (vcon_id, analysis_index, type, vendor,
                                      created_at,
                                      dialog_indices, body, encoding, schema,
                                      product, mediatype, filename, url,
                                      content_hash, confidence, metadata)
                VALUES %s
                """,
                [
                    (
                        vcon_uuid, i,
                        a.get("type") or "unknown",
                        a.get("vendor") or "unknown",
                        a.get("created_at") or now_iso,
                        _to_int_list(a.get("dialog")),
                        _to_text_body(a.get("body")),
                        a.get("encoding"),
                        a.get("schema"),
                        a.get("product"),
                        a.get("mediatype"),
                        a.get("filename"),
                        a.get("url"),
                        a.get("content_hash"),
                        a.get("confidence"),
                        _jsonb(a.get("extra") or a.get("metadata") or {}),
                    )
                    for i, a in enumerate(analysis)
                ],
            )

        if attachments:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO attachments (vcon_id, attachment_index, type, body,
                                         encoding, url, party, dialog,
                                         mimetype, filename, metadata)
                VALUES %s
                """,
                [
                    (
                        vcon_uuid, i,
                        a.get("type"),
                        _to_text_body(a.get("body")),
                        a.get("encoding"),
                        a.get("url"),
                        a.get("party"),
                        a.get("dialog"),
                        # vcon dict may use either "mediatype" (newer spec)
                        # or "mimetype" (older). Accept both.
                        a.get("mediatype") or a.get("mimetype"),
                        a.get("filename"),
                        _jsonb(a.get("extra") or {}),
                    )
                    for i, a in enumerate(attachments)
                ],
            )

    conn.commit()


def save(vcon_uuid: str, opts: Dict[str, Any] = None) -> None:
    """Storage entry point. Retries forever on supabase failures."""
    merged = {**default_options, **(opts or {})}
    started = time.time()

    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)
    if vcon is None:
        logger.error(f"supabase_direct: vcon {vcon_uuid} not found in redis")
        return

    d = vcon.to_dict()
    if "vcon" not in d or d.get("vcon") == "0.0.1":
        d["vcon"] = "0.3.0"

    backoff = merged.get("retry_initial_backoff_s", 0.5)
    max_backoff = merged.get("retry_max_backoff_s", 30.0)
    while True:
        try:
            conn = _get_connection(merged)
            _write_vcon(conn, d)
            duration = round(time.time() - started, 4)
            record_histogram("conserver.supabase_direct.duration", duration)
            increment_counter("conserver.supabase_direct.success", 1)
            return
        except Exception as e:
            increment_counter("conserver.supabase_direct.errors", 1)
            logger.warning(
                f"supabase_direct: write failed for {vcon_uuid}: {e}; "
                f"retrying in {backoff:.1f}s"
            )
            _drop_connection()
            time.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)
