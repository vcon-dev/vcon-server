import base64
import hashlib
import cbor2
import requests
from ecdsa import SigningKey
from pycose.messages import Sign1Message
from pycose.keys.ec2 import EC2Key
from pycose.keys.curves import P256
from links.scitt import create_hashed_signed_statement, register_signed_statement
from fastapi import HTTPException
from lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger
from starlette.status import HTTP_404_NOT_FOUND

logger = init_logger(__name__)

# Increment for any API/attribute changes
link_version = "0.3.0"

default_options = {
    "scrapi_url": "http://scittles:8000",
    "signing_key_pem": None,           # Base64-encoded PEM (preferred for containers/k8s)
    "signing_key_path": "/etc/scitt/signing-key.pem",  # Fallback for local dev
    "issuer": "conserver",
    "key_id": "conserver-key-1",
    "vcon_operation": "vcon_created",
    "store_receipt": True,
}

_LEAF_PREFIX = b"\x00"
_NODE_PREFIX = b"\x01"


def _compute_root(leaf_hash: bytes, leaf_index: int, tree_size: int, siblings: list) -> bytes:
    """Walk RFC 9162 inclusion proof and return the recomputed Merkle root."""
    current = leaf_hash
    current_index = leaf_index
    current_size = tree_size
    proof_idx = 0
    while current_size > 1:
        if current_index == current_size - 1 and current_size % 2 == 1:
            current_index //= 2
            current_size = (current_size + 1) // 2
            continue
        sibling = siblings[proof_idx]
        proof_idx += 1
        if current_index % 2 == 0:
            current = hashlib.sha256(_NODE_PREFIX + current + sibling).digest()
        else:
            current = hashlib.sha256(_NODE_PREFIX + sibling + current).digest()
        current_index //= 2
        current_size = (current_size + 1) // 2
    return current


def _verify_cose_receipt(receipt_bytes: bytes, statement_hash: bytes, scrapi_url: str) -> None:
    """
    Verify a COSE receipt before storing it.

    1. Parse COSE Sign1 → extract inclusion proof (leaf_index, tree_size, siblings)
    2. Compute leaf_hash = SHA-256(0x00 || statement_hash) per RFC 9162
    3. Walk proof → recompute root_hash
    4. Fetch transparency service public key from JWKS
    5. Verify COSE Sign1 signature with recomputed root_hash as detached payload

    Raises ValueError if any step fails.
    """
    # Step 1: parse receipt and extract inclusion proof
    msg = Sign1Message.decode(receipt_bytes)
    proofs_map = msg.uhdr.get(396, {})
    proofs_raw = proofs_map.get(-1, [])
    if not proofs_raw:
        raise ValueError("cose_receipt is missing inclusion proof (uhdr label 396/-1)")
    tree_size, leaf_index, siblings = cbor2.loads(proofs_raw[0])

    # Step 2: leaf hash per RFC 9162 (0x00 || statement_hash)
    leaf_hash = hashlib.sha256(_LEAF_PREFIX + statement_hash).digest()

    # Step 3: recompute Merkle root from inclusion proof
    root_hash = _compute_root(leaf_hash, leaf_index, tree_size, siblings)

    # Step 4: fetch JWKS — discover jwks_uri from transparency-configuration first
    config_resp = requests.get(
        f"{scrapi_url}/.well-known/transparency-configuration", timeout=10
    )
    config_resp.raise_for_status()
    config = cbor2.loads(config_resp.content)
    jwks_uri = config.get("jwks_uri") or f"{scrapi_url}/jwks"
    jwks_resp = requests.get(jwks_uri, timeout=10)
    jwks_resp.raise_for_status()
    jwk = jwks_resp.json()["keys"][0]

    x_bytes = base64.urlsafe_b64decode(jwk["x"] + "==")
    y_bytes = base64.urlsafe_b64decode(jwk["y"] + "==")
    cose_key = EC2Key(crv=P256, x=x_bytes, y=y_bytes)

    # Step 5: verify COSE Sign1 signature with recomputed root as detached payload
    msg.key = cose_key
    if not msg.verify_signature(detached_payload=root_hash):
        raise ValueError("cose_receipt signature verification failed — receipt is not authentic")


def run(
    vcon_uuid: str,
    link_name: str,
    opts: dict = default_options
) -> str:
    """
    SCITT lifecycle registration link.

    Creates a COSE Sign1 signed statement from the vCon hash and registers
    it on a SCRAPI-compatible Transparency Service (SCITTLEs).

    The vcon_operation option controls the lifecycle event type:
    - "vcon_created": registered before transcription
    - "vcon_enhanced": registered after transcription

    Args:
        vcon_uuid: UUID of the vCon to process.
        link_name: Name of the link instance (for logging).
        opts: Configuration options.

    Returns:
        The UUID of the processed vCon.
    """
    module_name = __name__.split(".")[-1]
    logger.info(f"Starting {module_name}: {link_name} for: {vcon_uuid}")
    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts

    # Get the vCon from Redis
    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)
    if not vcon:
        logger.info(f"{link_name}: vCon not found: {vcon_uuid}")
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=f"vCon not found: {vcon_uuid}"
        )

    # Build per-participant SCITT registrations
    payload = vcon.hash
    operation = opts["vcon_operation"]

    if opts.get("signing_key_pem"):
        pem = base64.b64decode(opts["signing_key_pem"]).decode("utf-8")
        signing_key = SigningKey.from_pem(pem, hashlib.sha256)
    else:
        signing_key = create_hashed_signed_statement.open_signing_key(opts["signing_key_path"])

    # Collect tel URIs from parties (Party objects use attrs, dicts use keys)
    party_tels = []
    for party in (vcon.parties or []):
        tel = party.get("tel") if isinstance(party, dict) else getattr(party, "tel", None)
        if tel:
            party_tels.append(tel)
        else:
            logger.warning(f"{link_name}: party without tel in {vcon_uuid}, skipping")

    # Fall back to vcon:// subject if no parties have tel
    if not party_tels:
        party_tels = [None]

    scrapi_url = opts["scrapi_url"]
    receipts = []

    for tel in party_tels:
        if tel:
            subject = f"tel:{tel}"
            operation_payload = f"{payload}:{operation}:{tel}"
            meta_map = {"vcon_operation": operation, "party_tel": tel}
        else:
            subject = f"vcon://{vcon_uuid}"
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
        logger.info(f"{link_name}: Created signed statement for {vcon_uuid} subject={subject} ({operation})")

        result = register_signed_statement.register_statement(scrapi_url, signed_statement)
        logger.info(f"{link_name}: Registered entry_id={result['entry_id']} subject={subject} for {vcon_uuid}")

        statement_hash = hashlib.sha256(operation_payload.encode("utf-8")).digest()
        _verify_cose_receipt(result["receipt"], statement_hash, scrapi_url)
        logger.info(f"{link_name}: Receipt verified for entry_id={result['entry_id']}")

        receipts.append({
            "entry_id": result["entry_id"],
            "cose_receipt": base64.b64encode(result["receipt"]).decode(),
            "vcon_operation": operation,
            "subject": subject,
            "vcon_hash": payload,
            "scrapi_url": scrapi_url,
        })

    # Store receipts as analysis entry on the vCon
    if opts.get("store_receipt", True):
        vcon.add_analysis(
            type="scitt_receipt",
            dialog=0,
            vendor="scittles",
            body=receipts if len(receipts) > 1 else receipts[0],
        )
        vcon_redis.store_vcon(vcon)
        logger.info(f"{link_name}: Stored {len(receipts)} SCITT receipt(s) for {vcon_uuid}")

    return vcon_uuid
