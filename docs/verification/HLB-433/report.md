# HLB-433 — Plane release-candidate evidence

Status: **INCOMPLETE for full acceptance**. Source contracts and scoped source
reviews PASS. Complete application packaging and native runtime proof remain
separate gates. [Child](https://linear.app/fashionfindrs/issue/HLB-433),
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
| REL-02 full image build | Complete API/worker/beat/migrator backend and full web, same application revision, offline payload verification | IN PROGRESS; no success candidate published yet |
| Native commands / authenticated API | Actual packaged image command execution and omitted-migration business assertion | NOT RUN; required before full acceptance |
| Restore / ordered deployment / recovery / browser | HLB-434/435/436 owned runtime gates | NOT RUN; no deployed readiness claim |

All 35 source tests are committed in tools/tests/test_plane_release.py. They use
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
307630465 bytes (Docker image Size). Frontend and final offline payload checks
remain in progress. No candidate success manifest has been published. The actual
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
incomplete pending complete images, final content verification and real native
command/API proof. Registry signatures, target-side release locking, effect
suppression, restored-data integrity, measured runtime admission and rollback
are separate later acceptance gates. No risk acceptance, production import,
cutover, deployed readiness or full migration completion is implied.
