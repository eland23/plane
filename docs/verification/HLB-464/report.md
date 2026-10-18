# HLB-464: Original actors and native link identity

Status: **implementation and scoped verification PASS; final review/CI pending**.
[HLB-464](https://linear.app/fashionfindrs/issue/HLB-464),
[PR11](https://github.com/eland23/plane/pull/11), parent
[HLB-431](https://linear.app/fashionfindrs/issue/HLB-431).
Policy: FashionFindrs docs/testing/POLICY.md and REPORT-TEMPLATE.md.

## Result and remaining work

The protected actor supplement contains two original Linear actors, including one
inactive author. Independent readback checks **801 creator and 137 assignee
references** against original issue pages. No accounts or invitations are created.
The refreshed live dry run has **zero unresolved actor references**, reducing 23
blockers to 6. All 110 observed public tables on .129 remained unchanged.

Native IssueLink now has complete, workspace-scoped unique source identity.
Tombstones retain uniqueness; a PostgreSQL trigger rejects source/workspace
rebinding. All three ordinary app/public/Space serializers make provenance
read-only. Reverse migration locks out writers before checking for imported
identities, then refuses to discard them.

The native schema change is implemented and rehearsed on .130; it is **not
deployed to .129**. Therefore the live dry run still names two missing link
columns, two missing initiative/milestone tables and two label-name collisions.
HLB-281/440/441 and HLB-453 retain planning/graph ownership. HLB-454 retains native
author/history/content rendering and file/link replay. This slice does not
complete the importer, native history, parity UI or cutover.

## Behavior to evidence

Owner for every row below: HLB-464. Existing public seams: dry_run_no_write,
reconciliation_detects_loss, content_attribution_roundtrip. Native persistence
proof uses real PostgreSQL and public Django serializers; no HTTP-role claim.

| Behavior | AC | Saved test / independent expectation | Layer and evidence | Result |
|---|---|---|---|---|
| Original inactive actor | AC4 / attribution prerequisite | original_inactive_actor: literal UUID/name/active=false, one read-only lookup, no overwrite,0700/0600; independent original-page check | pytest/source; actor-pass-known-state.xml | PASS |
| Denied/scope/corruption | scoped AC7 | denied_actor; actor_page_tampering_and_foreign_organization; unavailable_actor_stays_a_blocker: denied/null/canceled archives cannot masquerade as complete; hashes and source/org binding checked | pytest/source; actor-pass-known-state.xml | PASS |
| Typed actor reachability | AC4 | untrusted_rich_content: only declared actor UUID requested, content-shaped user ID never fetched | pytest/source; actor-pass-known-state.xml | PASS |
| Planner supplement | AC4 | verified_actor_supplement: six exact creator links become archived attribution; corrupt input rejects before destination capture; can_import stays false | pytest/service; actor-pass-known-state.xml | PASS |
| Native source identity retained | attribution prerequisite | native_link_retains_original_source_identity: exact original URL/namespace/UUID returned, provenance read-only in app/public/Space | native serializer; native-link-pass.xml | PASS,3 variants |
| Replay uniqueness | attribution prerequisite | import_link_identity_is_scoped_unique: duplicate key fails, manual URL/unbound identity retained, tombstone cannot free key | native PostgreSQL; native-link-pass.xml | PASS |
| Ordinary edit/malformed binding | attribution prerequisite | ordinary_link_serializer_cannot_rebind; partial_or_empty_source_binding: title edit persists without rebind; partial/blank pairs fail | native PostgreSQL/serializer; native-link-pass.xml | PASS |
| Direct update/workspace scope | attribution prerequisite | bound_source_identity; source_identity_can_exist_in_another_workspace: direct rebind/move denied; other workspace may hold same key | native PostgreSQL; native-link-pass.xml | PASS |
| Schema reversal | attribution prerequisite | schema_roundtrip: manual URL/title survive forward/reverse; bound identity blocks reversal | real MigrationExecutor; native-link-pass.xml | PASS |
| Competing import/reversal | attribution prerequisite | concurrent_import: observes actual lock wait, commits competing writer, requires reversal blocked and exact identity retained | real threads/connections/MigrationExecutor; native-link-pass.xml | PASS |
| Source loss detection | V2 | unchanged inactive-author assertion rejects replacement by Importer; restored suite passes | actor-failure-original-author.xml; actor-restore-and-repeat.xml | PASS |
| Native loss detection | V2 | unchanged uniqueness assertion fails with its real constraint removed; restored constraint, zero fixture rows, same10 native cases pass | native-failure-identity-loss.xml; native-fault-receipt.json; native-link-restored.xml | PASS |
| Fault target protection | V2/security | native_fault_target_is_rejected: empty/legacy/override DSNs rejected before Django startup or output creation | pytest/subprocess; native-fault-guard.xml | PASS,3 cases |
| Live source/no destination change | V3 | independent verifiers read original pages and saved snapshot digests | independent-live-readback.json; live-dry-run-summary.json | PASS |
| Native HTTP roles/browser/UI/cutover | separate ownership | No endpoint/TypeScript/UI changed; HLB-446/451/454/455 and runtime children own these gates | HTTP/Playwright/Jest | N/A here; NOT RUN for parent |

Inventory:15 rows,14 scoped PASS and1 separate-parent/N/A row. No approved
deferral. Actor six-case pass, intended author-loss assertion failure, six-case
restore. Native10-case pass, intended uniqueness assertion failure, ten-case
restore. Faults fail at intended assertions, not setup errors. MIG-04/MIG-09
are source/planning scope; native rows are bounded MIG-08 prerequisites.

## Setup, revisions and reproduction

Full SHAs are in artifacts/source-provenance.json. Actor implementation and final
private export:1ef8b8c. Native known state:0e0cf4b. Native implementation and
the ten normal test definitions remain byte-identical through f962855; only the
bounded fault runner and guards were added. Final native fault/restored run uses
f962855. Reports/artifacts are a later evidence commit.

Source checks use Python3.9.2/pytest8.4.2. Native tests use Python3.12,
pytest8.4.2 and pytest-django4.11.1 in the recorded backend dependency image.
The .130 CLI runner mounts a clean pushed source revision read-only; this is not
a complete fork release image or an application deployment. Dependency image:
sha256:f2470ea68b74b1746bc31a20112dac63e67f55e84e2580b30b03da8af49d2d7d.
PostgreSQL15.7-alpine digest and schema fixture checksum are in provenance.

Two base-schema setups were exercised:

- Full historical migration from an empty isolated database at pre-feature00fb7f3:
  three tests fail because IssueLink lacks identity fields (804.91s). This is a
  feature red, not the controlled-loss matrix.
- A read-only dump of installed .129 schema plus only public.django_migrations
  bookkeeping was restored transactionally on .130. Latest db migration0122.
  No user/business rows are in the dump; setup verifies zero users/issues/pages
  before run-owned fixtures. Migration0123 and actual reverse/concurrency tests
  pass. An initial restore into a database without public schema rolled back;
  creating the standard empty schema allowed the exact fixture to restore.
  Setup corrections are not intended failure controls.

Only isolated PostgreSQL/Redis dependencies and short-lived CLI runners started,
with fixed task names/network and256/64/512MiB limits. An initial sample measured
roughly190MiB combined; this is **not** a full Plane sizing or peak measurement.
No unrelated service stopped and no live schema/import/cutover occurred.

Reproduction: tools/LINEAR_ACTORS.md. Source tests:
tools/tests/test_linear_actors.py and test_link_fault_guard.py. Native tests:
apps/api/plane/tests/unit/test_import_link_fields.py and
contract/test_import_link_identity.py. Run the bounded fault with
python plane/tests/run_link_identity_fault.py --output /evidence/new-fault
inside the isolated .130 runner, then rerun the exact normal suite. Source fault:
python3 tools/check_linear_actors.py --output /var/tmp/new-evidence.

The actor query validates without errors against the official SDK schema retained
during discovery; successful live lookups are separate API evidence. Private
archives remain root-only under /var/lib/plane-migration/HLB-464-actors-final-20261018
and HLB-464-dry-run-final-20261018. Raw actor/schema payloads, credentials and source
user data are not committed. Temporary actor fault roots are removed; native
fixture cleanup is verified separately from retained evidence/dependencies.
No binary rendering or complete historical-user archive is claimed.

## Limits and open gates

Actor retrieval is an additional read window, not an atomic historical snapshot.
Cutoff, deltas, owner field dispositions and native import evidence remain open.
Archived attribution is distinct from native account provisioning. Identity
uniqueness lasts while the native record/tombstone exists; durable importer
ledger/retention lifecycle remains HLB-451/452 ownership.

The destination comparison covers observed logical public rows, columns, indexes
and constraints in two independent READ ONLY snapshots; not blob storage,
PostgreSQL sequence counters, physical maintenance/audit logs or an exclusive
lock over the whole run. Direct database/serializer tests do not replace native
HTTP roles/browser reload proof. Security delta:
docs/security/threat-models/HLB-431-linear-export/README.md.

Final source regression: 132 tests passed (artifacts/source-all.xml). Native cleanup readback confirms zero users, workspaces, projects, issues and links, with the uniqueness constraint and immutability trigger restored (artifacts/native-cleanup.json). Task dependencies remain available for subsequent parity work; CLI runners were removed.
