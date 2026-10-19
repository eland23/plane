# Verification evidence: HLB-434 Plane restore integrity

Status: **NOT RUN for full acceptance; source contracts PASS**. Author: Codex.
Reviewer: separate Standards and Spec/security review PASS at 8e5995c. [Child](https://linear.app/fashionfindrs/issue/HLB-434),
[parent](https://linear.app/fashionfindrs/issue/HLB-429). Policy: existing parent
verification decisions and FashionFindr `docs/testing/REPORT-TEMPLATE.md`.

## Scope and coverage

| Behavior ID | Spec AC | Owner ticket | Test path/name | Independent assertion | Layers | Result | Evidence |
|---|---|---|---|---|---|---|---|
| REL-03 / archive | AC2 | HLB-434 | tools/tests/test_plane_restore.py / valid_archive, malformed_or_corrupt_archive, archive_symlink_member | Independent captured archive digest, literal `abc` SHA-256, exact member identities; reject missing/changed/duplicate/unsafe members | pytest/CLI | PASS source | source-controls |
| REL-03 / bytes | AC2 | HLB-434 | downloaded_asset_matches_original_then_rejects_changed_bytes_and_recovers | Readback bytes equal literal original hash; same-size changed bytes fail; corrected readback passes | pytest/CLI | PASS source | source-controls |
| REL-03 / exact database | AC2 | HLB-434 | database_compare, exact_snapshot | Exact table set and row-value multiset, including JSON types and nested array order | pytest/CLI | PASS source | source-controls |
| REL-03 / preservation | AC2 | HLB-434 | preservation_rejects, duplicate_row_multiplicity | Old tables/columns/records retain values and multiplicity; additions require explicit mode | pytest/CLI | PASS source | source-controls |
| REL-03 / destination | AC2/V1 | HLB-434 | tools/tests/test_asset_store_guards.py / foreign_connection | Foreign endpoint/bucket/default credentials/config rejected before S3 client import; fake external SDK marker remains absent | pytest/process | PASS source | source-controls |
| REL-03 / execution mode | V1/V2 | HLB-434 | native_commands_deny_optimized_execution | Both native commands reject -O / PYTHONOPTIMIZE before protected operations | pytest/process | PASS source | source-controls |
| REL-03 / inspection | V2 | HLB-434 | indeterminate_docker_state | Unavailable Docker state preserves private readbacks/config and cannot produce a clean receipt | pytest/CLI fake | PASS source | source-controls |
| REL-03 / cleanup errors | V2 | HLB-434 | receipt_failure_still, diagnostic_failure_still | Receipt I/O failure still removes owned readbacks/credential files and closes lease; failed diagnostic retrieval/storage cannot prevent confirmed-owned resource removal | pytest/filesystem | PASS source | source-controls |
| REL-03 / real asset restore | AC2/V1/V2 | HLB-434 | native/asset_store_rehearsal.py + test_asset_store.py | Signed S3 restore and fresh GET readback: exact original/fixture keys, metadata and hashes; anonymous GET denied; corrupt fixture fails unchanged checksum assertion; restore repeats | authenticated S3 API/pytest | NOT RUN | native preparation only |
| REL-03 / own database restore | AC2/V1 | HLB-434 | shared runtime fixture preparation | Own restored database and supported fixture-M identities/content preserved through independently read destination APIs | native DB/API | NOT RUN | HLB-433 evidence does not waive this row |
| REL-03 / shared M integration | V1/V3 | HLB-434/435/436 | supported issue/module/cycle/wiki/asset fixture M | Literal identities/graph/order/assets and combined wiki/cycle reload | API/Playwright | NOT RUN | shared integration remains open |

Inventory: 11 scoped rows; 8 source rows proven, 3 runtime/integration rows NOT RUN,
0 approved deferrals. UI and Jest are N/A to this Python CLI/component slice;
actual browser journeys remain required under HLB-436. Optional TesterArmy is N/A
per the parent. No coverage claim extends beyond these rows.

## Provenance and reproduction

The asset archive was captured read-only from existing .129 storage and retained
root-only outside Git. The new CLI audits the real captured archive successfully:
1 original object / 98975 bytes; archive SHA-256
`df778660d7564f29eded43f1db31cdbda686e4f5526ef6df7f0143635e14547f`.
This is archive validation, not a destination restore claim.

Source contracts execute on the editor without services. The native fixture is
restricted to .130, fresh run-owned names, an internal network and no published
ports. It restores original object keys into a fresh isolated bucket plus the
committed inline-PNG/binary fixture constants in native/asset_fixture.py. Signed
SDK operations use only the fixed run-owned endpoint/bucket and generated private
credentials; no original endpoint or credentials are provisioned to the writer.

Native dependencies already staged on .130:

- Full backend dependency image `1c54c4fb…`, application e5c7acf. It supplies boto3;
  it is not started as an API/worker for this component.
- Hash-locked test runner `25c7d4cb…`, native pytest 9.0.3 (preflight verifies it).
- Object store `30cfd6ed…`, an existing pinned custom MinIO image. Its version CLI
  identifies DEVELOPMENT.GOGET, Go 1.24.7; no upstream release-tag claim is made.
  Source preparation has not yet proved its S3 compatibility here.

The store has a 256 MiB memory cap and read-only root, with an ephemeral data
filesystem. SDK and pytest clients are bounded and sequential; component admission
requires 768 MiB available memory and 512 MiB free disk. Original asset bytes are
limited to 16 MiB for this component fixture; readback is bounded to 32 MiB.
These are component limits, not full Plane sizing or release admission.

Reproduce source contracts:

```bash
python3 tools/check_plane_restore.py --output /absolute/new-evidence-directory
```

Before native execution, commit/push source and stage that Git archive on .130;
retain the original root-only archive at the documented private source path.
Run the staged native/asset_store_rehearsal.py only on .130. The fixed namespace
and output directory must be absent. Runtime/test/source hashes and exact-head CI
will be recorded with actual execution; none is inferred from source checks.

Private originals, credential material and diagnostics stay root-only outside
Git; public evidence contains synthetic source tests and sanitized metadata.
There is no automatic expiry configured. Retention remains with the operator
while the migration rehearsal is open.

## Three-check receipts

| Behavior IDs | Check | Expected result | Actual result | Exit | Artifacts |
|---|---|---|---|---|---|
| Source rows above | Known state | PASS | 45 pass / 0 errors | 0 | artifacts/source-controls/pass-known-state.xml |
| Byte guard | Bypass readback checksum | Unchanged contract fails | 1 intended failure / 0 errors | 1 | failure-asset-checksum.xml |
| Record guard | Bypass preservation comparison | Unchanged contracts fail | 3 intended failures of 5 cases / 0 errors | 1 | failure-record-preservation.xml |
| Endpoint guard | Remove endpoint admission | Fake client marker reached; unchanged tests fail | 2 intended failures of 6 cases / 0 errors | 1 | failure-sdk-endpoint.xml |
| Inspection guard | Treat permission failure as absence | Data-preservation assertion fails | 1 intended failure / 0 errors | 1 | failure-inspection-admission.xml |
| Receipt cleanup | Skip cleanup after receipt error | Readback cleanup assertion fails | 1 intended failure / 0 errors | 1 | failure-receipt-cleanup.xml |
| Source rows above | Restore and repeat | PASS | 45 pass / 0 errors | 0 | artifacts/source-controls/restore-and-repeat.xml |
| Real S3 rows | Known / corrupt / restored | PASS / intended checksum failure / PASS | NOT RUN | — | pending native receipts |

Source controlled defects affect temporary copies only; all fixture directories
are removed. They do not substitute for parent Control B against real restored
asset bytes. Initial TDD red checks are pre-implementation assertions, separately
retained and not counted as actual runtime fault controls. The reviewed source adds regression tests for diagnostic retrieval and storage
failures. Both fail against the previous cleanup and pass after the fix; original
archive bytes remain unchanged. Native image/isolation/code identity is recorded
by the controller; exact-head CI remains a separate gate before acceptance.

## Error handling and recovery

| Error case | Boundary | Dependencies | Assertions/recovery | Result |
|---|---|---|---|---|
| Corrupt/missing/duplicate/path-alias asset | Untrusted archive | Real filesystem | Fail fixed code; never extract; original inputs untouched | PASS source |
| FIFO/symlink/oversize input | File open | Real filesystem | Reject without waiting on FIFO or reading oversized contents | PASS source |
| Changed nested data, lost nullable column or duplicate row | Destination readback | Synthetic JSONL | Preserve literal values/types/multiplicity; exact and additions modes distinct | PASS source |
| Foreign endpoint, bucket or credentials | S3 initialization | Deliberate external SDK fake | Reject before importing client; no provider calls | PASS source |
| Docker permission/inspection failure | Cleanup | Deliberate external Docker fake | Preserve private readbacks and reject clean receipt | PASS source |
| Receipt write failure | Completion | Real filesystem/descriptor | Cleanup still runs and lease descriptor closes | PASS source |
| Actual object corruption and repair | Signed S3 PUT/GET | Real isolated server | Same normal test detects changed binary fixture, then passes after repair | NOT RUN |

## Evidence bundle

Source JUnit/native phase outputs: artifacts/source-controls/ and artifacts/tdd/.
No browser screenshots/traces are applicable to this source-only checkpoint.
Independent Standards and Spec/security review PASS at 8e5995c; cleanup P2
resolved with two red/green boundary regressions. Restore contracts CI
[39188012985](https://github.com/eland23/plane/actions/runs/39188012985) and React
Doctor 39188013027 PASS at that exact revision. Source artifacts contain synthetic
inputs only. No source result proves native restoration.

## Execution metrics

Source tests contain no model/provider calls. Durations are in native JUnit;
seven source phases form one serial matrix, not a reliability sample. Initial
red/green development runs are separate. Cached execution, model tokens, reserved
budget and billed cost are N/A/unavailable. No cost or performance claim is made.

## Cleanup and verdict

All owned source-test temporary directories were removed. No application service
or service container ran on the editor. The manual MinIO version CLI on .130 was
short-lived and removed itself; it is not S3 restore evidence.

Full child acceptance remains incomplete. Native signed S3 restore/corruption/
recovery, HLB-434's own database restore/readback, and supported shared fixture M
integration are still open. Existing HLB-433 DB/schema proof is preparatory
context and does not waive HLB-434 coverage. The prerequisite/acceptance alignment
remains explicit; no child is falsely marked complete to clear a blocker. Live
.129 and unrelated .130 workloads/data remain unchanged.

## Native attempt 01 (not an accepted fault control)

Revision 8e5995c reached the isolated server bootstrap, which failed before any
restore assertions: the non-root store could not write its new ephemeral data
filesystem. The correction assigns that new tmpfs to the existing UID/GID 1000
with mode 0700; no host directory or existing object store is changed. Cleanup
and rerun results will be recorded separately.
