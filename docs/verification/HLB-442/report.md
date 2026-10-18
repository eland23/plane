# Verification evidence: HLB-442 Linear issue export

Status: **PASS for the bounded issue-export source; INCOMPLETE for the full child/epic acceptance rows**.
Author: Codex. Independent Standards and Spec/security source reviews: PASS.
Spec: [HLB-442](https://linear.app/fashionfindrs/issue/HLB-442), parent [HLB-431](https://linear.app/fashionfindrs/issue/HLB-431).
Policy: FashionFindrs `docs/testing/POLICY.md` and `REPORT-TEMPLATE.md`.

## Scope and coverage

| Behavior ID | Spec AC | Owner | Saved test in `tools/tests/test_linear_export.py` | Independent assertion | Layer | Result | Evidence |
|---|---|---|---|---|---|---|---|
| MIG-01 / issue pages | AC1, V1 | HLB-442 | `test_export_retains_every_page_and_archived_payload` | Synthetic UUIDs 2 and 11 retained once, archived payload unchanged, next cursor used | pytest/contract | PASS | artifacts/pass-known-state.xml; live-issues-summary.json |
| MIG-01 / boundary | AC1 | HLB-442 | `test_foreign_parent_is_an_explicit_stub_not_a_foreign_payload` | Foreign UUID/team stub retained; no full foreign request | pytest/contract | PASS | artifacts/pass-known-state.xml |
| MIG-01 / source errors | AC1, V2 | HLB-442 | `test_invalid_or_partial_source_cannot_be_export_success`, `test_cursor_loop_after_a_committed_page_preserves_checkpoint` | Duplicate/wrong-team/partial/nested-truncated/malformed source fails; prior committed count/cursor retained | pytest/contract | PASS | artifacts/pass-known-state.xml |
| MIG-01 / retries | AC1, V2 | HLB-442 | `test_transport_bounds_rate_retry_and_preserves_fixed_endpoint`, `test_transport_exhausts_retries_and_closes_every_error`, `test_transport_never_logs_or_retries_authorization_error`, `test_transport_does_not_accept_a_response_after_deadline` | Fixed HTTPS endpoint; 3-attempt cap, <=30s retry; auth no retry; expired response rejected; error bodies excluded | pytest/contract | PASS simulated | artifacts/pass-known-state.xml |
| MIG-01 / recovery | AC1, V2 | HLB-442 | `test_auth_failure_then_resume_keeps_original_records_once`, page-limit/cancel/budget/lock tests | Original bytes retained; retry uses cursor once; concurrent writer refused; budget prevents partial page | pytest/filesystem | PASS | artifacts/pass-known-state.xml |
| MIG-01 / integrity and privacy | AC1, V2 | HLB-442 | tampering/scope, invalid-checkpoint, rejected-manifest, Git-destination/Git-detection/broken-marker tests | Exact rejected manifest bytes unchanged; Git/error gate before API/write; checksums and 0700/0600 verified | pytest/filesystem | PASS | artifacts/pass-known-state.xml |
| MIG-01 / original payload | AC1 | HLB-442 | `test_original_unicode_description_and_actor_payload_are_preserved` | Literal Unicode description/actor payload round trips without execution | pytest/filesystem | PASS | artifacts/pass-known-state.xml |
| MIG-01 / association-only document | AC1 | HLB-443 | Not in issue-only exporter | Must traverse documents/associations separately | contract/API | NOT RUN | HLB-443 |
| MIG-02 / cutoff and source mutation | AC1/2 | HLB-447 | Not in issue-only exporter | Must account for concurrent changes/deletions/inaccessible records through final delta | contract/API | NOT RUN | HLB-447 |
| MIG-01/02 / UI, Jest, browser | V1 | HLB-442 | N/A | CLI-only Python; no UI/TS change, destination write or hosted service | UI/Jest | N/A | source diff |

30 contract cases pass. Two parent behavior rows are only partially covered here;
association traversal and cutoff/delta reconciliation remain unproven. These are
existing planned child ownership, not approved waivers. This ticket stays open
for the broader repeated acceptance rows; no full-backup claim follows from it.

## Provenance and reproduction

Application and saved test source revision: `337c3334837dd2dabed880b8c34e3700c8a9ed1d`.
The four-run suite used exactly those source/test bytes before commit; this report
and sanitized artifacts are a later documentation-only commit. Python 3.9.2,
pytest 8.4.2, Git and real local private files; external HTTP is faked in contracts.
No app service, container or preview was started. VM/deployed identity: N/A to
this read-only CLI. Plane runtime remains separately blocked under HLB-433.

```bash
TMPDIR=/var/tmp python3 tools/check_linear_export.py --output /absolute/new-evidence-directory
python3 tools/linear_export.py \
  --team 98ad34ad-69c8-48e7-813a-812f9231be12 --output /absolute/private/new-run
# Authenticate via the environment; never put actual tokens in shell history.
# Complete-export verification:
python3 tools/linear_export.py --team 98ad34ad-69c8-48e7-813a-812f9231be12 \
  --output /absolute/private/existing-run --resume
```

Use existing environment injection, not the illustrative credential placeholder.
Response limit16MiB, default archive budget512MiB, disk reserve1GiB,
page ceiling10,000, per-attempt response deadline30s, socket timeout30s,
3 HTTP attempts and capped30s backoff. A blocked socket read may consume one
socket wait beyond the remaining wall-clock deadline before rejection.

## Three-check receipts

| Check | Expected | Actual | Exit | Artifact |
|---|---|---|---|---|
| Pass from known state | All normal assertions pass | 30 passed / 3.83s | 0 | artifacts/pass-known-state.xml and .log |
| Demonstrate page-loss detection | Exact expected UUID list/count assertion fails | 1 intended assertion failure / 0.79s | 1 | artifacts/failure-page-loss.xml and .log |
| Demonstrate checksum detection | Unchanged tamper rejection assertion fails | 1 intended missing-rejection failure / 0.92s | 1 | artifacts/failure-checksum.xml and .log |
| Restore and repeat | Original code and tests pass from new fixtures | 30 passed / 4.01s | 0 | artifacts/restore-and-repeat.xml and .log |

The runner mutates only temporary tool copies; no test assertion changes.
These controls prove fixture page-loss/integrity detection, not Linear API
permissions, complete workspace coverage, destination persistence or final cutoff.
All temporary matrix roots were removed after each case; receipts record absence.

## Real read-only source receipt

On 2026-10-18, the existing authorized credential returned **801 distinct FAS
issue UUIDs over17 pages**, with a terminal page observed. Independent file
readback recomputed every page hash, checked every team ID, unique IDs and
manifest count, and verified private permissions. Complete-export `--resume`
made one organization/team scope request and **zero issue-page requests**;
801 records remained. The current returned issue set contained0 archived issues
and0 foreign-parent boundaries; archived/boundary behavior is therefore synthetic
proof only. No hidden/deleted/inaccessible issue coverage is asserted.

The source window was19:55:14.708–19:55:24.887 UTC; verification at19:55:40.136.
This is explicitly non-atomic and issue-only. Raw records stay in the root-only
`/var/lib/plane-migration/HLB-442-20261018` directory outside Git, retained for
later migration reconciliation. Only sanitized counts/booleans/times are in
`artifacts/live-issues-summary.json`. No raw issue/actor contents or key included.
Initial attempted private location beneath `/root` was safely rejected by an
existing ancestor `.git` marker before provider access; actual storage passed
the fail-closed admission gate. No existing marker/resource was modified.

## Error handling and recovery

Auth loss, GraphQL partial errors, cursor loops, wrong team, duplicates, label
truncation, page/budget caps and cancellation fail explicitly and preserve committed
checkpoints. Shape/scope/hash rejection does not mutate the existing manifest.
Git detection uncertainty fails before source access/output creation. Network/429
are simulated; live credential scope/export and completed-resume used the real
fixed Linear endpoint. No provider fault, auth revocation, source deletion or
concurrent-source mutation was injected in live Linear.

## Evidence bundle and cleanup

Native pytest logs, native JUnit XML, runner receipts and sanitized live summary
are committed in `artifacts/`. Synthetic fixtures contain no real credentials or
source records; source reports exclude private payloads. GitHub CI uploads the
same contract matrix for30days, without live credentials. Exact-head CI is
recorded in the PR/Linear evidence comment after push; local evidence alone does
not establish CI success.

No live source/destination mutation, service or container was created. Raw export
is intentionally retained under protected storage; migration operator owns later
retention/removal. Matrix fixtures were removed after both failures and passes.
Pre-existing resources and Git markers were untouched. No cleanup failure.

Execution costs: no model/provider-generation calls in tests/export; token usage,
estimated cost and billed cost unavailable. No cache/replay claim; completed
resume replayed verified local pages and fetched scope only.

Source Standards and Spec/security PASS after fixes. Full child acceptance remains
INCOMPLETE pending association/final-delta ownership and reviewer disposition;
HLB-442 is not Done and no import/cutover authorization follows from this result.
Threat model: `docs/security/threat-models/HLB-431-linear-export/THREAT-MODEL.md`.
