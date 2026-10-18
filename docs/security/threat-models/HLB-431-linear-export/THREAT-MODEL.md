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
