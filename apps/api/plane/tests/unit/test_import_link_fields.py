"""Public native link construction/serialization, independent of a database fixture."""
from plane.db.models import IssueLink
from plane.app.serializers import IssueLinkSerializer


def test_native_link_retains_original_source_identity_and_api_marks_it_read_only():
    link=IssueLink(title='Original resource',url='https://example.invalid/original',
                   external_source='linear:fixture-org',external_id='original-attachment')
    serializer=IssueLinkSerializer(link)
    assert serializer.data['url']=='https://example.invalid/original'
    assert serializer.data['external_source']=='linear:fixture-org'
    assert serializer.data['external_id']=='original-attachment'
    assert serializer.fields['external_id'].read_only is True
    assert serializer.fields['external_source'].read_only is True
