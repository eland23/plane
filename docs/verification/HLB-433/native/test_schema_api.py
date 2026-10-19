"""Real HTTP assertions; invoke only through the .130 fixture controller."""
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

if not __debug__:
    raise RuntimeError('OPTIMIZED_EXECUTION_DENIED')

BASE = 'http://127.0.0.1:18191'
PATH = '/api/workspaces/plane-image-schema-433/projects/43300000-0000-4000-8000-000000000003/issues/43300000-0000-4000-8000-000000000004/issue-links/'


def get(path, authenticated=False):
    headers = {}
    if authenticated:
        fixture = json.loads(Path(os.environ['PLANE_SCHEMA_FIXTURE']).read_text())
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
    assert status == 403, 'Unauthenticated schema fixture must be denied'


def test_complete_packaged_schema_serves_exact_fixture_link():
    health, _ = get('/api/instances/')
    assert health == 200, 'API fixture bootstrap must succeed before schema assertion'
    status, body = get(PATH, authenticated=True)
    assert status == 200, f'Complete packaged schema must serve issue-link API; got {status}'
    rows = json.loads(body)
    assert isinstance(rows, list) and len(rows) == 1
    row = rows[0]
    assert row['id'] == '43300000-0000-4000-8000-000000000005'
    assert row['title'] == 'Existing supported schema fixture'
    assert row['url'] == 'https://example.invalid/plane-schema-fixture'
    assert row['external_source'] is None and row['external_id'] is None
