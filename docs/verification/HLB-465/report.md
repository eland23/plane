# HLB-465: Native module milestone prerequisite

Status: **implementation and scoped verification PASS; final evidence review and CI pending**.
[HLB-465](https://linear.app/fashionfindrs/issue/HLB-465),
[child PR12](https://github.com/eland23/plane/pull/12), parent
[HLB-431](https://linear.app/fashionfindrs/issue/HLB-431).
Policy: FashionFindrs docs/testing/POLICY.md and REPORT-TEMPLATE.md.

## Result and scope

Native ModuleMilestone and IssueMilestone records now support validated lifecycle
and scoped, single-valued assignment through public Python commands. Metadata
includes description, target date, status, ordering and archive state. Authenticated
actors are retained in creation/update audit fields. A referenced milestone cannot
be deleted until its assignments are explicitly cleared. Cleanup remains possible
after module membership removal or issue soft deletion. Other issue assignments
and module memberships remain intact.

The persistence prerequisite is distinct from HLB-440's interface and HTTP
adapter work. No TypeScript, UI or HTTP endpoint changes are included here.
HLB-440 retains native forms, real authenticated HTTP role/session behavior,
API readback plus browser reload, navigation and accessibility proof. HLB-281/441
retain initiatives and scoped labels; HLB-451/453 own actual import/reconciliation.
No .129 schema deployment, live import or cutover occurred. The saved live dry
run's six blockers remain live until approved native release and further work.

## Behavior to evidence

Owner for scoped rows: HLB-465. Parent seams milestone_lifecycle,
planning_forms_validation_cancel, planning_forms_persistence and
planning_authorization are exercised at the declared Python command boundary.
Native persistence uses real PostgreSQL on .130, not an intercepted response.

| Behavior | Owned AC/seam | Saved independent assertion | Layer | Result |
|---|---|---|---|---|
| Lifecycle/date clear/cancel/order/archive | PAR-05/06/08, milestone_lifecycle | Exact Preview/First release order, date 2026-11-03, original description and actor IDs; null date/cancelled/archive persist, unarchive restores ordered list | pytest/native command+DB | PASS |
| Named validation and correction | PAR-05, planning_forms_validation_cancel | 11 invalid value cases including enormous integer, NaN, bool, invalid date/status, forged scope/provenance, nontext description; saved Original/date remain and corrected name persists | pytest/native command+DB | PASS |
| Assignment/clear/deletion conflict | PAR-08, milestone_lifecycle | FAS-2 moves First→Second; FAS-5 remains First; conflict preserves value; clear removes only FAS-2 and permits delete; exact module memberships remain | pytest/native command+DB | PASS |
| Archived/cancelled record and database cardinality | PAR-08 | DB rejects second active value; archive/cancel retains assignment and delete conflict | pytest/PostgreSQL | PASS |
| Removed membership/deleted issue recovery | PAR-08 | Two variants: assign→membership removal (+issue soft delete)→conflict→clear→successful delete | pytest/native command+DB | PASS |
| Role and active-membership scope | PAR-11, planning_authorization | Guest reads exact protected row, mutation denied; inactive workspace/project/user and outsider cannot read/write; row unchanged | pytest/native command+DB | PASS |
| Foreign scope and archived target | PAR-11/PAR-08 | Foreign module/workspace/unjoined project rejected; archived assignment denied, unarchive retry succeeds; foreign clear preserves current value | pytest/native command+DB | PASS |
| Source identity and scope | migration prerequisite | Paired nonempty identity, uniqueness across tombstones, immutable source/module binding; foreign workspace/project binding rejected | pytest/PostgreSQL trigger/constraints | PASS |
| Reverse migration safety | migration prerequisite | Existing literal native milestone blocks reversal before DDL and remains readable | actual MigrationExecutor | PASS |
| Assignment/delete concurrency | PAR-08 | Observe real Lock wait, commit assignment, delete conflicts, original membership/target retained, threads terminate | actual threads/connections/PostgreSQL | PASS |
| Reference-loss detection | V2 | Actual deletion guard removed in memory; unchanged normal conflict assertion must fail nonzero; original definitions restored and fixture tables empty | native controlled defect | PASS |
| Identity-loss detection | V2 | Actual unique constraint removed; unchanged duplicate-source assertion must fail nonzero; finally restores constraint, empty fixture | native controlled defect | PASS |
| Restore and regression | V2 | Same normal milestone checks plus existing link serializer/identity/reversal/concurrency suite pass after both defects | pytest/PostgreSQL | PASS |
| Fault-target protection | security/V2 | Nine subprocess checks reject unrelated/empty/override DSNs for both fault helpers before Django/output setup | pytest/editor, no services | PASS |
| HTTP roles/session, UI/TS/browser/accessibility | HLB-440 ownership | No such adapter changed; require actual endpoint/UI evidence before parent completion | HTTP/Playwright/Jest | N/A for this prerequisite; NOT RUN for parent |

The controlled reference defect removes the real guard from trusted source in
memory, with a saved original/fault source checksum and restoration in finally.
Source files stay read-only. The identity defect removes only the allowlisted
synthetic table constraint and restores it in finally. They must fail at intended
assertions, not setup errors. Error controls do not claim exhaustive fault coverage
of every independent rule or future adapter.

## Reproduction, revisions and cleanup

Runbook: tools/MODULE_MILESTONES.md. All hosted dependencies and CLI runners are
on 192.168.1.130. The editor runs only source/guard checks, editing and Git.
Fixture source is the schema and migration-bookkeeping-only installed snapshot
recorded by HLB-464, with no business rows. SHA256:
4dd0722b6bb19801f818dc1a534710b415f32b636f1c4b610a38325687ed0acc.
Migrations 0123/0124 run against that isolated fixture. Historical full migration
and prior link proof are recorded separately under HLB-464.

Known-state and both controlled-loss runs use clean pushed source
0efd1f1d7ea80e5acd37f3d48ddc3bccfbfbbc7f. The final restored regression uses
540a4f6cc5b1da368c6b18719b013d029dedcc41. Native implementation and milestone
test definitions are unchanged; the older link migration test now reverses
later empty schemas and uses a database execution barrier before starting its
timed competing-write boundary, after historical/intermediate state rendering. Sources
are read-only mounted in a short-lived runner.
Backend dependency image is
sha256:f2470ea68b74b1746bc31a20112dac63e67f55e84e2580b30b03da8af49d2d7d;
Python3.12, pytest8.4.2, pytest-django4.11.1. This is not a complete fork release
image/application deployment. Limits: runner512MiB/1CPU, PostgreSQL256MiB/1CPU,
Redis64MiB/.25CPU. No new full-stack capacity or peak-memory claim.

The first development pass had22 cases; the final inventory adds overflow,
foreign-scope, cardinality and recovery cases. An initial pre-migration attempt
was interrupted and excluded from proof. It is not an intended failure control.
The existing link migration tests now restore the full current migration graph
so they cannot leave a later native schema unapplied. Two initial combined regressions each had36 passes and one failure reaching the
old link test lock boundary inside its15-second window. Both failed attempts are
retained as milestone-restored-final.xml/.log and milestone-restored-verified.xml/.log;
neither is an intended failure control. The final test waits immediately before
the real guard lock SQL, after historical/intermediate migration-state rendering,
then starts the competing writer. It executes the original SQL and retains the
actual lock-wait, committed-writer, blocked-reversal and exact-identity assertions.

Raw installed schema and source archives remain private outside Git. Retained
artifacts contain synthetic fixture output only. No provider
credential, original actor profile or raw installed schema is committed.
Native cleanup readback (artifacts/cleanup.json) confirms zero users, workspaces,
projects, modules, issues, links, milestones and assignments. The milestone source
constraint, active-issue partial unique index, scope/identity trigger and
migration0124 are present. All task CLI runners were removed. PostgreSQL/Redis
dependencies remain for subsequent parity work. Owned editor fixtures and an
unused temporary diagnostic tool were removed. Schema drift: No changes detected.
The partial uniqueness check uses pg_index; an initial pg_constraint-only probe
was corrected without modifying native data or schema.

Final evidence:27 known-state native passes; two separate intended one-assertion
failures with restoration receipts;37 restored native/regression passes in143.35s;
nine pre-framework target guards pass. Inventory:15 rows,14 scoped PASS plus
one separately owned parent/N/A row. No approved deferral. Full provenance is
in artifacts/source-provenance.json; failed timing runs remain retained.

## Review and limits

Two preliminary source findings were fixed: enormous integer ordering values now
produce ValidationError, and authorized clearing remains available after module
membership removal. Independent Standards and Spec/security source reviews PASS
at 0efd1f1; focused final test-scheduling reviews PASS at540a4f6. Final evidence review and exact-head CI remain separate gates.

CI runs the source actor regression/loss controls, destructive-target guards and
native definition compilation; real PostgreSQL checks run on .130 and are retained
here. CI does not independently rerun the native PostgreSQL suite. Command role
checks do not establish HTTP authentication or session recovery. Existing module
membership edits outside this command boundary require their own scope/concurrency
integration. No parent completion, production rollout or importer readiness claim.
