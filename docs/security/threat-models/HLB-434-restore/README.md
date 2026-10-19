# Isolated asset restore trust boundaries

This component is preparatory HLB-434 work. It does not admit a release or change
the existing .129 instance. Database restore and shared fixture M acceptance
remain open. The controller runs only on fashionfindrs-dev at 192.168.1.130 and
holds the shared rehearsal lease until ownership-checked cleanup completes.

| Boundary and threat | Control | Evidence |
| --- | --- | --- |
| Private backup to parser: substituted archive, traversal, oversized content | Trusted outer digest, per-object hashes and sizes, bounded streaming without extraction, regular nonsymlink inputs | Source archive contract suite; native-assets-4769e03 three-phase restore |
| Parser to object store: credentials or original data sent to another host | Exact internal endpoint, bucket, SDK hostname and credential shape checked before client initialization; random run credentials; internal Docker network with no published ports | Six connection rejection cases; native-assets-4769e03 runtime identity and signed readback |
| Rehearsal to existing services: deletion or overwrite of unrelated data | Refuse existing namespace/root, inspect owner labels before removal, require corroborated absence, refuse indeterminate Docker state | Cleanup boundary tests; native-assets-4769e03 independent cleanup receipt |
| Corruption control to original data: destructive test changes original object | Corrupt only fixed marked synthetic fixture key, restore from committed golden bytes; source archive stays read-only and checked again after cleanup | native-assets-4769e03 unchanged 4PASS / 1 intended FAIL / 4PASS sequence |
| Runtime to diagnostic artifacts: disclosure of keys, credentials or content | Raw logs, connection files and readbacks remain under private root; public evidence contains counts/hashes and authored errors; delete credentials/readbacks after confirmed cleanup | Source guards; native public outputs scanned against original values and credential markers |
| Diagnostic collection to cleanup: lost logs leave store running | Optional log failures recorded independently; ownership checks and deletion remain mandatory; unknown ownership never authorizes deletion | Retrieval and storage failure regressions at external Docker boundary |

The SDK restores original content headers and metadata, performs signed reads, and
captures an unsigned synthetic-object read for denial verification. Test containers
receive read-only downloaded bytes and no credentials or network. The application
image supplies pinned SDK dependencies only; this component does not start Django,
workers, webhooks, mail, or production imports. Public test output must be inspected
before publication because an assertion failure can otherwise disclose inputs.

Resource limits are component reservations, not full Plane sizing evidence. Logs
may retain private material after credential invalidation and stay outside Git.

## Database/API restore delta (preparatory)

The separate database controller restores only into a new owned .130 PostgreSQL
namespace under the same shared lease. Private dump and logical snapshot hashes
must match captured constants before mutation. A repeatable read-only transaction
captures all public logical rows; the public comparator requires exact equality
before migrations, preserves old row multiplicity/values after additions, and
compares the saved seeded snapshot exactly after restoring its private dump.
This covers logical rows, not all PostgreSQL catalogs/roles/grants.

The synthetic setup checks exact database URL, resolved Django connection,
settings, Redis endpoints and container hostname before writes. It creates a
single supported issue/link and native temporary session in the new database;
existing source rows are never the fault target. Anonymous API access is denied;
signed session reads assert literal UUID, title, URL and nullable provenance.
The controlled fault changes only that synthetic link title. Recovery stops the
owned API and restores the seeded dump; unchanged API assertions must pass again.

Internal networking has no published ports. No worker, mail or provider client
is started. The full backend payload fingerprint and application revision are
verified, all dependency images pinned, and source execution hashes recorded.
Memory/disk reservations remain component gates. Ownership checks precede
container/network deletion; failed state inspection preserves private database
and readbacks. Once absence is confirmed, delete owned database data, dump,
snapshots and session/environment files. Private diagnostics may retain expired
session material outside Git. Native database/API proof PASS at7b5ddfc:5PASS→1 intended content failure→5PASS,
exact seeded snapshot equality and original row preservation, mandatory singleton
internal-network/NetworkID readback, and independent cleanup. Public evidence is
in docs/verification/HLB-434/artifacts/native-database-7b5ddfc/. Full shared fixture
M and combined integration remain pending; this bounded proof does not waive them.
