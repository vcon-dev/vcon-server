"""Empty-string url/tel are accepted as absent at ingest; malformed values still fail.

Producers in the field send dialog.url "" for calls with no recording and party
tel "" for unknown numbers. Rejecting those bounced about 4.6% of one
production day's vCons with 422.
"""

import pytest
from pydantic import ValidationError

from api import DialogEntry, PartyEntry


def test_empty_url_and_tel_accepted_unchanged():
    assert DialogEntry(url="").url == ""
    assert PartyEntry(tel="").tel == ""


@pytest.mark.parametrize("model,field,value", [
    (DialogEntry, "url", "not-a-url"),
    (PartyEntry, "tel", "Anonymous"),
])
def test_malformed_values_still_rejected(model, field, value):
    with pytest.raises(ValidationError):
        model(**{field: value})
