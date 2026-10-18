"""Plan a Linear import against authenticated read-only Plane snapshots."""
import json
import subprocess
from pathlib import Path
from linear_export import SourceError

import argparse
import hashlib
import re
import uuid
from collections import Counter
from linear_export import identity, outside_git, manifest_file, private_file
from linear_coverage import read_bundle, digest, leaves
from linear_associations import read_private
from linear_assets import PROFILE as ASSET_PROFILE, attachment_page, discover, blob_hash, approved_url


class PlaneSnapshotSSH:
    """Fixed host/container; no token creation, API activity logs or write connection."""
    def __init__(self, run=subprocess.run):
        self.run=run

    def capture(self):
        program=Path(__file__).with_name('plane_snapshot.py').read_text()
        try:
            result=self.run(['ssh','-T','-o','BatchMode=yes','-o','ConnectTimeout=8',
                             'root@192.168.1.129','docker exec -i plane-app-api-1 python -'],
                            input=program,text=True,capture_output=True,timeout=90)
            if result.returncode or len(result.stdout.encode())>16*1024*1024:
                raise SourceError('DESTINATION_SNAPSHOT_FAILED')
            value=json.loads(result.stdout)
            if not isinstance(value,dict) or value.get('read_only') is not True:
                raise SourceError('DESTINATION_NOT_READ_ONLY')
            return value
        except (OSError,ValueError,subprocess.SubprocessError):
            raise SourceError('DESTINATION_SNAPSHOT_FAILED') from None


NATIVE = {'team':('projects','project'),'issue':('issues','issue'),'project':('modules','module'),
          'cycle':('cycles','cycle'),'label':('labels','label'),'state':('states','state'),
          'document':('pages','page'),'initiative':('initiatives','initiative'),
          'milestone':('module_milestones','milestone')}

def native_for(kind,record):
    if kind=='attachment':
        try:approved_url(record['url'])
        except SourceError:return ('issue_links','reference_link')
        return ('issue_attachments','issue_attachment')
    return NATIVE.get(kind)


def proposed_id(workspace, organization, kind, key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL,'plane-linear-import-v1/'+workspace+'/'+organization+'/'+kind+'/'+key))


def read_assets(directory,bundle):
    directory=Path(directory).resolve();outside_git(directory)
    if directory.stat().st_mode&0o077:raise SourceError('OUTPUT_PERMISSIONS')
    raw_manifest=read_private(directory/'manifest.json');value=json.loads(raw_manifest)
    if value.get('schema_version')!=1 or any(value.get(k)!=bundle[k] for k in ['organization_id','team_id']):raise SourceError('ASSET_INPUT_SCOPE')
    if value['status'] not in ['COMPLETE_FOR_DISCOVERED_ASSETS','COMPLETE_WITH_BLOCKED_ASSETS'] or value['source_fingerprint']!=bundle['fingerprint'] or value['profile']!=ASSET_PROFILE:
        raise SourceError('ASSET_INPUT_SCOPE')
    ids=sorted(key for kind,key in bundle['entities'] if kind=='issue')
    index,cursor,total=0,None,0;nodes=[];seen=set();cursors=set()
    if not isinstance(value['pages'],list) or len(value['pages'])>10000:raise SourceError('ASSET_INPUT_SHAPE')
    for number,page in enumerate(value['pages'],1):
        if index>=len(ids) or page['file']!='page-%06d.json'%number or page['issue']!=ids[index] or page['cursor']!=cursor:
            raise SourceError('ASSET_INPUT_PROVENANCE')
        raw=read_private(directory/page['file']);total+=len(raw)
        if total>512*1024*1024:raise SourceError('ASSET_INPUT_BUDGET')
        if hashlib.sha256(raw).hexdigest()!=page['sha256']:raise SourceError('CHECKSUM_MISMATCH')
        rows,more,next_cursor=attachment_page(json.loads(raw)['data'],ids[index],bundle['team_id'])
        for row in rows:
            key=identity(row['id'])
            if key in seen:raise SourceError('ASSET_DUPLICATE')
            seen.add(key);nodes.append(row)
        if more:
            if not next_cursor or (index,next_cursor) in cursors or next_cursor==cursor:raise SourceError('ASSET_CURSOR_LOOP')
            cursors.add((index,next_cursor));cursor=next_cursor
        else:index+=1;cursor=None
    if index!=len(ids):raise SourceError('INCOMPLETE_ASSET_INPUT')
    expected,references=discover(bundle,nodes)
    if [(e['key'],e['url'],e['owners']) for e in expected]!=[(e['key'],e['url'],e['owners']) for e in value['assets']] or references!=value['references']:
        raise SourceError('ASSET_INPUT_MAPPING')
    known={p['file'] for p in value['pages']}
    if any(p.name not in known for p in directory.glob('page-*.json')):raise SourceError('ORPHAN_PAGE')
    for entry in value['assets']:
        if entry['status']=='ARCHIVED':
            approved_url(entry['url'])
            sha=entry['sha256']
            if not re.fullmatch('[0-9a-f]{64}',sha) or entry['file']!='sha256-'+sha or entry['reference']!='asset:sha256:'+sha:raise SourceError('ASSET_INPUT_SHAPE')
            if blob_hash(directory/entry['file'],64*1024*1024)!=(entry['size'],sha):raise SourceError('ASSET_CHECKSUM_MISMATCH')
            total+=entry['size']
        elif entry['status']!='BLOCKED' or entry.get('code')!='ASSET_URL_DENIED':raise SourceError('INCOMPLETE_ASSET_INPUT')
        else:
            try:approved_url(entry['url'])
            except SourceError:pass
            else:raise SourceError('ASSET_INPUT_SHAPE')
    if total>512*1024*1024:raise SourceError('ASSET_INPUT_BUDGET')
    if (value['status']=='COMPLETE_FOR_DISCOVERED_ASSETS') != all(e['status']=='ARCHIVED' for e in value['assets']):raise SourceError('INCOMPLETE_ASSET_INPUT')
    return value,hashlib.sha256(raw_manifest).hexdigest(),nodes


