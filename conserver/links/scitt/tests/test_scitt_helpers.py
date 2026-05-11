import base64
import hashlib
import importlib
from types import SimpleNamespace
from unittest.mock import Mock, mock_open, patch

import cbor2
import pytest
from ecdsa import SigningKey

from links import scitt as scitt_module


chss = importlib.import_module("links.scitt.create_hashed_signed_statement")


def test_open_signing_key_and_read_file_delegate_to_file_io():
    with patch("builtins.open", mock_open(read_data="pem-data")), patch.object(
        chss.SigningKey, "from_pem", return_value="signing-key"
    ) as mock_from_pem:
        assert chss.open_signing_key("/tmp/key.pem") == "signing-key"
        mock_from_pem.assert_called_once_with("pem-data", hashlib.sha256)

    with patch("builtins.open", mock_open(read_data="payload-data")):
        assert chss.read_file("/tmp/payload.txt") == "payload-data"


@pytest.mark.parametrize(
    ("alg", "expected_label"),
    [
        ("SHA-256", chss.HEADER_LABEL_COSE_ALG_SHA256),
        ("SHA-384", chss.HEADER_LABEL_COSE_ALG_SHA384),
        ("SHA-512", chss.HEADER_LABEL_COSE_ALG_SHA512),
    ],
)
def test_create_hashed_signed_statement_builds_expected_headers(alg, expected_label):
    signing_key = SigningKey.generate()
    fake_message = Mock()
    fake_message.encode.return_value = b"signed"

    with patch.object(chss, "Sign1Message", return_value=fake_message) as mock_message, patch.object(
        chss.CoseKey, "from_dict", return_value="cose-key"
    ):
        result = chss.create_hashed_signed_statement(
            issuer="issuer",
            signing_key=signing_key,
            subject="subject",
            kid=b"kid-1",
            meta_map={"foo": "bar"},
            payload=b"payload-hash",
            payload_hash_alg=alg,
            payload_location="",
            pre_image_content_type="application/json",
        )

    assert result == b"signed"
    protected_header = mock_message.call_args.kwargs["phdr"]
    assert protected_header[chss.HEADER_LABEL_PAYLOAD_HASH_ALGORITHM] == expected_label
    assert protected_header[chss.HEADER_LABEL_CWT][chss.HEADER_LABEL_CWT_ISSUER] == "issuer"
    assert protected_header[chss.HEADER_LABEL_CWT][chss.HEADER_LABEL_CWT_SUBJECT] == "subject"
    assert protected_header[chss.HEADER_LABEL_META_MAP] == {"foo": "bar"}
    assert fake_message.key == "cose-key"


def test_main_reads_meta_map_and_payload_then_writes_output():
    args = SimpleNamespace(
        content_type="application/json",
        issuer="issuer-1",
        kid="kid-1",
        meta_map_file="/tmp/meta.json",
        output_file="/tmp/out.cbor",
        payload_file="/tmp/payload.json",
        payload_location="https://example.com/payload.json",
        signing_key_file="/tmp/key.pem",
        subject="subject-1",
    )
    output_handle = mock_open().return_value

    with patch.object(chss.argparse.ArgumentParser, "parse_args", return_value=args), patch.object(
        chss, "read_file", side_effect=['{"foo": "bar"}', '{"hello": "world"}']
    ), patch.object(chss, "open_signing_key", return_value="signing-key"), patch.object(
        chss, "create_hashed_signed_statement", return_value=b"signed-bytes"
    ) as mock_create, patch("builtins.open", mock_open()) as mocked_open:
        chss.main()

    mock_create.assert_called_once()
    assert mock_create.call_args.kwargs["meta_map"] == {"foo": "bar"}
    assert mock_create.call_args.kwargs["payload"] == hashlib.sha256(b'{"hello": "world"}').digest()
    mocked_open.assert_called_with("/tmp/out.cbor", "wb")
    mocked_open().write.assert_called_once_with(b"signed-bytes")


