import vcon_fixture
import vcon
import json
import pytest

_vcon = vcon_fixture.generate_mock_vcon()


def test_encoding():
    print("test_vcon:", _vcon)
    test_vcon = vcon.Vcon(_vcon)

    # Spec (draft-ietf-vcon-vcon-core-02 §2.3.2): body is always a String. A
    # dict/list passed in for convenience is JSON-encoded at the boundary and
    # the encoding is forced to "json".
    test_vcon.add_attachment(
        type="test_encoding_dict_coerced",
        body={"key": "value"},
        encoding="json",
    )
    assert test_vcon.find_attachment_by_purpose("test_encoding_dict_coerced") == {
        "type": "test_encoding_dict_coerced",
        "body": json.dumps({"key": "value"}),
        "encoding": "json",
    }

    test_vcon.add_attachment(
        type="test_encoding_list_coerced",
        body=["key", "value"],
        encoding="base64url",
    )
    assert test_vcon.find_attachment_by_purpose("test_encoding_list_coerced") == {
        "type": "test_encoding_list_coerced",
        "body": json.dumps(["key", "value"]),
        "encoding": "json",
    }

    # Invalid JSON string with encoding=json still raises.
    with pytest.raises(Exception):
        test_vcon.add_attachment(
            type="test_encoding_bad_json",
            body="not-valid-json",
            encoding="json",
        )

    # Invalid base64url string with encoding=base64url still raises.
    with pytest.raises(Exception):
        test_vcon.add_attachment(
            type="test_encoding_bad_b64",
            body="not valid base64!!!",
            encoding="base64url",
        )

    test_vcon.add_attachment(
            type= "test_encoding_str",
            body= "String value",
            encoding= "none",
    )
    assert test_vcon.find_attachment_by_purpose("test_encoding_str") == {
        "type": "test_encoding_str",
        "body": "String value",
        "encoding": "none",
    }

    test_vcon.add_attachment(
            type= "test_encoding_json",
            body= json.dumps({"key": "value"}),
            encoding= "json",
        
    )
    assert test_vcon.find_attachment_by_purpose("test_encoding_json") == {
        "type": "test_encoding_json",
        "body": json.dumps({"key": "value"}),
        "encoding": "json",
    }
