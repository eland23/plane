# Verification evidence: HLB-449 read-only import plan

Status: **PASS for the dry-run slice; real import BLOCKED; HLB-431 INCOMPLETE**.
Tracking: [HLB-449](https://linear.app/fashionfindrs/issue/HLB-449), parent
[HLB-431](https://linear.app/fashionfindrs/issue/HLB-431).
Separate Standards and Spec/security source reviews: PASS. Final evidence review
and exact-head CI are recorded on the child PR; neither is inferred from local tests.
Policy: FashionFindrs `docs/testing/POLICY.md` and `REPORT-TEMPLATE.md`.

## Live result and required Plane changes

Authenticated SSH / PostgreSQL snapshots of existing Plane at `192.168.1.129`
showed **110 public tables unchanged**, including row hashes, columns/types,
index and constraint hashes. The existing one workspace, one test project and
one issue were preserved. No source API calls, import writes, new token,
service start or deployment occurred. The planner completed with exit1 because
it found real blockers; this is a completed blocked plan, not an execution error.
An independent offline readback verified all801 issues against original source
pages and both saved snapshot hashes.

| Proposed destination capability | Count |
|---|---:|
| FAS project | 1 |
| Issues | 801 |
| Modules from Linear projects | 9 |
| Shared cycles | 19 |
| Labels / states | 46 / 6 |
| Initiatives / module milestones | 3 / 25 |
| Pages | 10 |
| Uploaded-file attachment proposals | 25 |
| External-resource reference links | 530 |

520 issues have a module;281 remain in the team backlog. Every source FAS number
and gap is retained; the maximum is813 and the next proposed number is814.
These are proposals, including capabilities whose schema is missing. There are
zero reused imported identities.555 attachment metadata records represent25
approved uploaded files and530 external-resource links; archived bytes are
verified, not uploaded or rendered. The full source counts, including36 project
updates and archived membership/user records, are in `artifacts/live-summary.json`.
Archive-only objects are not claimed as native imports.

The23 named blockers are:

- Missing native `initiatives` and `module_milestones` tables (two blockers).
  HLB-453 must implement portfolio/milestone parity before these native proposals.
- `issue_links` has no immutable `external_source` / `external_id` columns (two
  blockers). HLB-454 needs persistent import identity for safe link replay; a
  dedicated import identity ledger is also possible if scoped and verified.
- Two distinct source labels share a name and would violate Plane's active
  project/name uniqueness (two blockers). HLB-453 must preserve their distinct
  identities and semantics; the planner neither merges nor renames them.
-17 issue creator references have no exported actor record (17 blockers).
  HLB-454 must resolve complete actor provenance; never substitute the importer.

No issue-number conflict was found in this target. The stored coverage report
also keeps owner field dispositions, native evidence, verified cutoff and source
delta reconciliation open. A dry run cannot waive them. The final importer,
resumability, native graph/content evidence and reconciliation remain owned by
HLB-451/452/453/454/455. No capacity increase is required to run this planner.

## Behavior and evidence mapping

All saved tests are in `tools/tests/test_linear_import_plan.py`. Each row is owned
by HLB-449 and scoped to `dry_run_no_write` / `reconciliation_detects_loss`.

| Behavior | Owned AC | Saved test(s) | Independent expectation | Layer / result / artifact |
|---|---|---|---|---|
| MIG-04 immutable identity and numbers | AC4,V1 | dry_run_keeps_source_uuid_display_number_and_destination_uuid_separate | Literal six IDs/numbers2,5,11,17,21,30; literal independent UUID constants; next31 | pytest/service PASS; pass-known-state.xml |
| MIG-04 mapping composition | AC4,V1 | one_fas_project_two_modules_cross_module_parent_and_unassigned_issue | One project, two modules, five assigned/one free, shared cycle and cross-module parent | pytest/service PASS; pass-known-state.xml |
| MIG-04 collision/recovery/determinism | AC4,V2 | reserved_number_collision_blocks_and_correction_restores_identical_plan | Reserved deleted11 blocks FAS-11; corrected independent repeated plans identical | pytest/service PASS; pass-known-state.xml |
| MIG-04 source binding/name collision | AC4 | explicit_project_rejects_foreign_or_partial_source_binding; existing_name_collision_is_not_merged_by_name | Foreign/partial source cannot be reused; existing same-name project blocks without merging | pytest/service PASS; pass-known-state.xml |
| MIG-04 attachment identity inventory | AC4 | attachment_source_identity_reuses_exact_record_and_rejects_occupied_uuid; identity_inventory_cannot_be_omitted_when_records_exist | Exact source reuse; foreign UUID collision; omitted populated inventory rejected for links and attachments | pytest/service PASS; pass-known-state.xml |
| MIG-04 schema/number infrastructure | AC4 | numbering_infrastructure_is_required_even_for_empty_destination; identifier_reservation_inventory_accepts_plane_integer_primary_key | Missing scope/number/allocator schema blocks even empty; actual integer identifier metadata accepted, invalid denied | pytest/service PASS; pass-known-state.xml; native-identifier-red/green.xml |
| MIG-09 missing schema/edge | scoped AC7 | missing_schema_and_parent_reference_are_named_not_silently_dropped | Missing pages table and six exact parent references named, plan invalid | pytest/service PASS; pass-known-state.xml |
| MIG-09 destination drift | scoped AC7,V2 | destination_drift_is_named_and_prevents_a_stable_plan | One changed issues hash yields exact table diff and blocks no-change claim | pytest/service PASS; pass-known-state.xml |
| MIG-09 independent checker | scoped AC7,V2 | independent_receipt_checker_detects_number_loss | Original archive IDs/numbers/placement and raw snapshot digests checked; changed number rejected; optimized Python cannot bypass checks | pytest/offline PASS; optimized-checker-red/green.xml |
| MIG-04 private/error/no-overwrite | AC4,V2 | private_assets_are_verified_before_destination_access_and_outputs_never_overwrite | 0700/0600 files, existing output unchanged, corrupt blob denied before destination access | pytest/filesystem PASS; pass-known-state.xml |
| MIG-04 cancellation/scope/transport/CLI | AC4,V2 | cancelled_snapshot_and_unknown_workspace_preserve_input_without_output; snapshot_transport_is_fixed_authenticated_and_rejects_non_readonly_response; cli_exit_and_sanitized_transport_failure | Cancel/foreign workspace no output/input change; fixed authenticated read-only transport, sanitized timeout, CLI pending-gate exit3 | pytest/SSH external contract PASS; pass-known-state.xml |
| MIG-04 no-write live receipt | AC4,V3 | plane_snapshot.collect + verify_linear_import_plan.py | All110 public table/index/constraint/column fingerprints equal;801 source issues independently checked | authenticated SSH/DB + offline PASS; live-summary.json, independent-live-readback.json |
| V2 defect detection and cleanup | V2 | check_linear_import_plan.py | Unchanged collision and drift assertions fail nonzero under deliberate defects; restore passes; every isolated fixture removed | pytest/fault controls PASS; receipts.json, failure-*.xml, restore-and-repeat.xml |
| Native importer/reconciliation/authorization UI | parent AC4/7 | HLB-451 through455 | No native write/persistence or browser claim in this slice | NOT RUN; separately owned |
| UI/Jest/Playwright/TesterArmy and REST reload | V1 | N/A | CLI-only Python change, no UI/TS; direct authenticated database snapshots avoid API middleware writes | N/A |

Inventory:15 behavior rows,13 PASS,1 separately owned NOT RUN,1 N/A.
No approved deferrals. Fixture source IDs remain synthetic; never resolved in
live Linear. Full native fixture M will be verified by importer/graph/content
children. This slice exercises its six issue identity/gap and mapping combination.

## Provenance, limits and reproduction

Application/test revision: `3ecbbda` (full SHA in source-provenance.json), committed
and pushed with clean worktree before the completed live run. Final local suite:
**123 passed** (101 existing contracts +22 dry-run cases). Fault matrix:22 pass,
one intended collision failure, one intended drift failure,22 restored pass.
Native pytest XML/logs and cleanup receipts are committed in `artifacts/`.
Earlier development reds document the optimized-checker bypass and integer
reservation compatibility. They are not the fault matrix and setup errors are
not counted as intended failures. Retained synthetic logs normalize temporary
fixture directory paths only; raw private archives are never published.

The collector executes in existing `plane-app-api-1`, image
`plane-backend:homelab`, ID
`sha256:f2470ea68b74b1746bc31a20112dac63e67f55e84e2580b30b03da8af49d2d7d`.
No newly deployed application/test service. Python3.9.2 / pytest8.4.2 on editor;
the database collector uses its existing container Python/driver.

See `tools/LINEAR_IMPORT_PLAN.md` for exact commands, limits, exit codes and
mapping semantics. Run `python3 tools/check_linear_import_plan.py --output
/var/tmp/<new-evidence>` for the credential-free fault matrix. Run the independent
`tools/verify_linear_import_plan.py --issues <archive> --output <private-plan>`
against local receipts, without network. CI runs the same fault matrix with
pinned actions and no provider credentials.

Private before/after JSON and full mapping reside under root-only
`/var/lib/plane-migration/HLB-449-dry-run-20261018`. Their digests and source manifest
bindings are published; source records, names, UUIDs, raw SQL data and URLs stay
outside Git. The first live attempt aborted on valid integer metadata before
an output directory existed; a new regression fixed it before the completed run.
Cancellation and failed input cases also leave no plan output. Completed private
archives are deliberately retained; synthetic fault-run roots are removed.

The database comparison covers logical public table rows, columns/types, indexes
and constraints at two REPEATABLE READ snapshots. It does not cover external
blob storage, PostgreSQL sequence counters, physical WAL/maintenance, SSH/DB audit
logs or unrelated services. No concurrent logical changes were observed; two
snapshots do not prove an exclusive lock over the intervening period. The
collector enforces READ ONLY and rolls back; its configured role is not claimed
to be privilege-restricted. There is no destination write client.

Authenticated REST/native browser verification is NOT RUN because this slice
makes no native writes and GET middleware can change activity/token state.
Authenticated direct DB readback proves this slice's observed no-change contract;
it is not REST authorization or user-journey evidence. A complete importer must
be verified through those native layers before cutover. Security boundary and
control mapping: `docs/security/threat-models/HLB-431-linear-export/README.md`.
