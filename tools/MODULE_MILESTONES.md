# Native module milestone prerequisite (HLB-465)

`plane.app.services.milestones` is the public Python command boundary for create,
update, ordered list, assignment/clear and conflict-protected deletion. Callers
provide the authenticated active User and module UUID. Active workspace/project
Guest members may list; Member/Admin may mutate. UI/HTTP adapters and session
recovery are HLB-440 work, not delivered by this prerequisite.

Names are nonempty with 255-character limit; dates are ISO calendar dates or null;
status is planned/completed/cancelled; sort order is finite; archive is boolean.
Editing cannot set scope, provenance or audit fields. Cancellation and archive
retain membership. Archived targets reject new assignments; unarchive permits
retry. Reassignment is single-valued; clear preserves every other issue and
module membership. Referenced deletion conflicts until assignments are cleared.
Commands serialize on the module and issue. Module membership updates performed
by other code are outside this command boundary and must preserve its scope.

Migration 0124 follows 0123. It refuses reversal when either new native table has
any rows, including tombstones. Retain this schema or restore a compatible
backup; never discard native imported data to force rollback. No destructive
cleanup is an operator migration procedure.

Verification uses the isolated .130 CLI runner and synthetic PostgreSQL fixture
recorded under docs/verification/HLB-465/. Never start services on the editor.
Inside that fixed runner, execute:

```
python -m pytest plane/tests/contract/test_module_milestones.py -q -o addopts= -p no:cacheprovider --reuse-db --migrations --junitxml=/evidence/milestone-pass.xml
python plane/tests/run_milestone_command_fault.py --output /evidence/new-milestone-reference-fault
python plane/tests/run_link_identity_fault.py --contract milestone --output /evidence/new-milestone-fault
python -m pytest plane/tests/contract/test_module_milestones.py -q -o addopts= -p no:cacheprovider --reuse-db --migrations --junitxml=/evidence/milestone-restored.xml
python manage.py makemigrations --check --dry-run --skip-checks
```

The fault helper refuses unrelated DSNs before importing Django. It requires an
empty named synthetic milestone table, removes only its identity uniqueness
constraint, expects an unchanged normal assertion to fail, and restores the
constraint in finally. Each output directory is new. Retain failure/restoration
receipts and verify fixture absence. Source fault guards run without services:

```
python3 -m pytest tools/tests/test_link_fault_guard.py -q -o addopts=
```

Raw installed schema stays root-only outside Git. No .129 schema/import/cutover,
full application sizing, native browser UI or HTTP authorization proof is implied.

The reference-loss control removes the actual delete guard in memory, runs the unchanged normal assignment/delete assertion, and restores original command definitions in finally. Source files remain read-only. Assignment cleanup remains available after membership removal or issue soft deletion, so users can recover and delete an otherwise referenced milestone.
