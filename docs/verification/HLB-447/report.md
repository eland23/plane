# Verification evidence: HLB-447 snapshot deltas and coverage

Status: **PASS for the scoped HLB-447 source delta/coverage slice; parent HLB-431 INCOMPLETE**.
Author: Codex. Independent Standards and Spec/security source reviews: PASS.
Tracking: [HLB-447](https://linear.app/fashionfindrs/issue/HLB-447), parent
[HLB-431](https://linear.app/fashionfindrs/issue/HLB-431), [PR8](https://github.com/eland23/plane/pull/8).
Policy: FashionFindrs `docs/testing/POLICY.md` and `REPORT-TEMPLATE.md`.

## Behavior coverage

Tests below are saved in `tools/tests/test_linear_coverage.py`. Public seams are
`snapshot_delta_coverage` and source-scoped `reconciliation_detects_loss`.
All rows belong to HLB-447; the broad parent remains incomplete.

| Behavior | Owned AC | Saved test | Independent assertion | Layer | Result/artifact |
|---|---|---|---|---|---|
| MIG-02 edit/archive/missing issue | AC1/2 | concurrent_edit_archive_and_missing_record_are_named_without_inventing_deletion | Literal FAS-2 title, FAS-11 archive and missing FAS-5 named; no confirmed deletion/private value | pytest/API contract | PASS / pass-known-state.xml |
| MIG-02 cutoff | AC1/2 | archive_event_after_cutoff_is_an_explicit_exception | Literal archive field after specified cutoff remains exception; cutoff unverified | pytest/contract | PASS / pass-known-state.xml |
| MIG-02 observation provenance | AC1 | identical_snapshots; completed_resume_does_not_create_an_independent_capture | Same capture and copied/completed scope-only resume remain non-independent | pytest/filesystem | PASS / pass-known-state.xml |
| MIG-02 schema/access | AC2 | schema_inventory_keeps_permission_and_unavailable_outcomes_explicit; schema_auth_loss_stops_requests_and_retry_uses_new_private_output | Missing history type and denied comment type explicit; 403 stops further schema calls; fresh allowed retry succeeds | pytest/API contract | PASS simulated / pass-known-state.xml |
| MIG-02 cancel | V2 | schema_cancel_keeps_failed_checkpoint_and_no_false_success | Interrupted capture leaves private FAILED/INTERRUPTED checkpoint, no complete inventory | pytest/filesystem | PASS / pass-known-state.xml |
| MIG-02 source changes during traversal | AC1 | intra_snapshot_object_to_null_edit_is_not_silently_merged; schema_drift_is_not_hidden_when_record_values_are_unchanged | Project lead object→null conflict retained; exact added/removed Issue schema names | pytest/contract | PASS / pass-known-state.xml |
| MIG-09 missing edge/row | scoped AC7 | missing_document_edge_is_reported_with_exact_direction | Exact issue→documents→document edge and unconfirmed document tombstone; nonzero verdict | pytest/contract | PASS / pass-known-state.xml |
| MIG-09 CLI privacy/verdict | scoped AC7 | cli_returns_nonzero_for_named_loss_without_printing_private_payloads | Exit1, literal removed-edge count, protected report, no private title/content in console | pytest/subprocess | PASS / pass-known-state.xml |
| MIG-09 coverage disposition | AC2 | coverage_classifies_archived_unread_unavailable_and_unsupported_fields; nested_field_capture_and_credential_exclusion_are_distinct | Explicit archive/unread/unavailable/unsupported rows; nested object partial; credential exclusion; custom usage unknown | pytest/contract | PASS / pass-known-state.xml |
| MIG-09 presence vs usage | AC2 | coverage_empty_values_preserve_false_and_zero_as_populated | Null/empty text/list/object/relation unused; False/0/nonempty text populated for six literal fixture records | pytest/contract | PASS / pass-known-state.xml |
| MIG-09 corruption/recovery | V2 | corrupt_or_incomplete_input; report_is_private_inputs_unchanged_and_repeat_never_overwrites | Invalid archive creates no report; originals byte-identical, private output, no overwrite, fresh repeat equal but cutoff/native blocked | pytest/filesystem | PASS / pass-known-state.xml |
| MIG-09 deliberate loss | V2 | unchanged concurrent_edit_archive and missing_document_edge assertions | Suppressing field/edge differences fails the named business assertions; restored source passes | pytest fault controls | PASS / failure-*.xml and restore-and-repeat.xml |
| Real source | V3 | protected fresh exports + independent readback | New source observations, full private page/hash/graph checks and scoped diff readback | read-only Linear API/offline | PASS / live-summary.json and independent readback receipts |
| Native destination rows/assets/timestamps/workflows | parent AC3/6/7 | Later children HLB-448,451,453,454,455 | Protected source report cannot prove native import or browser behavior | API/UI | NOT RUN here; separate ownership |
| UI/Jest/browser/TesterArmy | V1 | N/A | CLI-only Python; no changed UI, TypeScript or hosted service | UI/Jest | N/A |

Inventory:15 behavior rows,13 PASS,1 NOT RUN under later-child ownership,1 N/A;0 approved deferrals. No coverage claim extends beyond these rows.

The fixture uses synthetic UUIDs for all six FAS-like source identities. Tests
never resolve those identifiers against live Linear. Destination fixture M and
native persistence/role/browser checks remain owned by later import children.
No applicable deferral is approved or silently counted as PASS.

## Provenance and reproduction

Artifact access: committed synthetic evidence is durable in Git; CI uploads the same sanitized matrix for30days. Private real-data archives are intentionally retained outside Git for migration reconciliation. No source values or credential strings were included after manual artifact inspection.

Application/test source: `8511256c17a45698ef172783ba33bbf151122bc3`, pushed
clean before the read-only source export. Matrix and combined regression suites
used these exact application/test bytes; this report/artifacts form a later
evidence commit. Python3.9.2 and pytest8.4.2. Controlled GraphQL callables are
external boundary fakes; no internal exporter function is mocked.

```bash
TMPDIR=/var/tmp python3 tools/check_linear_coverage.py --output /absolute/new-evidence
python3 -m pytest tools/tests/test_linear_export.py tools/tests/test_linear_associations.py tools/tests/test_linear_coverage.py -q --basetemp=/var/tmp/new-fixtures
```

Run operator schema/compare commands in `tools/LINEAR_COVERAGE.md`. Credentials
come from the existing environment, never arguments. Raw source records and
schema/report remain in root-only directories under `/var/lib/plane-migration`,
outside Git. Saved synthetic logs/JUnit contain no live source values. Trailing horizontal whitespace emitted by pytest was normalized for Git only; artifact-normalization.json retains original and committed hashes. Test results/assertions and JUnit counts are unchanged.
Deployment/image identity and VM URL: N/A, read-only CLI with zero destination
writes and no service/preview/container started. Existing .129/.130 data and
services are untouched. Exact-head CI is a separate PR merge gate, not inferred
from local tests.

## Three-check evidence and cleanup

| Check | Actual | Exit | Artifact |
|---|---|---|---|
| Pass from known state |16 cases,9.341s |0 | artifacts/pass-known-state.xml and .log |
| Demonstrate changed-field loss detection |1 intended assertion failure,1.145s |1 | artifacts/failure-modified-field.xml and .log |
| Demonstrate missing-edge detection |1 intended assertion failure,1.212s |1 | artifacts/failure-removed-edge.xml and .log |
| Restore and repeat |16 cases,8.469s |0 | artifacts/restore-and-repeat.xml and .log |
| Combined exporter regressions |69 cases,14.990s |0 | artifacts/combined-regressions.xml |

The runner modifies temporary production-source copies only. Saved normal
assertions remain unchanged. Negative JUnit records each have one failure,
zero errors: no setup crash replaces the intended business assertion. Fixture
roots are removed after all four matrix runs; acceptance/removal receipts are
saved in `artifacts/receipts.json`. Earlier red tests independently reproduced
metadata-only replay misclassification and empty-value misclassification; both
now pass. No flaky retry was needed. Private live archives are intentionally
retained as source recovery evidence, not test cleanup failures.

## Limits, security and readiness

Both issue and association archives are validated against their scope/profile,
committed page hashes, terminal traversal and graph totals before report output.
Incomplete/corrupt input fails without creating a report; a report is never
overwritten. Schema capture retains partial failure checkpoints and stops new
requests after authorization loss. Valid retry uses a new protected output.

The manifest records original observation identities separately from mutable
file fingerprints. Completed scope-only readback cannot become independent just
because its finish timestamp changed. Capture timestamps are local provenance,
not provider-signed proof; two equal non-atomic reads still do not prove a freeze.
A missing row may be inaccessible/deleted/out of scope and never authorizes
removal of destination data. Post-cutoff events and source conflicts remain
explicit. Historical schema comparison covers Issue only; prior schemas for
other types were not retained and remain explicitly unverified.

Available API fields are a capability inventory, not permission or record-
completeness proof. Unread fields/custom properties/types remain unknown usage.
Partial relation IDs are not a full object export. No native disposition is
inferred; all enumerated fields get archive/blocked/unavailable/unsupported
status and owner-disposition requirements, with credential fields explicitly
excluded. HLB-448 and later content/graph/import children must close their gaps.
Final owner dispositions, verified cutoff and native import evidence always
block cutover until independently satisfied by their owning work.

Threat model: `docs/security/threat-models/HLB-431-linear-export/THREAT-MODEL.md`.
ASVS focus V5 validation, V7 safe errors, V8 private storage plus pipeline.
No resolver, mutation, arbitrary-URL fetch, LLM/content execution or authorization
change added. Fixed API endpoint, bounded shared transport, private manifests,
hashed field differences and sanitized stdout protect the source credential and
payload. Existing transport bounds:16MiB response/file, three attempts/capped30s
backoff; socket wait may extend one response wait beyond remaining total deadline.
Archive replay is capped20,000 association pages/512MiB plus the separately
validated issue seed. No destination security-drift checks apply to this CLI.

Execution metrics: durations and case counts above; no model/provider generation
or cloud/service deployment. Model tokens, cached tokens and billed cost are
unavailable; no savings claim. Source capture uses read-only authenticated calls.

## Live source receipt

The clean pushed source captured all33 configured schema categories as available,
801 issues over17 pages and1,015 association pages with200 edges. Fresh source
window:2026-10-18 21:23:07.473–21:26:48.133 UTC. These are separate non-atomic
captures; scope is limited by the current credential and selected query profiles.

Comparison found exactly two issue field changes: one description and its
updatedAt timestamp. No issue/association entity addition or disappearance,
edge difference or Issue schema change was observed. It returns a nonzero
comparison verdict (1), correctly requiring reconciliation. There were no
observed intra-snapshot conflicts. This does not prove inaccessible/deleted
source completeness or a frozen cutoff.

The complete configured field ledger contains1,100 rows:159 archive and941
blocked/unread rows;0 native claims. These are schema-field rows, not a count
of missing product features. All33 schema types being visible does not prove
record-read access. Unread categories/fields remain explicit work or owner
dispositions; no API-unavailable type happened to occur in this live capture.
Unavailable, access-denied and unsupported cases are separately proven by the
controlled contracts. Final source cutoff, delta reconciliation, owner
resolutions and native import evidence remain blocked before cutover.

`artifacts/live-summary.json` retains only aggregate counts, time windows and
manifest hashes. `live-associations-readback.json` and the baseline receipt
independently rehash all raw graph pages and verify unique counts, all200 edges,
connection/cursor termination and private modes. `live-comparison-readback.json`
independently reconstructs issue row/field differences from raw issue pages
and graph-edge differences from the verified graphs, matching both changed
fields and no missing issue. It intentionally does not claim independent
association-field reconciliation, which remains later full-reconcile work.
The separate checker uses no production exporter imports or network calls.

The public CLI was rerun into a new private output. It returned1 with two
modified fields, identical semantic delta/coverage/readiness/cutoff, no provider
calls and unchanged input manifests (`live-cli-repeat.json`). The protected
source archives, schema and detailed reports remain outside Git under
`/var/lib/plane-migration/HLB-447-*`, intentionally retained for reconciliation.
No private field value, issue UUID, credential or asset URL enters these receipts.

Reproduce the independent readback with the protected source paths:

```bash
python3 docs/verification/HLB-443/verify_archive.py /private/new-associations
python3 docs/verification/HLB-447/verify_comparison.py \
  --before-issues /private/old-issues --after-issues /private/new-issues \
  --before-graph /private/old-associations --after-graph /private/new-associations \
  --report /private/saved-report
```

Standards and Spec/security source reviews PASS; final evidence review and CI
on the final PR head are recorded separately in the PR/Linear comments. Saved
fault fixtures were removed after every passing/failing run; no cleanup failure,
unresolved source review finding or unreported retry remains. Native import,
asset preservation, owner approval and cutover are not authorized by this report.
