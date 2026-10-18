"""Remove reference-deletion protection in memory on the isolated synthetic fixture.

Normal source files remain read-only. Unchanged public-command assertions must
fail, then original command definitions are restored before this process exits.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--contract',choices=['milestone'],default='milestone')
    args=parser.parse_args()
    target=urlsplit(os.environ.get('DATABASE_URL',''))
    if (target.scheme not in {'postgres','postgresql'} or target.hostname!='plane-hlb464-db'
        or target.path!='/plane_fixture_snapshot' or target.query or target.fragment):
        print(json.dumps({'code':'ISOLATED_FIXTURE_REQUIRED'}));return 2
    args.output.mkdir(parents=True,exist_ok=False)
    import django
    django.setup()
    from django.conf import settings
    import psycopg
    import pytest
    import plane.app.services.milestones as commands
    config=settings.DATABASES['default']
    if config['HOST']!='plane-hlb464-db' or config['NAME']!='plane_fixture_snapshot':
        raise RuntimeError('Isolated fixture database required')
    source=Path(commands.__file__).read_text()
    guard="    if IssueMilestone.objects.filter(milestone=row).exists():\n        raise MilestoneConflict('Explicitly clear every issue assignment before deletion')\n"
    if source.count(guard)!=1:raise RuntimeError('Expected exact reference protection')
    faulty=source.replace(guard,'')
    with psycopg.connect(host=config['HOST'],port=config.get('PORT') or 5432,
        user=config['USER'],password=config['PASSWORD'],dbname='test_'+config['NAME'],autocommit=True) as db:
        def inventory():
            with db.cursor() as cursor:
                cursor.execute('SELECT (SELECT count(*) FROM module_milestones), (SELECT count(*) FROM issue_milestones)')
                return list(cursor.fetchone())
        if inventory()!=[0,0]:raise RuntimeError('Expected empty synthetic milestone fixture')
        restored=False
        try:
            exec(compile(faulty,commands.__file__,'exec'),commands.__dict__)
            result=pytest.main(['plane/tests/contract/test_module_milestones.py',
                '-k','assignment_replaces_one_value_and_delete_conflicts_until_clear',
                '-q','-o','addopts=','-p','no:cacheprovider','--reuse-db','--migrations',
                '--junitxml='+str(args.output/'failure-reference-loss.xml')])
        finally:
            exec(compile(source,commands.__file__,'exec'),commands.__dict__)
            restored=Path(commands.__file__).read_text()==source
        rows_after=inventory()
    suites=ET.parse(args.output/'failure-reference-loss.xml').getroot().findall('testsuite')
    intended=(int(result)==1 and sum(int(s.get('tests',0)) for s in suites)==1
        and sum(int(s.get('failures',0)) for s in suites)==1
        and sum(int(s.get('errors',0)) for s in suites)==0
        and 'DID NOT RAISE' in ET.tostring(ET.parse(args.output/'failure-reference-loss.xml').getroot(),encoding='unicode'))
    receipt={'exit':int(result),'expected_failure':True,'intended_assertion_detected':intended,
        'source_restored':restored,'fixture_rows_after':rows_after,
        'original_source_sha256':hashlib.sha256(source.encode()).hexdigest(),
        'fault_source_sha256':hashlib.sha256(faulty.encode()).hexdigest(),
        'accepted':intended and restored and rows_after==[0,0]}
    (args.output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt));return 0 if receipt['accepted'] else 1


if __name__=='__main__':raise SystemExit(main())
