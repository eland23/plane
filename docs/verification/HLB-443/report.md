# Verification evidence: HLB-443 association export

Status: **PASS for HLB-443 association export; parent HLB-431 remains INCOMPLETE**.
Author: Codex. Independent Standards and Spec/security source review: PASS after fixes.
Spec: [HLB-443](https://linear.app/fashionfindrs/issue/HLB-443), parent [HLB-431](https://linear.app/fashionfindrs/issue/HLB-431).
Policy: FashionFindrs `docs/testing/POLICY.md` and `REPORT-TEMPLATE.md`.

## Scope and coverage

| Behavior | Owned AC | Owner | Saved test in tools/tests/test_linear_associations.py | Independent assertion | Layer | Result | Evidence |
|---|---|---|---|---|---|---|---|
| MIG-01 / issue-only document | AC1,V1 | HLB-443 | issue_association_discovers_document_when_team_projects_are_empty | Literal document UUID/content/edge retained even with empty team projects | pytest/contract | PASS | pass-known-state.xml |
| MIG-01 / six issue fixture | AC1 | HLB-443 | fixture_m_all_six_issue_document_associations_are_visited_once | Literal six issue UUIDs 2/5/11/17/21/30 requested exactly once, one issue-only document/edge | pytest/contract | PASS | pass-known-state.xml |
| MIG-01 / portfolio pages | AC1 | HLB-443 | paginated_portfolio_retains_shared_documents_edges_and_foreign_stubs | Exact project/initiative/document/milestone/update counts; archived second page; shared document edges retained; foreign project never traversed | pytest/contract | PASS | pass-known-state.xml |
| MIG-01 / cycle and label group | AC1 | HLB-443 | cycle_timezone_payload_and_exclusive_label_group_are_retained | Literal DST-offset timestamps preserved; group UUID/selection mode/child edge retained | pytest/contract | PASS | pass-known-state.xml |
| MIG-01 / initiative ancestors | AC1 | HLB-443 | initiative_parent_without_direct_project_is_traversed_once | Previously unreachable parent and its document discovered exactly once; hierarchy edge retained | pytest/contract | PASS | pass-known-state.xml |
| MIG-01 / standalone catalogs | AC1 | HLB-443 | standalone_team_document_is_discovered_without_project_or_issue_link; team_led_initiative_with_no_project_is_discovered | Literal team-only document and team-owned initiative discovered without project association | pytest/contract | PASS | pass-known-state.xml |
| MIG-01 / permission/scope | AC1,V2 | HLB-443 | bad_association_never_reports_success; foreign_cycle_team; milestone_cannot_claim_a_different_parent_project; team_catalog_rejects_foreign_document; foreign_catalog_initiative_is_denied_before_payload_commit_and_traversal | Explicit partial/duplicate/cursor/scope/parent errors; foreign initiative neither persisted nor expanded; no raw provider error in manifest | pytest/contract | PASS simulated | pass-known-state.xml |
| MIG-01 / integrity/recovery | AC1,V2 | HLB-443 | committed_pages_resume_after_auth_loss; checksum_and_malformed_resume; verified_seed; complete_resume; request_and_byte_limits; cancel_retains_committed_checkpoint; concurrent_writer | Original bytes retained, checksum/shape rejection leaves manifest unchanged, complete resume makes scope request only, private modes, limits/cancel preserve cursor, lock excludes writer | pytest/filesystem | PASS | pass-known-state.xml |
| MIG-02 / field capability limits | AC2 | HLB-443 | api_field_inventory_does_not_claim_unread_custom_usage_absent | Literal schema fields/presence counts; unread custom usage marked unresolved and requires cutover disposition | pytest/contract | PASS | pass-known-state.xml |
| MIG-02 / final cutoff and deletions | AC1/2 | HLB-447 | Separately owned | Must account for updates/deletions/inaccessible records and full coverage disposition | contract/API | NOT RUN here | HLB-447 |
| Asset bytes/history/import/native UI | Other parent AC | HLB-448 and later import children | Separately owned | Source archive is not destination/native-workflow proof | API/UI | NOT RUN here | parent coverage map |
| UI/Jest/browser/TesterArmy | V1 | HLB-443 | N/A | CLI-only Python; no changed TS/UI or hosted service | UI/Jest | N/A | source diff |

23 association cases pass; combined unchanged HLB-442 plus HLB-443 suite is53 cases.
The full synthetic destination fixture M and native journey expectations apply
to later import children; this slice tests the corresponding source association
identities/values at the locked export seam. No parent requirement is waived.

## Provenance and reproduction

Exporter/test source introduced at `05a56bd`; clean pushed live-run revision:
`58527592d7f86b103380da28f48c7fb45ae8c838`. The latter changes only runner whitespace;
exporter/test bytes remain identical. Matrix used these exact exporter/test
bytes before commit; this report and artifacts are a later evidence-only commit.
Python3.9.2, pytest8.4.2. External provider boundaries are controlled fakes in
contracts. Twenty-five generated query profiles validate with zero errors
against the official Linear SDK schema retrieved on2026-10-18; schema validation
is protocol evidence, not source permission/coverage evidence.

```bash
TMPDIR=/var/tmp python3 tools/check_linear_associations.py --output /absolute/new-evidence
python3 -m pytest tools/tests/test_linear_export.py tools/tests/test_linear_associations.py -q
# Inject an existing LINEAR_API_KEY through the environment; never print its value.
python3 tools/linear_associations.py --issues /absolute/private/issues \
  --output /absolute/private/new-associations
# Correct a prerequisite then resume the same source/output:
python3 tools/linear_associations.py --issues /absolute/private/issues \
  --output /absolute/private/existing-associations --resume
```

Default limits:20,000 requests,512MiB archive payload,16MiB per file/HTTP response,
1GiB free disk reserve; shared HTTP transport three attempts, capped30s backoff,
30s response deadline/socket timeout. A blocked read can consume one socket wait
beyond remaining wall-clock deadline before rejection. Request/archive limits
are explicit CLI arguments. Output is a separate0700 directory with0600 files;
input issue archive is read-only. No application/preview/container was started.
VM deployment identity: N/A to this read-only CLI; destination writes: zero.

## Three-check receipts

| Check | Expected | Actual | Exit | Artifact |
|---|---|---|---|---|
| Pass from known state | All normal saved assertions pass |23 passed,12.36s |0 | artifacts/pass-known-state.xml and .log |
| Demonstrate omitted-document detection | Literal document count/edge assertion fails |1 intended assertion failure,1.11s |1 | artifacts/failure-document-edge.xml and .log |
| Demonstrate checksum detection | Unchanged checksum rejection assertion fails |1 intended missing-rejection failure,1.31s |1 | artifacts/failure-checksum.xml and .log |
| Restore and repeat | Original source/tests pass with fresh fixtures |23 passed,11.99s |0 | artifacts/restore-and-repeat.xml and .log |

The runner mutates only temporary tool copies, never saved test assertions.
It removes the issue-document traversal and bypasses the resume checksum gate,
then restores normal source. All matrix fixture roots were removed after each
pass/failure; `artifacts/receipts.json` records acceptance and absence.
Pre-fix regressions independently caught a missing parent initiative and late
foreign-catalog initiative rejection; fixes then pass. No setup crash substitutes
for the named business assertions in the negative matrix.

## Error handling and recovery

Controlled GraphQL/auth loss, wrong scope, duplicates, bad cursor/parent/team,
corrupt seed/page/manifest, concurrency, cancellation and request/byte limits
must fail explicitly. Resume validates source fingerprint, exact connection/
cursor and all committed hashes before any checkpoint update. Complete resume
replays local pages and checks source scope without requesting graph pages.
Source permission errors are simulated; live graph visibility remains constrained
by the existing credential. Raw errors and credential values are excluded.

## Evidence bundle

Native pytest logs and native JUnit XML plus cleanup receipts are committed in
`artifacts/`. All included payloads are synthetic. Real issue/document/actor data
is retained only in private storage outside Git. CI runs the same matrix without
network credentials and retains its sanitized artifact for30days. Current-head
CI and final review disposition are recorded separately in PR/Linear comments.
No whole-PR CI success follows from local checks alone.

Threat model: `docs/security/threat-models/HLB-431-linear-export/THREAT-MODEL.md`.
Source ASVS focus V5 validation, V7 errors, V8 data protection plus pipeline.
No schema/resolver/mutation added; no Plane security-drift script exists, and
FashionFindr resolver authorization-map checks are N/A to the client-side query
profiles. Reviewed boundaries: source token, fixed HTTPS response, private input,
UUID variables, raw checkpoint/output and synthetic CI artifacts. No LLM/content
execution, URL download, source mutation or destination persistence claim.

## Execution metrics

Contract durations/attempts are in native logs above; no flaky retries were used.
Real source requests are read-only metadata queries, not model/provider generation.
Model tokens/cached tokens/billed cost unavailable; no caching or cost-saving
claim. Completed resume intentionally uses verified local replay and one scope
request. Existing services/data and the private issue input remain untouched.

## Live source receipt and verdict

The protected read-only run completed at clean pushed source5852759. It retained
**1,015 pages and200 association/hierarchy edges**, including9 projects,
3 initiatives,19 cycles,46 labels,6 states,2 team memberships,25 milestones,
36 project updates and10 documents. Three returned cycles were archived.
The `user` count of1 is project-member nodes, not a claim that every historical
actor in the workspace was enumerated. Source window:20:56:24.371–20:59:59.565 UTC
on2026-10-18. Input issue snapshot was earlier; no atomic cutoff is asserted.

Independent `verify_archive.py` recomputed every saved-page hash and reconstructed
unique per-kind counts, all200 edges, exact connection/cursor provenance and
terminal-page coverage from raw provider pages. It matched the recorded manifest
and private modes. This proves archive consistency, not hidden/deleted/API-inaccessible
record completeness. `artifacts/live-associations-summary.json` contains only
sanitized counts/booleans/times. Reproduce without network:

```bash
python3 docs/verification/HLB-443/verify_archive.py /absolute/private/associations
```

A separate completed `--resume` made exactly one organization/team scope request
and zero graph-page requests, preserved all1,015 raw page hashes, reproduced the
counts, and left the input issue manifest unchanged. Receipt:
`artifacts/live-resume-summary.json`. Real data remains root-only at
`/var/lib/plane-migration/HLB-443-20261018`, intentionally retained for migration
reconciliation. No private issue/document/actor content is committed.

Source Standards and Spec/security reviews PASS after the initiative ancestor and
pre-persistence scope corrections. Final evidence/CI disposition is posted on the
PR and Linear child separately. No unresolved source finding or cleanup failure;
all saved matrix fixtures were removed and pre-existing services/data retained.
Parent HLB-431 remains incomplete: final deltas/full field disposition, assets,
imports/reconciliation and native user journeys are owned by later children.
No import, deployment, integration cutover or source-authority change is included.
