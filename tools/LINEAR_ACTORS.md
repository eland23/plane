# Original actor supplements and native link identity

HLB-464 addresses the actor and external-resource identity prerequisites found by
HLB-449. It does not import accounts, invite inactive users or implement the
native historical timeline/content renderer owned by HLB-454.

## Source actor export

Use the existing read-only Linear credential in the environment. Never put its
value in a command, console log or Git artifact.

    python3 tools/linear_actors.py --issues /private/issues \
      --associations /private/associations --output /private/new-actors

Only typed creator/assignee/owner/lead/document/update/membership references and
already exported user UUIDs are looked up. Rich content cannot add candidates.
Each returned actor must match the requested UUID and source organization.
Original name/display name/email/active state/dates remain in 0700/0600 archives
outside Git. The actor profile and verified source fingerprint bind readback.
Provider errors and unavailable actors stay named BLOCKED outcomes. No guessed
identity, email matching, account creation, invitation or mutation query exists.

Limits:10,000 distinct referenced actors,16MiB per private response,64MiB total
pages; the existing fixed Linear transport bounds time, response size and retries.
Start/end dates are recorded. This is a separate read window, not an atomic
historical snapshot or a verified final-cutoff claim.

An existing output directory is never overwritten. Interrupted/invalid exports
retain a FAILED manifest which the planner refuses; retry into a new directory
after correcting access/input. Archives and prior failed receipts are retained
for operator inspection, not silently removed or mutated. Exit0 means completed,
exit1 means completed with explicit blocked actors, exit2 means failure.

    python3 tools/verify_linear_actors.py --issues /private/issues \
      --actors /private/actors
    python3 tools/linear_import_plan.py <existing required arguments> \
      --actors /private/actors
    python3 tools/check_linear_actors.py --output /var/tmp/new-actor-evidence

The no-network verifier checks original provider pages and all source issue
creator/assignee references independently. It uses explicit validation under
optimized Python. The planner verifies the supplement before SSH access and
maps users to archived attribution, never native accounts. Missing actors remain
blockers. Omitting --actors preserves the earlier no-supplement behavior.

## Native resource identity

Migration0123 adds nullable external_source/external_id to IssueLink. Manual
links stay unbound. Imported source identity is unique per destination workspace,
including tombstones, and must be complete/nonempty. A PostgreSQL trigger rejects
source/workspace rebinding. App, public API and Space serializers make both fields
read-only; normal title/URL edits retain provenance. A separately authorized
importer may bind through its internal transaction path, not ordinary API input.

Reverse migration takes ACCESS EXCLUSIVE before checking source bindings and
holds it through the atomic reversal. If any bound link exists, reversal refuses
before dropping fields, constraints or the trigger. Restore a compatible backup
or retain the schema; do not clear provenance or bypass the guard for rollback.

Native tests are saved in apps/api/plane/tests/{unit/test_import_link_fields.py,
contract/test_import_link_identity.py}. Run on .130 only, in the isolated fixture
runner using a clean pushed source revision and real PostgreSQL migrations:

    python -m pytest plane/tests/unit/test_import_link_fields.py \
      plane/tests/contract/test_import_link_identity.py -q -o addopts= \
      --reuse-db --migrations --junitxml=/evidence/native-link-pass.xml

The child fault runner checks its fixed synthetic database host/name, verifies an
empty link fixture, removes only its replay-identity constraint, runs the unchanged
normal assertion and restores the constraint in finally. It requires a single
intended assertion failure with no setup errors and zero remaining fixture rows:

    python plane/tests/run_link_identity_fault.py --output /evidence/new-fault

Then rerun the exact normal suite to prove restoration. Both scripts are CLI
jobs, not application services. Backend dependencies come from the recorded
image; changed source is mounted read-only from the pushed revision. No claim
about complete release images, live deployment, REST role authorization, browser
rendering or cutover follows from these tests. R1/R2/R3 and HLB-454 retain those
gates. See docs/verification/HLB-464/report.md for actual revisions and receipts.
