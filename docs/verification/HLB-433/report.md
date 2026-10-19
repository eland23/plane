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
| Native packaged command | Actual image on .130: Django system check, migration leaf 0124, milestone import, four entrypoint syntax checks | PASS bounded offline CLI; no database/schema or HTTP claim |
| Authenticated API | Omitted-migration business assertion and real authenticated readback | NOT RUN; required declared coverage remains open |
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
