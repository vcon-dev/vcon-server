# This is the SCITT link. It is the same as the Deepgram link, except it
# does not use Deepgram's API. Instead, it uses the SCITT API. 

""" Module for creating a SCITT signed statement """

import hashlib
import json
import argparse

from typing import Optional

from pycose.messages import Sign1Message
from pycose.headers import Algorithm, KID, ContentType
from pycose.algorithms import Es256
from pycose.keys.curves import P256
from pycose.keys.keyparam import KpKty, EC2KpD, EC2KpX, EC2KpY, KpKeyOps, EC2KpCurve
from pycose.keys.keytype import KtyEC2
from pycose.keys.keyops import SignOp, VerifyOp
from pycose.keys import CoseKey

from ecdsa import SigningKey, VerifyingKey
from lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger
import logging
import json
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
    RetryError,
)  # for exponential backoff
from lib.metrics import init_metrics

init_metrics()

logger = init_logger(__name__)

default_options = {
    "signing_key": "scitt-sign",
    "payload": "scitt-payload",
    "feed": "feed",
    "issuer": "issuer",
    "content_type": "application/json",
    "output_file": "signed-statement.cbor",
}

# Feed header label comes from version 2 of the scitt architecture document
# https://www.ietf.org/archive/id/draft-birkholz-scitt-architecture-02.html#name-envelope-and-claim-format
HEADER_LABEL_FEED = 392

# CWT header label comes from version 4 of the scitt architecture document
# https://www.ietf.org/archive/id/draft-ietf-scitt-architecture-04.html#name-issuer-identity
HEADER_LABEL_CWT = 13

# Various CWT header labels come from:
# https://www.rfc-editor.org/rfc/rfc8392.html#section-3.1
HEADER_LABEL_CWT_ISSUER = 1
HEADER_LABEL_CWT_SUBJECT = 2

# CWT CNF header labels come from:
# https://datatracker.ietf.org/doc/html/rfc8747#name-confirmation-claim
HEADER_LABEL_CWT_CNF = 8
HEADER_LABEL_CNF_COSE_KEY = 1


def open_signing_key(key_file: str) -> SigningKey:
    """
    opens the signing key from the key file.
    NOTE: the signing key is expected to be a P-256 ecdsa key in PEM format.
    """
    with open(key_file, encoding="UTF-8") as file:
        signing_key = SigningKey.from_pem(file.read(), hashlib.sha256)
        return signing_key


def open_payload(payload_file: str) -> str:
    """
    opens the payload from the payload file.
    NOTE: the payload is expected to be in json format.
          however, any payload of type bytes is allowed.
    """
    with open(payload_file, encoding="UTF-8") as file:
        payload = json.loads(file.read())

        # convert the payload to a cose sign1 payload
        payload = json.dumps(payload, ensure_ascii=False)

        return payload


def create_signed_statement(
    signing_key: SigningKey,
    payload_text: str,
    include_vcon: bool,
    feed: str,
    issuer: str,
    content_type: str,
) -> bytes:
    """
    creates a signed statement, given the signing_key, payload, feed and issuer
    """

    verifying_key: Optional[VerifyingKey] = signing_key.verifying_key
    assert verifying_key is not None

    # pub key is the x and y parts concatenated
    xy_parts = verifying_key.to_string()

    # ecdsa P256 is 64 bytes
    x_part = xy_parts[0:32]
    y_part = xy_parts[32:64]

    # create a protected header where
    #  the verification key is attached to the cwt claims
    protected_header = {
        Algorithm: Es256,
        KID: b"testkey",
        ContentType: content_type,
        HEADER_LABEL_FEED: feed,
        HEADER_LABEL_CWT: {
            HEADER_LABEL_CWT_ISSUER: issuer,
            HEADER_LABEL_CWT_SUBJECT: feed,
            HEADER_LABEL_CWT_CNF: {
                HEADER_LABEL_CNF_COSE_KEY: {
                    KpKty: KtyEC2,
                    EC2KpCurve: P256,
                    EC2KpX: x_part,
                    EC2KpY: y_part,
                },
            },
        },
    }

    # create the statement as a sign1 message using the protected header and payload
    statement = Sign1Message(phdr=protected_header, payload=payload_text.encode("utf-8"))

    # create the cose_key to sign the statement using the signing key
    cose_key = {
        KpKty: KtyEC2,
        EC2KpCurve: P256,
        KpKeyOps: [SignOp, VerifyOp],
        EC2KpD: signing_key.to_string(),
        EC2KpX: x_part,
        EC2KpY: y_part,
    }

    cose_key = CoseKey.from_dict(cose_key)
    statement.key = cose_key

    # sign and cbor encode the statement.
    # NOTE: the encode() function performs the signing automatically
    signed_statement = statement.encode([None])

    return signed_statement


def run(
    vcon_uuid,
    link_name,
    opts=default_options,
):
    module_name = __name__.split(".")[-1]
    logger.info(f"Starting {module_name}: {link_name} plugin for: {vcon_uuid}")
    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts

    vcon_redis = VconRedis()
    vCon = vcon_redis.get_vcon(vcon_uuid)
    if vCon is None:
        raise ValueError(f"vCon {vcon_uuid} not found in redis")
    
    # Create a signed statement and add it as an attachment to the vCon
    signing_key = open_signing_key(opts["signing_key"])
    payload = open_payload(opts["payload"])
    signed_statement = create_signed_statement(
        signing_key,
        payload,
        include_vcon=True,
        subject=opts["subject"],
        issuer=opts["issuer"],
        content_type=opts["content_type"],
    )
    

    vcon_redis.store_vcon(vCon)
    logger.info(f"Finished analyze - {module_name}:{link_name} plugin for: {vcon_uuid}")

    return vcon_uuid




