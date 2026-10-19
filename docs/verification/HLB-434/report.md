# Verification evidence: HLB-434 Plane restore integrity

Status: **NOT RUN for full acceptance; source contracts, native components and shared M schema/asset controls PASS**. Author: Codex.
Reviewer: separate Standards and Spec/security source reviews PASS at dd67694; final evidence review tracked on PR13. [Child](https://linear.app/fashionfindrs/issue/HLB-434),
[parent](https://linear.app/fashionfindrs/issue/HLB-429). Policy: existing parent
verification decisions and FashionFindr `docs/testing/REPORT-TEMPLATE.md`.

## Scope and coverage

| Behavior ID | Spec AC | Owner ticket | Test path/name | Independent assertion | Layers | Result | Evidence |
|---|---|---|---|---|---|---|---|
| REL-03 / archive | AC2 | HLB-434 | tools/tests/test_plane_restore.py / valid_archive, malformed_or_corrupt_archive, archive_symlink_member | Independent captured archive digest, literal `abc` SHA-256, exact member identities; reject missing/changed/duplicate/unsafe members | pytest/CLI | PASS source | source-controls-68a1227 |
| REL-03 / bytes | AC2 | HLB-434 | downloaded_asset_matches_original_then_rejects_changed_bytes_and_recovers | Readback bytes equal literal original hash; same-size changed bytes fail; corrected readback passes | pytest/CLI | PASS source | source-controls-68a1227 |
| REL-03 / exact database | AC2 | HLB-434 | database_compare, exact_snapshot | Exact table set and row-value multiset, including JSON types and nested array order | pytest/CLI | PASS source | source-controls-68a1227 |
| REL-03 / preservation | AC2 | HLB-434 | preservation_rejects, duplicate_row_multiplicity | Old tables/columns/records retain values and multiplicity; additions require explicit mode | pytest/CLI | PASS source | source-controls-68a1227 |
| REL-03 / destination | AC2/V1 | HLB-434 | tools/tests/test_asset_store_guards.py / foreign_connection | Foreign endpoint/bucket/default credentials/config rejected before S3 client import; fake external SDK marker remains absent | pytest/process | PASS source | source-controls-68a1227 |
| REL-03 / execution mode | V1/V2 | HLB-434 | native_commands_deny_optimized_execution | Both native commands reject -O / PYTHONOPTIMIZE before protected operations | pytest/process | PASS source | source-controls-68a1227 |
| REL-03 / inspection | V2 | HLB-434 | indeterminate_docker_state | Unavailable Docker state preserves private readbacks/config and cannot produce a clean receipt | pytest/CLI fake | PASS source | source-controls-68a1227 |
| REL-03 / cleanup errors | V2 | HLB-434 | receipt_failure_still, diagnostic_failure_still, test_shared_schema_control.py | Foreign or indeterminate fault image ownership preserves private data and blocks a clean receipt. Receipt I/O failure still removes owned readbacks/credential files and closes lease; failed diagnostic retrieval/storage cannot prevent confirmed-owned resource removal | pytest/filesystem | PASS source | source-controls-68a1227 |
| REL-03 / database destination | AC2/V1 | HLB-434 | tools/tests/test_database_restore_guards.py | Five foreign destinations rejected before Django import; both commands reject optimized execution | pytest/process | PASS source | source-controls-68a1227/failure-database-destination.xml |
| REL-03 / network isolation | AC2/V1 | HLB-434 | tools/tests/test_database_runtime_observer.py | Valid topology passes; additional network and wrong network ID produce no PASS receipt | pytest/CLI fake | PASS source | tdd/database-observer-red.xml and green.xml |
| REL-03 / real asset restore | AC2/V1/V2 | HLB-434 | native/asset_store_rehearsal.py + test_asset_store.py | Signed S3 restore and fresh GET readback: exact original/fixture keys, metadata and hashes; anonymous GET denied; corrupt fixture fails unchanged checksum assertion; restore repeats | authenticated S3 API/pytest | PASS component | native-assets-4769e03 |
| REL-03 / own database restore | AC2/V1 | HLB-434 | shared runtime fixture preparation | Own restored originals preserved; bounded synthetic link identity/content verified through authenticated API; full M remains separate | native DB/API | PASS bounded component | native-database-7b5ddfc |
| REL-03 / shared M API/assets | V1/V3 | HLB-434 | native/test_shared_fixture_m.py + test_asset_store.py | Literal IDs/graph/order/DST/memberships/wiki/document/access and authenticated asset bytes; exact saved dump recovery | native API/S3/pytest | PASS bounded shared fixture | shared-m-0a88a87 |
| REL-03 / combined schema and asset controls | V1/V2 | HLB-434 | shared_fixture_rehearsal.py / full unchanged suite across both defects | Omitted migration fails six issue reads and document API; saved dump recovery restores all30 checks; asset corruption fails2checks; second recovery passes30 | native DB/API/S3/pytest | PASS combined controls | shared-controls-dd67694 |
| REL-03 / combined browser/release | V3 | HLB-434/435/436 | wiki/cycle UI and release journeys | Actual edit/cancel/save/reload/error/retry and ordered release/readiness | Playwright/runtime | NOT RUN | owning gates remain open |

Inventory: 15 scoped rows; 10 source rows, 2 native component rows and 2 shared API/asset control rows proven; 1 browser/release row NOT RUN,
0 approved deferrals. UI and Jest are N/A to this Python CLI/component slice;
actual browser journeys remain required under HLB-436. Optional TesterArmy is N/A
per the parent. No coverage claim extends beyond these rows.

## Provenance and reproduction

The original .129 database and assets were captured read-only, retained root-only
outside Git, and staged on .130. No command in this rehearsal writes to .129.

| Input | Trusted SHA-256 | Independently checked contents |
|---|---|---|
| Database dump | 0cf879ce0cff92ada369167e9d6c3fd38d08fbfae67d3d4f1e24099ec2134849 | 110 original public tables / 812 logical rows |
| Logical snapshot | 951160d6a4523255cb295828c8b833c402f518fff8ec945b30b6cf541dbd7848 | Original values, JSON types, nullable columns and row multiplicity |
| Asset archive | df778660d7564f29eded43f1db31cdbda686e4f5526ef6df7f0143635e14547f | 1 original object / 98975 bytes |

The application image is the complete pushed e5c7acf098a890436ab6300f0bc8491c7dd22725
backend, OCI ID1c54c4fb…; its RootFS/config fingerprint is checked before database
mutation. PostgreSQL468d34fe…, Redis e7723ff7…, MinIO30cfd6ed… and test runner
25c7d4cb… are pinned by full IDs in the committed controllers. Native pytest9.0.3
is verified before execution. Boto3 1.34.96/Python3.12.10 executed the asset SDK.
MinIO identifies DEVELOPMENT.GOGET/Go1.24.7; no upstream release-tag claim is made.

Asset execution used pushed4769e0335a5db8f5a28a9d069dde5c34bd0bca08. Database
execution uses pushed7b5ddfcd2a39680d681c2cc980d301d848d5ce57. Application source,
controller/test source, current evidence head and CI are separate identities.
Executed file hashes are compared with pushed Git blobs before publishing.

Source checks run on the editor without services:

```bash
python3 tools/check_plane_restore.py --output /absolute/new-evidence-directory
```

For native reproduction, stage a clean pushed Git archive containing tools and
this native directory on .130; retain verified private inputs at the controller's
fixed source path. Run asset_store_rehearsal.py or database_restore_rehearsal.py
on .130 only. Each refuses an existing output namespace and holds the shared
rehearsal lease. Archive an earlier private run directory only after independently
confirming cleanup. Services run on internal networks with no published ports;
there is no human-facing preview URL for these components. Browser work remains
under HLB-436.

Database admission reserves960MiB available memory and2GiB disk; the asset
component reserves768MiB and512MiB respectively. Actual memory limits and network
state are captured in readback artifacts. These are component reservations,
not full Plane sizing or release readiness. No reservation was reduced for this
run. No workers, mail, provider sends or production imports run here.

## Three-check receipts

| Check | Known state | Controlled defect | Restored state | Evidence |
|---|---|---|---|---|
| Source contracts | 68PASS | Six source guard defects cause intended failures, zero errors | 68PASS | source-controls-68a1227/*.xml and receipts.json |
| Asset checksum | 4PASS | Same suite:1 intended checksum failure of4, zero errors/skips | 4PASS | native-assets-4769e03/ |
| Database/API | 5PASS | Same suite:1 intended title-content failure of5, zero errors/skips | 5PASS | native-database-7b5ddfc/ |
| Shared M API/assets | 30PASS | Same suite:2 intended checksum failures of30, zero errors/skips | 30PASS | shared-m-0a88a87/ |
| Shared M combined controls | 30PASS | Same suite:7 schema failures of30; recover30PASS, then2checksum failures of30, zero errors/skips | 30PASS | shared-controls-dd67694/ |

The six source defects bypass the asset checksum, original-row preservation,
SDK endpoint admission, Docker inspection admission, cleanup on receipt failure,
and database destination hostname. Expected failing counts are1,3(of5),2(of6),
1,1,2(of5). They affect temporary copies only; all copies are removed. They do not
substitute for native restored-data fault controls.

Observer regressions at the external host/Docker CLI boundary reproduced two
admission defects: an extra network and a mismatched NetworkID. Both failed the
unchanged rejection assertions on old code; corrected code passes all three
valid/invalid cases. The controller now mandates exact singleton network and
network-ID readback and includes the observer in executed code provenance.

Initial red/green development runs are saved in tdd/. They are not native fault
controls or a reliability sample. Native JUnit/log outputs are retained verbatim,
including runner whitespace. No model/provider cost, cache-hit or performance
claim is made; durations are native JUnit measurements.

## Error handling, recovery and cleanup

Archive/CLI source tests reject corrupt, unsafe, duplicate or missing entries,
FIFO/symlink/oversized inputs, altered nested data, lost nullable columns and
changed row multiplicity. Foreign SDK/database destinations are denied before
client/Django initialization; optimized execution is rejected before operations.
Indeterminate Docker inspection preserves private data and cannot produce a
clean receipt. Receipt or optional diagnostic I/O failure does not prevent
confirmed-owned resource cleanup; diagnostic loss is reported explicitly.

Asset recovery repairs only the marked synthetic binary. Exact object keys,
headers/metadata and original/golden hashes pass; anonymous synthetic GET returns
403. Independent cleanup confirmed zero owned containers/networks, removed
credential/readback files, unchanged original archive and reacquired lease.

Database recovery stops the owned API and restores the saved seeded dump. The
public comparator requires exact logical-row equality before restarting the API;
original rows are checked again with additions allowed after recovery. Logical
row checks do not prove every PostgreSQL catalog, role or grant.

Independent database cleanup PASS: zero owned containers/networks; restored
database data, temporary dump, snapshots, session and environment files removed;
original dump/snapshot unchanged; lease reacquired. Executed test copy SHA-256
matches pushed source, and the mandatory observer hash matches executed identity. Raw command/service logs, backups and
any expired session material remain root-only outside Git. No automatic expiry
is configured. Public outputs are scanned against original values and credential
markers before publication. Deleting temporary credential files does not claim
all diagnostic copies of credentials were physically erased.

## Attempts and limits

- Asset attempt01 (8e5995c): bootstrap failed before assertions because the
  non-root store could not write its temporary data filesystem. Its UID/GID/mode
  correction passed review; independent cleanup passed. This is setup evidence.
- Asset attempt02 (4769e03): accepted4PASS→1 intended failure→4PASS, cleanupPASS.
- Database attempt01 (dccc84f):5PASS→1 intended content failure→5PASS; exact
  recovery112tables/835rows and original110tables/812rows preserved. CleanupPASS.
  Its optional observer accepted extra networks, so that observer result is not
  accepted as complete isolation evidence. The stricter observer was added as a
  mandatory gate before a fresh run.
- Database attempt02 (7b5ddfc): accepted5PASS→1 intended content failure→5PASS,
  zero errors/skips. Mandatory strict network/image readbackPASS. Exact seeded
  recovery112tables/835rows; original110tables/812rows preserved. Independent
  cleanupPASS, with no diagnostic loss. All five executed code files match Git.
  Public artifacts were scanned against original snapshot string values and
  credential markers before publication; only metadata and synthetic failures
  were copied. Raw diagnostics remain private.

## Reviews, CI and verdict

Separate Standards and Spec/security reviews PASS for source7b5ddfc, including
resolution of the observer P2. Secure code guardian: no remaining findings on the
scoped database/observer diff. The standalone threat model is
`docs/security/threat-models/HLB-434-restore/README.md`. No security-drift script
exists in this fork; no GraphQL surface changes.

Exact executed-head CI PASS: [restore39189763635](https://github.com/eland23/plane/actions/runs/39189763635)
and [React Doctor39189763645](https://github.com/eland23/plane/actions/runs/39189763645).
The asset executed head has its own saved CI/provenance. Current evidence-head
CI/review is tracked separately on PR13; runtime is not inferred from CI.

Full HLB-434 remains INCOMPLETE. Shared supported fixture M API/asset proof now
passes, while combined browser coverage and ordered release/readiness
remain NOT RUN. API proof does not waive browser integration or HLB-435/436 gates. Prior HLB-433 proof
does not waive this ticket's verification. No deferrals were approved. No child
is marked complete to clear a dependency, and no merge, production delivery or
full runtime admission is claimed. Live .129 and unrelated .130 data/services
remain unchanged.

## Shared fixture M rehearsal

A new isolated shared controller combines original database and object restore,
supported fixture M setup, and 30 unchanged native API/asset checks. The fixture
covers six literal FAS identifiers, state totals, module membership and the
cross-module parent chain, blocking/related/duplicate edges, tied/null dates,
a cycle spanning DST, an inactive comment author/thread, wiki/inline image,
associated document and protected binary attachment. Two members, a guest viewer
and another workspace's member supply read/isolation checks. Document association
uses existing IssueLink and PageLog; its page is absent from workspace wiki.

The same suite must fail its two byte assertions after only the marked binary is
changed, then pass after asset repair and database dump recovery. Future portfolio
fields excluded by the parent runtime scope are not seeded. Browser editing,
cancel/save/error/retry, combined Control A and ordered release/readiness remain
open; collection and source checks do not prove native combined behavior.

Shared attempt01 (79419ff) ran the normal suite:27PASS/1FAIL, zero errors/skips.
The failure required identical ISO timestamp text even though the returned New
York offsets represent the golden UTC instants. This is an expectation defect,
not a controlled-failure result or accepted normal pass. The corrected contract
compares exact aware instants and the literal DST offsets (-04:00→-05:00); cycle
state totals now have an independent test. The second run expected29 cases.

Shared attempt02 (474f2dd) normal28PASS/1FAIL, zero errors/skips. DST instant and
offset checks passed. The remaining harness assertion requested an unstarted_issues
summary field that this API does not expose. The corrected contract preserves
total/completed/cancelled expectations6/2/2 and separately requires the supported
filtered cycle-issues API to return exactly Todo FAS-11/FAS-17. This run is not
accepted normal/fault evidence; the next run expects30 cases.

Shared attempt03 (36f1854) normal29PASS/1FAIL, zero errors/skips. Todo filtering
passed. The remaining harness assumption required cancelled_issues on cycle
detail, whose explicit response fields include only total_issues/completed_issues.
The corrected test requires6/2 there and exactly canceled FAS-21/FAS-30 through
the same supported filtered cycle-issues API. No golden membership/count changed.
This attempt is not accepted normal/fault proof; the next run retains30 cases.

## Accepted shared M run

Shared attempt04 executed pushed0a88a87d99a3e262ce81450925ae77f3f40de66d on .130:
30PASS → 2 intended checksum failures of30 → 30PASS, zero errors/skips throughout.
Only the marked synthetic binary changed. Both its authenticated API download
and independently captured storage bytes failed unchanged golden SHA assertions;
all other28 checks passed. Repairing that asset and restoring the actual saved
seeded database dump returned the same30 assertions to PASS.

Cycle detail verifies total/completed6/2; separate supported state filters verify
Todo FAS-11/FAS-17 and canceled FAS-21/FAS-30. Exact issue states, all6 membership,
module membership, numeric order, parent chain and relation types remain literal
golden assertions. The DST test checks equal UTC instants and exact -04:00/-05:00
offsets. Wiki and issue-associated document HTML/reference identity and private
inline/binary downloads pass, with anonymous and cross-workspace denial.

Mandatory runtime readback confirms all4 pinned services on exactly the owned
internal network, matching NetworkIDs, read-only roots and no published ports.
Nine executed file hashes match the pushed Git blobs; actual copied test/fixture
hashes and the observer hash match runtime identity. Independent cleanup confirms
zero owned containers/networks, no restored database/readbacks/dump/config/session
files, unchanged original3 input hashes and a reacquired lease. Private diagnostic
retention remains as described above. Selected artifacts were scanned against
original row values, original bucket/keys/headers and credential/signed-query markers
before publication.

Original database logical equality before migration and original-row preservation
after seeding/recovery PASS. Exact seeded dump logical equality before API restart
also PASS (112tables/895rows); counts are recorded in shared-m-0a88a87/roundtrip-integrity.json. This
is logical data preservation, not a PostgreSQL roles/grants/catalog equivalence claim.

Executed-head CI PASS: [restore39195518325](https://github.com/eland23/plane/actions/runs/39195518325)
and [ReactDoctor39195518517](https://github.com/eland23/plane/actions/runs/39195518517).
Final evidence-head CI is separate and tracked on PR13. At that revision, browser
UI writes/reload, error/retry/cancel, combined Control A and ordered release/worker
readiness remained open. Accepted combined Control A is recorded below. No production import, cutover, merge or full child completion.

## Combined Control A preparation and accepted execution

The saved shared rehearsal now adds the parent-defined omitted-migration control
between the known-state pass and asset corruption. The intended five phases are:
30PASS → seven schema assertion failures of30 → 30PASS → two checksum failures of30
→ 30PASS, zero errors/skips. The same test source/fixtures run in every phase.
The document assertion now names the schema HTTP200 contract explicitly; its
literal identity, content and association expectations remain unchanged.

The isolated database is reversed to0122 only after a seeded dump is saved. A
verified-base task image omits0123/0124; its real file probe and migrator cannot
recreate the omitted schema. Exact API image and missing-column readback precede
the normal suite. Restoring the saved dump and complete backend requires exact
logical equality and fresh strict runtime observation before each restored suite.
Foreign/unknown fault image cleanup must preserve data and never report success.
Cleanup guard development receipts are3FAIL→3PASS at the Docker process boundary;
these are source evidence, not native migration failure detection.

The prior accepted shared API/asset run remains valid at its separate revision.
Native combined Control A was pending at source68a1227 publication; its accepted
execution is recorded below. Browser journeys and ordered rollout/readiness remain
open until their own receipts exist. No production schema rollback is authorized.

Shared attempt05 (68a1227) passed30 normal checks. Omitted-migration phase
produced7 API assertion failures of30, zero errors/skips: six issue detail reads
and the issue-associated document read returned500. Independent private database
diagnostics confirmed the missing IssueLink source-column error. The controller
expected only the document failure, so it stopped before recovery; the five-phase
run is not accepted. The corrected receipt requires exactly those7 named500
assertions, with no changes to the normal30 tests or golden expectations, plus
mandatory database missing-column diagnostic readback before recovery. Selected
failed-run receipts and independent cleanup are saved in shared-attempt05-68a1227/.

## Accepted combined controls run

Shared attempt06 executed pushed `dd6769428a6d9517f60739d48710dd2ab00c1bc8` on .130.
The same30 tests produced **30PASS → 7 intended schema failures → 30PASS →
2 intended asset checksum failures → 30PASS**, zero errors/skips in every phase.
No assertions or fixtures changed between phases.

Control A's derived image omits0123/0124 from the verified complete backend.
A real file probe confirms both are absent, the actual migrator runs from that
image, schema readback confirms the two IssueLink columns remain absent, and
container inspection confirms the API uses that exact derived image. The full
suite fails exactly the six issue-detail reads and named issue-associated document
API HTTP200 assertions receiving500. PostgreSQL diagnostics confirm the missing
IssueLink source column; raw logs remain private. The other23 checks pass. Recovery restores the actual saved seeded
dump plus complete image, verifies112tables/895logicalrows exactly before API
startup, then passes strict4service isolation observation and all30 checks.

Control B then changes only the marked synthetic binary. Its authenticated API
and independent storage checksum assertions fail; the other28 checks pass. Asset
repair and another saved-dump recovery again require exact112table/895row equality,
fresh strict runtime observation and the final30PASS. Original110tables/812rows
remain preserved. This does not claim general PostgreSQL catalog/role/grant equality.

Independent cleanup PASS: no owned containers, networks or fault image; temporary
restored data/dump/readbacks/config/session files and fault build context removed;
all3 original input hashes unchanged and lease reacquired. The9 executed file
hashes and actual4 copied test/fixture files match pushedGit. Known-state and
both recovery observers verify exclusive internal network IDs, pinned images,
read-only roots and no published ports. Public artifacts passed original-value
and credential-marker scanning; raw command/service diagnostics remain private.

Exact executed-head CI PASS: [restore39198955624](https://github.com/eland23/plane/actions/runs/39198955624)
and [ReactDoctor39198955678](https://github.com/eland23/plane/actions/runs/39198955678).
The source-contract artifact records PR head68a1227 separately from the GitHub
workflow merge revision e3cf4b584336e199f92b0846dfb91b53fcd28abf. It contains68PASS,
six intended guard defects and68PASS again, with all temporary fixture directories
removed. Cleanup development evidence separately records3FAIL→3PASS; its6 verified synthetic
fixture directories were removed (tdd/shared-schema-cleanup-fixtures.json). Reviews and
CI for the final evidence head are tracked on PR13.

Browser journeys, serialized migration/service rollout, worker/dependency readiness
and HLB-435/436 remain open. The isolated schema reversal is only a controlled
defect on a disposable restored clone. It grants no production rollback, delivery,
import, merge or cutover approval. Full child/epic acceptance remains INCOMPLETE.
