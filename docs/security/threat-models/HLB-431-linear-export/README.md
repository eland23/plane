
## HLB-449 destination dry-run delta

New trust boundary: authenticated SSH into the existing Plane API container,
then a PostgreSQL READ ONLY / REPEATABLE READ connection. The fixed host/container
and SELECT-only collector avoid API-token creation, last-used updates and
middleware activity writes. No destination mutation client or new hosted service
is introduced. FF-C-SECRETS-HYGIENE / FF-C-PII-MINIMIZE: database credentials never
leave container environment; all public content is hashed remotely, minimal
identity rows stay in 0700/0600 archives outside Git. Fixed SQL identifiers are
allowlisted; provider/SSH failures are sanitized. Input UUIDs are validated and
never interpolated into shell/SQL. Missing/incomplete inventories fail closed.

`dry_run_no_write` binds before/after logical row/schema/index/constraint hashes;
`reconciliation_detects_loss` detects reservation collisions, wrong source
binding, missing schema/references and destination drift at public service seams.
Limits/statement timeout and SSH deadline bound collection. READ ONLY is a
transaction setting, not a claim that the configured database role lacks write
privileges; administrative compromise and physical/audit effects are outside
this comparison. Stored sequence counters/blob filesystem state are not covered.
The independent receipt checker checks issue IDs/counts/number/module placement
and saved snapshot checksums without trusting the planner's issue transformation.
Native import writes, access-control rendering and rollback remain later tickets.

## HLB-464 actor and native resource identity delta

FF-C-PII-MINIMIZE / FF-C-SECRETS-HYGIENE: typed actor references from verified
archives are the only source-derived lookup inputs; rich-content user-shaped
objects cannot expand scope. Fixed read-only Linear queries verify organization
and UUID before protected payload persistence. Profile/source/page hashes,
private modes, response/count budgets and named denied outcomes are checked
before destination reads. Console/CI receipts contain counts, not actor emails
or names. No account/invitation/provider mutation path is introduced.

Native IssueLink identity is nullable for manual links, complete and unique per
workspace for imports, and immutable once bound. All ordinary app/public/Space
serializer paths expose source fields read-only. PostgreSQL enforces uniqueness
across tombstones and rejects direct source/workspace rebinding. Static migration
SQL and quoted historical table names introduce no client SQL interpolation.
Reverse checks take ACCESS EXCLUSIVE before inspecting bindings and refuse
provenance loss under a competing import transaction.

Prove with dry_run_no_write/reconciliation_detects_loss source contracts and
content_attribution_roundtrip native serialization/constraint contracts. Native
database tests run only on synthetic .130 fixtures; schema/migration-bookkeeping
capture from .129 is read-only and excludes user/business rows. No production
schema/import mutation occurs. The source actor supplement is an additional
read window; final cutoff and actor/native timeline reconciliation remain open.

### HLB-465 native milestone command boundary

Milestones are project/module/workspace scoped native records. Ordinary commands
accept an authenticated active User and require active workspace and project
membership; write roles are Member/Admin, Guest may list. Foreign UUIDs and
unavailable membership return the same scope denial. Values are explicitly
allowlisted and validated; source IDs, workspace/module bindings and audit actors
cannot be supplied through editing values. Audit fields use the authenticated
actor. This Python boundary is not an HTTP authentication/session adapter.

A module lock serializes all milestone commands; issue locks and an active-issue
unique constraint keep assignment single-valued. Assignment/removal preserves
unrelated issue values; referenced deletion conflicts until explicit clearing.
Native imported identity is paired, workspace-unique across tombstones and
immutable. A PostgreSQL trigger checks milestone module/project/workspace binding.
Atomic migration reversal locks both native tables and refuses to discard rows.
Only fixed synthetic .130 database/table/constraint/test targets can be used by
the fault helper; pre-framework guards and finally-restoration remain mandatory.

No live source/destination writes, account operations, new network calls, UI,
HTTP endpoint or session behavior is introduced. Endpoint authorization, native
UI behavior, module-membership editing, full import ledger/reconciliation and
serialized release remain separately owned gates. No production rollout claim.
