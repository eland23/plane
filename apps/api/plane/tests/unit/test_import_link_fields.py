"""Public native link construction/serialization, independent of a database fixture."""
import pytest
from plane.db.models import IssueLink
from plane.app.serializers import IssueLinkSerializer
from plane.api.serializers.issue import IssueLinkSerializer as PublicIssueLinkSerializer
from plane.space.serializer.issue import IssueLinkSerializer as SpaceIssueLinkSerializer


@pytest.mark.parametrize("serializer_class", [IssueLinkSerializer, PublicIssueLinkSerializer, SpaceIssueLinkSerializer])
def test_native_link_retains_original_source_identity_and_api_marks_it_read_only(serializer_class):
    link=IssueLink(title='Original resource',url='https://example.invalid/original',
                   external_source='linear:fixture-org',external_id='original-attachment')
    serializer=serializer_class(link)
    assert serializer.data['url']=='https://example.invalid/original'
    assert serializer.data['external_source']=='linear:fixture-org'
    assert serializer.data['external_id']=='original-attachment'
    assert serializer.fields['external_id'].read_only is True
    assert serializer.fields['external_source'].read_only is True
