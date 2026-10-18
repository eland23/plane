# FashionFindrs Linear source export

HLB-442 owns issue export. This is **not** the full migration backup: projects,
documents, comments, history, assets and field-coverage disposition belong to
the remaining HLB-431 children. The manifest says `COMPLETE_FOR_ISSUES`, and
`atomic_snapshot` is false. HLB-447 must reconcile changes during export.

The query follows the [official SDK schema](https://github.com/linear/linear/blob/master/packages/sdk/src/schema.graphql)
and [pagination documentation](https://linear.app/developers/pagination).
Issues are filtered by immutable team UUID on the server; archived issues are
included. Fifty issues and up to fifty labels per issue keep request complexity
bounded. If nested label pagination is needed, the exporter fails explicitly;
it never claims truncated membership is complete. Foreign parent references
are stored as ID/team stubs; unrelated issue contents are not fetched.

Use Python 3.9+, Git and an existing authorized `LINEAR_API_KEY` environment
variable. The tool never accepts a token as a command-line argument, requests
mutations, follows redirects, logs headers or prints provider error bodies.
Only the fixed HTTPS Linear API endpoint receives the credential. Prefer a
read-only credential restricted to the intended source team.

```bash
python3 tools/linear_export.py \
  --team 98ad34ad-69c8-48e7-813a-812f9231be12 \
  --output /absolute/private-storage/new-run
```

Output must be outside every Git working tree. New exports never overwrite an
existing directory. Directory permissions are 0700; JSON/checkpoints are 0600.
Public stdout includes only status/counts. Private files preserve the GraphQL
data payloads, including descriptions, actors and timestamps. Response headers,
credentials and error bodies are excluded. Do not upload these files as test
evidence or copy them into Git.

Default payload budget is 512 MiB; `--max-bytes` may set an explicit alternative.
One GiB free disk headroom, a per-response 16 MiB limit, 10,000-page ceiling,
bounded HTTP attempts/backoff and response deadline prevent silent unbounded
reads. Limits fail explicitly, retaining committed checkpoints. Actual required
storage should be established from the source inventory, not guessed from this
default budget.

After an ordinary auth/network/limit interruption, correct the prerequisite and
repeat with `--resume` and the same team/output. Resume checks organization,
team, query fingerprint, page identities/counts and SHA-256 before continuing
from the saved cursor. Complete exports can be verified again with `--resume`.
An orphan page from a process/power failure between page and checkpoint commits
fails `ORPHAN_PAGE`: preserve the private directory for scoped operator recovery;
do not automatically delete it or present it as a complete snapshot. The lock
prevents a second writer to the same export, including after an error.

This tool writes only its private export and never changes Linear/Plane records,
starts services or enables agent pickup. Respect the source's retention/access
requirements and preserve the private archive until migration is reconciled.

Reproduce the synthetic evidence without credentials or network services:

```bash
python3 tools/check_linear_export.py --output /absolute/new-evidence-directory
```

The harness uses external provider fakes, real private files/Git guards and saved
tests. It deliberately drops a page and bypasses checksum comparison in isolated
tool copies, then restores the normal code. Both controls must fail at the
intended unchanged assertions, with clean passes before/after and JUnit/native
receipts. They do not replace a separately recorded real source export.