def validated_snapshot(value):
    if not isinstance(value,dict) or value.get('read_only') is not True:raise SourceError('DESTINATION_NOT_READ_ONLY')
    if value.get('schema_version')!=1 or not isinstance(value.get('tables'),dict) or not isinstance(value.get('rows'),dict):
        raise SourceError('DESTINATION_SHAPE')
    for table,entry in value['tables'].items():
        if not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',table) or not isinstance(entry.get('columns'),dict) or type(entry.get('count')) is not int or entry['count']<0 or not re.fullmatch('[0-9a-f]{64}',entry.get('sha256','')):
            raise SourceError('DESTINATION_SHAPE')
    for table,rows in value['rows'].items():
        if table not in value['tables'] or not isinstance(rows,list) or len(rows)>100000:raise SourceError('DESTINATION_SHAPE')
        if len(rows)!=value['tables'][table]['count']:raise SourceError('DESTINATION_INVENTORY_COUNT')
        seen=set()
        for row in rows:
            key=identity(row['id'])
            if key in seen:raise SourceError('DESTINATION_DUPLICATE_ID')
            seen.add(key)
    for table in set(NATIVE[k][0] for k in NATIVE)|{'issue_sequences','project_identifiers','issue_links','issue_attachments'}:
        if table in value['tables'] and value['tables'][table]['count'] and table not in value['rows']:
            raise SourceError('DESTINATION_INVENTORY_MISSING')
    return value


