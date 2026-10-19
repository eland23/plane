# HLB-433 — Plane release-candidate evidence

Status: **INCOMPLETE for full acceptance**. Source contracts and scoped source
reviews PASS. Complete application packaging and the bounded restored-schema API control
PASS; shared runtime-fixture and full release proof remain separate gates. [Child](https://linear.app/fashionfindrs/issue/HLB-433),
[parent](https://linear.app/fashionfindrs/issue/HLB-429),
[PR4](https://github.com/eland23/plane/pull/4).

## Behavior and acceptance

| Behavior / AC | Saved seam / independent assertion | Result |
|---|---|---|
| REL-01 / AC1 | Public preflight CLI: exact target, namespace, Git SHA/ref/clean state, trusted probe, capacity errors/recovery and concurrent build rejection | PASS source contracts |
| REL-02 / AC1 | Complete image manifest: literal Git blob/content hashes, missing/changed/whiteout/symlink/ancestor replacement, command identities and pinned external stages | PASS synthetic contracts and real scratch-image export format |
| Packaging admission | Low capacity yields PACKAGING_ONLY with separate blocked runtime admission; normal release still fails TARGET_CAPACITY | PASS; cannot authorize deployment |
| Private diagnostics | Foreign/enclosing/worktree/bare repository outputs denied before log creation or Docker; error marker stays private with 0700 directory/0600 logs | PASS source contracts |
| Helper cleanup | Failed probe's owned child terminates; stream deadlines reap owned process groups | PASS source contracts |
| REL-02 full image build | Complete API/worker/beat/migrator backend and full web, same application revision, offline payload verification | PASS complete images and 708 backend payload files |
| Native packaged command | Actual image on .130: Django system check, migration leaf 0124, milestone import, four entrypoint syntax checks | PASS bounded offline CLI; no database/schema or HTTP claim |
| Authenticated API | Omitted-migration business assertion and real authenticated readback | PASS bounded normal / missing-schema / restored API sequence; shared fixture M integration remains open |
| Restore / ordered deployment / recovery / browser | HLB-434/435/436 owned runtime gates | NOT RUN; no deployed readiness claim |

The original 35 source tests are committed in tools/tests/test_plane_release.py. They use
real temporary Git repositories/remotes and controlled external SSH/Docker fakes.
The scratch image proves Docker export format only, not the complete application.
UI/Jest are N/A to this CLI-only change. The parent's real authenticated API and
later browser controls remain required under their owned acceptance gates.

## Stable source provenance and controlled faults

Tested source: bcdee4f57ea6a1fc0917728bb4c9b74cbc72c527. Git blob identities:

- tools/plane_release.py: b5740371566efe6e7ee16a07dcf8443518e268ca
- tools/tests/test_plane_release.py: 5894c9450be4b225cc54adbf970ee718a2752755
- tools/check_plane_release.py: b29a57f6dc46f89f77e8362fa240b347c093d68b

[Exact-head CI](https://github.com/eland23/plane/actions/runs/39179329092)
records head_sha bcdee4f and tests GitHub's merge ref
1b2242d93fd1d2a9e6c93b481a295f8c958e250f. These source contracts pass; this is
not an independently hosted application runtime test. Durable JUnit/native output:
[receipts](artifacts/packaging-ci-bcdee4f/receipts.json).

| Phase | Actual expected result | JUnit |
|---|---|---|
| Pass from known state | 35 pass, exit0 | [XML](artifacts/packaging-ci-bcdee4f/pass-known-state.xml) |
| Removed target guard | 1 intended assertion failure, exit1, 0 errors | [XML](artifacts/packaging-ci-bcdee4f/failure-target-guard.xml) |
| Bypassed image hash comparison | 3 intended assertion failures, exit1, 0 errors | [XML](artifacts/packaging-ci-bcdee4f/failure-image-integrity.xml) |
| Packaging incorrectly grants PASS | 1 intended assertion failure, exit1, 0 errors | [XML](artifacts/packaging-ci-bcdee4f/failure-packaging-admission.xml) |
| Removed owned-helper cleanup | 1 intended assertion failure, exit1, 0 errors | [XML](artifacts/packaging-ci-bcdee4f/failure-owned-helper-cleanup.xml) |
| Removed private-output guard | 4 intended assertion failures, exit1, 0 errors | [XML](artifacts/packaging-ci-bcdee4f/failure-private-output.xml) |
| Restore and repeat | 35 pass, exit0 | [XML](artifacts/packaging-ci-bcdee4f/restore-and-repeat.xml) |

The runner mutates temporary copies, preserving unchanged normal assertions.
All seven receipts are accepted and their owned fixture directories removed.
Rerun: python3 tools/check_plane_release.py --output /absolute/new-evidence-dir.
The editor runs source checks and builds only; all future hosted verification
is restricted to 192.168.1.130.

Earlier 25-test artifacts remain under artifacts/ as historical evidence. A local
six-phase matrix with the same final CLI/test blobs passed 35 clean/restored cases;
it predates the runner's added seventh privacy fault. An accidentally overlapping
local final matrix was stopped before acceptance, its inactive owned copy removed,
and a serial seven-phase rerun started. That rerun exceeded its 180-second
first-suite timeout while full image builds were active; it is not accepted
evidence. Exact-head CI independently completed all seven phases successfully.
No interrupted/timed-out run is an intended failure-detection receipt or a
successful retry. These runs are not a reliability sample.

## Actual packaging progress and capacity limits

Application source: e5c7acf098a890436ab6300f0bc8491c7dd22725 at pushed
refs/heads/agent/HLB-431-linear-export. A partial checkout initially lacked 3433
reachable Git blobs; they were fetched in bulk without changing tracked source.
The first package attempt ended SOURCE_CHECK before Docker builds and emitted no
candidate; it is not controlled failure evidence.

The second package attempt uses the full Git archive and upstream API/web build,
with immutable Python/Node/nginx base digests, source labels, serial frontend
build tasks and 2304 MiB Node heap. Backend build completed:
sha256:0488a84e9e4c903d972420fa7c28ebaa6a006e27049dc3e57d6ec1e2d45717ec,
307630465 bytes (Docker image Size). Frontend completed as
sha256:9e5f1f51d8bd35efe70adb1385ea76b3ca88395a1a3ea24d9d9f52b7afdeb196,
103280599 bytes. Both builds and offline payload checks pass, including 708 backend
files. The [candidate](artifacts/full-package/candidate.json) and
[checkpoint](artifacts/full-package/checkpoint.json) record PACKAGING_ONLY with
runtime admission blocked. Combined image Size is 410911064 bytes; this is not
full-stack disk usage or memory sizing. Both images are staged in the .130 image
cache. The actual
builder loaded the 08a15ab implementation before the later output guard; its logs
are under a root-only /var/lib/plane-release directory, outside every checkout.
The candidate records its actual builder checksum; source reviews of bcdee4f do
not retroactively change that builder identity.

Read-only .130 inspection observed about 9.2 GiB free Docker disk and 1.1 GiB
available memory, below the initial 10 GiB / 2 GiB runtime reservation. This is a
conservative admission budget, not measured Plane requirements. Packaging is
allowed separately and grants no runtime admission. Read-only .129 inventory
found 1 issue, 4 pages and 1 asset of 98975 bytes. Counts alone do not prove a backup or
restore and do not establish peak runtime needs. This evidence does not establish a need for hardware expansion. Existing live .129 remains unchanged.

Unused editor image tags were removed only after checking no container ancestry;
about 2.8 GB was reclaimed. Current-task build/checks do not start applications on
the editor. All unrelated containers, volumes and .130 workloads are preserved.
Private original backups/profiles/build logs remain outside Git. Raw dependency
logs are not included in this evidence bundle.

## Security, reviews and residual work

[Threat boundaries](../../security/threat-models/HLB-429-plane-runtime/README.md):
source/ref and image payload, target/namespace/probe, process/log outputs and
runtime admission. Scoped ASVS V5 validation, V7 logging, V8 data protection and
pipeline/secrets review: no remaining findings. The output guard rejects all
ancestor Git markers, bare repositories, Git directory environment overrides and
indeterminate filesystem checks. External commands use argument vectors, bounded
timeouts and owned process groups; errors expose codes. Dependency logs remain
0700/0600 outside Git. Filename checks are not a full arbitrary-source secret scan.

Independent Standards and Spec/security source reviews PASS at bcdee4f. Reviewers
did not execute tests or inspect CI; CI is a separate gate. The full child remains
incomplete pending shared fixture M integration and remaining owned
acceptance checks. Real authenticated schema-control proof now passes. Complete images, content verification and the bounded native
command probe now pass. Registry signatures, target-side release locking, effect
suppression, restored-data integrity, measured runtime admission and rollback
are separate later acceptance gates. No risk acceptance, production import,
cutover, deployed readiness or full migration completion is implied.

## Bounded native backend command result

Pushed probe source e9c3d63ea051a845e6a444fdef63febb351f8b4e ran on .130
against the transferred complete backend. [Native result](artifacts/native-command/attempt-03.log),
[provenance](artifacts/native-command/provenance.json),
[independent cleanup](artifacts/native-command/cleanup.json).
[Source CI](https://github.com/eland23/plane/actions/runs/39180147308) passed on
that exact head, including both optimized-execution guard cases.

The editor's classic Docker store identifies this image by config digest 0488a84e;
.130's containerd store imports it as immutable OCI manifest 1c54c4fb. The probe
pins the target digest and checks every source RootFS diffID plus the canonical
runtime configuration fingerprint 8e7ddf80e918f7a1360a43aeb0cbc68902ef33878ce2215b7bd6135e61ba94cc,
source revision and tree before execution. Mutable labels alone cannot pass.
The two image-store Size values differ; they are not additive runtime storage.

The probe runs a short-lived CLI container with network none, no ports, read-only
rootfs, bounded tmpfs, 512 MiB / 1 CPU / 128 PIDs and no real credentials or records.
Django's native system check passes; the loader finds 0124_module_milestones;
the native milestone module imports and all four service entrypoint files are
executable and pass sh syntax checks. Entrypoints are not started as services.
A single docker stats observation was 103.5 MiB under the 512 MiB cap; this is not
peak-memory or full-stack sizing evidence. No live database/schema, authenticated
HTTP, worker startup, restore or deployment readiness is proved by this result.

The first attempt stopped before container creation because config vs manifest
image identity differed. The second found a missing synthetic Redis URL during
Django setup and removed its owned container. Those are setup failures, not
intended business fault controls. After correction, the third passes and its
container is removed; independent readback finds zero remaining containers using
that image. Failed attempt logs are retained alongside the pass. No original
records, database, bucket, external provider or live .129 service was accessed.

Source review caught assertion guards bypassable under optimized Python. Outer
and inner probes now reject optimized execution before protected operations.
Two unchanged public subprocess tests (-O and PYTHONOPTIMIZE) first failed against
the old source reaching fake external commands, then pass with exact exit 2/code
and no marker. JUnit records both red and green separately. Scoped correction
Standards and Spec/security reviews PASS; all full-child remaining gates stay open.

Reproduce from the clean pushed source using the trusted target only:

```bash
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@192.168.1.130 python3 - \
  < docs/verification/HLB-433/native/backend_command_probe.py
```

The fixed image must already be staged, and the small single-CLI reservation must
be available. The script rejects other hosts, optimized Python and mismatched
image/provenance before starting the CLI container. This is a test admission
boundary and does not override the full release preflight.

## Expanded source safety controls

Source 3cab2da61115bba1692133056760c413cca23a7f adds the isolated restored-schema
controller and pre-Django seed boundary. The serial local matrix passes 47 checks
from known state and 47 after restoration, with nine controlled fault phases.
Each has zero setup errors: target (1 failure), payload identity (3), packaging
admission (1), owned helper cleanup (1), private outputs (4), seed admission (6),
inspection failure handling (1), receipt-failure cleanup (1), and lease cleanup
(1). All 11 receipts are accepted and temporary source fixtures removed.

The schema controller runs only on .130, with production settings, an internal
network, API/client access confined to that network, random private credentials and no workers. It
checks private backup hashes before restoring a dedicated clone. No original
service or datastore is modified. Seed admission rejects foreign database names,
hosts, settings, replica configuration and brokers before initializing Django.
Indeterminate Docker inspection preserves the clone rather than reporting clean
removal. Receipt I/O failure still attempts cleanup and closes the release lease.
The controller is published for runtime execution; source safety checks alone do
not establish its API result.

[CI for source 3cab2da](https://github.com/eland23/plane/actions/runs/39182430122)
passes all 11 phases on merge ref 134703620d78183231fdbd09c301fbd1550eddbe.
Durable [CI receipts](artifacts/source-ci-3cab2da/receipts.json) and
[local receipts](artifacts/source-controls-3cab2da/receipts.json) record the same
47 clean/restored tests and nine intended controls. These are source contracts,
separate from restored-data API execution.

Independent Standards and Spec/security reviews PASS on committed harness source
3cab2da61115bba1692133056760c413cca23a7f, including the pre-Django seed admission,
failed-inspection behavior and receipt/lease cleanup corrections. Reviewers did
not run tests or CI and do not grant runtime acceptance.

The first schema API attempt restored all 110 source tables / 812 rows exactly
before migrations, then completed migrations and synthetic setup. It did not
reach API assertions: this VM does not publish host-loopback bindings for an
internal-only Docker network. The owned attempt was interrupted, all containers
and network removed, and cloned database/credentials removed; root-only
diagnostics are retained. This is a setup failure, not the required omitted-
migration negative control. Source 494e47b removes host publication and uses an
internal-network HTTP client plus readiness inside the API container. A boundary
regression fails on the old host HTTP path, then all 13 safety checks pass.

[CI for network correction 494e47b](https://github.com/eland23/plane/actions/runs/39182821944)
passes all 48 known-state/restored checks and nine intended source fault phases.
[CI provenance](artifacts/source-ci-494e47b/provenance.json) pins the tested merge
ref. Independent Standards and Spec/security review PASS on this correction.
The separate [red/green regression](artifacts/network-regression/provenance.json)
is source-boundary evidence; it does not replace the real API phases.

Attempt 02 reached production-settings API readiness (HTTP 200) but the selected
test image did not contain pytest. No business assertions ran; the attempt
failed and removed its owned containers/network/clone/credentials. Private logs
are retained separately. This setup failure is not counted as fault detection.

A dedicated 71253286-byte test-only image now uses the pinned Python base and
five SHA-256 locked wheels, including pytest 9.0.3 from the application test
requirements. The offline build definition and requirements are committed at
ee21e40. [Transfer provenance](artifacts/schema-runner/provenance.json) binds
the editor config digest to the VM OCI manifest through identical RootFS and
runtime configuration. It contains no application source or backup. Controller
99aa49ff037daee145ed29a36aa29b81e52f2e58 verifies the pinned runner version in a
network-none, read-only, 128 MiB container before creating a database or network.
Wrong/empty-version boundary checks pass along with the existing 13 safety
cases. Standards and Spec/security correction reviews PASS on this commit.

Source 99aa49f also passes [51 known/restored source checks plus nine fault phases
in CI](https://github.com/eland23/plane/actions/runs/39183430363).
[Durable receipts](artifacts/source-ci-99aa49f/receipts.json) and merge-ref provenance
remain separate from actual API evidence. A network-none native runner CLI on
.130 returns exactly pytest 9.0.3 and removes itself.

Attempt 03 stopped before creating resources at COMPONENT_DISK_RESERVATION:
VM free disk had fallen to 1439404032 bytes. No API assertion or business-control
result is claimed. Removing the old unreferenced plane-backend:homelab image
reclaimed about 443 MB. Two obsolete HLB-464 source-fixture directories, mounted
by no container, were archived privately, fully parsed/validated, then removed
from .130, reclaiming a further 322486272 bytes. Their evidence and runner
dependencies remain. [Cleanup receipt](artifacts/owned-storage-cleanup/receipt.json)
records the archive checksum and checks; the archive is root-only outside Git.
Free disk rose to 2204045312 bytes without lowering the component reservation or
removing unrelated images, containers, volumes or live .129 data.

Attempt 04 passes the real authenticated exact-link assertion (literal fixture
ID/title/URL and null provenance). Its anonymous request correctly returns 401;
the harness had incorrectly expected 403. Packaged source
apps/api/plane/authentication/adapter/exception.py explicitly assigns 401 for
NotAuthenticated, and common.EXCEPTION_HANDLER selects that function. Source
b1e38efde29cddfa7eda620be61c1d0835166d31 changes the exact expectation to 401;
it does not accept multiple statuses. Focused Standards and Spec/security
reviews PASS. Attempt 04 as a whole is not accepted and never reaches the
omitted-migration phase. Its containers/network/clone/credentials were removed.
[Prior-attempt metadata](artifacts/schema-api-attempts/prior-attempts.json)
keeps setup failures and the mistaken expectation separate from the required
three-phase proof. Original native logs remain private outside Git.

## Actual restored-schema API control — PASS

Application revision e5c7acf098a890436ab6300f0bc8491c7dd22725 and test/controller
source b1e38efde29cddfa7eda620be61c1d0835166d31 ran on 192.168.1.130. The
[provenance](artifacts/schema-api-b1e38ef/provenance.json) binds the immutable
backend manifest and exact executed test-file SHA-256 to pushed source. The same
read-only test file is used throughout.

| Phase | Actual result | Native JUnit |
|---|---|---|
| Known state | 2 pass, exit 0, 0 errors | [XML](artifacts/schema-api-b1e38ef/pass-known-state.xml) |
| Omit required migrations / old schema | 1 intended schema assertion failure, exit 1, 0 errors | [XML](artifacts/schema-api-b1e38ef/failure-omitted-migration.xml) |
| Restore complete image / good clone | 2 pass, exit 0, 0 errors | [XML](artifacts/schema-api-b1e38ef/restore-and-repeat.xml) |

Anonymous requests return the exact application-contract 401. A real native
session authenticates the fixture link GET and verifies its literal UUID, title,
URL and null provenance through the complete image. The fault is a derived image
with 0123/0124 files removed and a second restored database reversed to 0122;
bootstrap /api/instances/ still returns 200 before the unchanged link-schema
assertion fails with HTTP 500. A separate read-only Docker-log observation
confirms the missing issue_links.external_source column, tying that failure to
the injected schema defect rather than startup/authentication.
[Fault identity](artifacts/schema-api-b1e38ef/fault-identity.json) and
[private-log hash/cause](artifacts/schema-api-b1e38ef/fault-cause.json).

The source backup restores with exact equality across all 110 tables / 812 rows
before migration. After both successful phases, every original row retains all
original field values; the synthetic fixture and added schema records are
allowed additions. [Pre-migration integrity](artifacts/schema-api-b1e38ef/restore-integrity.json),
[post-migration preservation](artifacts/schema-api-b1e38ef/preservation.json).
This is documented fixture setup plus real authenticated readback, not an import
or UI-write claim.

[Native completion](artifacts/schema-api-b1e38ef/native-result.log) and
[phase receipts](artifacts/schema-api-b1e38ef/receipts.json) pass. Independent
[cleanup readback](artifacts/schema-api-b1e38ef/independent-cleanup.json) finds zero
owned containers, no network, no fault tag or digest, no cloned PostgreSQL data
or environment/session fixture files, and can reacquire the release lease.
Original backup inputs are retained privately for the later restore rehearsal.
Private diagnostic logs are retained root-only and may include invalidated
fixture session output; no raw database, object keys, credentials or API logs
are committed. Live .129 was not modified.

[CI on b1e38ef](https://github.com/eland23/plane/actions/runs/39184401102) passes
51 source checks from known state and after restoration, plus all nine intended
source faults with zero errors. [CI provenance](artifacts/source-ci-b1e38ef/provenance.json)
records the exact head and tested merge ref separately from the .130 execution.

### Coverage limits still open

This component fixture contains only a dedicated existing-field issue/link and
session, plus the preserved original database. It is not the complete supported
issue/module/cycle/wiki/asset fixture M. No applicable parent coverage is waived:
shared fixture-M integration and the combined wiki/cycle reload belong to the
remaining runtime preparation across HLB-434/435/436. HLB-433 remains open until
its full owned acceptance is reviewed against that shared integration.

Asset restore/checksum corruption, full compatible-service startup/readiness,
migration rerun/maintenance/recovery, and browser editing/reload remain NOT RUN
under their owning children. This API control does not admit a full release,
prove full-stack sizing, authorize production import/cutover, or replace those
gates. No public preview endpoint was published for the component test.
