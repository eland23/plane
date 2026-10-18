# HLB-431 delta: read-only source issue export

Scope: HLB-442 operator CLI, not the unmodified Plane application. No application
auth surface, destination importer or new hosted service is added. This scoped
system model is the baseline for the export tool only; it does not assert a
full review of Plane's existing product platform.

Boundaries: trusted operator environment credential → fixed HTTPS Linear API →
untrusted JSON/page cursors → validated private filesystem checkpoint/export.
Git/CI receive synthetic fixtures and sanitized receipts only. The source team
UUID and authenticated organization are bound to the checkpoint; cross-team
parents remain reference stubs. Linear remains authoritative.

| Threat | STRIDE / response | Control and prove_with | State / residual |
|---|---|---|---|
| Credential forwarded through a redirect or error log | Disclosure; avoid/mitigate | Fixed endpoint, NoRedirect, safe codes, no raw errors; HTTP failure tests | Source controls; real provider auth/read recorded separately |
| Exporting a different team's records | Spoofing/disclosure; mitigate | Server filter plus every-record team check; boundary stub test | Tested protocol; source token role remains external |
| Private data committed/shared by default | Disclosure; mitigate | Outside-Git gate, 0700 directory/0600 files, no token argument; private output and Git guard tests | Accidental operator copies outside this tool remain possible |
| Lost page or partial GraphQL error called success | Tampering/repudiation; mitigate | Cursor/UUID checks, explicit failed manifest; page-loss fault control | Concurrent source changes require later cutoff/delta reconciliation |
| Resuming corrupted or different-scope data | Tampering; mitigate | Query/org/team binding, per-page hash/count verification; unchanged checksum defect test | Trusted operator owns output; source deltas not yet reconciled |
| Retry/response/storage exhaustion | Denial of service; mitigate | Three attempts, capped backoff, size/page/storage limits and deadline; retry/budget tests | Socket operation may consume its bounded I/O timeout after deadline |
| Concurrent writer overwrites an archive | Tampering; mitigate | Exclusive new directory, flock, no-follow exclusive page writes and atomic manifest replacement | Ordinary errors resume; crash-created orphans require explicit recovery |

No threat is formally accepted and none is labelled fully mitigated based on
source tests alone. No live token or private payload belongs in this document.
Subsequent association/asset/import/cutover tickets must extend this model before
crossing their new trust boundaries. Full migration completion requires native
destination behavior and revision-bound evidence, not just an export file.

## HLB-443 association-export delta

The issue archive is a read-only input, independently checked for private modes,
query fingerprint, exact team, page checksums, unique UUIDs and terminal coverage.
The derived archive is a separate private directory; it binds its checkpoint to
the exact input manifest and exporter bytes. Resume replays verified pages before
allowing checkpoint changes. Rejected checkpoints remain unchanged.

All source-derived identifiers pass UUID validation and enter GraphQL variables.
Only static endpoint/field definitions select queries; response content is data,
never rendered or executed. Project-associated initiative membership yields
foreign project UUID stubs only; those projects are never traversed. Team-bearing
cycles/states/memberships and labels/documents reject foreign teams. Scope and
parent mismatch fails before a page is committed. Introspection records field
names without interpreting absent/unread fields as unused. Schema-visible fields
and original observed issue field presence have explicit coverage entries;
unread custom usage remains disposition-required under HLB-447.

Raw pages include documents/update bodies and actor data, so only protected
storage retains them. CI receives synthetic fixtures and sanitized summaries.
No document/attachment URL is fetched, no source or destination record mutated,
and no credential is exported. Request/page, response, archive and free-disk
budgets limit work. Complete resume makes only a scope request and replays local
pages; no new provider pages are fetched. Every exported association has an
explicit edge and the raw page records its parent connection/cursor.

Residuals: source permissions bound visibility; non-atomic source changes,
unknown/unexposed fields, sub-document/history/comment traversal and final delta
reconciliation require later coverage disposition. A source GraphQL/permission
error stops with a failed checkpoint, never a full-completeness claim. Local
root/operators remain trusted; crash-orphan recovery preserves files for an
operator rather than deleting private records. No new formal risk acceptance.