def plan_import(issues,associations,assets,coverage,reader,workspace,destination,target_project=None):
    workspace=identity(workspace)
    if target_project:target_project=identity(target_project)
    try:
        bundle=read_bundle(issues,associations)
        asset_manifest,asset_hash,attachments=read_assets(assets,bundle)
        entities=dict(bundle['entities'])
        for row in attachments:entities[('attachment',identity(row['id']))]=leaves(row)
        coverage_path=Path(coverage).resolve();outside_git(coverage_path)
        if coverage_path.stat().st_mode&0o077:raise SourceError('OUTPUT_PERMISSIONS')
        coverage_bytes=read_private(coverage_path/'manifest.json');coverage_value=json.loads(coverage_bytes)
        if coverage_value['after_fingerprint']!=bundle['fingerprint'] or coverage_value['status']!='COMPLETE_WITH_READINESS_BLOCKERS':raise SourceError('COVERAGE_INPUT_SCOPE')
        before=validated_snapshot(reader.capture())
        if workspace not in {r['id'] for r in before['rows'].get('workspaces',[]) if not r.get('deleted_at')}:raise SourceError('DESTINATION_WORKSPACE')
        namespace='linear:'+bundle['organization_id']
        projects=before['rows'].get('projects',[])
        existing_project=next((r for r in projects if r['id']==target_project),None) if target_project else None
        if target_project and (not existing_project or existing_project.get('workspace_id')!=workspace or existing_project.get('identifier')!='FAS' or existing_project.get('deleted_at')):
            raise SourceError('DESTINATION_PROJECT')
        owned_projects=[r for r in projects if r.get('workspace_id')==workspace and r.get('external_source')==namespace and r.get('external_id')==bundle['team_id'] and not r.get('deleted_at')]
        if not target_project and len(owned_projects)==1:existing_project=owned_projects[0]
        project=existing_project['id'] if existing_project else proposed_id(workspace,bundle['organization_id'],'team',bundle['team_id'])
        blockers=[];mapping=[]
        if existing_project:
            binding=(existing_project.get('external_source'),existing_project.get('external_id'))
            if binding not in [(None,None),('',''),(namespace,bundle['team_id'])] and any(binding):
                blockers.append({'code':'PROJECT_SOURCE_ID_COLLISION'})
        if len(owned_projects)>1:blockers.append({'code':'DUPLICATE_PROJECT_SOURCE_ID'})
        if any(r.get('workspace_id')==workspace and r.get('identifier')=='FAS' and r['id']!=project for r in projects):blockers.append({'code':'PROJECT_IDENTIFIER_COLLISION'})
        for (kind,key),record in sorted(entities.items()):
            native=native_for(kind,record)
            row={'source_payload_sha256':digest(record),'display_name':record.get('name',record.get('title')),
                 'source_organization':bundle['organization_id'],'source_kind':kind,'source_uuid':key,
                 'destination_table':native[0] if native else None,
                 'destination_kind':native[1] if native else ('boundary' if kind.endswith('_reference') else 'archive'),
                 'workspace_uuid':workspace,'project_uuid':project if native and native[0] not in ['projects','pages','initiatives'] else None,
                 'destination_uuid':project if kind=='team' else (proposed_id(workspace,bundle['organization_id'],kind,key) if native else None),
                 'action':'create' if native else ('reference' if kind.endswith('_reference') else 'archive')}
            if kind=='issue':
                match=re.fullmatch(r'FAS-([1-9][0-9]*)',record.get('identifier',''))
                row.update(source_identifier=record.get('identifier'),sequence_id=int(match[1]) if match else None)
                if not match or row['sequence_id']>=2147483647: blockers.append({'code':'INVALID_SOURCE_NUMBER','kind':kind,'source_uuid':key})
            mapping.append(row)
        issue_rows=[r for r in mapping if r['source_kind']=='issue']
        numbers=Counter(r['sequence_id'] for r in issue_rows if r['sequence_id'] is not None)
        for row in mapping:
            native=native_for(row['source_kind'],entities[(row['source_kind'],row['source_uuid'])])
            if not native:continue
            existing=before['rows'].get(native[0],[])
            matches=[r for r in existing if r.get('workspace_id')==workspace and r.get('external_source')==namespace and r.get('external_id')==row['source_uuid']]
            if row['source_kind']=='team' and existing_project:
                row['destination_uuid']=project;row['action']='reuse_identity';continue
            if len(matches)>1:blockers.append({'code':'DUPLICATE_DESTINATION_SOURCE_ID','kind':row['source_kind'],'source_uuid':row['source_uuid']})
            elif matches:
                match=matches[0]
                if match.get('deleted_at') or ('project_id' in match and match['project_id']!=project):
                    blockers.append({'code':'DESTINATION_SOURCE_SCOPE','kind':row['source_kind'],'source_uuid':row['source_uuid']})
                else:row.update(destination_uuid=match['id'],action='reuse_identity')
                if row['source_kind']=='issue' and match.get('sequence_id')!=row['sequence_id']:
                    blockers.append({'code':'SOURCE_NUMBER_CHANGED','source_uuid':row['source_uuid']})
            if any(r['id']==row['destination_uuid'] and r not in matches for r in existing):
                blockers.append({'code':'DESTINATION_UUID_COLLISION','kind':row['source_kind'],'source_uuid':row['source_uuid']})
        # These active-row name constraints exist in the pinned Plane models.
        # Names detect conflicts only; they never select a reusable identity.
        named=[r for r in mapping if r['destination_table'] in ['projects','modules','labels','states'] and r['display_name']]
        for row in named:
            table=row['destination_table']
            scope='workspace_id' if table=='projects' else 'project_id'
            scope_id=workspace if table=='projects' else project
            existing=before['rows'].get(table,[])
            conflict=any(r.get(scope)==scope_id and r.get('name')==row['display_name'] and not r.get('deleted_at') and r['id']!=row['destination_uuid'] for r in existing)
            conflict=conflict or any(r is not row and r['destination_table']==table and r['display_name']==row['display_name'] for r in named)
            if conflict:blockers.append({'code':'DESTINATION_NAME_COLLISION','kind':row['source_kind'],'source_uuid':row['source_uuid'],'table':table})
        if any(r.get('workspace_id')==workspace and r.get('name')=='FAS' and r.get('project_id')!=project for r in before['rows'].get('project_identifiers',[])):
            blockers.append({'code':'PROJECT_IDENTIFIER_COLLISION'})
        occupied=[r for r in before['rows'].get('issues',[]) if r.get('project_id')==project]
        reservations=[r for r in before['rows'].get('issue_sequences',[]) if r.get('project_id')==project]
        for row in issue_rows:
            number=row['sequence_id']
            if numbers[number]>1:blockers.append({'code':'DUPLICATE_SOURCE_NUMBER','source_uuid':row['source_uuid'],'sequence_id':number})
            if any(r.get('sequence_id')==number and r['id']!=row['destination_uuid'] for r in occupied) or any(r.get('sequence')==number and r.get('issue_id')!=row['destination_uuid'] for r in reservations):
                blockers.append({'code':'NUMBER_COLLISION','source_uuid':row['source_uuid'],'sequence_id':number})
        reserved_numbers=[r.get('sequence_id') for r in occupied]+[r.get('sequence') for r in reservations]
        if any(type(n) is not int or n<1 for n in reserved_numbers):raise SourceError('DESTINATION_SEQUENCE_SHAPE')
        next_number=max([r['sequence_id'] or 0 for r in issue_rows]+reserved_numbers+[0])+1
        if next_number>2147483647:blockers.append({'code':'NEXT_NUMBER_OUT_OF_RANGE'})
        by_source={(r['source_kind'],r['source_uuid']):r for r in mapping}
        profiles=sorted({(r['source_kind'],r['destination_table']) for r in mapping if r['destination_table']})
        if issue_rows:profiles.append(('issue_allocator','issue_sequences'))
        for kind,table in profiles:
            if table not in before['tables']:
                blockers.append({'code':'MISSING_SCHEMA_TABLE','kind':kind,'table':table});continue
            columns=before['tables'][table]['columns']
            required=['id','workspace_id','external_source','external_id']
            if table not in ['projects','pages','initiatives']:required.append('project_id')
            if table=='issues':required.append('sequence_id')
            if table=='projects':required.append('identifier')
            if table=='issue_sequences':required=['id','project_id','issue_id','sequence']
            for field in required:
                if field not in columns:blockers.append({'code':'MISSING_SCHEMA_COLUMN','kind':kind,'table':table,'field':field})
        if existing_project and existing_project.get('identifier')!='FAS':blockers.append({'code':'PROJECT_IDENTIFIER_MISMATCH'})
        links=[];unresolved=[]
        def link(kind,key,field,target_kind,target_key,boundary=False):
            target_key=identity(target_key)
            target=by_source.get((target_kind,target_key))
            if boundary:
                disposition='external_boundary'
            elif target is None:
                problem={'code':'UNRESOLVED_REFERENCE','kind':kind,'source_uuid':key,'field':field,'target_kind':target_kind,'target_uuid':target_key}
                unresolved.append(problem);blockers.append(problem);disposition='unresolved'
            elif target['destination_kind']=='archive':
                disposition='archive'
            else:disposition='native_proposal'
            links.append({'kind':kind,'source_uuid':key,'field':field,'target_kind':target_kind,'target_uuid':target_key,
                          'destination_uuid':target['destination_uuid'] if target else None,'disposition':disposition})
        fields={'issue':{'parent':'issue','project':'project','cycle':'cycle','state':'state','creator':'user','assignee':'user'},
                'project':{'lead':'user'},'initiative':{'parentInitiative':'initiative','owner':'user'},
                'milestone':{'project':'project'},'document':{'issue':'issue','project':'project','initiative':'initiative','cycle':'cycle','parentDocument':'document'},
                'label':{'parent':'label'},'attachment':{'issue':'issue'}}
        for (kind,key),record in sorted(entities.items()):
            for field,target_kind in fields.get(kind,{}).items():
                if record.get(field+'.id'):
                    foreign=kind=='issue' and field=='parent' and record.get('parent.team.id') not in [None,bundle['team_id']]
                    link(kind,key,field,target_kind,record[field+'.id'],foreign)
            if kind=='issue':
                for label in record.get('labels.nodes',[]):link(kind,key,'labels','label',label['id'])
            native=native_for(kind,record)
            if native and record.get('archivedAt'):
                table=native[0];columns=before['tables'].get(table,{}).get('columns',{})
                if 'archived_at' not in columns:blockers.append({'code':'MISSING_SCHEMA_COLUMN','kind':kind,'table':table,'field':'archived_at'})
                elif columns['archived_at']=='date':blockers.append({'code':'FIELD_PRECISION_GAP','kind':kind,'source_uuid':key,'field':'archivedAt','destination_field':'archived_at'})
        for parent,key,field,child,child_key in sorted(bundle['edges']):
            parent='team' if parent=='catalog' else parent
            canonical=child.replace('_reference','')
            boundary=child.endswith('_reference') and (canonical,child_key) not in by_source
            link(parent,key,field,canonical if child.endswith('_reference') else child,child_key,boundary)
        parents={key:record.get('parent.id') for (kind,key),record in entities.items() if kind=='issue'}
        for key in sorted(parents):
            visited=set();current=key
            while current in parents:
                if current in visited:
                    blockers.append({'code':'PARENT_CYCLE','source_uuid':key});break
                visited.add(current);current=parents[current]
        if asset_manifest['status']=='COMPLETE_WITH_BLOCKED_ASSETS':blockers.append({'code':'BLOCKED_SOURCE_ASSETS'})
        for row in issue_rows:
            source_project=bundle['entities'][('issue',row['source_uuid'])].get('project.id')
            row['source_project_uuid']=source_project
            row['module_uuid']=by_source.get(('project',source_project),{}).get('destination_uuid') if source_project else None
        after=validated_snapshot(reader.capture())
        unchanged=before['tables']==after['tables'] and before['rows']==after['rows']
        changes=[{'table':name,'before':before['tables'].get(name),'after':after['tables'].get(name)} for name in sorted(set(before['tables'])|set(after['tables'])) if before['tables'].get(name)!=after['tables'].get(name)]
        if not unchanged:blockers.append({'code':'DESTINATION_CHANGED'})
        report={'schema_version':1,'source_fingerprint':bundle['fingerprint'],'asset_manifest_sha256':asset_hash,
                'coverage_manifest_sha256':hashlib.sha256(coverage_bytes).hexdigest(),
                'target':{'workspace_uuid':workspace,'project_uuid':project,'identifier':'FAS','action':'reuse' if existing_project else 'create'},
                'mapping':sorted(mapping,key=lambda r:(r['source_kind'],r.get('sequence_id') or 0,r['source_uuid'])),
                'counts':dict(sorted(Counter(r['source_kind'] for r in mapping).items())),
                'proposed_counts':dict(sorted(Counter(r['destination_kind'] for r in mapping if r['action']=='create').items())),
                'reused_identity_counts':dict(sorted(Counter(r['destination_kind'] for r in mapping if r['action']=='reuse_identity').items())),
                'next_sequence_id':next_number,
                'status':'BLOCKED' if blockers else 'PLAN_VALID_WITH_MIGRATION_GATES',
                'blockers':sorted({json.dumps(b,sort_keys=True):b for b in blockers}.values(),key=lambda b:json.dumps(b,sort_keys=True)),'plan_valid':not blockers,
                'links':links,'unresolved_references':unresolved,'destination_changes':changes,
                'issue_placement':{'module_assigned':sum(r['module_uuid'] is not None for r in issue_rows),'module_free':sum(r['module_uuid'] is None for r in issue_rows)},'can_import':False,
                'migration_gates':coverage_value['readiness']['blockers']+['authorized_importer_and_native_verification_required'],
                'destination_before':digest(before),'destination_after':digest(after),
                'destination_unchanged':unchanged,'destination_writes':0,
                'assets':{'archived':sum(e['status']=='ARCHIVED' for e in asset_manifest['assets']),'blocked':sum(e['status']=='BLOCKED' for e in asset_manifest['assets'])}}
        directory=Path(destination).resolve();outside_git(directory);directory.mkdir(mode=0o700,parents=True,exist_ok=False)
        private_file(directory/'destination-before.json',json.dumps(before,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode())
        private_file(directory/'destination-after.json',json.dumps(after,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode())
        manifest_file(directory,report);return report
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        raise SourceError('PLAN_INPUT_OR_IO') from None


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['issues','associations','assets','coverage','workspace','output']:
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--target-project')
    args=parser.parse_args(argv)
    try:
        result=plan_import(args.issues,args.associations,args.assets,args.coverage,
                           PlaneSnapshotSSH(),args.workspace,args.output,args.target_project)
        print(json.dumps({k:result[k] for k in ['status','counts','proposed_counts','next_sequence_id','destination_unchanged','can_import']}))
        return 1 if result['blockers'] else 3
    except KeyboardInterrupt:
        print(json.dumps({'code':'CANCELLED'}));return 130
    except SourceError as error:
        print(json.dumps({'code':str(error)}));return 2


if __name__=='__main__':raise SystemExit(main())
