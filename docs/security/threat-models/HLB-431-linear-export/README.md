
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