## HLB-447 coverage and snapshot-delta delta

The new schema capture client uses only the existing fixed Linear HTTPS transport,
static type names and UUID-bound source scope. It requests field names, never
integration/session/credential values. API-denied and missing type results stay
explicit; loss of authentication stops further type requests and marks remaining
inventory blocked. Schema metadata and comparison manifests stay in protected
0700 directories with0600 checkpoints outside Git.

Offline comparison verifies both issue/association archives, their source binding,
complete traversal/cursor/hash/graph proofs, organization/team and time windows
before creating a new report. It never modifies input archives or overwrites a
report. Changed fields are identified by kind/UUID/path and hashes, not raw private
values. Original snapshots remain the recovery source. Missing records are
unconfirmed tombstone candidates: absence may mean deletion, lost access or scope
change and never authorizes destination deletion. Source intra-snapshot edits,
schema drift and cutoff exceptions remain visible. Equal snapshots or repeated
readback of one archive cannot establish an atomic cutoff/freeze.

Every schema-visible field in the enumerated migration categories receives a
source disposition; unread values and partial object capture are distinguished
from preserved raw payloads. Native behavior is never inferred from an archive.
Credential fields are intentionally excluded per migration scope. Unexposed or
uncaptured custom properties/types remain unknown usage and require explicit
feature-owner disposition. This tool cannot authorize cutover or waive native
import/reconciliation evidence owned by later children.

Controls: FF-C-SECRETS-HYGIENE, FF-C-PII-MINIMIZE and validation/error boundaries.
Prove with snapshot_delta_coverage and reconciliation_detects_loss contracts,
including named missing field/edge assertions and unchanged input/output bytes.
No new resolver/mutation/authz surface, hosted service or destination write.

## HLB-448 asset export delta

New boundary: private provider attachment metadata and uploaded bytes to protected
local storage. `asset_integrity_contract` proves FF-C-URL-VALIDATE,
FF-C-IMAGE-URL-VALIDATE, FF-C-SECRETS-HYGIENE and FF-C-PII-MINIMIZE.
Only exact HTTPS uploads.linear.app URLs may receive the Linear authorization
header. Alternate ports, userinfo, fragments, control characters, backslashes,
private/IP hosts and redirects are rejected; proxies are disabled for the asset
transport. The configured hostname belongs to the trusted provider (no user-
controlled DNS name). Response final URL/status are checked. No arbitrary URL,
external PR fetch, source mutation, content execution or destination write.

Private attachment pages validate issue/team/UUID/cursor identity before commit.
The output binds verified issue/association archives and a static query profile.
Resume replays saved pages and verifies every committed blob hash/size/private
mode before writable checkpoint state. Exclusive locking prevents concurrent
writers; inputs are read-only. URLs, signed query strings and raw attachment
metadata remain private and never enter console/CI evidence.

Stream per-asset deadline30s/socket wait30s, size64MiB, aggregate512MiB and
metadata-page/count budgets bound egress/storage; the1GiB disk reserve is a
conservative operation guard, not Plane runtime sizing. Each blob is fsynced,
content-addressed and committed with an exclusive hardlink; private temporary
files are removed on controlled failure/cancel. Hard-kill stale partials require
explicit operator cleanup and are never silently overwritten. Completed resume
performs scope read only and no redownload. Transient failures can be resumed;
no automatic unbounded retry. Private blob corruption blocks resume with the
checkpoint unchanged. A stored SHA256 proves archive integrity, not an upstream
provider checksum unless an independent expected digest is separately available.

Markdown/HTML images and recognized rich-content image fields become required
asset candidates; unsupported hosts/data-image payloads remain explicit blocked
assets. External issue/PR references remain links. Discovery covers current
verified source payloads plus paginated issue attachment metadata. Unexported
comments/history and nonstandard content syntax remain coverage gaps in later
content/export work, not a full-backup or native rendering claim. Durable local
asset references must be uploaded/rewritten/verified by HLB-454 and storage
recovery by R2 before cutover.
