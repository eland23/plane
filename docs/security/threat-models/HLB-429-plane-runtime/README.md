# Plane runtime packaging trust boundaries

HLB-433 packages a clean, pushed, source-bound revision into complete pinned-base
images. Input refs, target, namespace, paths and digest format are validated before
builds. The source archive and backend image payload are independently compared
against Git blobs; symlink/whiteout/ancestor substitution is rejected. Source
snapshots and stream process groups are cleaned. Build locks serialize candidates.

Packaging-only admission cannot grant runtime admission: low-capacity targets
remain BLOCKED in the manifest, and release preflight retains its strict gate.
Package mode still rejects unavailable/malformed probes, wrong/shared targets,
dirty/unpushed source and mutable bases. No deployment or migration command is
executed by this tool. Host build commands do not host application services.

Dependency command output remains private in exclusive-created 0600 files beneath
a new0700 outside-Git log directory. Errors expose codes rather than raw command
output. Preserve failed build logs for diagnosis without uploading credentials.
Tracked-filename checks do not establish that arbitrary source text is secret-free.

HLB-434 owns private backup/asset restore, HLB-435 owns target-side release locking,
measured runtime admission, ordered migration, effect suppression and recovery.
The existing .129 instance cannot be a deployment target. New trust boundaries
and live runtime evidence must be added when those commands are implemented.
