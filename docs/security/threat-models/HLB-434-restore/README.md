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

## Shared fixture M preparation

The shared controller restores original rows and bytes into another fresh .130
namespace, then seeds only supported synthetic fields. It uses fixed database,
Redis and storage destinations; storage configuration is checked before Django
initialization and after settings resolution. The private network contains four
pinned services, all checked by mandatory exclusive-network/image readback.
No workers or external provider sends run. Its larger component reservation is
1536 MiB available memory plus the existing 2 GiB disk gate.

Native tests receive only short-lived fixture sessions, with no storage credential
mount. Asset redirects are not followed automatically: require the exact internal
storage hostname, bucket/key path and port, then make a separate request without
the session cookie. The bounded corruption target remains the marked synthetic
binary. Recovery repairs that asset and restores the saved seeded DB dump. Raw
storage reads, source backups and session/config values remain private; selected
public outputs require review for original values and signed query parameters.

The golden JSON contains synthetic FAS-like identifiers, never looked up in live
Linear. Issue-linked project documents use existing IssueLink/PageLog fields;
future portfolio, milestone and exclusive-label features are excluded by the
parent runtime scope. Combined API/asset proof PASS at0a88a87:30PASS→2 intended checksum failures→30PASS, zero errors/skips. Mandatory four-service isolation readback, nine executed code hashes, exact saved dump equality, original-row preservation and independent cleanup PASS. Selected public artifacts were scanned for original values and signed/credential material. At that revision, browser journeys, combined Control A and ordered release/readiness remained pending; the accepted combined control follows below.

## Shared omitted-migration control

The shared rehearsal now applies Control A to the same isolated restored fixture.
After the normal suite passes and a seeded dump is saved, the owned API stops.
Only the cloned database is reversed to migration0122. A task-labelled image
based on the verified backend omits0123/0124; a real file probe, migrator run and
schema readback must confirm omission before the unchanged API assertion runs.
The faulty API must use that exact image. Recovery restores the saved seeded
dump and complete backend; exact logical equality precedes API startup, then
strict isolation readback and the full unchanged suite repeat. Asset Control B
runs afterward, with another dump recovery and unchanged suite repeat.

This intentionally destructive schema control is fixed to the fresh .130 clone;
it is not a general rollback command or production rollback authorization. The
migration's imported-identity reversal guard remains active. Failure preserves
root-only diagnostics and invokes owned cleanup. Task fault images are removed
only after affirmative inspection of their owner label; foreign or indeterminate
image state preserves private working data and cannot produce a clean receipt.
No broad image/build cache pruning is performed. Cleanup boundary tests reproduce
three failures on old code and pass after the guard/removal is added. Actual
combined Control A evidence now PASS atdd67694:30PASS→7 intended schema failures→
30PASS→2 intended checksum failures→30PASS, zero errors/skips. The full suite is
unchanged across both faults and recoveries. Both saved-dump recoveries match
112tables/895logicalrows exactly; original rows remain preserved. Independent
cleanup confirms fault image/resource absence and unchanged originals. Native
evidence is in artifacts/shared-controls-dd67694; browser and ordered release
gates remain open. These results are separate from source cleanup tests.
