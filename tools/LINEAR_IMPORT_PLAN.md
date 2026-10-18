# Read-only Linear → Plane dry run (HLB-449)

Consumes completed, private issue, association, asset and coverage archives.
It makes no Linear calls and has no Plane mutation client. Run on the editor as a
CLI only; snapshots execute through authenticated SSH on the existing Plane API
container at 192.168.1.129. No service is started or deployed.

```sh
python3 tools/linear_import_plan.py \
  --issues /var/lib/plane-migration/HLB-447-issues-20261018 \
  --associations /var/lib/plane-migration/HLB-447-associations-20261018 \
  --assets /var/lib/plane-migration/HLB-448-assets-final-20261018 \
  --coverage /var/lib/plane-migration/HLB-447-comparison-20261018 \
  --workspace <existing-workspace-uuid> \
  --output /var/lib/plane-migration/<new-private-run>
```

Optional `--target-project UUID` selects an active FAS project in that workspace.
An unbound project can be selected explicitly; any partial or foreign source
binding blocks the plan. Automatic reuse requires the immutable Linear org/team
binding. Names never select identities. Other records reuse only matching
workspace/source UUID markers and project scope. The plan does not update them.

Exit 1 means a completed plan with blockers, 3 means a structurally valid plan
with remaining migration gates, 2 means input/transport failure, 130 cancellation.
There is no successful import exit and `can_import` is always false.
Output must be a new directory outside Git. Directories are 0700, files 0600.
Detailed names, UUIDs, URLs and snapshots remain private; stdout contains counts.
On interruption, remove only an inspected incomplete output directory or choose
a new run directory. Inputs and previous outputs are never overwritten.

## Mapping and evidence

One Linear FAS team → one FAS project; Linear projects → modules; shared cycles,
labels/states, documents/pages, initiatives and milestones receive independent
identities. Issues retain FAS-N and N without gap filling or renumbering.
UUIDv5 inputs are `plane-linear-import-v1/<workspace>/<source-org>/<kind>/<UUID>`
in the URL namespace. Display IDs, source UUIDs, payload checksums and proposed
Plane UUIDs stay separate. External-resource attachments become reference links;
approved uploaded assets become attachment proposals. Binary bytes are verified,
not uploaded. Native actor/history/content rendering remain later children.

The planner names missing schema, unresolved references, number reservations,
foreign/duplicate identities, occupied deterministic UUIDs, native active name
collisions, deleted targets, archive precision loss and hierarchy cycles.
This is a prerequisite plan, not a complete mutation payload or schema migration.
Future imports must recheck constraints/authorization against the current target.
Missing native capabilities are blockers, not automatic archive-only downgrades.

The collector enforces PostgreSQL READ ONLY / REPEATABLE READ then rolls back.
It hashes every public table's logical rows plus column types, index definitions
and constraints. Minimal identity inventories allow explicit collision checks.
Credentials/user content are hashed on the host, never exported. Limits are
1m rows/table, 100k inventoried records/table, 16MiB response and 90s SSH timeout;
exceeding a limit aborts. Database settings/sequence counters outside public table
rows, filesystem/blob state and unrelated services are not covered. SSH/DB audit
logs and physical database maintenance may occur. No REST endpoint is called,
so no token-last-used or API activity mutation is induced by this tool.

`destination-before.json` and `destination-after.json` are two independent
consistent transactions, not a transaction spanning the whole run. Any observed
concurrent database change blocks the no-change proof. Unchanged hashes prove
observed logical state equality; the read-only transaction and absent mutation
client establish this tool's no-write boundary. Neither establishes cutover
readiness or native behavior.

Independent receipt check (no network):

```sh
python3 tools/verify_linear_import_plan.py --issues <issues> --output <run>
python3 tools/check_linear_import_plan.py --output /var/tmp/<new-evidence>
```

The latter saves native pytest XML/logs for a clean pass, intentional number
collision and destination drift regressions, and restored pass. Temporary copies
and fixtures are removed. No credentials or live source data are needed in CI.