def test_compute_root_and_verify_cose_receipt_paths():
    leaf_hash = hashlib.sha256(scitt_module._LEAF_PREFIX + b"statement").digest()
    sibling = b"s" * 32
    expected_root = hashlib.sha256(scitt_module._NODE_PREFIX + leaf_hash + sibling).digest()

    assert scitt_module._compute_root(leaf_hash, 0, 2, [sibling]) == expected_root

    msg = Mock()
    msg.uhdr = {396: {-1: [cbor2.dumps((2, 0, [sibling]))]}}
    msg.verify_signature.return_value = True
    config_resp = Mock(content=cbor2.dumps({"jwks_uri": "https://example.com/jwks"}))
    config_resp.raise_for_status = Mock()
    x = base64.urlsafe_b64encode(b"x" * 32).decode().rstrip("=")
    y = base64.urlsafe_b64encode(b"y" * 32).decode().rstrip("=")
    jwks_resp = Mock()
    jwks_resp.raise_for_status = Mock()
    jwks_resp.json.return_value = {"keys": [{"x": x, "y": y}]}

    with patch.object(scitt_module.Sign1Message, "decode", return_value=msg), patch(
        "links.scitt.requests.get", side_effect=[config_resp, jwks_resp]
    ):
        scitt_module._verify_cose_receipt(b"receipt", b"statement", "https://example.com")

    msg.verify_signature.assert_called_once_with(detached_payload=expected_root)

    missing_proof_msg = Mock()
    missing_proof_msg.uhdr = {396: {-1: []}}
    with patch.object(scitt_module.Sign1Message, "decode", return_value=missing_proof_msg):
        with pytest.raises(ValueError, match="missing inclusion proof"):
            scitt_module._verify_cose_receipt(b"receipt", b"statement", "https://example.com")


def test_run_uses_inline_signing_key_and_handles_failure_counters():
    vcon = Mock()
    vcon.hash = "deadbeef"
    vcon.parties = [{"tel": "+15551234567"}, {"tel": "+15557654321"}]
    vcon.add_analysis = Mock()
    redis = Mock(get_vcon=Mock(return_value=vcon), store_vcon=Mock())
    opts = {
        **scitt_module.default_options,
        "signing_key_pem": base64.b64encode(b"pem-data").decode(),
    }

    with patch("links.scitt.VconRedis", return_value=redis), patch.object(
        scitt_module.SigningKey, "from_pem", return_value="signing-key"
    ), patch("links.scitt.create_hashed_signed_statement.create_hashed_signed_statement", return_value=b"signed"), patch(
        "links.scitt.register_signed_statement.register_statement",
        side_effect=[{"entry_id": "1", "receipt": b"r1"}, {"entry_id": "2", "receipt": b"r2"}],
    ), patch("links.scitt._verify_cose_receipt"):
        result = scitt_module.run("vc-1", "scitt_created", opts)

    assert result == "vc-1"
    assert vcon.add_analysis.call_args.kwargs["body"] == [
        {
            "entry_id": "1",
            "cose_receipt": base64.b64encode(b"r1").decode(),
            "vcon_operation": "vcon_created",
            "subject": "tel:+15551234567",
            "vcon_hash": "deadbeef",
            "scrapi_url": scitt_module.default_options["scrapi_url"],
        },
        {
            "entry_id": "2",
            "cose_receipt": base64.b64encode(b"r2").decode(),
            "vcon_operation": "vcon_created",
            "subject": "tel:+15557654321",
            "vcon_hash": "deadbeef",
            "scrapi_url": scitt_module.default_options["scrapi_url"],
        },
    ]

    with patch("links.scitt.VconRedis", return_value=redis), patch.object(
        scitt_module.SigningKey, "from_pem", return_value="signing-key"
    ), patch(
        "links.scitt.create_hashed_signed_statement.create_hashed_signed_statement",
        side_effect=RuntimeError("create failed"),
    ), patch("links.scitt.increment_counter") as mock_counter:
        with pytest.raises(RuntimeError, match="create failed"):
            scitt_module.run("vc-1", "scitt_created", opts)
    mock_counter.assert_called_once_with(
        "conserver.link.scitt.statement_creation_failures",
        attributes={"link.name": "scitt_created", "vcon.uuid": "vc-1"},
    )

    with patch("links.scitt.VconRedis", return_value=redis), patch.object(
        scitt_module.SigningKey, "from_pem", return_value="signing-key"
    ), patch("links.scitt.create_hashed_signed_statement.create_hashed_signed_statement", return_value=b"signed"), patch(
        "links.scitt.register_signed_statement.register_statement",
        side_effect=RuntimeError("register failed"),
    ), patch("links.scitt.increment_counter") as mock_counter:
        with pytest.raises(RuntimeError, match="register failed"):
            scitt_module.run("vc-1", "scitt_created", opts)
    mock_counter.assert_called_once_with(
        "conserver.link.scitt.registration_failures",
        attributes={"link.name": "scitt_created", "vcon.uuid": "vc-1"},
    )
