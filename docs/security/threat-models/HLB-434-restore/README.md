# Isolated asset restore trust boundaries

This component is preparatory HLB-434 work. It does not admit a release or change
the existing .129 instance. Database restore and shared fixture M acceptance
remain open. The controller runs only on fashionfindrs-dev at 192.168.1.130 and
holds the shared rehearsal lease until ownership-checked cleanup completes.

| Boundary and threat | Control | Evidence |
| --- | --- | --- |
| Private backup to parser: substituted archive, traversal, oversized content | Trusted outer digest, per-object hashes and sizes, bounded streaming without extraction, regular nonsymlink inputs | Source archive contract suite; native restore still pending |
| Parser to object store: credentials or original data sent to another host | Exact internal endpoint, bucket, SDK hostname and credential shape checked before client initialization; random run credentials; internal Docker network with no published ports | Six connection rejection cases; native identity/readback still pending |
| Rehearsal to existing services: deletion or overwrite of unrelated data | Refuse existing namespace/root, inspect owner labels before removal, require corroborated absence, refuse indeterminate Docker state | Cleanup boundary tests; native independent cleanup readback still pending |
| Corruption control to original data: destructive test changes original object | Corrupt only fixed marked synthetic fixture key, restore from committed golden bytes; source archive stays read-only and checked again after cleanup | Native unchanged assertion sequence still pending |
| Runtime to diagnostic artifacts: disclosure of keys, credentials or content | Raw logs, connection files and readbacks remain under private root; public evidence contains counts/hashes and authored errors; delete credentials/readbacks after confirmed cleanup | Source guards; native artifact inspection still pending |
| Diagnostic collection to cleanup: lost logs leave store running | Optional log failures recorded independently; ownership checks and deletion remain mandatory; unknown ownership never authorizes deletion | Retrieval and storage failure regressions at external Docker boundary |

The SDK restores original content headers and metadata, performs signed reads, and
captures an unsigned synthetic-object read for denial verification. Test containers
receive read-only downloaded bytes and no credentials or network. The application
image supplies pinned SDK dependencies only; this component does not start Django,
workers, webhooks, mail, or production imports. Public test output must be inspected
before publication because an assertion failure can otherwise disclose inputs.

Resource limits are component reservations, not full Plane sizing evidence. Logs
may retain private material after credential invalidation and stay outside Git.
