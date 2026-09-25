import pytest
from lib.links.filters import is_included
import vcon


@pytest.mark.asyncio
async def test_is_included():
    _vcon = vcon.Vcon.build_new()
    _vcon.add_attachment(
        body=["category:12"],
        type="tags",
    )

    assert is_included(None, _vcon)
    assert is_included({}, _vcon)
    assert is_included(
        {
            "only_if": {
                "section": "attachments",
                "type": "tags",
                "includes": "category:12",
            }
        },
        _vcon,
    )
    assert not is_included(
        {
            "only_if": {
                "section": "attachments",
                "type": "tags",
                "includes": "category:1",
            }
        },
        _vcon,
    )
    assert not is_included(
        {
            "only_if": {
                "section": "analysis",
                "type": "customer_frustration",
                "includes": "NEEDS REVIEW",
            }
        },
        _vcon,
    )

    _vcon = vcon.Vcon.build_new()
    _vcon.add_analysis(
        type="customer_frustration",
        body='"foo bar NEEDS REVIEW bar foo"',
        dialog=0,
        vendor="FooBar Inc.",
        encoding="json"
    )
    assert is_included(
        {
            "only_if": {
                "section": "analysis",
                "type": "customer_frustration",
                "includes": "NEEDS REVIEW",
            }
        },
        _vcon,
    )
    assert not is_included(
        {
            "only_if": {
                "section": "analysis",
                "type": "customer_frustration_123",
                "includes": "NEEDS REVIEW",
            }
        },
        _vcon,
    )


@pytest.mark.asyncio
async def test_is_included_matches_raw_dict_body():
    # draft-ietf-vcon-vcon-core-04 §2.3.2: with encoding "json" the body is
    # the JSON value itself (a dict here), not a string. The substring match
    # must still find tokens inside it via its JSON-serialized form.
    _vcon = vcon.Vcon.build_new()
    _vcon.add_analysis(
        type="customer_frustration",
        body={"verdict": "NEEDS REVIEW", "score": 0.9},
        dialog=0,
        vendor="FooBar Inc.",
    )
    assert is_included(
        {
            "only_if": {
                "section": "analysis",
                "type": "customer_frustration",
                "includes": "NEEDS REVIEW",
            }
        },
        _vcon,
    )
    assert not is_included(
        {
            "only_if": {
                "section": "analysis",
                "type": "customer_frustration",
                "includes": "ALL CLEAR",
            }
        },
        _vcon,
    )


@pytest.mark.asyncio
async def test_is_included_matches_raw_list_attachment_body():
    _vcon = vcon.Vcon.build_new()
    _vcon.add_attachment(
        body=["category:12", "category:99"],
        type="tags2",
    )
    assert is_included(
        {
            "only_if": {
                "section": "attachments",
                "type": "tags2",
                "includes": "category:99",
            }
        },
        _vcon,
    )
