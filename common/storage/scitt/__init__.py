import base64
import hashlib
from ecdsa import SigningKey
from links.scitt import create_hashed_signed_statement, register_signed_statement
from lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger

logger = init_logger(__name__)

default_options = {
    "scrapi_url": "http://scittles:8000",
    "signing_key_pem": None,            # Base64-encoded PEM (preferred for containers/k8s)
    "signing_key_path": "/etc/scitt/signing-key.pem",  # Fallback for local dev
    "issuer": "conserver",
    "key_id": "conserver-key-1",
    "operations": ["vcon_enhanced"],
}


def save(vcon_id, opts=default_options):
    """Register per-participant SCITT entries for a vCon as a storage backend.

    Runs in parallel with other storages (e.g. webhook). Does NOT write receipts
    back to the vCon in Redis to avoid races with parallel storage writers.
    The transparency service is the authoritative store for receipts.

    Each party with a tel field gets a separate SCITT entry per operation, with
    subject=tel:+number for portal queryability. Falls back to vcon://{vcon_id}
    when no parties have tel.
    """
    merged = default_options.copy()
    merged.update(opts)
    opts = merged

    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_id)
    if not vcon:
        logger.warning("scitt storage: vCon not found: %s", vcon_id)
        return

    payload = vcon.hash

    if opts.get("signing_key_pem"):
        pem = base64.b64decode(opts["signing_key_pem"]).decode("utf-8")
        signing_key = SigningKey.from_pem(pem, hashlib.sha256)
    else:
        signing_key = create_hashed_signed_statement.open_signing_key(opts["signing_key_path"])

    party_tels = []
    for party in (vcon.parties or []):
        tel = party.get("tel") if isinstance(party, dict) else getattr(party, "tel", None)
        if tel:
            party_tels.append(tel)
        else:
            logger.warning("scitt storage: party without tel in %s, skipping", vcon_id)

    if not party_tels:
        party_tels = [None]

    scrapi_url = opts["scrapi_url"]

    for operation in opts.get("operations", ["vcon_enhanced"]):
        for tel in party_tels:
            if tel:
                subject = f"tel:{tel}"
                operation_payload = f"{payload}:{operation}:{tel}"
                meta_map = {"vcon_operation": operation, "party_tel": tel}
            else:
                subject = f"vcon://{vcon_id}"
                operation_payload = f"{payload}:{operation}"
                meta_map = {"vcon_operation": operation}

            signed_statement = create_hashed_signed_statement.create_hashed_signed_statement(
                issuer=opts["issuer"],
                signing_key=signing_key,
                subject=subject,
                kid=opts["key_id"].encode("utf-8"),
                meta_map=meta_map,
                payload=operation_payload.encode("utf-8"),
                payload_hash_alg="SHA-256",
                payload_location="",
                pre_image_content_type="application/vcon+json",
            )

            result = register_signed_statement.register_statement(scrapi_url, signed_statement)
            logger.info(
                "scitt storage: registered %s entry_id=%s subject=%s for %s",
                operation,
                result["entry_id"],
                subject,
                vcon_id,
            )
