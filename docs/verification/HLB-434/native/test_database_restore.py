"""Real HTTP assertions; invoke only through the .130 fixture controller."""
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

if not __debug__:
    raise RuntimeError('OPTIMIZED_EXECUTION_DENIED')

BASE = 'http://plane-rehearsal-db-434-20261019-api:8000'
PATH = '/api/workspaces/plane-database-restore-434/projects/43400000-0000-4000-8000-000000000003/issues/43400000-0000-4000-8000-000000000004/issue-links/'


def get(path, authenticated=False):
    headers = {}
    if authenticated:
        fixture = json.loads(Path(os.environ['PLANE_RESTORE_FIXTURE']).read_text())
        headers['Cookie'] = fixture['cookie_name'] + '=' + fixture['session_key']
    try:
        response = urlopen(Request(BASE + path, headers=headers), timeout=30)
    except HTTPError as error:
        response = error
    with response:
        status = response.status
        body = response.read() if status == 200 else b''
    return status, body


def test_schema_api_requires_authenticated_session():
    status, _ = get(PATH)
    assert status == 401, 'Unauthenticated schema fixture must be denied'


def restored_link():
    health, _ = get('/api/instances/')
    assert health == 200, 'API bootstrap must succeed before restore assertion'
    status, body = get(PATH, authenticated=True)
    assert status == 200, f'Restored database must serve issue-link API; got {status}'
    rows = json.loads(body)
    assert isinstance(rows, list) and len(rows) == 1, 'Exactly one fixture link must persist'
    return rows[0]


def test_restored_database_retains_exact_fixture_identity():
    assert restored_link()['id'] == '43400000-0000-4000-8000-000000000005'


def test_restored_database_retains_golden_fixture_content():
    assert restored_link()['title'] == 'Golden restored attachment link', 'Restored fixture content must equal golden value'


def test_restored_database_retains_fixture_url():
    assert restored_link()['url'] == 'https://example.invalid/plane-schema-fixture'


def test_restored_database_retains_nullable_source_identity():
    row=restored_link()
    assert row['external_source'] is None and row['external_id'] is None
