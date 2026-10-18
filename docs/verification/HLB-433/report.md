# HLB-433 — Plane release-candidate evidence

Status: **BLOCKED for full acceptance**. Source contracts: **PASS**. Owner: Codex.
Review: Standards PASS; Spec source correctness PASS, full acceptance INCOMPLETE.
Spec: [HLB-429](https://linear.app/fashionfindrs/issue/HLB-429).
Child: [HLB-433](https://linear.app/fashionfindrs/issue/HLB-433).

## Scope and coverage

| Behavior / AC | Saved test or command | Independent assertion | Result |
|---|---|---|---|
| REL-01 / PLN-REL-AC1 | `release_preflight_*`, concurrent candidate test | Exact target/namespace/error codes, Git SHA/ref and clean state; locked builds rejected | PASS at command/contract boundary |
| REL-02 / PLN-REL-AC1 | `complete_image_manifest_*`, snapshot, stage pinning and backend command tests | Literal content hashes, source Git blobs, exact command map and immutable identities | PASS for synthetic fixtures and real scratch-image export format |
| REL-02 full build | `plane_release.py build` | Complete Plane API/worker/migrator/frontend images, verified against source and commands | BLOCKED; not built |
| V1–V3 | `check_plane_release.py` and linked JUnit/native receipts | Two clean suites around unchanged tests detecting actual bounded source defects | PASS for covered contracts; not a full ticket PASS |

All 25 saved tests are in `tools/tests/test_plane_release.py`. They cover target,
namespace, dirty/unpushed/mismatched source, capacity error/recovery, malformed
probe handling, process locks, mixed revisions, missing/changed/whiteout/symlink
and ancestor-replaced content, archive exclusions, command identities, pinned
external build stages and process-group deadlines including an exited leader.

## Provenance and reproduction

- Tested source revision: `6738024cd930b2174f00442f446f5cc416ba3f54`.
  Tests ran on equivalent source blobs before commit; source was then committed,
  pushed and checked clean. Later report-only commits do not change those tests.
- Application deployment revision: N/A; no Plane runtime was deployed.
- Test host: editing/build server, Python 3.9.2, pytest 8.4.2, Docker 29.1.1.
- The only real Docker builds are synthetic `FROM scratch` archive-format fixtures.
  They have no RUN/CMD service process; no containers/services were started.
- SSH/Docker protocol fakes test external failures. Real Git repositories/remotes
  prove source identity behavior. These are separate from live application API proof.
- Rerun: `python3 tools/check_plane_release.py --output /absolute/new-evidence-dir`.
  Output must be a new directory. It saves JUnit XML plus native logs/receipts.
- UI, Jest and authenticated application API: N/A for the new CLI-only interface;
  no application API/UI changed. The parent-defined omitted-migration API control
  remains **NOT RUN** until the isolated complete application is available.
- Hosted verification and any future services remain restricted to `.130`.

## Three-check receipts

| Run | Expected | Actual | JUnit |
|---|---|---|---|
| Pass from known state | clean pass | 25 passed, exit 0 | [XML](artifacts/pass-known-state.xml) |
| Target-guard defect | intended assertion failure | 1 failed, exit 1; unchanged test catches removed target denial | [XML](artifacts/failure-target-guard.xml) |
| Image-integrity defect | intended assertion failure | 3 failed, exit 1; unchanged missing/changed/whiteout tests catch bypassed comparison | [XML](artifacts/failure-image-integrity.xml) |
| Restore and repeat | clean pass | 25 passed, exit 0 | [XML](artifacts/restore-and-repeat.xml) |

The runner mutates temporary **copies** of the tool, leaving the normal tests
unchanged. Negative suites fail at business assertions, not setup timeouts.
Fixtures are synthetic; no live customer or Linear records were modified.
Receipts: [JSON](artifacts/receipts.json). Native logs accompany each XML.

## Live preflight and blocked acceptance

The pushed clean revision was invoked with the real trusted SSH target, full
commit SHA, exact pushed branch ref and `plane-rehearsal-migration` namespace.
It exited 2 with `TARGET_CAPACITY` before building, writing a candidate manifest
or changing services. Independent read-only VM inspection found about 5.1 GiB
free disk and 1.46 GiB available memory, below the initial 10 GiB / 2 GiB
reservation budget. That budget is an admission rule, not measured app sizing.

Complete Plane images, actual backend command execution, authenticated API
failure controls, database compatibility, runtime identity and deployment
readiness are **NOT RUN/BLOCKED**. The scratch-image check cannot establish them.
HLB-433 stays incomplete; dependent release/restore tickets remain blocked.
No services on `.129` or `.130` were stopped or changed.

## Security and review

Diff-scoped pipeline/secrets review: pinned GitHub actions, contents-read-only
workflow, checkout credentials not persisted, no untrusted secret-bearing CI,
validated source/namespace/base digest inputs, no local shell interpolation of
inputs, bounded external processes and sanitized errors. Source hashes include
all copied backend payloads/entrypoints, independently compared with Git blobs;
image whiteouts/replacements cannot leave an invalid lower-layer file accepted.

Review found archive-attribute omissions, ancestor replacement, deadline edges,
mutable nginx base and missing entrypoint validation; these were fixed and
regression cases added. Existing Abide telemetry is ignored as local output;
rubrics/policies/hooks remain enabled and trackable. No residual risk acceptance
is implied. Registry signatures, runtime hardening and actual release locking
belong to subsequent gates.

## Cleanup and verdict

All four receipt runs removed their owned fixture directories. Synthetic image
tags were removed in `finally`; final image inventory contains no
`plane-release-test` tags. Stream timeout tests kill their owned process groups.
Docker build cache was not pruned, and unrelated resources were untouched.

JUnit/native artifacts are committed here for durable review rather than relying
solely on CI's 30-day artifact retention. Attempt count: one final four-run matrix;
earlier TDD/review cycles are not a reliability sample and are not hidden as
successful retries. Cache/model/token/billed cost: N/A (no inference provider).

Verdict: source implementation is reviewable; **do not mark the ticket Done** or
claim a complete migration runtime until blocked build/API/runtime proof passes.
