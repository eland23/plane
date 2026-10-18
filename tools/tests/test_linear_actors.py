"""Source actor export/readback contracts use synthetic identities only."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from linear_export import SourceError
from test_linear_coverage import snapshot
from test_linear_associations import TEAM, ORG

ACTOR = '90000000-0000-0000-0000-000000000019'


class Actors:
    def __init__(self, active=False, denied=False):
        self.active, self.denied, self.calls = active, denied, []

    def __call__(self, query, variables):
        self.calls.append((query, variables))
        if self.denied:
            return {'errors': [{'message': 'private provider details'}]}
        return {'data': {'organization': {'id': ORG}, 'user': {
            'id': variables['id'], 'organization': {'id': ORG}, 'name': 'Inactive fixture author',
            'displayName': 'Fixture', 'email': 'fixture@example.invalid', 'active': self.active,
            'createdAt': '2020-01-01T00:00:00Z', 'updatedAt': '2026-01-01T00:00:00Z', 'archivedAt': None}}}


def test_original_inactive_actor_is_archived_without_invitation_and_verified_on_readback(tmp_path):
    from linear_actors import export_actors, read_actors
    from linear_coverage import read_bundle
    issues, associations = snapshot(tmp_path/'source', extra_fields={'creator': {'id': ACTOR}})
    provider=Actors();output=tmp_path/'actors'
    result=export_actors(provider,issues,associations,output)
    assert result['counts']=={'archived':1,'blocked':0}
    assert len(provider.calls)==1 and provider.calls[0][1]=={'id':ACTOR}
    assert all('mutation' not in q.lower() for q,_ in provider.calls)
    actors,manifest_hash=read_actors(output,read_bundle(issues,associations))
    assert actors[ACTOR]['active'] is False and actors[ACTOR]['name']=='Inactive fixture author'
    assert len(manifest_hash)==64
    assert output.stat().st_mode & 0o777==0o700
    assert all(p.stat().st_mode & 0o777==0o600 for p in output.iterdir())
    before=(output/'manifest.json').read_bytes()
    with pytest.raises(SourceError):export_actors(provider,issues,associations,output)
    assert (output/'manifest.json').read_bytes()==before


def test_denied_actor_remains_named_without_provider_error_leak(tmp_path):
    from linear_actors import export_actors, read_actors
    from linear_coverage import read_bundle
    source=snapshot(tmp_path/'source', extra_fields={'creator': {'id': ACTOR}})
    output=tmp_path/'actors';result=export_actors(Actors(denied=True),*source,output)
    assert result['counts']=={'archived':0,'blocked':1}
    assert result['actors'][0]['source_uuid']==ACTOR and result['actors'][0]['status']=='BLOCKED'
    assert 'private provider details' not in (output/'manifest.json').read_text()
    assert read_actors(output,read_bundle(*source))[0]=={}


def test_actor_page_tampering_and_foreign_organization_are_rejected(tmp_path):
    from linear_actors import export_actors, read_actors
    from linear_coverage import read_bundle
    source=snapshot(tmp_path/'source', extra_fields={'creator': {'id': ACTOR}})
    output=tmp_path/'actors';export_actors(Actors(),*source,output)
    manifest=json.loads((output/'manifest.json').read_text());page=output/manifest['actors'][0]['file']
    page.write_text('{}')
    with pytest.raises(SourceError,match='ACTOR_CHECKSUM'):read_actors(output,read_bundle(*source))
    def foreign(q,v):
        result=Actors()(q,v);result['data']['user']['organization']['id']=TEAM;return result
    with pytest.raises(SourceError,match='ACTOR_SCOPE'):export_actors(foreign,*source,tmp_path/'foreign')


def test_verified_actor_supplement_resolves_original_creator_in_dry_run_and_rejects_tamper_before_ssh(tmp_path):
    from linear_actors import export_actors
    from linear_import_plan import plan_import
    from test_linear_import_plan import inputs, Destination, WS
    source=inputs(tmp_path,extra_fields={'creator':{'id':ACTOR}})
    directory=tmp_path/'actors';export_actors(Actors(),*source[:2],directory)
    report=plan_import(*source,Destination(),WS,tmp_path/'plan',actors=directory)
    assert report['unresolved_references']==[]
    links=[link for link in report['links'] if link['field']=='creator']
    assert len(links)==6 and all(link['disposition']=='archive' for link in links)
    assert report['counts']['user']==1 and report['actor_manifest_sha256']
    assert report['can_import'] is False
    manifest=json.loads((directory/'manifest.json').read_text());(directory/manifest['actors'][0]['file']).write_text('{}')
    reader=Destination()
    with pytest.raises(SourceError,match='ACTOR_CHECKSUM'):
        plan_import(*source,reader,WS,tmp_path/'bad',actors=directory)
    assert reader.calls==0


def test_untrusted_rich_content_cannot_expand_actor_lookup_scope(tmp_path):
    from linear_actors import export_actors
    source=snapshot(tmp_path/'source',extra_fields={'creator':{'id':ACTOR},'descriptionData':{'user':{'id':'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee'}}})
    provider=Actors();result=export_actors(provider,*source,tmp_path/'actors')
    assert [variables['id'] for _,variables in provider.calls]==[ACTOR]
    assert result['counts']['archived']==1


def test_unavailable_actor_stays_a_blocker_and_cancelled_archive_is_not_consumable(tmp_path):
    from linear_actors import export_actors,read_actors
    from linear_coverage import read_bundle
    from linear_import_plan import plan_import
    from test_linear_import_plan import inputs,Destination,WS
    source=inputs(tmp_path,extra_fields={'creator':{'id':ACTOR}})
    actors=tmp_path/'denied';export_actors(Actors(denied=True),*source[:2],actors)
    report=plan_import(*source,Destination(),WS,tmp_path/'plan',actors=actors)
    assert {'code':'SOURCE_ACTOR_UNAVAILABLE','source_uuid':ACTOR} in report['blockers']
    assert len(report['unresolved_references'])==6
    def cancel(query,variables):raise KeyboardInterrupt()
    with pytest.raises(SourceError,match='CANCELLED'):
        export_actors(cancel,*source[:2],tmp_path/'cancelled')
    with pytest.raises(SourceError,match='INCOMPLETE_ACTOR_INPUT'):
        read_actors(tmp_path/'cancelled',read_bundle(*source[:2]))
